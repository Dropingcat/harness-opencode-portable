#!/usr/bin/env python3
"""MCP server: SearXNG search wrapper for Hermes research_web delegate.

Exposes one tool: searxng_search — performs a local SearXNG JSON search
and returns results. Bound to http://127.0.0.1:8888 (local Docker container).
"""
import asyncio
import json
import os
import urllib.parse
from typing import Any

import urllib.request

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888")
DEFAULT_TIMEOUT = int(os.environ.get("SEARXNG_TIMEOUT", "15"))

server = Server("searxng")


def _search(query: str, categories: str = "general", limit: int = 8, timeout: int = DEFAULT_TIMEOUT) -> list[dict]:
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "categories": categories,
    })
    url = f"{SEARXNG_URL}/search?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "hermes-searxng-mcp/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    results = []
    for r in (data.get("results") or [])[:limit]:
        results.append({
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
            "engine": r.get("engine", ""),
        })
    return results


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="searxng_search",
            description="Search the web via local SearXNG instance. Returns title, url, snippet for each result.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "categories": {
                        "type": "string",
                        "description": "SearXNG category: general, images, news, it, science, files, social media.",
                        "default": "general",
                    },
                    "limit": {"type": "integer", "description": "Max results to return.", "default": 8, "minimum": 1, "maximum": 20},
                    "timeout": {"type": "integer", "description": "Request timeout seconds.", "default": DEFAULT_TIMEOUT},
                },
                "required": ["query"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if name != "searxng_search":
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}))]
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    args = arguments or {}
    query = str(args.get("query", "")).strip()
    if not query:
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": "query is required"}))]
    categories = str(args.get("categories", "general"))
    limit = int(args.get("limit", 8))
    timeout = int(args.get("timeout", DEFAULT_TIMEOUT))
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(None, _search, query, categories, limit, timeout)
    except Exception as exc:
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": str(exc), "searxng_url": SEARXNG_URL}))]
    payload = {"ok": True, "query": query, "categories": categories, "count": len(results), "results": results}
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())