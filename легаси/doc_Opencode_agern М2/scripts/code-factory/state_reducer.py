#!/usr/bin/env python3
"""Pure event reducer for the code factory.

Agents emit typed evidence. Only this reducer derives authoritative task state.
The event log is append-only and hash chained so a saved run can be replayed.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "config" / "factory_gate_policy.json"
TERMINAL = {"DONE", "FAILED", "BLOCKED", "AMBIGUOUS"}


def canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def event_hash(event_without_hash: dict) -> str:
    return hashlib.sha256(canonical(event_without_hash).encode("utf-8")).hexdigest()


def load_policy(path: str | Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_POLICY_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def verify_event_chain(events: list[dict]) -> list[str]:
    errors: list[str] = []
    prev = None
    for idx, ev in enumerate(events, start=1):
        if ev.get("seq") != idx:
            errors.append(f"event[{idx}]: seq must be {idx}, got {ev.get('seq')!r}")
        if ev.get("prev_hash") != prev:
            errors.append(f"event[{idx}]: prev_hash mismatch")
        supplied = ev.get("event_hash")
        body = {k: v for k, v in ev.items() if k != "event_hash"}
        expected = event_hash(body)
        if supplied != expected:
            errors.append(f"event[{idx}]: event_hash mismatch")
        prev = supplied
    return errors


def _blank_projection() -> dict:
    return {
        "task": {},
        "cycle": {"state": "PENDING", "attempt": 0, "iteration": 0, "attempt_limit": 0, "iteration_limit": 0, "stop_reason": None},
        "budget": {"spent_steps": 0, "spent_cost_rub": 0.0, "max_cost_rub": 0.0},
        "attempts": [],
        "evidence": [],
        "gate_set": {},
        "required_gates": [],
        "verdicts": {},
        "audit": [],
    }


def _gate_outcome(policy: dict, agent_type: str, payload: dict) -> str | None:
    sem = policy.get("gate_semantics", {}).get(agent_type)
    if not sem:
        return None
    value = payload.get("verdict") if agent_type in {"reviewer", "auditor"} else payload.get("result")
    for outcome, values in (("PASS", sem.get("pass", [])), ("RETRY", sem.get("retry", [])), ("FAIL", sem.get("terminal_fail", [])), ("BLOCK", sem.get("block", []))):
        if value in values:
            return outcome
    return None


def _current_attempt(p: dict) -> dict | None:
    return p["attempts"][-1] if p["attempts"] else None


def _refresh_gate_state(p: dict, policy: dict) -> None:
    attempt = _current_attempt(p)
    if not attempt:
        return
    gates = attempt["gates"]
    p["gate_set"] = deepcopy(gates)
    outcomes = list(gates.values())
    if "BLOCK" in outcomes:
        p["cycle"]["state"] = "BLOCKED"
        p["cycle"]["stop_reason"] = "gate_blocked"
        attempt["status"] = "BLOCKED"
    elif "FAIL" in outcomes:
        p["cycle"]["state"] = "FAILED"
        p["cycle"]["stop_reason"] = "gate_rejected"
        attempt["status"] = "FAILED"
    elif "RETRY" in outcomes:
        attempt["status"] = "REWORK"
        if attempt["attempt_no"] >= p["cycle"]["attempt_limit"]:
            p["cycle"]["state"] = "FAILED"
            p["cycle"]["stop_reason"] = "attempt_limit"
        else:
            p["cycle"]["state"] = "REWORK"
            p["cycle"]["stop_reason"] = "targeted_rework"
    elif all(gates.get(g) == "PASS" for g in p["required_gates"]):
        p["cycle"]["state"] = "PASSED"
        p["cycle"]["stop_reason"] = "all_required_gates_passed"
        attempt["status"] = "PASSED"
    else:
        p["cycle"]["state"] = "RUNNING"
        pending = [g for g in p["required_gates"] if gates.get(g) != "PASS"]
        p["cycle"]["stop_reason"] = "awaiting:" + ",".join(pending) if pending else None
        attempt["status"] = "RUNNING"


def reduce_events(events: list[dict], policy: dict | None = None) -> dict:
    policy = policy or load_policy()
    effective_policy = policy
    p = _blank_projection()
    for ev in events:
        typ = ev["type"]
        payload = ev.get("payload", {})
        p["audit"].append({"seq": ev["seq"], "event_id": ev["event_id"], "type": typ, "actor": ev.get("actor"), "ts": ev.get("ts")})
        if typ == "TASK_CREATED":
            if isinstance(payload.get("gate_policy"), dict):
                effective_policy = payload["gate_policy"]
            p["task"] = deepcopy(payload)
            lim = int(payload["attempt_limit"])
            p["cycle"].update({"state": "PENDING", "attempt_limit": lim, "iteration_limit": lim})
            p["budget"]["max_cost_rub"] = float(payload["max_cost_rub"])
            p["required_gates"] = list(payload.get("required_gates") or effective_policy["required_gates"])
        elif typ == "ATTEMPT_STARTED":
            no = int(payload["attempt_no"])
            gates = {g: "PENDING" for g in p["required_gates"]}
            p["attempts"].append({"attempt_id": payload["attempt_id"], "attempt_no": no, "status": "RUNNING", "gates": gates, "evidence_ids": [], "started_at": ev.get("ts")})
            p["cycle"].update({"state": "RUNNING", "attempt": no, "iteration": no - 1, "stop_reason": None})
            p["gate_set"] = deepcopy(gates)
        elif typ == "AGENT_EVIDENCE":
            attempt = _current_attempt(p)
            evidence = deepcopy(payload)
            evidence.update({"event_id": ev["event_id"], "seq": ev["seq"], "attempt_id": ev.get("attempt_id"), "actor": ev.get("actor")})
            p["evidence"].append(evidence)
            if attempt and ev.get("attempt_id") == attempt["attempt_id"]:
                attempt["evidence_ids"].append(payload["evidence_id"])
                agent = payload["agent_type"]
                outcome = _gate_outcome(effective_policy, agent, payload["data"])
                if agent in attempt["gates"] and outcome:
                    attempt["gates"][agent] = outcome
                module = payload.get("module", "default")
                p["verdicts"].setdefault(f"{agent}:{module}", []).append({"attempt": attempt["attempt_no"], "outcome": outcome, "data": deepcopy(payload["data"])})
                _refresh_gate_state(p, effective_policy)
        elif typ == "BUDGET_SPENT":
            p["budget"]["spent_steps"] += int(payload.get("steps", 0))
            p["budget"]["spent_cost_rub"] += float(payload.get("cost_rub", 0.0))
            if p["budget"]["spent_cost_rub"] >= p["budget"]["max_cost_rub"]:
                p["cycle"].update({"state": "BLOCKED", "stop_reason": "budget_exceeded"})
        elif typ == "MANUAL_BLOCK":
            p["cycle"].update({"state": "BLOCKED", "stop_reason": payload.get("reason", "manual_block")})
        elif typ == "AMBIGUITY_RECORDED":
            p["cycle"].update({"state": "AMBIGUOUS", "stop_reason": payload.get("reason", "requires_user")})
        elif typ == "TASK_FINALIZED":
            p["cycle"].update({"state": "DONE", "stop_reason": "finalized"})
    return p
