# -*- coding: utf-8 -*-
"""
damage_basket.py — КОРЗИНА УРОНА (скрипт-счётчик).

Аудитор НЕ считает урон сам. Он бросает техдолги в корзину (файл).
Скрипт (этот модуль) читает корзину, начисляет урон (severity -> очки),
и при достижении ПОРОГА (по умолчанию 100) вызывает скрипт сна.

Изоляция: корзина — единственный канал между аудитором и остальными.
Оркестратор/аудитор не имеют общего контекста; только файл корзины.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_BASKET = Path(os.environ.get(
    'HARNESS_DAMAGE_BASKET', str(Path(__file__).parent.parent.parent / '.damage_basket')))


class DamageEntry:
    """Запись урона в корзине."""

    __slots__ = ("entry_id", "rule_id", "engine", "severity", "message",
                 "target", "damage_points", "timestamp", "auditor_id")

    def __init__(self, rule_id: str, engine: str, severity: str, message: str,
                 target: str = "", auditor_id: str = "external") -> None:
        self.entry_id = str(uuid.uuid4())[:8]
        self.rule_id = rule_id
        self.engine = engine
        self.severity = severity
        self.message = message
        self.target = target
        # CRITICAL = 25, WARNING = 5, LOW = 1 (настраиваемо)
        self.damage_points = {"CRITICAL": 25, "WARNING": 5, "LOW": 1}.get(severity, 1)
        self.timestamp = datetime.now().isoformat()
        self.auditor_id = auditor_id

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}


class DamageBasket:
    """Корзина урона: аудитор бросает долги, скрипт считает урон."""

    def __init__(self, basket_dir: Optional[str] = None,
                 threshold: int = 100) -> None:
        self.dir = Path(basket_dir) if basket_dir else _DEFAULT_BASKET
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / 'basket.json'
        self.threshold = threshold
        self.entries: List[DamageEntry] = []
        self._load()

    # ------------------------------------------------------ для аудитора
    def drop(self, entry: DamageEntry) -> int:
        """Аудитор бросает долг в корзину. Возвращает текущий суммарный урон."""
        self.entries.append(entry)
        self._save()
        return self.total_damage()

    def drop_many(self, entries: List[DamageEntry]) -> int:
        for e in entries:
            self.entries.append(e)
        self._save()
        return self.total_damage()

    # ------------------------------------------------------ для скрипта
    def total_damage(self) -> int:
        """Суммарный урон по всем записям."""
        return sum(e.damage_points for e in self.entries)

    def recent_damage(self, n: int = 10) -> List[DamageEntry]:
        return self.entries[-n:]

    def should_trigger_sleep(self) -> bool:
        """Урон достиг порога → вызвать скрипт сна."""
        return self.total_damage() >= self.threshold

    def trigger_sleep(self, orchestrator: str) -> Dict[str, Any]:
        """При достижении порога: формирует триггер сна (для SleepController)."""
        return {
            'trigger': 'DAMAGE_THRESHOLD',
            'orchestrator': orchestrator,
            'total_damage': self.total_damage(),
            'threshold': self.threshold,
            'entries': [e.to_dict() for e in self.entries],
            'triggered_at': datetime.now().isoformat(),
        }

    def cluster_by_rule(self) -> Dict[str, List[DamageEntry]]:
        """Группировка долгов по rule_id (для кластеризации при сне)."""
        clusters: Dict[str, List[DamageEntry]] = {}
        for e in self.entries:
            clusters.setdefault(e.rule_id, []).append(e)
        return clusters

    def reset(self) -> None:
        """Очистка корзины (после успешного сна)."""
        self.entries = []
        self._save()

    # ------------------------------------------------------ персистентность
    def _save(self) -> None:
        data = {
            'threshold': self.threshold,
            'entries': [e.to_dict() for e in self.entries],
            'saved_at': datetime.now().isoformat(),
        }
        self.file.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding='utf-8')

    def _load(self) -> None:
        if self.file.exists():
            try:
                data = json.loads(self.file.read_text(encoding='utf-8'))
                self.threshold = data.get('threshold', self.threshold)
                for e in data.get('entries', []):
                    self.entries.append(DamageEntry(
                        e['rule_id'], e['engine'], e['severity'],
                        e['message'], e.get('target', ''), e.get('auditor_id', 'external')))
            except Exception:
                self.entries = []