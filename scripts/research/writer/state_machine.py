#!/usr/bin/env python3
"""Детерминированный движок фаз писателя.

Управляет жизненным циклом Writer Cell: переходы фаз, чекпоинты,
восстановление после обрыва, валидация стейта.

НЕ использует LLM — только детерминированная логика.
"""

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PHASES = [
    "AWAITING_ANSWERS",
    "PLANNING",
    "WRITING",
    "WAVE_A",
    "REVISING",
    "WAVE_B",
    "CONSISTENCY",
    "REVERIFY",
    "REGRESSION",
    "DONE",
]

TRANSITIONS: dict[str, str] = {
    "AWAITING_ANSWERS": "PLANNING",
    "PLANNING": "WRITING",
    "WRITING": "WAVE_A",
    "WAVE_A": "REVISING",
    "REVISING": "WAVE_B",
    "WAVE_B": "CONSISTENCY",
    "CONSISTENCY": "REVERIFY",
    "REVERIFY": "REGRESSION",
    "REGRESSION": "DONE",
}

FINAL_PHASES = {"DONE", "FINAL"}

EMPTY_STATE: dict[str, Any] = {
    "_meta": {
        "version": 1,
        "discussion_id": "",
        "document": "",
        "created_at": "",
        "updated_at": "",
        "profile": "resercher",
    },
    "cycle": {
        "iteration": 0,
        "phase": "AWAITING_ANSWERS",
        "total_iterations_max": 3,
        "stop_reason": None,
    },
    "text_versions": {
        "original": "",
        "current": "",
        "history": [],
    },
    "questions": {},
    "patches": {},
    "verdicts_flow": {},
    "regression": {},
    "budget": {
        "spent_tokens": 0,
        "spent_cost_rub": 0.0,
        "max_cost_rub": 20.0,
        "per_iteration": {},
    },
    "checkpoints": [],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def create_state(
    discussion_id: str,
    document: str,
    original_text: str,
    max_iterations: int = 3,
    max_cost_rub: float = 20.0,
) -> dict:
    state = copy.deepcopy(EMPTY_STATE)
    now = _now()
    state["_meta"]["discussion_id"] = discussion_id
    state["_meta"]["document"] = document
    state["_meta"]["created_at"] = now
    state["_meta"]["updated_at"] = now
    state["text_versions"]["original"] = original_text
    state["text_versions"]["current"] = original_text
    state["cycle"]["total_iterations_max"] = max_iterations
    state["budget"]["max_cost_rub"] = max_cost_rub
    state["checkpoints"].append({"phase": "AWAITING_ANSWERS", "at": now})
    return state


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

    fd, tmp = tempfile.mkstemp(dir=parent or ".", prefix=".writer_state_tmp_", suffix=".tmp")
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


def advance_phase(state: dict, state_path: str) -> str:
    current = state["cycle"]["phase"]
    if current in FINAL_PHASES:
        raise ValueError(f"Already in final phase: {current}")
    if current not in TRANSITIONS:
        raise ValueError(f"Unknown phase: {current}")
    next_phase = TRANSITIONS[current]
    state["cycle"]["phase"] = next_phase
    state["checkpoints"].append({"phase": next_phase, "at": _now()})
    save_state(state, state_path)
    return next_phase


def start_new_iteration(state: dict, state_path: str) -> str:
    state["cycle"]["iteration"] += 1
    state["cycle"]["phase"] = "AWAITING_ANSWERS"
    state["cycle"]["stop_reason"] = None
    state["checkpoints"].append(
        {"phase": "AWAITING_ANSWERS", "at": _now(), "iteration": state["cycle"]["iteration"]}
    )
    save_state(state, state_path)
    return "AWAITING_ANSWERS"


def finalize(state: dict, state_path: str, reason: str = "all_criteria_met") -> str:
    state["cycle"]["phase"] = "FINAL"
    state["cycle"]["stop_reason"] = reason
    state["checkpoints"].append({"phase": "FINAL", "at": _now(), "reason": reason})
    save_state(state, state_path)
    return "FINAL"


def add_question(state: dict, group_index: int, role: str, text: str, n: int = 1) -> str:
    qid = f"q_{group_index}_{n}"
    state["questions"][qid] = {
        "group_index": group_index,
        "role": role,
        "text": text,
        "asked_in_iteration": state["cycle"]["iteration"],
        "answer": None,
        "answered_at": None,
        "used_in_patch": None,
    }
    return qid


def record_answer(state: dict, qid: str, answer: str) -> bool:
    if qid not in state["questions"]:
        return False
    state["questions"][qid]["answer"] = answer
    state["questions"][qid]["answered_at"] = _now()
    return True


def pending_questions(state: dict) -> list[dict]:
    return [
        {"id": qid, **q}
        for qid, q in state["questions"].items()
        if q["answer"] is None
    ]


def answered_questions(state: dict) -> list[dict]:
    return [
        {"id": qid, **q}
        for qid, q in state["questions"].items()
        if q["answer"] is not None
    ]


def add_patch(state: dict, patch_id: str, group_index: int, issue_types: list[str]) -> str:
    state["patches"][patch_id] = {
        "group_index": group_index,
        "iteration": state["cycle"]["iteration"],
        "status": "created",
        "issue_types": issue_types,
        "before_hash": None,
        "after_hash": None,
        "justification": None,
        "wave_A": None,
        "wave_B": None,
        "consistency": None,
        "reverify": None,
        "open_honest_reason": None,
    }
    return patch_id


def update_patch_status(state: dict, patch_id: str, status: str, **kwargs) -> bool:
    if patch_id not in state["patches"]:
        return False
    state["patches"][patch_id]["status"] = status
    for k, v in kwargs.items():
        state["patches"][patch_id][k] = v
    return True


def record_verdict_flow(state: dict, group_index: int, verdict: str) -> None:
    gi = str(group_index)
    if gi not in state["verdicts_flow"]:
        state["verdicts_flow"][gi] = []
    state["verdicts_flow"][gi].append(
        {"iteration": state["cycle"]["iteration"], "verdict": verdict}
    )


def record_regression(
    state: dict,
    ks_p_value: float,
    semantic_agreement: float,
    conformal_set: list[str],
    regress_count: int,
    improve_count: int,
    residual_count: int,
) -> None:
    state["regression"][f"iteration_{state['cycle']['iteration']}"] = {
        "ks_p_value": ks_p_value,
        "semantic_agreement": semantic_agreement,
        "conformal_set": conformal_set,
        "regress_count": regress_count,
        "improve_count": improve_count,
        "residual_count": residual_count,
    }


def add_budget(state: dict, tokens: int, cost_rub: float) -> None:
    state["budget"]["spent_tokens"] += tokens
    state["budget"]["spent_cost_rub"] += cost_rub
    it = str(state["cycle"]["iteration"])
    if it not in state["budget"]["per_iteration"]:
        state["budget"]["per_iteration"][it] = {"tokens": 0, "cost_rub": 0.0}
    state["budget"]["per_iteration"][it]["tokens"] += tokens
    state["budget"]["per_iteration"][it]["cost_rub"] += cost_rub


def budget_exceeded(state: dict) -> bool:
    return state["budget"]["spent_cost_rub"] >= state["budget"]["max_cost_rub"]


def iterations_exhausted(state: dict) -> bool:
    return state["cycle"]["iteration"] >= state["cycle"]["total_iterations_max"]


def add_text_version(state: dict, version: str, path: str, file_hash: str) -> None:
    state["text_versions"]["history"].append(
        {"version": version, "path": path, "hash": file_hash}
    )
    state["text_versions"]["current"] = path


def resume(state: dict) -> dict:
    return {
        "discussion_id": state["_meta"]["discussion_id"],
        "document": state["_meta"]["document"],
        "phase": state["cycle"]["phase"],
        "iteration": state["cycle"]["iteration"],
        "pending_questions": pending_questions(state),
        "answered_questions": answered_questions(state),
        "budget_spent_rub": state["budget"]["spent_cost_rub"],
        "budget_max_rub": state["budget"]["max_cost_rub"],
        "patches_count": len(state["patches"]),
        "patches_by_status": _count_by_status(state),
        "last_checkpoint": state["checkpoints"][-1] if state["checkpoints"] else None,
    }


def _count_by_status(state: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in state["patches"].values():
        s = p.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return counts


def validate(state: dict) -> list[str]:
    errors = []
    if state["_meta"].get("version") != 1:
        errors.append("unsupported state version")
    if not state["_meta"].get("discussion_id"):
        errors.append("missing discussion_id")
    if not state["_meta"].get("document"):
        errors.append("missing document")
    phase = state["cycle"]["phase"]
    if phase not in PHASES and phase not in FINAL_PHASES:
        errors.append(f"unknown phase: {phase}")
    if state["cycle"]["iteration"] < 0:
        errors.append("negative iteration")
    if state["budget"]["spent_cost_rub"] < 0:
        errors.append("negative budget")
    for qid, q in state["questions"].items():
        if not qid.startswith("q_"):
            errors.append(f"invalid question id: {qid}")
        if "group_index" not in q:
            errors.append(f"question {qid} missing group_index")
    for pid, p in state["patches"].items():
        if "group_index" not in p:
            errors.append(f"patch {pid} missing group_index")
        if "status" not in p:
            errors.append(f"patch {pid} missing status")
    return errors


def is_phase_completed(state: dict, phase: str) -> bool:
    for cp in state["checkpoints"]:
        if cp["phase"] == phase:
            return True
    return False


def recover(state: dict) -> dict:
    phase = state["cycle"]["phase"]
    iteration = state["cycle"]["iteration"]
    completed = is_phase_completed(state, phase)
    return {
        "phase": phase,
        "iteration": iteration,
        "phase_completed": completed,
        "action": "continue" if completed else f"restart_{phase.lower()}",
        "pending_questions": pending_questions(state),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: state_machine.py <command> [args]")
        print("commands: create, advance, resume, validate, recover")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "create":
        state = create_state(
            discussion_id=sys.argv[2] if len(sys.argv) > 2 else "test-discussion",
            document=sys.argv[3] if len(sys.argv) > 3 else "test.pdf",
            original_text=sys.argv[4] if len(sys.argv) > 4 else "test.txt",
        )
        path = sys.argv[5] if len(sys.argv) > 5 else "/tmp/writer_state_test.json"
        result = save_state(state, path)
        print(result)

    elif cmd == "advance":
        path = sys.argv[2]
        state = load_state(path)
        next_phase = advance_phase(state, path)
        print(f"advanced to {next_phase}")

    elif cmd == "resume":
        path = sys.argv[2]
        state = load_state(path)
        info = resume(state)
        print(json.dumps(info, ensure_ascii=False, indent=2))

    elif cmd == "validate":
        path = sys.argv[2]
        state = load_state(path)
        errors = validate(state)
        if errors:
            print("ERRORS:")
            for e in errors:
                print(f"  - {e}")
        else:
            print("valid")

    elif cmd == "recover":
        path = sys.argv[2]
        state = load_state(path)
        info = recover(state)
        print(json.dumps(info, ensure_ascii=False, indent=2))
