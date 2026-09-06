#!/usr/bin/env python3
"""MCP server: academic_search — arXiv + OpenAlex search (no API keys needed).

Tools:
  arxiv_search — search arXiv, return title/authors/abstract/published/pdf_url
  openalex_search — search OpenAlex, return title/authors/year/doi/cited_by_count
"""
import asyncio
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("academic-search")
TIMEOUT = int(os.environ.get("ACADEMIC_SEARCH_TIMEOUT", "20"))
ARXIV_BASE = "https://export.arxiv.org/api/query"
OPENALEX_BASE = "https://api.openalex.org/works"

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}

# VNNet proxy breaks external APIs (urllib uses env proxies). Bypass proxy directly.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _arxiv_search(query: str, max_results: int = 5) -> list[dict]:
    params = urllib.parse.urlencode({"search_query": f"all:{query}", "max_results": str(max_results)})
    url = f"{ARXIV_BASE}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-academic-mcp/1.0"})
    with _OPENER.open(req, timeout=TIMEOUT) as resp:
        xml_data = resp.read().decode("utf-8")
    root = ET.fromstring(xml_data)
    results = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        arxiv_id = entry.find("atom:id", ARXIV_NS)
        aid = arxiv_id.text.split("/abs/")[-1] if arxiv_id is not None and arxiv_id.text else ""
        title = entry.find("atom:title", ARXIV_NS)
        summary = entry.find("atom:summary", ARXIV_NS)
        published = entry.find("atom:published", ARXIV_NS)
        authors = [a.find("atom:name", ARXIV_NS).text for a in entry.findall("atom:author", ARXIV_NS) if a.find("atom:name", ARXIV_NS) is not None]
        pdf_link = ""
        for link in entry.findall("atom:link", ARXIV_NS):
            if link.get("title") == "pdf":
                pdf_link = link.get("href", "")
                break
        results.append({
            "arxiv_id": aid,
            "title": (title.text or "").strip().replace("\n", " ") if title is not None else "",
            "authors": authors[:5],
            "abstract": (summary.text or "").strip()[:500] if summary is not None else "",
            "published": (published.text or "")[:10] if published is not None else "",
            "pdf_url": pdf_link,
        })
    return results


def _openalex_search(query: str, per_page: int = 5) -> list[dict]:
    params = urllib.parse.urlencode({"search": query, "per-page": str(per_page)})
    url = f"{OPENALEX_BASE}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-academic-mcp/1.0"})
    with _OPENER.open(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    results = []
    for w in data.get("results", []):
        authorships = w.get("authorships", [])
        authors = [a.get("author", {}).get("display_name", "") for a in authorships[:5]]
        results.append({
            "openalex_id": w.get("id", ""),
            "title": w.get("title", "") or "",
            "authors": authors,
            "year": w.get("publication_year"),
            "doi": w.get("doi", ""),
            "cited_by_count": w.get("cited_by_count", 0),
            "type": w.get("type", ""),
            "abstract": (w.get("abstract_inverted_index") and _invert_abstract(w["abstract_inverted_index"])) or "",
        })
    return results


def _invert_abstract(inv: dict) -> str:
    positions = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)[:500]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="arxiv_search",
            description="Search arXiv.org for academic papers (CS, Physics, Math, etc). No API key needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms."},
                    "max_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="openalex_search",
            description="Search OpenAlex (open scholarly graph, 240M+ works). Returns title, authors, year, DOI, citation count.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms."},
                    "per_page": {"type": "integer", "default": 5, "minimum": 1, "maximum": 25},
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    args = arguments or {}
    query = str(args.get("query", "")).strip()
    if not query:
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": "query is required"}))]
    loop = asyncio.get_event_loop()
    try:
        if name == "arxiv_search":
            results = await loop.run_in_executor(None, _arxiv_search, query, int(args.get("max_results", 5)))
            payload = {"ok": True, "source": "arxiv", "query": query, "count": len(results), "results": results}
        elif name == "openalex_search":
            results = await loop.run_in_executor(None, _openalex_search, query, int(args.get("per_page", 5)))
            payload = {"ok": True, "source": "openalex", "query": query, "count": len(results), "results": results}
        else:
            return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}))]
    except Exception as exc:
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": str(exc)}))]
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())