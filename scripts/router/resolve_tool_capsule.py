#!/usr/bin/env python3
"""Resolve tool families and concrete tools for a route."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def load(name: str) -> dict:
    return json.loads((root() / "config" / name).read_text(encoding="utf-8"))


def resolve(route_id: str) -> dict:
    families = load("tool_families.json")["families"]
    policy = load("tool_capsule_policy.json")
    priorities = policy.get("family_priority", {}).get(route_id, [])
    resolved = []
    for family_id in priorities:
        meta = families.get(family_id)
        if not meta:
            continue
        if route_id not in meta.get("allowed_routes", []):
            continue
        resolved.append(
            {
                "family": family_id,
                "tools": meta.get("tools", []),
                "guard_required": meta.get("guard_required", False),
                "side_effects": meta.get("side_effects", "unknown"),
            }
        )
    # SkillMaster: фиксация использования скила (повседневный цикл)
    _record_skill_usage(route_id, resolved)
    # MemoryCirculator: L2->L3 перенос + L3->L1 циркуляция (изолированный агент)
    _circulate_memory(route_id)
    return {"ok": bool(resolved), "route_id": route_id, "families": resolved}


def _circulate_memory(route_id: str) -> None:
    """Роутер обеспечивает циркуляцию паттернов (мягкая интеграция, без сбоев)."""
    try:
        import sys as _sys
        meta_dir = root() / "scripts" / "meta"
        if str(meta_dir) not in _sys.path:
            _sys.path.insert(0, str(meta_dir))
        from memory_circulator import MemoryCirculator
        mc = MemoryCirculator()
        # L2: запомнить факт использования route
        mc.l2_remember(route_id, {
            'lesson_text': f'route {route_id} used',
            'reason_codes': [f'ROUTE_{route_id.upper()}'],
            'evidence_refs': [f'route:{route_id}'],
        })
        # L2 -> L3: перенос зрелых уроков (admissions >= порога)
        mc.promote_to_l3(route_id)
    except Exception:
        pass  # не ломаем роутер


def _record_skill_usage(route_id: str, families: list) -> None:
    """Каждый вызов тула → record_usage в SkillMaster (мягкая интеграция)."""
    try:
        import sys as _sys
        meta_dir = root() / "scripts" / "meta"
        if str(meta_dir) not in _sys.path:
            _sys.path.insert(0, str(meta_dir))
        from skill_master import SkillMaster
        sm = SkillMaster()
        skill_name = route_id.replace('/', '_') or 'route'
        outcome = "ok" if families else "error"
        sm.record_usage(skill_name, outcome=outcome)
    except Exception:
        pass  # не ломаем роутер


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: resolve_tool_capsule.py <route_id>")
        return 2
    print(json.dumps(resolve(sys.argv[1]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
