#!/usr/bin/env python3
"""Bounded semantic Tribunal role launcher.

The launcher receives an already compiled execution envelope.  It does not
select roles, providers, evidence, tools or branches.  The OpenCode worker is
asked to return one strict JSON object; deterministic admission remains in
researcher_core.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _runner import run_with_contract

server = Server("opencode-tribunal-role")

CONTRACT = (Path(__file__).resolve().parents[2] / "config" / "tribunal_role_provider_contract.md").read_text(encoding="utf-8")

MODEL = "ollama-cloud/glm-5.2"
TIMEOUT = 180


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="tribunal_role",
            description="Execute one bounded Tribunal question/answer/defense role from a compiled execution envelope.",
            inputSchema={
                "type": "object",
                "properties": {
                    "execution_envelope": {"type": "object"},
                    "model": {"type": "string", "default": MODEL},
                    "timeout": {"type": "integer", "default": TIMEOUT},
                },
                "required": ["execution_envelope"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if name != "tribunal_role":
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}, ensure_ascii=False))]
    args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    envelope = args.get("execution_envelope")
    if not isinstance(envelope, dict):
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": "execution_envelope object is required"}, ensure_ascii=False))]
    task = "EXECUTION_ENVELOPE:\n" + json.dumps(envelope, ensure_ascii=False, indent=2)
    result = await run_with_contract(
        "tribunal_role",
        task,
        CONTRACT,
        args.get("model", MODEL),
        int(args.get("timeout", TIMEOUT)),
    )
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
