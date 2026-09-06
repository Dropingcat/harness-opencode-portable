#!/usr/bin/env python3
"""Event-sourced runtime for the code factory.

No reviewer/tester/auditor is allowed to mutate global task state. Agent outputs
are stored as typed evidence events; state_reducer is the sole state authority.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from state_reducer import canonical, event_hash, load_policy, reduce_events, verify_event_chain

DEFAULT_ITERATION_LIMIT = 3
DEFAULT_MAX_COST_RUB = 20.0
STATES = ["PENDING", "RUNNING", "REWORK", "PASSED", "FAILED", "AMBIGUOUS", "BLOCKED", "DONE"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append_event(state: dict, typ: str, actor: str, payload: dict, attempt_id: str | None = None) -> dict:
    events = state.setdefault("events", [])
    ev = {
        "seq": len(events) + 1,
        "event_id": str(uuid.uuid4()),
        "type": typ,
        "actor": actor,
        "attempt_id": attempt_id,
        "payload": payload,
        "ts": _now(),
        "prev_hash": events[-1]["event_hash"] if events else None,
    }
    ev["event_hash"] = event_hash(ev)
    events.append(ev)
    return ev


def _materialize(state: dict) -> dict:
    projection = reduce_events(state["events"], load_policy())
    state["projection"] = projection
    # Compatibility views for existing readers. They are generated, never authoritative.
    state["cycle"] = projection["cycle"]
    state["budget"] = projection["budget"]
    state["attempts"] = projection["attempts"]
    state["evidence"] = projection["evidence"]
    state["verdicts"] = projection["verdicts"]
    state["audit"] = projection["audit"]
    state["_meta"]["updated_at"] = _now()
    return state


def create_state(task_id: str, task_name: str, iteration_limit: int = DEFAULT_ITERATION_LIMIT,
                 max_cost_rub: float = DEFAULT_MAX_COST_RUB, required_gates: list[str] | None = None) -> dict:
    policy = load_policy()
    if iteration_limit < 1:
        raise ValueError("iteration_limit must be >= 1")
    gates = required_gates or list(policy["required_gates"])
    policy_hash = __import__("hashlib").sha256(canonical(policy).encode("utf-8")).hexdigest()
    state = {"_meta": {"version": 2, "format": "event-sourced", "created_at": _now(), "updated_at": _now()}, "events": []}
    _append_event(state, "TASK_CREATED", "controller", {
        "task_id": task_id, "task_name": task_name, "attempt_limit": iteration_limit,
        "max_cost_rub": max_cost_rub, "required_gates": gates,
        "gate_policy_hash": policy_hash, "gate_policy": policy,
    })
    return _materialize(state)


def load_state(path: str) -> dict:
    state = json.loads(Path(path).read_text(encoding="utf-8"))
    if state.get("_meta", {}).get("version") != 2:
        raise ValueError("legacy factory state is not writable by stage-2 runtime; initialize a new run")
    errors = verify_event_chain(state.get("events", []))
    if errors:
        raise ValueError("event log integrity failure: " + "; ".join(errors))
    return _materialize(state)


def save_state(state: dict, path: str) -> str:
    _materialize(state)
    content = json.dumps(state, ensure_ascii=False, indent=2)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".factory_tmp_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise
    return f"ok: wrote {os.path.getsize(path)} bytes to {path}"


def start(state: dict, path: str) -> str:
    if state["cycle"]["state"] != "PENDING":
        raise ValueError(f"start: expected PENDING, got {state['cycle']['state']}")
    _append_event(state, "ATTEMPT_STARTED", "controller", {"attempt_id": "attempt-1", "attempt_no": 1}, "attempt-1")
    save_state(state, path)
    return state["cycle"]["state"]


def _begin_retry_if_needed(state: dict) -> None:
    _materialize(state)
    if state["cycle"]["state"] != "REWORK":
        return
    next_no = state["cycle"]["attempt"] + 1
    if next_no <= state["cycle"]["attempt_limit"]:
        aid = f"attempt-{next_no}"
        _append_event(state, "ATTEMPT_STARTED", "state_reducer", {"attempt_id": aid, "attempt_no": next_no}, aid)
        _materialize(state)


def submit_evidence(state: dict, agent_type: str, module: str, data: dict, path: str) -> str:
    if state["cycle"]["state"] in {"DONE", "FAILED", "BLOCKED", "AMBIGUOUS"}:
        raise ValueError(f"cannot submit evidence in terminal state {state['cycle']['state']}")
    attempt_id = state["attempts"][-1]["attempt_id"]
    payload = {
        "evidence_id": str(uuid.uuid4()), "agent_type": agent_type, "module": module,
        "data": data,
    }
    _append_event(state, "AGENT_EVIDENCE", agent_type, payload, attempt_id)
    _materialize(state)
    _begin_retry_if_needed(state)
    save_state(state, path)
    return state["cycle"]["state"]


def record_verdict(state: dict, module_id: str, verdict: str, path: str) -> str:
    """Compatibility facade. Reviewer verdict is evidence, never a direct state write."""
    return submit_evidence(state, "reviewer", module_id, {"verdict": verdict}, path)


def add_budget(state: dict, steps: int, cost_rub: float, path: str) -> str:
    _append_event(state, "BUDGET_SPENT", "controller", {"steps": steps, "cost_rub": cost_rub}, state["attempts"][-1]["attempt_id"] if state["attempts"] else None)
    save_state(state, path)
    return state["cycle"]["state"]


def auditor_block(state: dict, path: str) -> str:
    _append_event(state, "MANUAL_BLOCK", "controller", {"reason": "auditor_block"}, state["attempts"][-1]["attempt_id"] if state["attempts"] else None)
    save_state(state, path)
    return state["cycle"]["state"]


def finalize(state: dict, path: str) -> str:
    if state["cycle"]["state"] != "PASSED":
        raise ValueError(f"finalize: expected PASSED, got {state['cycle']['state']}")
    _append_event(state, "TASK_FINALIZED", "controller", {})
    save_state(state, path)
    return state["cycle"]["state"]


def validate(state: dict) -> list[str]:
    errors = []
    if state.get("_meta", {}).get("version") != 2: errors.append("unsupported state version")
    errors.extend(verify_event_chain(state.get("events", [])))
    try:
        p = reduce_events(state.get("events", []), load_policy())
        if p["cycle"]["state"] not in STATES: errors.append(f"unknown state: {p['cycle']['state']}")
    except Exception as e:
        errors.append(f"reducer failure: {e}")
    return errors


def replay(state: dict) -> dict:
    errors = verify_event_chain(state.get("events", []))
    if errors: raise ValueError("event log integrity failure: " + "; ".join(errors))
    return reduce_events(state["events"], load_policy())


def resume(state: dict) -> dict:
    p = replay(state)
    return {
        "task_id": p["task"].get("task_id"), "state": p["cycle"]["state"],
        "attempt": p["cycle"]["attempt"], "iteration": p["cycle"]["iteration"],
        "attempt_limit": p["cycle"]["attempt_limit"], "iteration_limit": p["cycle"]["iteration_limit"],
        "stop_reason": p["cycle"]["stop_reason"], "required_gates": p["required_gates"],
        "gate_set": p["gate_set"], "budget_spent_rub": p["budget"]["spent_cost_rub"],
        "budget_max_rub": p["budget"]["max_cost_rub"], "event_count": len(state["events"]),
        "gate_policy_hash": p["task"].get("gate_policy_hash"),
        "last_event_hash": state["events"][-1]["event_hash"] if state["events"] else None,
    }
