#!/usr/bin/env python3
"""Minimal MCP router for one-shot OpenCode delegation."""

import asyncio
import json
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


OPENCODE_BIN = os.environ.get("CODER_ROUTER_OPENCODE") or os.environ.get("OPENCODE_BIN") or shutil.which("opencode") or str(Path.home() / ".opencode" / "bin" / "opencode")
DEFAULT_WORKDIR = os.environ.get("OPENCODE_HARNESS_ROOT") or str(Path.home())
TIMEOUT_SECONDS = int(os.environ.get("CODER_ROUTER_TIMEOUT", "300"))
MODEL_BY_CLASS = {
    "free": os.environ.get("CODER_ROUTER_FREE_MODEL", "opencode/hy3-free"),
    "fast": os.environ.get("CODER_ROUTER_FAST_MODEL", "ollama-cloud/glm-5.2"),
    "polza": os.environ.get("CODER_ROUTER_POLZA_MODEL", "polza/deepseek/deepseek-v4-flash-0731"),
}

server = Server("coder-router")


def _json_text(payload: dict[str, Any]) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


def _resolve_model(model_class: str) -> str:
    if "/" in model_class:
        return model_class
    model = MODEL_BY_CLASS.get(model_class)
    if not model:
        raise ValueError(f"Unknown model_class: {model_class}")
    return model


async def handle_coder_run(arguments: dict[str, Any]) -> list[TextContent]:
    task = str(arguments.get("task") or "").strip()
    if not task:
        return _json_text({"ok": False, "error": "task is required"})

    model_class = str(arguments.get("model_class") or "free").strip()
    workdir = Path(str(arguments.get("workdir") or DEFAULT_WORKDIR)).expanduser().resolve()
    if not workdir.exists() or not workdir.is_dir():
        return _json_text({"ok": False, "error": f"workdir does not exist or is not a directory: {workdir}"})

    try:
        model = _resolve_model(model_class)
    except ValueError as exc:
        return _json_text({"ok": False, "error": str(exc), "known_model_classes": sorted(MODEL_BY_CLASS)})

    cmd = [OPENCODE_BIN, "run", "--pure", "--model", model, "--dir", str(workdir), task]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(workdir),
            stdin=subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        os.killpg(proc.pid, signal.SIGKILL)
        await proc.wait()
        return _json_text({"ok": False, "error": f"opencode timed out after {TIMEOUT_SECONDS}s", "model": model})
    except OSError as exc:
        return _json_text({"ok": False, "error": f"failed to start opencode: {exc}"})

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    return _json_text({
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "model_class": model_class,
        "model": model,
        "workdir": str(workdir),
        "stdout": stdout,
        "stderr": stderr,
    })


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="coder_run",
            description="Run OpenCode once with --pure for delegated coding, analysis, or smoke checks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task prompt passed to opencode run."},
                    "model_class": {
                        "type": "string",
                        "description": "Model class: free, fast, polza, or an exact provider/model string.",
                        "default": "free",
                    },
                    "workdir": {"type": "string", "description": "Working directory.", "default": DEFAULT_WORKDIR},
                },
                "required": ["task"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    if name != "coder_run":
        return _json_text({"ok": False, "error": f"Unknown tool: {name}"})
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    return await handle_coder_run(arguments or {})


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
