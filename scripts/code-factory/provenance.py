#!/usr/bin/env python3
"""Artifact provenance primitives for the code-factory runtime.

The event log is authoritative. Files are referenced by SHA-256, never trusted by
path alone. Untrusted artifacts are inadmissible until a guard PASS exists, or a
sanitized derivative with its own hash is registered and guarded.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "config" / "artifact_provenance_policy.json"


def canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_bytes(canonical(obj).encode("utf-8"))


def load_policy(path: str | Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_POLICY_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def policy_hash(policy: dict | None = None) -> str:
    return sha256_json(policy or load_policy())


def origin_spec(origin: str, policy: dict | None = None) -> dict:
    p = policy or load_policy()
    try:
        return p["origins"][origin]
    except KeyError as exc:
        raise ValueError(f"unknown artifact origin: {origin}") from exc


def artifact_from_file(artifact_id: str, path: str | Path, *, origin: str,
                       tool_id: str | None = None, source_ref: str | None = None,
                       media_type: str | None = None, metadata: dict | None = None,
                       source_artifact_id: str | None = None, policy: dict | None = None) -> dict:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"artifact file not found: {path}")
    spec = origin_spec(origin, policy)
    return {
        "artifact_id": artifact_id,
        "origin": origin,
        "trust": spec["trust"],
        "guard_required": bool(spec.get("guard_required")),
        "tool_id": tool_id,
        "source_ref": source_ref,
        "source_artifact_id": source_artifact_id,
        "path_hint": str(p),
        "content_hash": sha256_file(p),
        "size_bytes": p.stat().st_size,
        "media_type": media_type or "application/octet-stream",
        "metadata": metadata or {},
    }


def artifact_admissibility(record: dict, guards: list[dict], policy: dict | None = None) -> tuple[bool, str]:
    p = policy or load_policy()
    if not record:
        return False, "artifact_not_registered"
    if not record.get("guard_required"):
        return True, "internal_origin"
    matching = [g for g in guards if g.get("artifact_id") == record.get("artifact_id")]
    if not matching:
        return False, "guard_missing"
    verdict = matching[-1].get("verdict")
    if verdict not in p.get("accepted_guard_verdicts", ["PASS"]):
        return False, f"guard_{str(verdict).lower()}"
    return True, "guard_passed"


def verify_artifact_file(record: dict, path: str | Path | None = None) -> tuple[bool, str]:
    target = Path(path or record.get("path_hint", ""))
    if not target.exists() or not target.is_file():
        return False, "file_missing"
    actual = sha256_file(target)
    if actual != record.get("content_hash"):
        return False, "content_hash_mismatch"
    return True, "hash_match"
