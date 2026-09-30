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
        self.damage_log: List[Dict[str, Any]] = []   # урон + причина (от валидатора)
        self.sleep_state: Dict[str, Any] = {}        # состояние сна (ветки, статус)
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
        # damage: критичность сигналов (с записью причины — от внешнего валидатора)
        damage = 0.0
        for s in signals:
            sev = s.get('severity', 'OK')
            if sev == 'CRITICAL':
                damage -= 25.0
            elif sev == 'WARNING':
                damage -= 5.0
            if sev in ('CRITICAL', 'WARNING'):
                # причина урона: validator/rule_id/сообщение
                self.damage_log.append({
                    'cycle': self.cycle,
                    'damage': -25.0 if sev == 'CRITICAL' else -5.0,
                    'source': s.get('validator') or s.get('channel') or 'orchestrator',
                    'rule_id': s.get('rule_id'),
                    'message': s.get('message', '')[:100],
                    'ts': datetime.now().isoformat(),
                })
        if metrics and metrics.get('error_score') is not None:
            err_score = metrics['error_score']
            damage -= err_score * 20.0
            if err_score > 0.3:
                self.damage_log.append({
                    'cycle': self.cycle,
                    'damage': -round(err_score * 20.0, 1),
                    'source': 'metrics',
                    'rule_id': 'ERROR_SCORE',
                    'message': f'error_score={err_score:.2f}',
                    'ts': datetime.now().isoformat(),
                })
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
            'damage_log': self.damage_log[-50:],
            'sleep_state': self.sleep_state,
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
                self.damage_log = data.get('damage_log', [])
                self.sleep_state = data.get('sleep_state', {})
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

    # ---------------------------------------------------------- дашборд
    def dashboard(self) -> Dict[str, Any]:
        """Дашборд состояния для промптов: HP, урон, причины, сон."""
        recent_damage = self.damage_log[-8:]
        return {
            'orchestrator': self.orchestrator,
            'cycle': self.cycle,
            'hp': self.health.health_points,
            'level': self.health.level,
            'lives': self.health.lives_remaining,
            'deaths': self.deaths,
            'recoveries': self.recoveries,
            'veto': self.veto(),
            'recent_damage': recent_damage,
            'total_damage_taken': round(sum(d['damage'] for d in self.damage_log), 1),
            'sleep': self.sleep_state,
        }

    def dashboard_text(self) -> str:
        """Текстовая проекция дашборда для промпта (LLM видит это)."""
        d = self.dashboard()
        lines = [
            f"[DASHBOARD {d['orchestrator']}]",
            f"  HP={d['hp']:.0f} | level={d['level']} | lives={d['lives']} | cycle={d['cycle']}",
            f"  deaths={d['deaths']} recoveries={d['recoveries']} veto={d['veto']}",
            f"  total_damage={d['total_damage_taken']}",
        ]
        if d['recent_damage']:
            lines.append("  recent_damage:")
            for dm in d['recent_damage']:
                lines.append(f"    -{abs(dm['damage'])} HP: [{dm['source']}] {dm.get('rule_id','')} {dm['message']}")
        if d['sleep']:
            lines.append(f"  SLEEP: {d['sleep']}")
        return "\n".join(lines)

    # ---------------------------------------------------------- цикл сна (гит-сон)
    def sleep_begin(self, task: str, branches: Optional[List[str]] = None) -> str:
        """Оркестратор уходит в сон: фиксируем ветки решения техдолгов.
        Возвращает sleep_id."""
        import uuid as _uuid
        sleep_id = str(_uuid.uuid4())[:8]
        self.sleep_state = {
            'sleep_id': sleep_id,
            'task': task[:80],
            'branches': branches or [],
            'merged': False,
            'started_at': datetime.now().isoformat(),
            'hp_at_sleep': self.health.health_points,
        }
        self.trace.append(TraceEntry('V2', 'sleep_begin', {'sleep_id': sleep_id}))
        self._save_state()
        return sleep_id

    def sleep_branch_add(self, branch: str) -> None:
        """Добавить ветку решения техдолга в текущий сон."""
        if self.sleep_state:
            self.sleep_state['branches'].append(branch)

    def sleep_merge(self, success: bool = True, result_summary: str = "") -> None:
        """Слияние всех веток сна в одну; при успехе — выход из сна."""
        if not self.sleep_state:
            return
        self.sleep_state['merged'] = success
        self.sleep_state['result'] = result_summary[:100]
        self.sleep_state['ended_at'] = datetime.now().isoformat()
        self.trace.append(TraceEntry('V2', 'sleep_merge', {
            'sleep_id': self.sleep_state.get('sleep_id'),
            'success': success,
        }))
        # после сна — восстановление HP (если слияние без багов)
        if success:
            self.health.apply_impact(+10.0)
        self._save_state()