# -*- coding: utf-8 -*-
"""
sleep_planner.py — ИЗОЛИРОВАННЫЙ АГЕНТ ПЛАНИРОВАНИЯ СНА.

Роли:
- Видит ТОЛЬКО корзину урона + историю ошибок (не состояние оркестратора).
- Кластеризует долги по rule_id/engine.
- Создаёт ПРОМПТ СНА для оркестратора (когда тот входит в сон).
- Его цикл ведёт СКРИПТ (детерминированный), не LLM сама.

Изоляция: планировщик <-> аудитор НЕ связаны. Планировщик получает
только корзину. Аудитор только бросает в корзину.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from damage_basket import DamageBasket, DamageEntry


class SleepPlan:
    """План сна: кластеры долгов → ветки → промпт сна."""

    def __init__(self, orchestrator: str, clusters: Dict[str, List[DamageEntry]]) -> None:
        self.plan_id = str(uuid.uuid4())[:8]
        self.orchestrator = orchestrator
        self.clusters = clusters
        self.branches: List[str] = []
        self.created_at = datetime.now().isoformat()
        self._build_branches()

    def _build_branches(self) -> None:
        """Каждый кластер долгов → ветка fix/<rule_id>."""
        for rule_id in self.clusters:
            self.branches.append(f"fix/{rule_id}")

    def sleep_prompt(self) -> str:
        """Промпт сна для оркестратора (создаёт планировщик)."""
        lines = [
            f"[SLEEP-PLAN:{self.plan_id}] оркестратор={self.orchestrator}",
            f"Причина сна: достигнут порог урона. Ветки решения: {', '.join(self.branches)}",
            "Техдолги (из корзины):",
        ]
        for rule_id, entries in self.clusters.items():
            damages = sum(e.damage_points for e in entries)
            lines.append(f"  fix/{rule_id}: {len(entries)} находок, урон {damages} "
                         f"(пример: {entries[0].message if entries else ''})")
        lines.append("Критерий выхода: все ветки слиты без багов и без увода от исходной задачи.")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id, "orchestrator": self.orchestrator,
            "branches": self.branches,
            "clusters": {k: [e.to_dict() for e in v] for k, v in self.clusters.items()},
            "sleep_prompt": self.sleep_prompt(),
        }


class SleepPlannerAgent:
    """Изолированный планировщик сна. Цикл ведёт скрипт (run_sleep_planner)."""

    def __init__(self, basket: DamageBasket,
                 cluster_fn: Optional[Callable[[List[DamageEntry]], Dict[str, List[DamageEntry]]]] = None,
                 state_dir: Optional[str] = None) -> None:
        self.basket = basket
        self.cluster_fn = cluster_fn or self._cluster_default
        self.state_dir = Path(state_dir) if state_dir else Path(os.environ.get(
            'HARNESS_PLANNER_STATE', str(Path(__file__).parent.parent.parent / '.planner_state')))
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.history: List[SleepPlan] = []

    # ------------------------------------------------------ цикл (ведёт скрипт)
    def run_plan(self, orchestrator: str) -> Optional[SleepPlan]:
        """Скрипт вызывает: если урон >= порога — план сна."""
        if not self.basket.should_trigger_sleep():
            return None
        entries = self.basket.entries
        clusters = self.cluster_fn(entries)
        plan = SleepPlan(orchestrator, clusters)
        self.history.append(plan)
        return plan

    def create_sleep_prompt(self, orchestrator: str) -> str:
        """Промпт сна (для оркестратора при входе в сон)."""
        plan = self.run_plan(orchestrator)
        return plan.sleep_prompt() if plan else "[no sleep needed]"

    # ------------------------------------------------------ кластеризация
    @staticmethod
    def _cluster_default(entries: List[DamageEntry]) -> Dict[str, List[DamageEntry]]:
        """По rule_id."""
        clusters: Dict[str, List[DamageEntry]] = {}
        for e in entries:
            clusters.setdefault(e.rule_id, []).append(e)
        return clusters

    def cluster_by_engine(self, entries: List[DamageEntry]) -> Dict[str, List[DamageEntry]]:
        clusters: Dict[str, List[DamageEntry]] = {}
        for e in entries:
            clusters.setdefault(e.engine, []).append(e)
        return clusters