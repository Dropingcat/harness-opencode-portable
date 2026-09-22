#!/usr/bin/env python3
"""downloader.py — канонический загрузчик источников для research-контура.

Заменяет десятки ad-hoc скриптов (scihub_*.py, download_*.py, retry_*.py,
xcom_*.py, check_*.py) в C:\\Temp\\opencode. Единая точка скачивания с:
- CrossRef-gate (валидация DOI перед загрузкой) — TD-106/127
- HTTP(S) download с retry/backoff/таймаутом (TD-118)
- sha256 + проверка %PDF + размер
- провенанс-JSON (URL, дата, hash, метод, статус) — TD-124
- извлечение текста PDF (pypdf, если доступен)

Usage:
    python downloader.py doi --doi 10.1080/... --out <dir> [--skip-crossref]
    python downloader.py url --url https://... --out <dir> [--name file.pdf]
    python downloader.py crossref --doi 10.1080/...            # только проверка DOI
    python downloader.py extract --pdf <file.pdf> [--out <dir>] # PDF -> txt
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import ssl
import sys
import time
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UA = "research-harness/1.0 mailto:research@local"
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3
BACKOFF = [2, 5, 10]

# DoH (DNS over HTTPS) резолверы — обход системного DNS (TD-153)
DOH_RESOLVERS = [
    "https://cloudflare-dns.com/dns-query?name={host}&type=A",
    "https://dns.google/resolve?name={host}&type=A",
    "https://1.1.1.1/dns-query?name={host}&type=A",
]
DOH_HEADERS = {"accept": "application/dns-json"}


def resolve_alt_dns(host: str, timeout: int = 8) -> str | None:
    """Резолв хоста через DoH (DNS over HTTPS), обходя системный DNS (TD-153)."""
    for tmpl in DOH_RESOLVERS:
        try:
            url = tmpl.format(host=urllib.parse.quote(host))
            req = urllib.request.Request(url, headers={**UA_HEADERS(), **DOH_HEADERS})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode("utf-8", errors="replace"))
            for ans in d.get("Answer", []):
                if ans.get("type") == 1 and ans.get("data"):
                    ip = ans["data"]
                    if ip and not ip.startswith("0."):
                        return ip
        except Exception:
            continue
    return None


def UA_HEADERS() -> dict:
    return {"User-Agent": UA}


def dns_preflight(host: str) -> dict:
    """Проверить резолв хоста системным DNS и DoH (TD-153)."""
    result = {"host": host, "system_dns": None, "doh_dns": None, "ok": False}
    try:
        result["system_dns"] = socket.gethostbyname(host)
    except Exception as e:
        result["system_dns_error"] = str(e)[:80]
    result["doh_dns"] = resolve_alt_dns(host)
    result["ok"] = bool(result["system_dns"] or result["doh_dns"])
    return result


def _ctx(verify: bool = True) -> ssl.SSLContext:
    c = ssl.create_default_context()
    if not verify:
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
    return c


def http_get(url: str, timeout: int = DEFAULT_TIMEOUT, verify: bool = True,
             retries: int = MAX_RETRIES, binary: bool = True) -> tuple[int, bytes | str]:
    """GET с retry/backoff + обход DNS (TD-153).

    При ENOTFOUND/NameResolutionError резолвим хост через DoH и повторяем
    запрос на IP с Host-заголовком (обход заблокированного системного DNS).
    Возвращает (status, body_bytes|text).
    """
    last = None
    host_by_ip = None  # (ip, host) для обхода DNS
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            if host_by_ip:
                ip, host = host_by_ip
                url_ip = url.replace(f"://{host}", f"://{ip}", 1)
                req = urllib.request.Request(url_ip, headers={"User-Agent": UA, "Accept": "*/*",
                                                             "Host": host})
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx(verify)) as r:
                data = r.read()
                return r.status, data
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (403, 404, 410):
                return e.code, b""
        except (socket.gaierror, urllib.error.URLError) as e:
            last = str(e)[:120]
            # Обход DNS: резолвим через DoH и пробуем IP+Host
            if not host_by_ip:
                parsed = urllib.parse.urlparse(url)
                ip = resolve_alt_dns(parsed.hostname)
                if ip:
                    host_by_ip = (ip, parsed.hostname)
                    print(f"DNS fallback: {parsed.hostname} -> {ip} (DoH)", file=sys.stderr)
                    continue  # пробуем сразу
        except Exception as e:
            last = str(e)[:120]
        if attempt < retries:
            time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
    return 0, last.encode("utf-8") if isinstance(last, str) else last


def crossref_check(doi: str, timeout: int = 20) -> dict:
    """Валидация DOI через CrossRef. Возвращает метаданные или {ok: False}."""
    try:
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", errors="replace"))
        m = d.get("message", {})
        title = (m.get("title") or [""])[0]
        auths = [str(a.get("given", "")) + " " + str(a.get("family", "")) for a in m.get("author", [])]
        yr = m.get("issued", {}).get("date-parts", [[None]])[0][0]
        return {"ok": True, "title": title[:200], "authors": auths[:5], "year": yr}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120], "doi": doi}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_pdf(data: bytes) -> bool:
    return data[:4] == b"%PDF"


def provenance(name: str, url: str, data: bytes, method: str, status: str,
               extra: dict | None = None) -> dict:
    """Провенанс-запись (TD-124): URL, дата, hash, размер, метод, статус."""
    return {
        "file": name,
        "source_url": url,
        "download_date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha256(data),
        "size_bytes": len(data),
        "method": method,
        "verification_status": status,
        **(extra or {}),
    }


def save_with_provenance(data: bytes, out_dir: Path, name: str, url: str,
                         method: str, status: str, extra: dict | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / name
    dest.write_bytes(data)
    prov = provenance(name, url, data, method, status, extra)
    (out_dir / f"{name}.prov.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  OK {name}: {len(data)} B, sha256={prov['sha256'][:16]}... [{status}]")
    return dest


def scihub_resolve(doi: str, timeout: int = 40) -> tuple[str | None, str]:
    """Извлечение PDF-ссылки из Sci-Hub по DOI. Возвращает (pdf_url|None, ошибка)."""
    for host in ("sci-hub.ru", "sci-hub.se", "sci-hub.st"):
        url = f"https://{host}/" + urllib.parse.quote(doi)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx(False)) as r:
                html = r.read().decode("utf-8", errors="replace")
            patterns = [
                r'<embed[^>]+src="([^"]+)"',
                r'<iframe[^>]+src="([^"]+)"',
                r"(?:location|window\.open|href)\s*[=(]\s*['\"]([^'\"]+\.pdf[^'\"]*)['\"]",
                r"src='([^']+\.pdf[^']*)'",
            ]
            for p in patterns:
                m = re.search(p, html)
                if m:
                    return m.group(1), ""
        except Exception as e:
            last = str(e)[:100]
            continue
    return None, "PDF-ссылка не найдена ни на одном зеркале"


def openalex_search(doi: str = None, title: str = None, author: str = None, year: int = None,
                    timeout: int = 30) -> dict:
    """Поиск через OpenAlex (без лимитов, fallback метаданных — TD-152).

    По DOI — точное; по title+author — библиографический поиск.
    Возвращает {ok, works:[{title, doi, year, oa_pdf, authors, venue}]}.
    """
    try:
        if doi:
            url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi)
        else:
            q = urllib.parse.quote(f"{title or ''} {author or ''}".strip())
            url = f"https://api.openalex.org/works?search={q}&per-page=5"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}

    if doi and "title" in data:
        works = [data]
    else:
        works = data.get("results", [])
    out = []
    for w in works:
        oa = (w.get("open_access") or {}).get("oa_url")
        out.append({
            "title": (w.get("title") or "")[:200],
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "year": w.get("publication_year"),
            "oa_pdf": oa,
            "authors": [a.get("author", {}).get("display_name") for a in w.get("authorships", [])][:5],
            "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
        })
    return {"ok": True, "works": out}


def doi_redirect(doi: str, timeout: int = 20) -> str | None:
    """DOI → фактический URL (следуем redirect'ам doi.org). Возвращает target."""
    try:
        req = urllib.request.Request("https://doi.org/" + urllib.parse.quote(doi),
                                     headers={"User-Agent": UA}, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.geturl()
    except Exception:
        return None


def wayback_fetch(url: str, timeout: int = 40) -> tuple[int, bytes]:
    """Получить файл через web.archive.org (fallback для 404/403 — TD-152)."""
    wb = "https://web.archive.org/web/" + urllib.parse.quote(url, safe="/:?=&")
    return http_get(wb, timeout=timeout, retries=2)


# Локальные корпуса PDF (RS-025: сначала локально, потом внешние)
LOCAL_PDF_DIRS = [
    r"F:\AnalisysDataSet\pdfs",
    r"F:\1\_STRUCTURED\09_LITERATURE",
    r"F:\1\_STRUCTURED\09_LITERATURE\1_Литература_данные\ГОСТы_ТУ",
]


def find_local_pdf(doi: str = None, title: str = None, author: str = None, year: int = None) -> str | None:
    """Поиск PDF в локальных корпусах по DOI/автору/году/названию (TD-152, RS-025).

    Возвращает путь или None. Матчинг по имени файла: автор (фамилия), год, DOI-фрагмент.
    """
    import re as _re
    patterns = []
    if doi:
        # DOI-фрагмент: последняя часть (например 'S0021889891010804')
        tail = doi.rsplit("/", 1)[-1]
        if len(tail) > 6:
            patterns.append(_re.compile(_re.escape(tail[:12]), _re.I))
    if author:
        fam = author.split()[-1].strip().lower()
        if len(fam) > 3:
            patterns.append(_re.compile(_re.escape(fam[:8]), _re.I))
    if year:
        patterns.append(_re.compile(str(year), re.IGNORECASE))
    if not patterns:
        return None
    for d in LOCAL_PDF_DIRS:
        root = Path(d)
        if not root.is_dir():
            continue
        for f in root.rglob("*.pdf"):
            low = f.name.lower()
            if all(p.search(low) for p in patterns):
                return str(f)
    return None


def cmd_resolve(args) -> int:
    """Каскадный resolve DOI→PDF (TD-152): метаданные→openAccessPdf→Sci-Hub→wayback.

    Возвращает валидный PDF (проверка %PDF) или 'not found' с честным статусом.
    """
    doi = args.doi
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = args.name or (doi.replace("/", "_") + ".pdf")

    # 0. Локальный корпус (RS-025/TD-152): ищем PDF по DOI/автору/году ДО внешних
    local = find_local_pdf(doi=doi)
    if not local:
        # попробуем по названию после получения метаданных ниже
        local = None
    if local:
        data = Path(local).read_bytes()
        if is_pdf(data):
            save_with_provenance(data, out, name, "file://" + local, "local_corpus", "verified_pdf",
                                 {"doi": doi, "local_path": local})
            print(f"OK (локально): {local} -> {name} ({len(data)} B)")
            return 0

    # 1. Метаданные: CrossRef (fallback OpenAlex)
    meta = crossref_check(doi)
    if not meta.get("ok"):
        oa = openalex_search(doi=doi)
        if oa.get("ok") and oa.get("works"):
            w = oa["works"][0]
            meta = {"ok": True, "title": w.get("title"), "authors": w.get("authors", []),
                    "year": w.get("year"), "oa_pdf": w.get("oa_pdf")}
    print(f"[1] Метаданные: {meta.get('ok')} — {meta.get('title', '?')[:60]} ({meta.get('year')})")

    # 1.5. Локальный поиск по метаданным (автор/год/название), если DOI не сработал
    if not local:
        author = (meta.get("authors") or [None])[0] if meta.get("ok") else None
        local2 = find_local_pdf(title=meta.get("title"), author=author, year=meta.get("year")) if meta.get("ok") else None
        if local2:
            data = Path(local2).read_bytes()
            if is_pdf(data):
                save_with_provenance(data, out, name, "file://" + local2, "local_corpus", "verified_pdf",
                                     {"doi": doi, "local_path": local2})
                print(f"OK (локально по метаданным): {local2} -> {name} ({len(data)} B)")
                return 0

    # 2. openAccessPdf (OpenAlex/CrossRef)
    candidates = []
    if meta.get("oa_pdf"):
        candidates.append(("oa_pdf", meta["oa_pdf"]))
    if not candidates:
        oa = openalex_search(doi=doi)
        if oa.get("ok") and oa.get("works"):
            w = oa["works"][0]
            if w.get("oa_pdf"):
                candidates.append(("oa_pdf", w["oa_pdf"]))

    # 3. Sci-Hub
    candidates.append(("scihub", None))  # маркер: решается в scihub_resolve

    for src, url in candidates:
        try:
            if src == "scihub":
                pdf_url, err = scihub_resolve(doi)
                if not pdf_url:
                    print(f"  [scihub] {err}")
                    continue
                status, data = http_get(pdf_url, timeout=args.timeout, verify=False, retries=2)
            else:
                status, data = http_get(url, timeout=args.timeout, retries=2)
            if status == 200 and isinstance(data, bytes) and data and is_pdf(data):
                save_with_provenance(data, out, name, url or pdf_url, src, "verified_pdf",
                                     {"doi": doi, "meta": meta})
                print(f"OK: {name} ({len(data)} B) via {src}")
                return 0
            if status in (403, 429):
                print(f"  [{src}] {status}, пауза {BACKOFF[1]}s")
                time.sleep(BACKOFF[1])
            else:
                print(f"  [{src}] статус {status} (не PDF)")
        except Exception as e:
            print(f"  [{src}] ERR {str(e)[:80]}")
            continue

    # 4. wayback для landing/oa (последняя попытка по известному URL)
    if meta.get("oa_pdf"):
        print("  [wayback] пробую web.archive.org...")
        st, data = wayback_fetch(meta["oa_pdf"], timeout=args.timeout)
        if st == 200 and data and is_pdf(data):
            save_with_provenance(data, out, name, "web.archive.org/" + meta["oa_pdf"], "wayback", "verified_pdf",
                                 {"doi": doi, "meta": meta})
            print(f"OK: {name} via wayback ({len(data)} B)")
            return 0

    print(f"NOT FOUND: {doi} — источники исчерпаны (проверь вручную)")
    return 6


def cmd_doi(args) -> int:
    doi = args.doi
    out = Path(args.out)
    if not args.skip_crossref:
        meta = crossref_check(doi)
        if not meta.get("ok"):
            print(f"DOI НЕ подтверждён CrossRef: {meta.get('error')}", file=sys.stderr)
            return 2
        print(f"CrossRef: {meta.get('year')} — {meta.get('title')[:60]}")
    pdf_url, err = scihub_resolve(doi)
    if not pdf_url:
        print(f"Sci-Hub: {err}", file=sys.stderr)
        return 3
    if pdf_url.startswith("//"):
        pdf_url = "https:" + pdf_url
    elif pdf_url.startswith("/"):
        pdf_url = "https://sci-hub.ru" + pdf_url
    status, data = http_get(pdf_url, timeout=args.timeout, verify=False)
    if status != 200 or not isinstance(data, bytes) or not data:
        print(f"Скачивание PDF не удалось: status={status}", file=sys.stderr)
        return 4
    if not is_pdf(data):
        print("Скачано, но не PDF (возможно капча/HTML)", file=sys.stderr)
        return 5
    name = args.name or (doi.replace("/", "_") + ".pdf")
    save_with_provenance(data, out, name, pdf_url, "scihub", "verified_pdf",
                         {"doi": doi, "crossref": meta if not args.skip_crossref else None})
    return 0


def cmd_url(args) -> int:
    """Универсальный загрузчик: GET URL → файл + провенанс.

    --expect pdf (или .pdf в имени) — проверяет %PDF; при несоответствии НЕ
    сохраняет как успех (TD-125/151: не подсовывать HTML вместо PDF).
    """
    url = args.url
    out = Path(args.out)
    name = args.name or Path(urllib.parse.urlparse(url).path).name or "download.bin"
    expect_pdf = args.expect == "pdf" or (not args.expect and name.lower().endswith(".pdf"))

    status, data = http_get(url, timeout=args.timeout, retries=args.retries)
    if status != 200 or not isinstance(data, bytes) or not data:
        print(f"GET {url} -> {status} (после {args.retries} ретраев)", file=sys.stderr)
        return 4

    if expect_pdf and not is_pdf(data):
        # Не PDF: сохраняем как unknown (не .pdf), помечаем, чтобы не путать
        if data[:4] in (b"<htm", b"<!DO", b"<hea"):
            print(f"ERROR: {url} вернул HTML (не PDF), не сохраняю как {name} — вероятно, ссылка/капча", file=sys.stderr)
            (out / f"{name}.html").write_bytes(data)
            return 5
        print(f"WARN: {url} — не PDF (первые {data[:8]!r}), сохраняю как {name}.bin", file=sys.stderr)
        name = name + ".bin"

    method = "http"
    vstatus = "verified_pdf" if is_pdf(data) else ("text" if data[:2] in (b"{\"", b"[{") else "unknown")
    save_with_provenance(data, out, name, url, method, vstatus)
    return 0


def cmd_crossref(args) -> int:
    meta = crossref_check(args.doi)
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0 if meta.get("ok") else 2


def cmd_extract(args) -> int:
    pdf = Path(args.pdf)
    out_dir = Path(args.out) if args.out else pdf.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / (pdf.stem + ".txt")
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf не установлен: pip install pypdf", file=sys.stderr)
        return 5
    reader = PdfReader(str(pdf))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    text = "\n".join(parts)
    txt_path.write_text(text, encoding="utf-8")
    (out_dir / f"{pdf.stem}.extract.json").write_text(
        json.dumps({"source": pdf.name, "pages": len(reader.pages), "chars": len(text),
                    "method": "pypdf", "sha256": sha256(pdf.read_bytes()),
                    "date": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK {pdf.name} -> {txt_path.name}: {len(text)} chars, {len(reader.pages)} pages")
    return 0


def cmd_dns(args) -> int:
    """Проверка резолва хоста системным DNS и DoH (TD-153)."""
    res = dns_preflight(args.host)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 3


def main() -> int:
    ap = argparse.ArgumentParser(description="Канонический загрузчик источников (TD-127)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doi", help="скачать статью по DOI через Sci-Hub с CrossRef-gate")
    p.add_argument("--doi", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--skip-crossref", action="store_true")
    p.set_defaults(fn=cmd_doi)

    p = sub.add_parser("url", help="скачать по прямому URL (универсальный)")
    p.add_argument("--url", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--expect", choices=["pdf", "text", "any"], default=None, help="ожидаемый тип (pdf — проверит %PDF)")
    p.add_argument("--retries", type=int, default=3)
    p.set_defaults(fn=cmd_url)

    p = sub.add_parser("crossref", help="проверить DOI через CrossRef")
    p.add_argument("--doi", required=True)
    p.set_defaults(fn=cmd_crossref)

    p = sub.add_parser("resolve", help="каскадный resolve DOI→PDF (TD-152)")
    p.add_argument("--doi", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--name", default=None)
    p.set_defaults(fn=cmd_resolve)

    p = sub.add_parser("dns", help="проверить резолв хоста (TD-153)")
    p.add_argument("--host", required=True)
    p.set_defaults(fn=cmd_dns)

    p = sub.add_parser("extract", help="извлечь текст из PDF (pypdf)")
    p.add_argument("--pdf", required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_extract)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())