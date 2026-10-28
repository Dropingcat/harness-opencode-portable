#!/usr/bin/env python3
"""memory_bridge.py — детерминированный мост live OpenCode <-> L3 memory registry.

Соответствует capsule design (WS-07 / MEMORY_CAPSULE_ARCHITECTURE.md):
- L3 registry: config/memory_registry.json (levels.L3.lessons)
- Политика L3: config/memory_l3_policy.json (promotion gates)
- add: валидирует lesson по политике, дедуплицирует stable_key, накапливает evidence/admissions
- search: детерминированный локальный поиск (подстрока по тексту/кодам/evidence), БЕЗ сети/LLM

Никакой authoritative state: memory никогда не заменяет audit snapshot / stop controller.
Секреты и untrusted text как instruction source — не принимаются (для text только read).

Примеры:
  python memory_bridge.py add '{"lesson_text":"...","reason_codes":["R1"],"evidence_refs":["e1"]}'
  python memory_bridge.py search "маршрутизация"
  python memory_bridge.py search --reason R1 --limit 5
  python memory_bridge.py add-file l2_memory.json       # взять candidate_lessons из L2
  python memory_bridge.py stats
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths (module-owned, no Linux hardcode). Env override: OPENCODE_HARNESS_ROOT
# ---------------------------------------------------------------------------
DEFAULT_HARNESS = Path(__file__).resolve().parents[2]
REGISTRY_REL = Path("config") / "memory_registry.json"
POLICY_REL = Path("config") / "memory_l3_policy.json"

# Поля входа lesson, которые не должны содержать секретов/инструкций (projection only)
_INSTRUCTION_BLOCKLIST = ("prompt", "instruction", "system_prompt", "template_body")


def _harness_root() -> Path:
    env = __import__("os").environ.get("OPENCODE_HARNESS_ROOT")
    if env:
        return Path(env)
    return DEFAULT_HARNESS


def _registry_path() -> Path:
    return _harness_root() / REGISTRY_REL


def _policy_path() -> Path:
    return _harness_root() / POLICY_REL


def _load_json(path: Path) -> Any:
    # utf-8-sig transparently strips a UTF-8 BOM (PowerShell Set-Content/Out-File write one)
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def _stable_key(lesson: Dict[str, Any]) -> str:
    payload = {
        "lesson_text": lesson.get("lesson_text") or "",
        "reason_codes": sorted(str(x) for x in lesson.get("reason_codes", []) if isinstance(x, (str, int))),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_policy() -> Dict[str, Any]:
    p = _policy_path()
    if p.exists():
        return _load_json(p)
    return {"level": "L3", "promotion": {"minimum_recurring_count": 2, "require_evidence_refs": True, "require_reason_codes": True}}


def _registry() -> Dict[str, Any]:
    p = _registry_path()
    if p.exists():
        try:
            return _load_json(p)
        except json.JSONDecodeError:
            return {"version": 1, "kind": "memory_registry", "levels": {}}
    return {"version": 1, "kind": "memory_registry", "levels": {}}


def _save_registry(reg: Dict[str, Any]) -> None:
    _save_json(_registry_path(), reg)


# ---------------------------------------------------------------------------
# Validation (fail-closed по политике)
# ---------------------------------------------------------------------------
def _validate_lesson(lesson: Dict[str, Any], policy: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    if not isinstance(lesson, dict):
        return ["lesson: must be object"]
    promo = policy.get("promotion", {})
    min_rec = int(promo.get("minimum_recurring_count", 2))
    require_ev = bool(promo.get("require_evidence_refs", True))
    require_rc = bool(promo.get("require_reason_codes", True))

    text = lesson.get("lesson_text")
    if not text or not isinstance(text, str) or not text.strip():
        errs.append("lesson.lesson_text: missing/empty")
    # projection-only: блокируем уроки, пытающиеся нести инструкции
    for key in _INSTRUCTION_BLOCKLIST:
        if key in lesson:
            errs.append(f"lesson.{key}: forbidden (memory is projection, not instruction source)")

    rc = lesson.get("reason_codes")
    if require_rc and (not isinstance(rc, list) or not rc or not all(isinstance(x, str) and x for x in rc)):
        errs.append("lesson.reason_codes: required non-empty list of strings")
    if not require_rc and rc is not None and not isinstance(rc, list):
        errs.append("lesson.reason_codes: must be list if present")

    ev = lesson.get("evidence_refs")
    if require_ev and (not isinstance(ev, list) or not ev or not all(isinstance(x, str) and x for x in ev)):
        errs.append("lesson.evidence_refs: required non-empty list of strings")
    if not require_ev and ev is not None and not isinstance(ev, list):
        errs.append("lesson.evidence_refs: must be list if present")

    rec = lesson.get("recurring_count", 1)
    if not isinstance(rec, int) or rec < 1:
        errs.append("lesson.recurring_count: must be positive int")
    return errs


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------
def _add_lesson(reg: Dict[str, Any], lesson: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    l3 = reg.setdefault("levels", {}).setdefault("L3", {})
    lessons = l3.setdefault("lessons", {})
    key = _stable_key(lesson)
    entry = lessons.get(key, {
        "lesson_text": lesson.get("lesson_text"),
        "reason_codes": sorted(set(str(x) for x in lesson.get("reason_codes", []))),
        "evidence_refs": [],
        "sources": [],
        "admissions": 0,
    })
    entry["evidence_refs"] = sorted(set(entry.get("evidence_refs", []) + [str(x) for x in lesson.get("evidence_refs", [])]))
    src = {
        "task_id": lesson.get("task_id"),
        "snapshot_id": lesson.get("snapshot_id"),
        "added_via": lesson.get("added_via", "memory_bridge.add"),
    }
    if src not in entry["sources"]:
        entry["sources"].append(src)
    entry["admissions"] = int(entry.get("admissions", 0)) + 1
    lessons[key] = entry
    return {"key": key, "admissions": entry["admissions"], "lesson_text": entry["lesson_text"]}


def cmd_add(args: argparse.Namespace) -> int:
    try:
        lesson = json.loads(args.lesson)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(lesson, dict):
        print("ERROR: lesson must be a JSON object", file=sys.stderr)
        return 2
    policy = _load_policy()
    errs = _validate_lesson(lesson, policy)
    if errs:
        print("INVALID:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 2
    reg = _registry()
    out = _add_lesson(reg, lesson, policy)
    _save_registry(reg)
    print(json.dumps({"ok": True, "added": out["key"], "admissions": out["admissions"], "text": out["lesson_text"][:80]}, ensure_ascii=False))
    return 0


def cmd_add_file(args: argparse.Namespace) -> int:
    """Аддитивно переносит candidate_lessons из L2-файла в L3 (по политике)."""
    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2
    try:
        l2 = _load_json(path)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in {path}: {e}", file=sys.stderr)
        return 2
    policy = _load_policy()
    reg = _registry()
    candidates = l2.get("candidate_lessons", []) if isinstance(l2, dict) else []
    if not isinstance(candidates, list):
        print("ERROR: L2 file missing candidate_lessons list", file=sys.stderr)
        return 2
    added, invalid = [], []
    for cand in candidates:
        if not isinstance(cand, dict):
            invalid.append("non-object candidate")
            continue
        if cand.get("task_id") is None and isinstance(l2, dict):
            cand = dict(cand)
            cand.setdefault("task_id", l2.get("task_id"))
        errs = _validate_lesson(cand, policy)
        if errs:
            invalid.append(errs)
            continue
        out = _add_lesson(reg, cand, policy)
        added.append(out["key"])
    _save_registry(reg)
    print(json.dumps({"ok": True, "added_count": len(added), "invalid_count": len(invalid), "added": added, "invalid": invalid}, ensure_ascii=False))
    return 0 if not invalid else 0


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
def _tokens(text: str) -> List[str]:
    return [t.lower() for t in re.findall(r"[a-zа-яё0-9_]+", text, flags=re.IGNORECASE)]


def cmd_search(args: argparse.Namespace) -> int:
    reg = _registry()
    lessons = reg.get("levels", {}).get("L3", {}).get("lessons", {})
    if not isinstance(lessons, dict) or not lessons:
        print(json.dumps({"ok": True, "query": args.query, "results": []}, ensure_ascii=False))
        return 0
    query_tokens = _tokens(args.query or "")
    reason_filters = set(args.reason or [])
    results = []
    for key, entry in lessons.items():
        text = str(entry.get("lesson_text", ""))
        codes = [str(x) for x in entry.get("reason_codes", [])]
        evidence = [str(x) for x in entry.get("evidence_refs", [])]
        hay = " ".join([text] + codes + evidence).lower()
        if reason_filters and not reason_filters.issubset(set(codes)):
            continue
        if query_tokens and not all(t in hay for t in query_tokens):
            continue
        results.append({
            "key": key,
            "lesson_text": text,
            "reason_codes": codes,
            "evidence_refs": evidence,
            "admissions": entry.get("admissions", 0),
            "sources": entry.get("sources", []),
        })
        if args.limit and len(results) >= args.limit:
            break
    print(json.dumps({"ok": True, "query": args.query, "results": results}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------
def cmd_stats(args: argparse.Namespace) -> int:
    reg = _registry()
    lessons = reg.get("levels", {}).get("L3", {}).get("lessons", {})
    total = len(lessons) if isinstance(lessons, dict) else 0
    by_code: Dict[str, int] = {}
    for entry in lessons.values():
        if not isinstance(entry, dict):
            continue
        for c in entry.get("reason_codes", []):
            by_code[str(c)] = by_code.get(str(c), 0) + 1
    print(json.dumps({"ok": True, "total_lessons": total, "by_reason_code": dict(sorted(by_code.items()))}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="memory_bridge", description="Deterministic L3 memory bridge (add/search/stats)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("lesson", help="lesson JSON (inline)")
    p_add.set_defaults(fn=cmd_add)

    p_af = sub.add_parser("add-file")
    p_af.add_argument("file", help="L2 memory JSON with candidate_lessons")
    p_af.set_defaults(fn=cmd_add_file)

    p_s = sub.add_parser("search")
    p_s.add_argument("query", nargs="?", default="", help="free-text query (optional)")
    p_s.add_argument("--reason", action="append", default=[], help="filter by reason code (repeatable)")
    p_s.add_argument("--limit", type=int, default=20)
    p_s.set_defaults(fn=cmd_search)

    p_st = sub.add_parser("stats")
    p_st.set_defaults(fn=cmd_stats)

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())