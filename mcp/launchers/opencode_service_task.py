#!/usr/bin/env python3
"""MCP Launcher: opencode_service_task — Composio-сервисы (Calendar/Gmail/Drive/GitHub)."""

import asyncio
import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _runner import run_with_contract

server = Server("opencode-service-task")

CONTRACT = """\
Ты — service-worker. Твоя задача: работа с внешними сервисами через Composio MCP.

Composio v2 API (мета-инструменты, работай в этом порядке):
1. COMPOSIO_SEARCH_TOOLS — найди нужный tool по описанию (например "create calendar event")
2. COMPOSIO_GET_TOOL_SCHEMAS — получи точную схему параметров (никогда не выдумывай slug)
3. COMPOSIO_MULTI_EXECUTE_TOOL — выполни действие с payload по схеме
4. COMPOSIO_MANAGE_CONNECTIONS / COMPOSIO_WAIT_FOR_CONNECTIONS — если нужно подключение

РАЗРЕШЕНО:
- только Composio MCP (Calendar, Gmail, Drive, GitHub, Slack)
- только явно указанные toolkits
- dry-run по умолчанию (подготовить payload, показать preview)
- чтение файлов в workdir

ЗАПРЕЩЕНО:
- массовые действия без подтверждения
- удаление данных
- отправка сообщений/писем без preview
- правка конфигов, sudo, установка пакетов
- доступ к alisa-assistant профилю
- раскрывать секреты/ключи

ЛЮФТ:
- искать нужный tool в Composio
- подготовить payload
- выполнить только если task contract разрешает

ВЫХОД (запиши в <run_dir>/results.json):
{
  "planned_action": "описание действия",
  "toolkit": "googlecalendar|gmail|drive|github|slack",
  "dry_run": true,
  "requires_confirmation": true,
  "payload_preview": {...}
}
"""

MODEL = "ollama-cloud/glm-5.2"
TIMEOUT = 180


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="service_task",
            description="Run a service delegate: Composio MCP (Calendar/Gmail/Drive/GitHub). Dry-run by default.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Service task (e.g. 'create calendar event', 'send email draft')."},
                    "model": {"type": "string", "description": "Override model.", "default": MODEL},
                    "timeout": {"type": "integer", "description": "Timeout seconds.", "default": TIMEOUT},
                },
                "required": ["task"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if name != "service_task":
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}, ensure_ascii=False))]
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    args = arguments or {}
    result = await run_with_contract(
        "service_task",
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