#!/usr/bin/env python3
"""Откат патча при регрессии (N12.5 revert).

При conformal-наборе {accept, reject} — откатывает дифф к предыдущей версии.
При {defer} — помечает open_honest.
"""

import json
import os
from pathlib import Path
from typing import Any

from sexpr import SExpr, format_sexpr


def revert_patch(
    patch_id: str,
    state: dict,
    text_versions: dict = None,
) -> dict:
    text_versions = text_versions or {}

    patches = state.get("patches", {})
    if patch_id not in patches:
        return {"status": "error", "reason": f"patch {patch_id} not found"}

    pinfo = patches[patch_id]
    current_status = pinfo.get("status", "unknown")

    if current_status == "open_honest":
        return {"status": "skipped", "reason": "already open_honest"}

    history = state.get("text_versions", {}).get("history", [])
    if len(history) >= 2:
        prev = history[-2]
        current = history[-1]
        state["text_versions"]["current"] = prev["path"]
        state["text_versions"]["history"] = history[:-1]
        reverted_to = prev["version"]
    else:
        reverted_to = "original"
        state["text_versions"]["current"] = state["text_versions"]["original"]

    update_patch_status(state, patch_id, "reverted",
        reverted_from=current_status,
        reverted_to=reverted_to,
        reverted_at=_now(),
    )

    return {
        "status": "reverted",
        "patch_id": patch_id,
        "from_status": current_status,
        "to_version": reverted_to,
    }


def mark_open_honest(
    patch_id: str,
    state: dict,
    reason: str = "conformal gate: defer",
) -> dict:
    patches = state.get("patches", {})
    if patch_id not in patches:
        return {"status": "error", "reason": f"patch {patch_id} not found"}

    update_patch_status(state, patch_id, "open_honest",
        open_honest_reason=reason,
        marked_at=_now(),
    )

    return {
        "status": "open_honest",
        "patch_id": patch_id,
        "reason": reason,
    }


def handle_regression_gate(
    gate: str,
    patches: dict,
    state: dict,
) -> dict:
    results = {}
    for pid in patches:
        if gate == "revert":
            results[pid] = revert_patch(pid, state)
        elif gate == "open_honest":
            results[pid] = mark_open_honest(pid, state, "conformal gate: defer")
        else:
            results[pid] = {"status": "accepted", "patch_id": pid}
    return results


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def update_patch_status(state: dict, patch_id: str, status: str, **kwargs) -> bool:
    if patch_id not in state.get("patches", {}):
        return False
    state["patches"][patch_id]["status"] = status
    for k, v in kwargs.items():
        state["patches"][patch_id][k] = v
    return True


if __name__ == "__main__":
    state = {
        "patches": {
            "p_12": {"group_index": 12, "status": "accepted"},
            "p_45": {"group_index": 45, "status": "accepted"},
        },
        "text_versions": {
            "original": "original.txt",
            "current": "patched_v2.txt",
            "history": [
                {"version": "v1", "path": "patched_v1.txt", "hash": "sha256:abc"},
                {"version": "v2", "path": "patched_v2.txt", "hash": "sha256:def"},
            ],
        },
    }

    r = revert_patch("p_12", state)
    print(f"revert: {r}")
    assert r["status"] == "reverted"
    assert state["text_versions"]["current"] == "patched_v1.txt"
    assert state["patches"]["p_12"]["status"] == "reverted"

    r2 = mark_open_honest("p_45", state, "conformal gate: defer")
    print(f"open_honest: {r2}")
    assert r2["status"] == "open_honest"
    assert state["patches"]["p_45"]["status"] == "open_honest"

    results = handle_regression_gate("revert", state["patches"], state)
    print(f"handle gate revert: {list(results.keys())}")

    print("OK")
