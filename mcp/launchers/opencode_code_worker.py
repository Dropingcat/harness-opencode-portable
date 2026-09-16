#!/usr/bin/env python3
"""MCP Launcher: opencode_code_worker — кодинг, рефакторинг, тесты."""

import asyncio
import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _runner import run_with_contract

server = Server("opencode-code-worker")

CONTRACT = """\
Ты — code-worker. Твоя задача: кодинг, рефакторинг, тесты.

РАЗРЕШЕНО:
- чтение репозитория/project
- write только в project/worktree (run_dir)
- tests/build/run
- skills: verification-planning, simplify, worktrees

ЗАПРЕЩЕНО:
- править .hermes, .config/opencode, secrets
- ставить системные зависимости без разрешения
- коммитить в git
- доступ к alisa-assistant профилю
- раскрывать секреты/ключи

ЛЮФТ:
- выбирать реализацию внутри контракта
- нельзя менять цель
- если scope растёт — остановиться и вернуть уточнение

ВЫХОД (запиши в run_dir/results.json):
{
  "what_changed_or_found": "...",
  "files_touched": ["..."],
  "tests_run": [{"cmd": "...", "pass": true/false, "output": "..."}],
  "risks": ["..."],
  "next_step": "..."
}
"""

MODEL = "ollama-cloud/glm-5.2"
TIMEOUT = 300


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="code_work",
            description="Run a code worker delegate: read repo → write in worktree → run tests → report.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Coding task (e.g. 'refactor X', 'add test Y', 'fix bug Z')."},
                    "model": {"type": "string", "description": "Override model.", "default": MODEL},
                    "timeout": {"type": "integer", "description": "Timeout seconds.", "default": TIMEOUT},
                },
                "required": ["task"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if name != "code_work":
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}, ensure_ascii=False))]
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    args = arguments or {}
    result = await run_with_contract(
        "code_work",
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