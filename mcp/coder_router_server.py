#!/usr/bin/env python3
"""Minimal MCP router for one-shot OpenCode delegation."""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# M1 semantic transport adapter (DEV-05/TD-062). Import is best-effort: when
# the adapter module is unavailable the router MUST NOT silently fall back to
# the legacy CLI — it stays on the legacy path AND flags it in the response
# (`legacy_only=True`, `transport="opencode_cli_legacy"`). M3a: transport
# selection is delegated to M1's `resolve_transport()` (HARNESS_TRANSPORT).
_CODE_FACTORY_DIR = str(Path(__file__).resolve().parent.parent / "scripts" / "code-factory")
if _CODE_FACTORY_DIR not in sys.path:
    sys.path.insert(0, _CODE_FACTORY_DIR)
try:
    from semantic_transport import (
        build_coder_request,
        classify_purpose,
        execute_coder_semantic,
        resolve_transport,
    )

    _LEGACY_ONLY = False
except ImportError:  # pragma: no cover - exercised by tests/coder/test_coder_router_wiring.py
    build_coder_request = None  # type: ignore[assignment]
    classify_purpose = None  # type: ignore[assignment]
    execute_coder_semantic = None  # type: ignore[assignment]
    resolve_transport = None  # type: ignore[assignment]
    _LEGACY_ONLY = True


OPENCODE_BIN = os.environ.get("CODER_ROUTER_OPENCODE") or os.environ.get("OPENCODE_BIN") or shutil.which("opencode") or str(Path.home() / ".opencode" / "bin" / "opencode")
DEFAULT_WORKDIR = os.environ.get("OPENCODE_HARNESS_ROOT") or str(Path.cwd())
TIMEOUT_SECONDS = int(os.environ.get("CODER_ROUTER_TIMEOUT", "300"))
MODEL_BY_CLASS = {
    "free": os.environ.get("CODER_ROUTER_FREE_MODEL", "opencode/hy3-free"),
    "fast": os.environ.get("CODER_ROUTER_FAST_MODEL", "ollama-cloud/glm-5.2"),
    "polza": os.environ.get("CODER_ROUTER_POLZA_MODEL", "polza/deepseek/deepseek-v4-flash-0731"),
}

_LEGACY_REASON = "plugin bridge not enabled or adapter unavailable"

# transport identifiers in responses (M3a)
_TRANSPORT_PLUGIN = "harness-plugin-bridge"
_TRANSPORT_LEGACY = "opencode_cli_legacy"

server = Server("coder-router")


def _allowed_roots() -> list[Path]:
    raw = os.environ.get("CODER_ROUTER_ALLOWED_ROOTS")
    if raw:
        return [Path(x).expanduser().resolve() for x in raw.split(os.pathsep) if x.strip()]
    return [Path(DEFAULT_WORKDIR).expanduser().resolve()]


def _is_allowed_workdir(path: Path) -> bool:
    for root in _allowed_roots():
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _json_text(payload: dict[str, Any]) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


def _transport_unavailable(payload: dict[str, Any]) -> list[TextContent]:
    """Fail-closed response: transport NOT available, CLI is NOT called.

    M3a (DEV-05): the operator explicitly selected the plugin transport
    (HARNESS_TRANSPORT=plugin) but the bridge is not resolvable (M1 adapter
    ImportError, missing HARNESS_SEMANTIC_ENABLED, or missing bridge peer).
    There is NO silent fallback to the legacy CLI — the request is rejected
    with host_error and the CLI subprocess is never launched.
    """
    payload.setdefault("ok", False)
    payload.setdefault("transport", "plugin_transport_unavailable")
    payload.setdefault("error", "plugin transport requested but unavailable; fail-closed (no CLI fallback)")
    payload.setdefault(
        "host_error",
        "plugin transport unavailable; fail-closed: legacy CLI NOT called",
    )
    return _json_text(payload)


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
    if not _is_allowed_workdir(workdir):
        return _json_text({"ok": False, "error": f"workdir outside CODER_ROUTER_ALLOWED_ROOTS: {workdir}", "allowed_roots": [str(p) for p in _allowed_roots()]})

    try:
        model = _resolve_model(model_class)
    except ValueError as exc:
        return _json_text({"ok": False, "error": str(exc), "known_model_classes": sorted(MODEL_BY_CLASS)})

    # Transport selection (M3a, DEV-05): delegated to M1's resolve_transport().
    # - "plugin" -> plugin path; an unavailable bridge fails closed WITHOUT any
    #   legacy CLI call (never a silent switch).
    # - "cli"   -> legacy path (flagged transport="opencode_cli_legacy").
    # - "auto"  -> plugin iff bridge available, else legacy (documented auto).
    if not _LEGACY_ONLY:
        selected = resolve_transport()
        if selected == "plugin":
            req = build_coder_request(
                execution_id=f"coder-{uuid.uuid4().hex}",
                purpose="CODE_WORK",
                bounded_input={"task": task, "workdir": str(workdir)},
                expected_output={},
                worktree=str(workdir),
                timeout_ms=TIMEOUT_SECONDS * 1000,
                model_policy={"model_id": model},
            )
            result = execute_coder_semantic(req)
            return _json_text({
                "ok": result.get("runtime_status") == "COMPLETED",
                "transport": _TRANSPORT_PLUGIN,
                "semantic_result": result,
                "model": model,
                "workdir": str(workdir),
            })
    else:
        # M1 adapter unavailable. The ONLY transport available here is the
        # legacy CLI — but an EXPLICIT plugin selection must fail closed
        # (DEV-05): no silent CLI fallback for HARNESS_TRANSPORT=plugin.
        explicit = (os.environ.get("HARNESS_TRANSPORT") or "").strip().lower()
        if explicit == "plugin":
            return _transport_unavailable({
                "model": model,
                "workdir": str(workdir),
            })

    # Legacy CLI transport: allowed ONLY as an explicit (flagged) fallback.
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
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        await proc.wait()
        return _json_text({
            "ok": False,
            "error": f"opencode timed out after {TIMEOUT_SECONDS}s",
            "model": model,
            "transport": _TRANSPORT_LEGACY,
            "legacy_reason": _LEGACY_REASON,
        })
    except OSError as exc:
        return _json_text({
            "ok": False,
            "error": f"failed to start opencode: {exc}",
            "transport": _TRANSPORT_LEGACY,
            "legacy_reason": _LEGACY_REASON,
        })

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
        "transport": _TRANSPORT_LEGACY,
        "legacy_reason": _LEGACY_REASON,
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
