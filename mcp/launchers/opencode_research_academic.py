#!/usr/bin/env python3
"""MCP Launcher: opencode_research_academic — научные источники."""

import asyncio
import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _runner import run_with_contract

server = Server("opencode-research-academic")

CONTRACT = """\
Ты — research-academic-worker. Твоя задача: научный поиск и анализ источников.

РАЗРЕШЕНО:
- searxng_search MCP (поиск научных тем, категории science/it)
- extract_document MCP (извлечение текста из скачанных PDF/DOCX)
- opencode-research-papers (arXiv, OpenAlex — если доступно)
- research-mcp (если установлен: Semantic Scholar, CrossRef, citation graph)
- чтение файлов в workdir

ПОРЯДОК: searxng_search (science) → скачать PDF → extract_document → анализ.

ЗАПРЕЩЕНО:
- широкий web search без причины (только если научные источники пусты)
- Sci-Hub без отдельного разрешения
- запись вне research-run директории
- правка конфигов, sudo, установка пакетов
- доступ к alisa-assistant профилю

ЛЮФТ:
- расширять запрос синонимами
- citation graph depth 1-2
- отбрасывать мусорные источники

ВЫХОД (запиши в <run_dir>/results.json):
{
  "papers": [{"doi": "...", "title": "...", "authors": "...", "year": ..., "citations": ...}],
  "citation_graph": "путь к графу",
  "evidence_table": [{"claim": "...", "source": "...", "support": "supports|contradicts|context"}],
  "gaps": ["что не покрыто"],
  "recommended_next_searches": ["..."]
}
"""

MODEL = "ollama-cloud/glm-5.2"
TIMEOUT = 300


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="research_academic",
            description="Run an academic research delegate: arXiv/OpenAlex/Semantic Scholar search → citation graph → evidence table.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Academic research query."},
                    "model": {"type": "string", "description": "Override model.", "default": MODEL},
                    "timeout": {"type": "integer", "description": "Timeout seconds.", "default": TIMEOUT},
                },
                "required": ["task"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if name != "research_academic":
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}, ensure_ascii=False))]
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    args = arguments or {}
    result = await run_with_contract(
        "research_academic",
        args.get("task", ""),
        CONTRACT,
        args.get("model", MODEL),
        int(args.get("timeout", TIMEOUT)),
    )
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())