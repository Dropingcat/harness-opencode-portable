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


def _ctx(verify: bool = True) -> ssl.SSLContext:
    c = ssl.create_default_context()
    if not verify:
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
    return c


def http_get(url: str, timeout: int = DEFAULT_TIMEOUT, verify: bool = True,
             retries: int = MAX_RETRIES, binary: bool = True) -> tuple[int, bytes | str]:
    """GET с retry/backoff. Возвращает (status, body_bytes|text)."""
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx(verify)) as r:
                data = r.read()
                return r.status, data
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (403, 404, 410):
                return e.code, b""
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
    url = args.url
    out = Path(args.out)
    status, data = http_get(url, timeout=args.timeout)
    if status != 200 or not isinstance(data, bytes):
        print(f"GET {url} -> {status}", file=sys.stderr)
        return 4
    name = args.name or Path(urllib.parse.urlparse(url).path).name or "download.bin"
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

    p = sub.add_parser("url", help="скачать по прямому URL")
    p.add_argument("--url", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--name", default=None)
    p.set_defaults(fn=cmd_url)

    p = sub.add_parser("crossref", help="проверить DOI через CrossRef")
    p.add_argument("--doi", required=True)
    p.set_defaults(fn=cmd_crossref)

    p = sub.add_parser("extract", help="извлечь текст из PDF (pypdf)")
    p.add_argument("--pdf", required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_extract)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())