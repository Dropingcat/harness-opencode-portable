#!/usr/bin/env python3
"""Read-only development tracker consistency gate; not runtime certification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
HISTORY_HASH = "0f5d96969a23e1766dc748f7f833d220e7f85f53cffe8bd5e07b7a201b349647"
ORIGINAL_HASH = "9e7303c2801a7cac72fab5718c6eed3b338352c87add7f31a283ae78a04be199"
STATUSES = ("done", "in_progress", "not_started")
DIMENSIONS = ("implemented", "connected", "host_tested", "certified")
LEVELS = {"PASS", "PARTIAL", "NOT_TESTED", "BLOCKED"}
HISTORICAL_COMPLETION_SCOPE = (
    "OpenCode 1.18.30 only; historical DONE, not 2.0.29 certification"
)


def check(data: dict) -> list[str]:
    errors = []
    # Optional negative marker only: this reconciliation has no semantic acceptance.
    if "semantic_ready" in data and data["semantic_ready"] is not False:
        errors.append("unsupported semantic_ready claim; only false is permitted")
    records = data.get("dev_items", []) + data.get("workstreams", [])
    ids = [item.get("id") for item in records]
    if len(set(ids)) != len(ids):
        errors.append("duplicate IDs")
    expected = {}
    for group, prefix in (("dev_items", "dev"), ("workstreams", "workstream")):
        for status in STATUSES:
            expected[f"{prefix}_{status}"] = sum(item.get("status") == status for item in data.get(group, []))
    if data.get("counts") != expected:
        errors.append("counts differ from records")
    refs = list(data.get("critical_path", []))
    for item in records:
        if item.get("status") not in STATUSES:
            errors.append(f"invalid status: {item.get('id')}")
        if item.get("id") in ("DEV-03", "DEV-04", "WS-57A"):
            if item.get("completion_scope") != HISTORICAL_COMPLETION_SCOPE:
                errors.append(f"missing/changed historical completion_scope: {item.get('id')}")
        refs.extend(item.get("internal_refs", []))
        # DEV/WS prose mentions are internal; TD and file/source refs are external.
        refs.extend(re.findall(r"\b(?:DEV-\d+|WS-\d+[A-Z]?)\b", " ".join(
            str(item.get(field, "")) for field in ("evidence", "next_gate"))))
        readiness = item.get("current_readiness")
        if readiness is not None:
            if (readiness.get("host_version") != "2.0.29" or
                    any(readiness.get(key) not in LEVELS for key in DIMENSIONS) or
                    not readiness.get("scope") or not readiness.get("external_sources")):
                errors.append(f"invalid readiness: {item.get('id')}")
            # Certification cannot outrun implementation, connection or host tests,
            # even when production_ready is absent or explicitly false.
            if readiness.get("certified") == "PASS" and any(
                    readiness.get(key) != "PASS" for key in DIMENSIONS[:-1]):
                errors.append(f"incompatible certified readiness: {item.get('id')}")
        if item.get("production_ready") is True:
            if not readiness or any(readiness.get(key) != "PASS" for key in DIMENSIONS):
                errors.append(f"incompatible V2 production_ready: {item.get('id')}")
    for ref in refs:
        if ref not in ids:
            errors.append(f"dangling internal reference: {ref}")
    for required in ("DEV-03", "DEV-04", "DEV-05", "DEV-08", "DEV-09", "WS-58A"):
        item = next((item for item in records if item.get("id") == required), {})
        if not item.get("current_readiness"):
            errors.append(f"missing current readiness: {required}")
    history = data.get("history", [])
    snapshot = history[0].get("snapshot") if history else None
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                                       separators=(",", ":")).encode("utf-8")).hexdigest()
    if (digest != HISTORY_HASH or not history or
            history[0].get("snapshot_sha256") != HISTORY_HASH or
            history[0].get("original_sha256") != ORIGINAL_HASH):
        errors.append("missing or altered historical evidence/history hash")
    if isinstance(snapshot, dict):
        by_id = {item.get("id"): item for item in records}
        for old in snapshot.get("dev_items", []) + snapshot.get("workstreams", []):
            current = by_id.get(old["id"], {})
            if any(current.get(key) != old[key] for key in ("id", "title", "result") if key in old):
                errors.append(f"missing/changed historical item: {old['id']}")
    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config/development_tracker.json"
    try:
        errors = check(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors = [f"invalid tracker: {exc}"]
    print(json.dumps({"result": "FAIL" if errors else "PASS", "errors": errors}, ensure_ascii=False))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
