# -*- coding: utf-8 -*-
"""
orchestrator_integration.py — точка интеграции Meta-Cycle в оркестраторов.

Подключается к ЛЮБОМУ оркестратору (research/writing/code) через единый интерфейс:
  - pre_task(task): health-check + legacy-search (не решать заново)
  - post_task(result, metrics): debt-сбор, damage, trace
  - on_failure(failure): AAR-подобная запись, фичи в legacy

Оркестратор вызывает эти методы в своём цикле; детерминированный слой (V-1, legacy,
trace) живёт в scripts/meta/* и НЕ зависит от конкретного контура.
"""
from __future__ import annotations

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# импорты meta-слоя (создают детерминированное состояние в памяти/файле)
_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from health_monitor import HealthMonitor, SystemHealth, StyleMetrics, HealthReport
from legacy import LegacyArchive, ExperiencePattern, LegacyRecord, PatternCategory
from trace_store import TraceStore, TraceEntry


class OrchestratorIntegration:
    """
    Единый адаптер Meta-Cycle для оркестраторов.
    Использование:
        meta = OrchestratorIntegration('research', state_dir)
        ok, hint = meta.pre_task(task)
        result = <оркестратор выполняет задачу>
        meta.post_task(task, result, metrics)
    """

    def __init__(self, orchestrator: str = "research",
                 state_dir: Optional[str] = None,
                 health_points: float = 100.0,
                 lives: int = 5) -> None:
        self.orchestrator = orchestrator
        # состояние (persistent в файле, чтобы переживать вызовы)
        self.state_dir = Path(state_dir) if state_dir else Path(os.environ.get(
            'HARNESS_META_STATE', str(_META.parent.parent / '.meta_state')))
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f'{orchestrator}_meta_state.json'

        self.health = SystemHealth(health_points=health_points, lives_remaining=lives)
        self.monitor = HealthMonitor()
        self.legacy = LegacyArchive()
        self.trace = TraceStore()
        self.cycle = 0
        self.deaths = 0
        self.recoveries = 0
        self._load_state()
        # внедряемые колбэки (для кастомизации)
        self.generate_test_fn = None   # (text) -> StyleMetrics

    # ---------------------------------------------------------- публичный API

    def pre_task(self, task: str) -> tuple:
        """Перед задачей: health-check + legacy-search."""
        self.cycle += 1
        # 1. Legacy search: не решать заново
        similar = self.legacy.search_similar_failures(task, threshold=0.1)
        hint = ""
        if similar:
            hint = f"[legacy] {len(similar)} похожих провалов; применить уроки"
            self.trace.append(TraceEntry('V6', 'legacy_hint',
                                         {'count': len(similar), 'task': task[:60]}))
        # 2. Health-check: можно ли генерировать
        if self.health.level in ('dead', 'critical') or self.health.lives_remaining <= 0:
            self._reanimate()
        self.trace.append(TraceEntry('V-1', 'pre_task', {'cycle': self.cycle,
                                                         'hp': self.health.health_points}))
        return self.health.level not in ('dead',), hint

    def post_task(self, task: str, result: Any,
                  metrics: Optional[Dict[str, float]] = None,
                  signals: Optional[List[Dict[str, Any]]] = None) -> str:
        """После задачи: metrics → health (damage), trace, debt-сигнал."""
        signals = signals or [{'severity': 'OK', 'channel': 'orchestrator',
                               'message': 'ok'}]
        # метрики стиля
        sm = self._build_style_metrics(result, metrics)
        report = HealthReport(self.health, signals, sm)
        # damage: критичность сигналов
        damage = 0.0
        for s in signals:
            if s.get('severity') == 'CRITICAL':
                damage -= 25.0
            elif s.get('severity') == 'WARNING':
                damage -= 5.0
        if metrics and metrics.get('error_score') is not None:
            damage -= metrics['error_score'] * 20.0
        self.health.apply_impact(damage)
        self.trace.append(TraceEntry('V-1', 'post_task',
                                     {'hp': self.health.health_points,
                                      'damage': damage, 'cycle': self.cycle}))
        # смерть?
        if self.health.level in ('critical', 'dead') and self.health.health_points < 50:
            self.deaths += 1
            self.health.record_death()
            self.health.health_points = 60.0
            self.health.record_recovery()
            self.recoveries += 1
            self.legacy.register_pattern(ExperiencePattern(
                PatternCategory.FAILURE, f'death:{self.orchestrator}',
                'критический демедж в оркестраторе', tags=[self.orchestrator]))
            self._save_state()
            return 'DEATH'
        self._save_state()
        return 'OK'

    def on_failure(self, failure: str, task: str = "", tags: Optional[List[str]] = None) -> None:
        """Запись провала в legacy (фича/урок)."""
        rec = LegacyRecord(self._current_version(), task, failure,
                           tags=tags or [self.orchestrator])
        self.legacy.archive(rec)
        self.trace.append(TraceEntry('V6', 'failure_archived',
                                     {'reason': failure[:80]}))
        self._save_state()

    def veto(self) -> bool:
        """Право вето: система может остановить генерацию."""
        return self.health.level in ('critical', 'dead') or self.health.lives_remaining <= 0

    # ---------------------------------------------------------- внутренние

    def _build_style_metrics(self, result: Any, metrics: Optional[Dict[str, float]]) -> StyleMetrics:
        if self.generate_test_fn:
            try:
                return self.generate_test_fn(result)
            except Exception:
                pass
        m = metrics or {}
        text = str(result) if result else ""
        return StyleMetrics(
            avg_sentence_length=m.get('avg_sentence_length', 15.0),
            terminology_density=m.get('terminology_density', 0.1),
            filler_word_ratio=m.get('filler_word_ratio', 0.1),
            citation_per_claim=m.get('citation_per_claim', 1.0),
            method_specification_ratio=m.get('method_specification_ratio', 0.7),
            golden_corpus_similarity=m.get('golden_similarity', 0.7),
        )

    def _current_version(self) -> str:
        return f"{self.orchestrator}-c{self.cycle}"

    def _reanimate(self) -> None:
        self.health.health_points = 60.0
        self.health.lives_remaining = 3
        self.health.record_recovery()
        self.recoveries += 1
        self.trace.append(TraceEntry('V-1', 'reanimated', {}))

    def _save_state(self) -> None:
        data = {
            'orchestrator': self.orchestrator,
            'health': self.health.to_dict(),
            'cycle': self.cycle,
            'deaths': self.deaths,
            'recoveries': self.recoveries,
            'saved_at': datetime.now().isoformat(),
        }
        self.state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                   encoding='utf-8')

    def _load_state(self) -> None:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding='utf-8'))
                self.cycle = data.get('cycle', 0)
                self.deaths = data.get('deaths', 0)
                self.recoveries = data.get('recoveries', 0)
                h = data.get('health', {})
                self.health = SystemHealth(
                    health_points=h.get('health_points', 100.0),
                    lives_remaining=h.get('lives_remaining', 3))
            except Exception:
                pass

    def status(self) -> Dict[str, Any]:
        return {
            'orchestrator': self.orchestrator,
            'cycle': self.cycle,
            'health': self.health.to_dict(),
            'deaths': self.deaths,
            'recoveries': self.recoveries,
            'legacy_records': len(self.legacy.records),
            'veto': self.veto(),
        }