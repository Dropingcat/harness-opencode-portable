# -*- coding: utf-8 -*-
"""
orchestrator.py — MetaCycleOrchestrator (главный оркестратор V-1/V1-V8).

Связывает: TraceStore + LegacyArchive + StateManager + HealthMonitor + DebtDrivenCycle.
Цикл: pre-check → legacy search → branch → dream(s) → monitor (V-1) →
      success? promote : AAR → lessons → patterns → legacy → retry.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from branch import Artifact, BranchStatus, ExperimentBranch, ExperimentRun, SkillInvocation
from health_monitor import HealthMonitor
from legacy import (ExperiencePattern, LegacyArchive, LegacyRecord, LessonLearned,
                    PatternCategory)
from state import ErrorVector, StateManager, SystemState
from trace_store import TraceStore, TraceEntry, TransitionRecord


class DreamOutcome:
    SUCCESS = "success"
    DEGRADATION = "degradation"
    DEATH = "death"
    INCONCLUSIVE = "inconclusive"


class MetaCycleOrchestrator:
    """Главный оркестратор: полный цикл задачи."""

    def __init__(self, initial_state: Optional[SystemState] = None) -> None:
        self.trace = TraceStore()
        self.legacy = LegacyArchive()
        self.state_mgr = StateManager(initial_state or SystemState())
        self.health = HealthMonitor()
        self.current_state = self.state_mgr.current
        self.cycle_count = 0
        # внедряемые колбэки (для тестов/реальной генерации)
        self.generate_fn = None        # (task, branch) -> (text, invocations)
        self.evaluate_fn = None        # (text) -> (metrics, signals)
        self.reanimate_fn = None

    def initialize(self) -> None:
        self.trace.save_snapshot(self.current_state)
        self.trace.append(TraceEntry("SYSTEM", "initialization",
                                     {"version": self.current_state.version_id}))

    def run_task(self, task: str) -> str:
        self.cycle_count += 1
        # 1. Pre-check (V-1)
        if self.health.pre_generation_check().severity == "CRITICAL":
            self._reanimate()
        # 2. Legacy search
        similar = self.legacy.search_similar_failures(task, threshold=0.1)
        if similar:
            self.trace.append(TraceEntry("V6", "legacy_hit",
                                         {"count": len(similar), "task": task[:60]}))
        # 3. Branch
        branch = ExperimentBranch(self.current_state.version_id,
                                  {"task": task, "cycle": self.cycle_count})
        # 4. Dreams (упрощённо: 1 прогон + мониторинг)
        outcome = DreamOutcome.INCONCLUSIVE
        run = ExperimentRun(branch.branch_id, branch.delta.get("task", ""), task)
        try:
            text, invocations = self._generate(task, branch)
            run.llm_output = text
            run.skill_invocations = [SkillInvocation(**i) if isinstance(i, dict) else i
                                     for i in invocations]
            branch.add_run(run)
            # 5. Monitor V-1
            metrics, signals = self._evaluate(text)
            run.evaluation_metrics = metrics
            branch.aggregated_metrics = metrics
            if any(s.get("severity") == "CRITICAL" for s in signals):
                outcome = DreamOutcome.DEATH
            elif metrics.get("error_score", 1.0) < 0.3:
                outcome = DreamOutcome.SUCCESS
            else:
                outcome = DreamOutcome.DEGRADATION
        except Exception as e:
            outcome = DreamOutcome.DEATH
            run.llm_output = f"ERROR: {e}"
        # 6. Развилка
        if outcome == DreamOutcome.SUCCESS:
            self._promote(branch, run)
            return text
        else:
            self._archive_failure(branch, run, outcome)
            return self._fallback_or_retry(task, text)

    # --- внутренние ---
    def _generate(self, task: str, branch: ExperimentBranch):
        if self.generate_fn:
            return self.generate_fn(task, branch)
        # дефолт: заглушка
        artifact = Artifact("text", f"[stub:{task}]", branch.branch_id, ["generated"])
        branch.add_artifact(artifact)
        return f"[stub:{task}]", []

    def _evaluate(self, text: str):
        if self.evaluate_fn:
            return self.evaluate_fn(text)
        return {"error_score": 0.0}, [{"severity": "OK", "channel": "stub"}]

    def _promote(self, branch: ExperimentBranch, run: ExperimentRun) -> None:
        branch.close(BranchStatus.PROMOTED)
        # применяем дельту к состоянию
        new_state = self.state_mgr.apply_delta(branch.delta)
        self.current_state = new_state
        self.trace.save_snapshot(new_state)
        self.trace.record_transition(TransitionRecord(
            branch.parent_version_id, new_state.version_id,
            branch.delta, [run.run_id], {}, branch.aggregated_metrics))
        # паттерн успеха
        pattern = ExperiencePattern(PatternCategory.SUCCESS,
                                    f"success:{branch.branch_id[:8]}",
                                    "успешная стратегия",
                                    involved_skills=[i.get("skill_name", "?")
                                                     for i in [s.to_dict() for s in run.skill_invocations]])
        self.legacy.register_pattern(pattern)

    def _archive_failure(self, branch: ExperimentBranch, run: ExperimentRun,
                         outcome: str) -> None:
        branch.close(BranchStatus.REJECTED)
        rec = LegacyRecord(branch.parent_version_id,
                           branch.delta.get("task", ""),
                           rejection_reason=outcome,
                           max_achieved_metrics=run.evaluation_metrics)
        lesson = LessonLearned(f"outcome:{outcome}",
                               f"избегать: {outcome}", priority=3,
                               source_branch_id=branch.branch_id)
        rec.lessons = [lesson]
        rec.failure_patterns = [ExperiencePattern(
            PatternCategory.FAILURE, f"fail:{outcome}", outcome,
            source_lesson_ids=[lesson.lesson_id])]
        self.legacy.archive(rec)
        self.trace.append(TraceEntry("V6", "archived",
                                     {"branch": branch.branch_id, "outcome": outcome}))

    def _fallback_or_retry(self, task: str, text: str) -> str:
        return text if text else f"[failed:{task}]"

    def _reanimate(self) -> None:
        if self.reanimate_fn:
            self.reanimate_fn()
        else:
            self.health = HealthMonitor()
        self.trace.append(TraceEntry("V-1", "reanimated", {}))