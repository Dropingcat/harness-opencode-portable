#!/usr/bin/env python3
"""MCP Launcher: opencode_profile_configurator — настройка профилей Hermes."""

import asyncio
import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _runner import run_with_contract

server = Server("opencode-profile-configurator")

CONTRACT = """\
Ты — profile-configurator. Твоя задача: настройка конфигов Hermes профилей.

РАЗРЕШЕНО читать и править ТОЛЬКО (default-профиль):
- /home/orangepi/.hermes/config.yaml
- /home/orangepi/.hermes/SOUL.md
- /home/orangepi/.config/opencode/opencode.jsonc
- /home/orangepi/.hermes/prisms/*.md
- /home/orangepi/.hermes/skills/*/SKILL.md
- /home/orangepi/.hermes/mcp/*.py и /home/orangepi/.hermes/mcp/launchers/*.py

СТРОГО ЗАПРЕЩЕНО трогать:
- /home/orangepi/.hermes/profiles/alisa-assistant/ (всё)

ОБЯЗАТЕЛЬНО:
- backup перед изменением (копия в /home/orangepi/.hermes/backups/)
- валидация YAML/JSONC после правки
- smoke-test: python3 -c "import yaml; yaml.safe_load(open('...'))"

ЗАПРЕЩЕНО:
- писать секреты/ключи прямо в config (только env)
- менять systemd units без подтверждения
- перезапускать gateway без подтверждения
- коммитить в git
- удалять файлы без бэкапа

ВЫХОД (запиши в run_dir/results.json):
{
  "files_changed": ["..."],
  "backups_created": ["..."],
  "validation": {"file": "...", "valid": true/false},
  "smoke_tests": [{"cmd": "...", "pass": true/false}],
  "summary": "...",
  "requires_restart": true/false,
  "risks": ["..."]
}
"""

# TD-D6/AG-D6 (issue #18): явная фиксация legacy-транспорта (см.
# docs/LEGACY_TRANSPORT_REGISTRY.json; гейт check_legacy_transport.py).
TRANSPORT_TAG = "opencode_cli_legacy"

MODEL = "ollama-cloud/glm-5.2"
TIMEOUT = 300


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="profile_config",
            description="Run a profile configurator delegate: edit Hermes/OpenCode configs with backup + validation + smoke-test.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Config task (e.g. 'add MCP server X', 'update SOUL.md')."},
                    "model": {"type": "string", "description": "Override model.", "default": MODEL},
                    "timeout": {"type": "integer", "description": "Timeout seconds.", "default": TIMEOUT},
                },
                "required": ["task"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if name != "profile_config":
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}, ensure_ascii=False))]
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    args = arguments or {}
    result = await run_with_contract(
        "profile_config",
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