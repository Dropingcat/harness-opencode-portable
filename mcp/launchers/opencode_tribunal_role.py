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
import os
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

# TD-D6/AG-D6 (issue #18): явная фиксация legacy-транспорта (см.
# docs/LEGACY_TRANSPORT_REGISTRY.json; гейт check_legacy_transport.py).
TRANSPORT_TAG = "opencode_cli_legacy"

MODEL = os.environ.get("OPENCODE_TRIBUNAL_MODEL", "ollama-cloud/glm-5.2")
TIMEOUT = int(os.environ.get("OPENCODE_TRIBUNAL_TIMEOUT", "180"))


def _provider_payload(result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("ok"):
        return result
    run_dir = Path(str(result.get("run_dir") or ""))
    result_path = run_dir / "results.json"
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else json.loads(str(result.get("stdout") or ""))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"provider returned no valid Tribunal JSON: {exc}", "run_dir": str(run_dir)}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "provider Tribunal result must be a JSON object", "run_dir": str(run_dir)}
    return payload


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
        MODEL,
        TIMEOUT,
    )
    return [TextContent(type="text", text=json.dumps(_provider_payload(result), ensure_ascii=False, indent=2))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
