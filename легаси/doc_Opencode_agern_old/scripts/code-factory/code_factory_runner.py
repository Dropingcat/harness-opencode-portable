#!/usr/bin/env python3
"""Детерминированный runner фабрики кода."""

import json
import os
import sys
from datetime import datetime, timezone

STATES = ["PENDING", "RUNNING", "PASSED", "FAILED", "AMBIGUOUS", "BLOCKED", "DONE"]
DEFAULT_ITERATION_LIMIT = 3
DEFAULT_MAX_COST_RUB = 20.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_state(task_id: str, task_name: str, iteration_limit: int = DEFAULT_ITERATION_LIMIT,
                 max_cost_rub: float = DEFAULT_MAX_COST_RUB) -> dict:
    return {
        "_meta": {
            "version": 1,
            "task_id": task_id,
            "task_name": task_name,
            "created_at": _now(),
            "updated_at": _now(),
        },
        "cycle": {"state": "PENDING", "iteration": 0, "iteration_limit": iteration_limit, "stop_reason": None},
        "budget": {"spent_steps": 0, "spent_cost_rub": 0.0, "max_cost_rub": max_cost_rub},
        "verdicts": {},
        "audit": [],
    }


def load_state(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, path: str) -> str:
    state["_meta"]["updated_at"] = _now()
    content = json.dumps(state, ensure_ascii=False, indent=2)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=parent or ".", prefix=".factory_tmp_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return f"ok: wrote {os.path.getsize(path)} bytes to {path}"


def _audit(state: dict, step: str, decision: str) -> None:
    state["audit"].append({"step": step, "decision": decision, "ts": _now()})


def start(state: dict, path: str) -> str:
    if state["cycle"]["state"] != "PENDING":
        raise ValueError(f"start: expected PENDING, got {state['cycle']['state']}")
    state["cycle"]["state"] = "RUNNING"
    _audit(state, "start", "RUNNING")
    save_state(state, path)
    return "RUNNING"


def record_verdict(state: dict, module_id: str, verdict: str, path: str) -> str:
    if verdict not in ("APPROVE", "REQUEST_CHANGES", "REJECT", "AMBIGUOUS"):
        raise ValueError(f"unknown verdict: {verdict}")
    state["cycle"]["iteration"] += 1
    state["verdicts"].setdefault(module_id, []).append({"iteration": state["cycle"]["iteration"], "verdict": verdict})
    _audit(state, f"verdict_{module_id}", verdict)
    if verdict == "AMBIGUOUS":
        state["cycle"]["state"] = "AMBIGUOUS"
        state["cycle"]["stop_reason"] = "requires_user"
    elif verdict == "REJECT":
        state["cycle"]["state"] = "FAILED"
        state["cycle"]["stop_reason"] = "iteration_limit"
    elif verdict == "APPROVE":
        state["cycle"]["state"] = "PASSED"
        state["cycle"]["stop_reason"] = "approved"
    elif verdict == "REQUEST_CHANGES":
        if state["cycle"]["iteration"] >= state["cycle"]["iteration_limit"]:
            state["cycle"]["state"] = "FAILED"
            state["cycle"]["stop_reason"] = "iteration_limit"
        else:
            state["cycle"]["state"] = "RUNNING"
    save_state(state, path)
    return state["cycle"]["state"]


def add_budget(state: dict, steps: int, cost_rub: float, path: str) -> str:
    state["budget"]["spent_steps"] += steps
    state["budget"]["spent_cost_rub"] += cost_rub
    _audit(state, "budget", f"+{steps} steps, +{cost_rub} rub")
    if state["budget"]["spent_cost_rub"] >= state["budget"]["max_cost_rub"]:
        state["cycle"]["state"] = "BLOCKED"
        state["cycle"]["stop_reason"] = "budget_exceeded"
    save_state(state, path)
    return state["cycle"]["state"]


def auditor_block(state: dict, path: str) -> str:
    state["cycle"]["state"] = "BLOCKED"
    state["cycle"]["stop_reason"] = "auditor_block"
    _audit(state, "auditor", "BLOCKED")
    save_state(state, path)
    return "BLOCKED"


def finalize(state: dict, path: str) -> str:
    if state["cycle"]["state"] != "PASSED":
        raise ValueError(f"finalize: expected PASSED, got {state['cycle']['state']}")
    state["cycle"]["state"] = "DONE"
    _audit(state, "finalize", "DONE")
    save_state(state, path)
    return "DONE"


def validate(state: dict) -> list[str]:
    errors = []
    if state["_meta"].get("version") != 1:
        errors.append("unsupported state version")
    if not state["_meta"].get("task_id"):
        errors.append("missing task_id")
    if state["cycle"]["state"] not in STATES:
        errors.append(f"unknown state: {state['cycle']['state']}")
    if state["cycle"]["iteration"] < 0:
        errors.append("negative iteration")
    if state["budget"]["spent_cost_rub"] < 0:
        errors.append("negative budget")
    return errors


def resume(state: dict) -> dict:
    return {
        "task_id": state["_meta"]["task_id"],
        "state": state["cycle"]["state"],
        "iteration": state["cycle"]["iteration"],
        "iteration_limit": state["cycle"]["iteration_limit"],
        "stop_reason": state["cycle"]["stop_reason"],
        "budget_spent_rub": state["budget"]["spent_cost_rub"],
        "budget_max_rub": state["budget"]["max_cost_rub"],
        "verdicts": state["verdicts"],
        "last_audit": state["audit"][-1] if state["audit"] else None,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: code_factory_runner.py <command> [args]")
        sys.exit(1)
