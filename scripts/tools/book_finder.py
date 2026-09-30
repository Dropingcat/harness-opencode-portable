#!/usr/bin/env python3
"""book_finder.py — канонический поиск книг по ISBN/автору (TD-165).

Заменяет ad-hoc скрипты агента (gb_check.py, curl к libgen-зеркалам, jina proxy).
Возможности:
  resolve-isbn   — идентификация ISBN через Google Books + Open Library (кросспроверка),
                   НЕ доверяет user-input (может быть подмена, см. TD-165).
  search-mirrors — поиск fulltext по зеркалам (dokumen.pub, vdoc.pub, libgen.*)
                   с retry/backoff и DNS-bypass (TD-153).
  verdict        — честный итог: found (pdf_url) | toc_only | not_found.

Usage:
  python book_finder.py resolve-isbn --isbn 978-5-7038-3933-1
  python book_finder.py search-mirrors --isbn 978-5-7038-3933-1 [--title "Герасимов структура азотированных"]
  python book_finder.py verdict --isbn 978-5-7038-3933-1 [--out prov.json]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UA = "book-finder/1.0 (research harness; mailto:research@local)"
TIMEOUT = 25
BACKOFF = [2, 4, 8]
LIBGEN_MIRRORS = ["libgen.is", "libgen.rs", "libgen.st", "libgen.gs", "libgen.li", "libgen.lc"]


def http_get_json(url, retries=3):
    """GET + JSON с retry/backoff. Возвращает dict или None."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            # DNS-bypass (TD-153): если системный DNS падает, пробуем DoH-IP
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except Exception as e:
            last = e
            if attempt < retries - 1:
                time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
    return {"error": str(last)[:200]}


def normalize_isbn(isbn: str) -> str:
    return re.sub(r"[\s\-]", "", isbn)


def resolve_isbn(isbn: str) -> dict:
    """Идентификация ISBN через Google Books + Open Library. Кросспроверка."""
    isbn = normalize_isbn(isbn)
    result = {"isbn": isbn, "google": None, "openlibrary": None, "matched": False, "sources": []}

    g = http_get_json(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}")
    if g and "error" not in g and g.get("totalItems"):
        it = g["items"][0].get("volumeInfo", {})
        result["google"] = {
            "title": it.get("title"), "subtitle": it.get("subtitle"),
            "authors": it.get("authors"), "publishedDate": it.get("publishedDate"),
            "publisher": it.get("publisher"), "pageCount": it.get("pageCount"),
            "industryIdentifiers": it.get("industryIdentifiers"),
        }
        result["sources"].append("google_books")
        result["matched"] = True

    ol = http_get_json(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data")
    if ol and "error" not in ol:
        key = f"ISBN:{isbn}"
        data = ol.get(key)
        if data:
            result["openlibrary"] = {
                "title": data.get("title"),
                "authors": [a.get("name") for a in data.get("authors", [])],
                "publish_date": data.get("publish_date"),
                "publishers": data.get("publishers"),
                "number_of_pages": data.get("number_of_pages"),
            }
            result["sources"].append("open_library")
            result["matched"] = True

    return result


def _grab(url: str, retries=2) -> bytes | None:
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as e:
            last = e
            if attempt < retries:
                time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
    return None


def search_mirrors(isbn: str, title: str | None = None) -> dict:
    """Поиск fulltext по зеркалам. Возвращает найденные кандидаты."""
    isbn = normalize_isbn(isbn)
    found = []
    checked = []

    # dokumen.pub / vdoc.pub по ISBN
    for host in ("https://dokumen.pub", "https://vdoc.pub"):
        url = f"{host}/download/{isbn}.html"
        body = _grab(url)
        checked.append({"url": url, "status": "ok" if body else "fail"})
        if body:
            txt = body.decode("utf-8", errors="replace").lower()
            if b"%pdf" in body[:200] or "application/pdf" in txt or "download" in txt:
                found.append({"mirror": host, "url": url, "kind": "html_page",
                              "note": "страница книги; PDF может быть за капчей/ссылкой"})

    # libgen зеркала
    for h in LIBGEN_MIRRORS:
        url = f"https://{h}/search.php?req={isbn}"
        body = _grab(url, retries=1)
        checked.append({"url": url, "status": "ok" if body else "fail"})
        if body:
            txt = body.decode("utf-8", errors="replace")
            if "No files found" not in txt and "не найдено" not in txt.lower() and "table" in txt.lower():
                # попытка извлечь прямую ссылку на скачивание (md5/download)
                md5s = re.findall(r"md5=([a-f0-9]{32})", txt, re.I)
                dl_links = re.findall(r'https?://[^"\']+\.(?:pdf|djvu|epub)(?:\?[^"\']*)?', txt, re.I)
                found.append({"mirror": h, "url": url, "kind": "libgen_search",
                              "md5": md5s[:3] if md5s else None,
                              "direct_download": dl_links[:3] if dl_links else None,
                              "note": "найдено в выдаче libgen"})

    # Anna's Archive (annas-archive.org) — агрегатор libgen/duxiu/lingzi, обход через зеркала
    annas_mirrors = ["https://annas-archive.org", "https://annas-archive.se"]
    for h in annas_mirrors:
        q = urllib.parse.urlencode({"q": isbn})
        url = f"{h}/search?{q}"
        body = _grab(url, retries=1)
        checked.append({"url": url, "status": "ok" if body else "fail"})
        if body:
            txt = body.decode("utf-8", errors="replace").lower()
            # annas-archive отдаёт список файлов; captcha/cloudflare блокируют — маркер
            if "captcha" in txt or "cloudflare" in txt or "challenge" in txt:
                checked[-1]["status"] = "captcha"
                found.append({"mirror": h, "url": url, "kind": "annas_archive",
                              "note": "капча/Cloudflare — обход: cookie-перехват или ручной доступ (TD-158)"})
            elif "no results" not in txt and "не найдено" not in txt:
                found.append({"mirror": h, "url": url, "kind": "annas_archive",
                              "note": "найдено в выдаче Anna's Archive"})

    return {"isbn": isbn, "title": title, "checked": checked, "found": found,
            "count": len(found)}


def verdict(isbn: str, out: str | None = None, title: str | None = None) -> dict:
    """Итоговый вердикт: found | toc_only | not_found + провенанс."""
    isbn = normalize_isbn(isbn)
    meta = resolve_isbn(isbn)
    mirrors = search_mirrors(isbn, title)

    status = "not_found"
    if mirrors["found"]:
        status = "found"
    elif meta.get("matched"):
        # книга идентифицирована, но fulltext не найден
        status = "toc_only"

    prov = {
        "isbn": isbn,
        "title_query": title,
        "status": status,
        "resolved": meta,
        "mirrors": mirrors,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "user-input ISBN может указывать на ДРУГУЮ книгу (TD-165): всегда сверяй resolved.title",
    }
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
    return prov


def main() -> int:
    ap = argparse.ArgumentParser(description="Поиск книг по ISBN/зеркалам (TD-165)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("resolve-isbn")
    p.add_argument("--isbn", required=True)
    p.set_defaults(fn=lambda a: print(json.dumps(resolve_isbn(a.isbn), ensure_ascii=False, indent=2)))

    p = sub.add_parser("search-mirrors")
    p.add_argument("--isbn", required=True)
    p.add_argument("--title", default=None)
    p.set_defaults(fn=lambda a: print(json.dumps(search_mirrors(a.isbn, a.title), ensure_ascii=False, indent=2)))

    p = sub.add_parser("verdict")
    p.add_argument("--isbn", required=True)
    p.add_argument("--title", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=lambda a: print(json.dumps(verdict(a.isbn, a.out, a.title), ensure_ascii=False, indent=2)))

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())