#!/usr/bin/env python3
"""MCP Launcher: opencode_research_web — веб-поиск и первичный сбор."""

import asyncio
import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _runner import run_with_contract

server = Server("opencode-research-web")

CONTRACT = """\
Ты — research-web-worker. Твоя задача: веб-поиск и первичный сбор информации.

РАЗРЕШЕНО:
- searxng_search MCP (приоритет! локальный SearXNG, быстрый, JSON API)
- browser MCP (веб-страницы, fetch, extract — для чтения найденных URL)
- DDG поиск (если SearXNG недоступен)
- Composio Search (дополнительно)
- fetch/extract инструментов
- чтение файлов в workdir

ПОРЯДОК: сначала searxng_search → потом browser/fetch для чтения топ-URL.

ЗАПРЕЩЕНО:
- править системные конфиги (.hermes, .config)
- sudo, установка пакетов
- запуск фоновых процессов
- доступ к alisa-assistant профилю
- раскрывать секреты/ключи

ВЫХОД (запиши в <run_dir>/results.json):
{
  "query": "исходный запрос",
  "sources": [{"url": "...", "title": "...", "snippet": "..."}],
  "raw_notes_path": "путь к сырым заметкам",
  "summary": "краткая сводка",
  "uncertainties": ["что не удалось выяснить"]
}
"""

MODEL = "ollama-cloud/glm-5.2"
TIMEOUT = 300


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="research_web",
            description="Run a web research delegate: search → extract → summarize. Returns sources + notes + uncertainties.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Research query/task for the web worker."},
                    "model": {"type": "string", "description": "Override model (provider/model).", "default": MODEL},
                    "timeout": {"type": "integer", "description": "Timeout in seconds.", "default": TIMEOUT},
                },
                "required": ["task"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if name != "research_web":
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}, ensure_ascii=False))]
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    args = arguments or {}
    task = args.get("task", "")
    model = args.get("model", MODEL)
    timeout = int(args.get("timeout", TIMEOUT))
    result = await run_with_contract("research_web", task, CONTRACT, model, timeout)
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())