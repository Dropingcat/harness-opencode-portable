"""Deterministically collect L2 task memory from an audit snapshot JSON."""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_POLICY = {
    "bindings": {
        "task_id_paths": ["task.task_id", "task.id", "task_id"],
        "task_title_paths": ["task.title", "task.name", "title"],
        "snapshot_id_paths": ["snapshot_id", "audit_id", "task.snapshot_id", "run.graph_snapshot_id"],
        "claim_list_paths": ["claims"],
        "audit_list_paths": ["audits", "audit_entries", "validation_events"],
    },
    "rules": {
        "accepted_claim_id_keys": ["claim_id", "id"],
        "accepted_audit_reason_code_keys": ["reason_code", "code", "reason_codes"],
        "accepted_audit_status_keys": ["status", "result"],
    },
}


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _get_path(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _first_present(obj: Dict[str, Any], paths: Iterable[str]) -> Any:
    for path in paths:
        value = _get_path(obj, path)
        if value is not None:
            return value
    return None


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def _claim_id(claim: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for key in keys:
        value = claim.get(key)
        if isinstance(value, (str, int)):
            return str(value)
    return None


def _audit_reason_codes(audit: Dict[str, Any], keys: List[str]) -> List[str]:
    for key in keys:
        value = audit.get(key)
        if isinstance(value, str) and value:
            return [value]
        if isinstance(value, list):
            return [str(v) for v in value if isinstance(v, (str, int)) and str(v)]
    return []


def _audit_status(audit: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for key in keys:
        value = audit.get(key)
        if isinstance(value, (str, int)):
            return str(value)
    return None


def _evidence_from_claim(claim: Dict[str, Any]) -> List[str]:
    refs = claim.get("evidence_refs")
    if isinstance(refs, list):
        return [str(v) for v in refs if isinstance(v, (str, int)) and str(v)]
    return []


def _claim_reason_codes(claim: Dict[str, Any]) -> List[str]:
    reasons = claim.get("reasons")
    out: List[str] = []
    if isinstance(reasons, list):
        for item in reasons:
            if isinstance(item, dict) and isinstance(item.get("code"), str) and item["code"]:
                out.append(item["code"])
    return sorted(set(out))


def collect_l2(snapshot: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    bindings = policy.get("bindings", {})
    rules = policy.get("rules", {})
    task_id = _first_present(snapshot, bindings.get("task_id_paths", []))
    task_title = _first_present(snapshot, bindings.get("task_title_paths", []))
    snapshot_id = _first_present(snapshot, bindings.get("snapshot_id_paths", []))
    claims = _as_list(_first_present(snapshot, bindings.get("claim_list_paths", [])))
    audits = _as_list(_first_present(snapshot, bindings.get("audit_list_paths", [])))
    claim_id_keys = list(rules.get("accepted_claim_id_keys", []))
    reason_code_keys = list(rules.get("accepted_audit_reason_code_keys", []))
    status_keys = list(rules.get("accepted_audit_status_keys", []))

    claim_refs: List[str] = []
    issue_counts: Dict[str, int] = {}
    candidate_lessons: List[Dict[str, Any]] = []

    for claim in claims:
        if not isinstance(claim, dict):
            continue
        cid = _claim_id(claim, claim_id_keys)
        if cid:
            claim_refs.append(cid)
            reason_codes = _claim_reason_codes(claim)
            evidence_refs = _evidence_from_claim(claim)
            if reason_codes and evidence_refs:
                candidate_lessons.append(
                    {
                        "lesson_text": claim.get("proposition") or claim.get("text"),
                        "reason_codes": reason_codes,
                        "evidence_refs": evidence_refs,
                        "claim_ref": cid,
                        "status": claim.get("status"),
                        "recurring_count": 1,
                    }
                )

    for idx, audit in enumerate(audits):
        if not isinstance(audit, dict):
            continue
        reason_codes = sorted(set(_audit_reason_codes(audit, reason_code_keys)))
        status = _audit_status(audit, status_keys)
        claim_ref = audit.get("claim_id") or audit.get("claim_ref") or audit.get("target_claim") or audit.get("target")
        evidence_refs = []
        refs = audit.get("evidence_refs")
        if isinstance(refs, list):
            evidence_refs = [str(v) for v in refs if isinstance(v, (str, int)) and str(v)]
        for code in reason_codes:
            issue_counts[code] = issue_counts.get(code, 0) + 1
        if reason_codes and evidence_refs:
            candidate_lessons.append(
                {
                    "lesson_text": audit.get("lesson") if isinstance(audit.get("lesson"), str) else None,
                    "reason_codes": reason_codes,
                    "evidence_refs": sorted(set(evidence_refs)),
                    "claim_ref": str(claim_ref) if isinstance(claim_ref, (str, int)) else None,
                    "audit_ref": audit.get("audit_id", idx),
                    "status": status,
                    "recurring_count": int(audit.get("recurring_count", 1)) if isinstance(audit.get("recurring_count", 1), int) else 1,
                }
            )

    return {
        "kind": "task_memory",
        "level": "L2",
        "task_id": str(task_id) if isinstance(task_id, (str, int)) else None,
        "task_title": task_title if isinstance(task_title, str) else None,
        "snapshot_id": str(snapshot_id) if isinstance(snapshot_id, (str, int)) else None,
        "claim_refs": sorted(set(claim_refs)),
        "issue_counts": issue_counts,
        "candidate_lessons": candidate_lessons,
        "provenance": {"source": "claim_graph_audit_snapshot"},
    }


def main(argv: List[str]) -> int:
    if len(argv) not in (2, 3):
        print("Usage: collect_l2.py SNAPSHOT_JSON [POLICY_JSON]", file=sys.stderr)
        return 2
    snapshot = _load_json(argv[1])
    policy = _load_json(argv[2]) if len(argv) == 3 else DEFAULT_POLICY
    result = collect_l2(snapshot, policy)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
