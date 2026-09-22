"""Promote recurring L2 lessons into an L3 registry."""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Dict, List

DEFAULT_POLICY = {
    "promotion": {
        "minimum_recurring_count": 2,
        "require_evidence_refs": True,
        "require_reason_codes": True
    }
}


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _stable_key(lesson: Dict[str, Any]) -> str:
    payload = {
        "lesson_text": lesson.get("lesson_text") or "",
        "reason_codes": sorted(str(x) for x in lesson.get("reason_codes", []) if isinstance(x, (str, int)))
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _valid_lesson(lesson: Dict[str, Any], threshold: int, require_evidence: bool, require_reason_codes: bool) -> bool:
    recurring_count = lesson.get("recurring_count")
    if not isinstance(recurring_count, int) or recurring_count < threshold:
        return False
    reason_codes = lesson.get("reason_codes")
    evidence_refs = lesson.get("evidence_refs")
    if require_reason_codes and (not isinstance(reason_codes, list) or not reason_codes):
        return False
    if require_evidence and (not isinstance(evidence_refs, list) or not evidence_refs):
        return False
    return True


def promote(l2_memory: Dict[str, Any], registry: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    promotion = policy.get("promotion", {})
    threshold = int(promotion.get("minimum_recurring_count", 2))
    require_evidence = bool(promotion.get("require_evidence_refs", True))
    require_reason_codes = bool(promotion.get("require_reason_codes", True))
    levels = registry.setdefault("levels", {})
    l3 = levels.setdefault("L3", {})
    lessons = l3.setdefault("lessons", {})

    for lesson in l2_memory.get("candidate_lessons", []):
        if not isinstance(lesson, dict):
            continue
        if not _valid_lesson(lesson, threshold, require_evidence, require_reason_codes):
            continue
        key = _stable_key(lesson)
        entry = lessons.get(key, {
            "lesson_text": lesson.get("lesson_text"),
            "reason_codes": sorted(set(str(x) for x in lesson.get("reason_codes", []))),
            "evidence_refs": [],
            "sources": [],
            "admissions": 0
        })
        entry["evidence_refs"] = sorted(set(entry.get("evidence_refs", []) + [str(x) for x in lesson.get("evidence_refs", [])]))
        source = {"task_id": l2_memory.get("task_id"), "snapshot_id": l2_memory.get("snapshot_id")}
        if source not in entry["sources"]:
            entry["sources"].append(source)
        entry["admissions"] = int(entry.get("admissions", 0)) + 1
        lessons[key] = entry

    return registry


def main(argv: List[str]) -> int:
    if len(argv) not in (3, 4):
        print("Usage: promote_l2_to_l3.py L2_MEMORY_JSON REGISTRY_JSON [POLICY_JSON]", file=sys.stderr)
        return 2
    l2_memory = _load_json(argv[1])
    registry = _load_json(argv[2])
    policy = _load_json(argv[3]) if len(argv) == 4 else DEFAULT_POLICY
    result = promote(l2_memory, registry, policy)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
