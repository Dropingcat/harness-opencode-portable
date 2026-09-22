#!/usr/bin/env python3
"""mini_searxng.py — локальная замена SearXNG без Docker (TD-128).

Полный SearXNG не устанавливается на Windows (файлы с ':' в NTFS), Docker нет.
Этот сервер даёт тот же JSON-интерфейс `/search?q=&format=json`, что ожидает
`searxng_search_server.py` (127.0.0.1:8888), но ищет через:
  1. arXiv API (export.arxiv.org/api/query) — научные результаты
  2. OpenAlex API (api.openalex.org/works) — научные результаты
  3. DuckDuckGo HTML (html.duckduckgo.com) — веб-результаты (fallback)

Usage:
  python mini_searxng.py [--port 8888] [--host 127.0.0.1]

Интерфейс (как SearXNG): GET /search?q=<query>&format=json&categories=<general|science>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = "mini-searxng/1.0 (research harness)"


def _arxiv(q: str, limit: int = 5) -> list[dict]:
    try:
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": f"all:{q}", "start": 0, "max_results": limit})
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            xml = r.read().decode("utf-8", errors="replace")
        entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
        out = []
        for e in entries:
            title = re.search(r"<title>(.*?)</title>", e, re.S)
            link = re.search(r"<id>(.*?)</id>", e, re.S)
            summary = re.search(r"<summary>(.*?)</summary>", e, re.S)
            out.append({
                "url": link.group(1).strip() if link else "",
                "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else "",
                "content": re.sub(r"\s+", " ", summary.group(1)).strip()[:400] if summary else "",
                "engine": "arxiv",
            })
        return out
    except Exception:
        return []


def _openalex(q: str, limit: int = 5) -> list[dict]:
    try:
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
            {"search": q, "per-page": limit})
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
        out = []
        for w in d.get("results", []):
            loc = (w.get("primary_location") or {}).get("landing_page_url") or (
                w.get("doi") and "https://doi.org/" + w["doi"].replace("https://doi.org/", ""))
            out.append({
                "url": loc or "",
                "title": (w.get("title") or ""),
                "content": ((w.get("abstract_inverted_index") and "abstract available") or ""),
                "engine": "openalex",
            })
        return out
    except Exception:
        return []


def _ddg(q: str, limit: int = 5) -> list[dict]:
    try:
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": q})
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
        out = []
        # result__a href="..." > title </a> ... result__snippet
        blocks = re.findall(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>(.*?)class="result__snippet"[^>]*>(.*?)</', html, re.S)
        for href, title, _, snip in blocks[:limit]:
            out.append({
                "url": re.sub(r"&amp;", "&", href),
                "title": re.sub(r"<[^>]+>", "", title).strip(),
                "content": re.sub(r"<[^>]+>", "", snip).strip()[:400],
                "engine": "ddg",
            })
        return out
    except Exception:
        return []


def _search(q: str, categories: str, limit: int) -> dict:
    results = []
    if categories in ("general", "science"):
        results += _arxiv(q, limit)
        results += _openalex(q, limit)
    if categories == "general" or not results:
        results += _ddg(q, limit)
    return {"query": q, "results": results[:limit], "count": len(results[:limit])}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/healthz":
            self._send({"status": "ok"})
            return
        if parsed.path != "/search":
            self._send({"error": "not found"}, code=404)
            return
        params = urllib.parse.parse_qs(parsed.query)
        q = params.get("q", [""])[0]
        fmt = params.get("format", ["json"])[0]
        categories = params.get("categories", ["general"])[0]
        limit = int(params.get("limit", ["8"])[0])
        if not q:
            self._send({"error": "empty q"})
            return
        if fmt != "json":
            self._send({"error": "only json"}, code=400)
            return
        try:
            res = _search(q, categories, limit)
        except Exception as e:
            self._send({"error": str(e)}, code=500)
            return
        self._send(res)

    def _send(self, obj: dict, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"mini-searxng on http://{args.host}:{args.port} (JSON /search?q=&format=json)", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())