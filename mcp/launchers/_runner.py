#!/usr/bin/env python3
"""Shared runner for MCP launcher servers — isolated run-directory delegation.

The run directory isolates generated artifacts, but this is not an OS sandbox. Filesystem
access must be constrained by the OpenCode host/runtime policy.
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

OPENCODE_BIN = os.environ.get("OPENCODE_BIN") or shutil.which("opencode") or str(Path.home() / ".opencode" / "bin" / "opencode")
RUNS_BASE = Path(os.environ.get("OPENCODE_RUNS_DIR", str(Path.home() / ".opencode" / "runs")))

# TD-D6/AG-D6 (issue #18): канонический токен legacy-транспорта. Все launchers поверх
# run_with_contract вызывают `opencode run --pure` напрямую — это явный fallback-путь,
# НЕ сертифицированный plugin semantic.execute (миграция — P5 по NEXT_PHASE_PLAN.md).
# Гейт фиксации: scripts/tools/check_legacy_transport.py, реестр: docs/LEGACY_TRANSPORT_REGISTRY.json.
TRANSPORT = "opencode_cli_legacy"


async def run_with_contract(
    launcher_name: str,
    task: str,
    contract: str,
    model: str = "ollama-cloud/glm-5.2",
    timeout: int = 300,
    read_only_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Run opencode run --pure with a contract prompt in an isolated run directory."""
    if not task.strip():
        return {"ok": False, "error": "task is required"}

    run_id = f"{int(time.time())}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    run_dir = RUNS_BASE / launcher_name / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write contract + task as the prompt
    full_prompt = (
        f"{contract}\n\n"
        f"---\n"
        f"RUN INFO:\n"
        f"  run_dir: {run_dir}\n"
        f"  Запиши результаты в {run_dir}/results.json\n\n"
        f"---\n"
        f"TASK:\n{task}\n"
    )
    prompt_file = run_dir / "contract.md"
    prompt_file.write_text(full_prompt, encoding="utf-8")

    # Write metadata
    meta = {
        "launcher": launcher_name,
        "model": model,
        "timeout": timeout,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "declared_read_only_paths": read_only_paths or [],
        "sandbox_enforced": False,
        # TD-D6: фиксация транспорта — meta.json обязан нести legacy-токен.
        "transport": TRANSPORT,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    cmd = [
        OPENCODE_BIN, "run", "--pure",
        "--model", model,
        "--dir", str(run_dir),
        full_prompt,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(run_dir),
            stdin=subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        await proc.wait()
        result = {
            "ok": False,
            "error": f"opencode timed out after {timeout}s",
            "run_dir": str(run_dir),
            "run_id": run_id,
            "transport": TRANSPORT,
        }
        (run_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
    except OSError as exc:
        result = {
            "ok": False,
            "error": f"failed to start opencode: {exc}",
            "run_dir": str(run_dir),
            "run_id": run_id,
            "transport": TRANSPORT,
        }
        (run_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    result = {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "launcher": launcher_name,
        "model": model,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "stdout": stdout,
        "stderr": stderr,
        # TD-D6: явная фиксация legacy-транспорта в результате tool-call.
        "transport": TRANSPORT,
        "legacy_reason": "semantic.execute plugin path not live-certified (P5 migration)",
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result