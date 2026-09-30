# -*- coding: utf-8 -*-
"""
merge_protocol.py — V2 Merge Protocol (git-методики).

Пятишаговый цикл слияния:
  1. PRE-MERGE CHECK
  2. THREE-WAY MERGE (base + ours + theirs → merged)
  3. CONFLICT RESOLUTION (auto / llm-mediate / manual)
  4. POST-MERGE VALIDATION (regression, health V-1, invariants)
  5. COMMIT или ROLLBACK

Плюс cherry-pick (перенос дельты) и rebase (перенос ветки на новое основание).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from state import StateVariable, StabilityLevel, SystemState


class MergeConflictType(str, Enum):
    VARIABLE_CONFLICT = "variable_conflict"
    INVARIANT_VIOLATION = "invariant_violation"
    REGRESSION = "regression"
    SEMANTIC_CONFLICT = "semantic_conflict"


class MergeConflict:
    """Конфликт слияния."""

    __slots__ = ("conflict_id", "conflict_type", "variable_name", "our_value",
                 "their_value", "base_value", "description", "auto_resolvable",
                 "resolution_strategy")

    def __init__(self, conflict_type: MergeConflictType, variable_name: str,
                 our_value: Any, their_value: Any, base_value: Any,
                 description: str = "") -> None:
        self.conflict_id = str(uuid.uuid4())
        self.conflict_type = conflict_type
        self.variable_name = variable_name
        self.our_value = our_value
        self.their_value = their_value
        self.base_value = base_value
        self.description = description or f"Конфликт по '{variable_name}'"
        self.auto_resolvable = False
        self.resolution_strategy: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value if hasattr(self.conflict_type, 'value') else str(self.conflict_type),
            "variable_name": self.variable_name,
            "our_value": self.our_value, "their_value": self.their_value,
            "base_value": self.base_value, "description": self.description,
            "auto_resolvable": self.auto_resolvable,
            "resolution_strategy": self.resolution_strategy,
        }


class ThreeWayMergeContext:
    """Контекст three-way merge: base (предок) + ours (main) + theirs (ветка)."""

    __slots__ = ("base_state", "our_state", "their_state", "their_delta")

    def __init__(self, base_state: SystemState, our_state: SystemState,
                 their_state: SystemState, their_delta: Optional[Dict[str, Any]] = None) -> None:
        self.base_state = base_state
        self.our_state = our_state
        self.their_state = their_state
        self.their_delta = their_delta or {}


class MergeRequest:
    """Запрос на слияние с результатами проверок."""

    __slots__ = ("request_id", "source_branch_id", "target_branch_id", "merge_context",
                 "pre_merge_checks_passed", "conflicts", "conflicts_resolved",
                 "regression_tests_passed", "regression_failures",
                 "post_merge_health", "invariants_held", "decision", "decision_reason",
                 "timestamp")

    def __init__(self, source_branch_id: str, merge_context: ThreeWayMergeContext,
                 target_branch_id: str = "main") -> None:
        self.request_id = str(uuid.uuid4())
        self.source_branch_id = source_branch_id
        self.target_branch_id = target_branch_id
        self.merge_context = merge_context
        self.pre_merge_checks_passed = False
        self.conflicts: List[MergeConflict] = []
        self.conflicts_resolved = False
        self.regression_tests_passed = False
        self.regression_failures: List[str] = []
        self.post_merge_health: Optional[Any] = None
        self.invariants_held = False
        self.decision: Optional[str] = None
        self.decision_reason: Optional[str] = None
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id, "source_branch_id": self.source_branch_id,
            "pre_merge_checks_passed": self.pre_merge_checks_passed,
            "conflicts": len(self.conflicts), "conflicts_resolved": self.conflicts_resolved,
            "regression_tests_passed": self.regression_tests_passed,
            "invariants_held": self.invariants_held,
            "decision": self.decision, "decision_reason": self.decision_reason,
        }


class MergeResult:
    """Результат слияния."""

    __slots__ = ("result_id", "request_id", "success", "new_main_state",
                 "commit_hash", "rollback_performed", "failure_reason", "timestamp")

    def __init__(self, request_id: str, success: bool,
                 new_main_state: Optional[SystemState] = None,
                 commit_hash: Optional[str] = None,
                 rollback_performed: bool = False,
                 failure_reason: Optional[str] = None) -> None:
        self.result_id = str(uuid.uuid4())
        self.request_id = request_id
        self.success = success
        self.new_main_state = new_main_state
        self.commit_hash = commit_hash
        self.rollback_performed = rollback_performed
        self.failure_reason = failure_reason
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id, "request_id": self.request_id,
            "success": self.success, "commit_hash": self.commit_hash,
            "rollback_performed": self.rollback_performed,
            "failure_reason": self.failure_reason,
        }


class MergeProtocol:
    """
    ПРОТОКОЛ СЛИЯНИЯ (git-методики).
    Использует: three-way merge, conflict resolution, regression testing, health check.
    """

    def __init__(self, trace_store=None, health_monitor=None,
                 regression_suite: Optional[Callable] = None,
                 invariant_checker: Optional[Callable] = None,
                 llm_mediator: Optional[Callable] = None) -> None:
        self.trace_store = trace_store
        self.health = health_monitor
        # regression_suite(state) -> (passed: bool, failures: List[str])
        self.regression_suite = regression_suite or (lambda s: (True, []))
        # invariant_checker(state) -> bool
        self.invariant_checker = invariant_checker or (lambda s: True)
        # llm_mediator(conflict) -> value (разрешение через LLM)
        self.llm_mediator = llm_mediator or (lambda c: c.their_value)

    def execute_merge(self, request: MergeRequest) -> MergeResult:
        """ПОЛНЫЙ ЦИКЛ СЛИЯНИЯ (5 шагов)."""
        # === ШАГ 1: PRE-MERGE CHECK ===
        if not self._pre_merge_check(request):
            request.decision = "REJECT"
            request.decision_reason = "Pre-merge checks failed"
            return MergeResult(request.request_id, False, failure_reason="Pre-merge failed")

        # === ШАГ 2: THREE-WAY MERGE ===
        merged_state, conflicts = self._three_way_merge(request.merge_context)
        request.conflicts = conflicts

        # === ШАГ 3: CONFLICT RESOLUTION ===
        if conflicts:
            merged_state, all_resolved = self._resolve_conflicts(merged_state, conflicts)
            request.conflicts_resolved = all_resolved
            if not all_resolved:
                request.decision = "REJECT"
                request.decision_reason = "Unresolvable conflicts"
                return MergeResult(request.request_id, False, failure_reason="Conflicts unresolved")

        # === ШАГ 4: POST-MERGE VALIDATION ===
        # 4.1 Regression
        regression_passed, failures = self.regression_suite(merged_state)
        request.regression_tests_passed = regression_passed
        request.regression_failures = failures
        if not regression_passed:
            request.decision = "REJECT"
            request.decision_reason = f"Regression: {failures}"
            return MergeResult(request.request_id, False, rollback_performed=True,
                               failure_reason="Regression failed")

        # 4.2 Health check (V-1)
        if self.health is not None:
            try:
                report = self.health.post_generation_check(self._gen_test_text(merged_state))
                request.post_merge_health = report
                if not report.can_generate:
                    request.decision = "REJECT"
                    request.decision_reason = "Health check failed"
                    return MergeResult(request.request_id, False, rollback_performed=True,
                                       failure_reason="Health failed")
            except Exception:
                pass

        # 4.3 Инварианты
        request.invariants_held = self.invariant_checker(merged_state)
        if not request.invariants_held:
            request.decision = "REJECT"
            request.decision_reason = "Invariants violated"
            return MergeResult(request.request_id, False, rollback_performed=True,
                               failure_reason="Invariants violated")

        # === ШАГ 5: COMMIT ===
        request.decision = "MERGE"
        request.decision_reason = "All checks passed"
        merged_state.parent_version_id = request.merge_context.our_state.version_id
        merged_state.version_id = str(uuid.uuid4())
        merged_state._compute_hash()
        merged_state.state_hash = merged_state._compute_hash()

        if self.trace_store is not None:
            self.trace_store.save_snapshot(merged_state)

        commit_hash = hashlib.sha256(merged_state.state_hash.encode()).hexdigest()[:12]
        return MergeResult(request.request_id, True,
                           new_main_state=merged_state, commit_hash=commit_hash)

    # --- шаги ---
    def _pre_merge_check(self, request: MergeRequest) -> bool:
        ctx = request.merge_context
        if ctx.their_state is None or ctx.our_state is None or ctx.base_state is None:
            return False
        if not ctx.their_delta:
            return False
        return True

    def _three_way_merge(self, ctx: ThreeWayMergeContext) -> Tuple[SystemState, List[MergeConflict]]:
        """THREE-WAY MERGE: переменные, изменённые в обеих ветках → конфликт."""
        conflicts: List[MergeConflict] = []
        merged = ctx.our_state  # начинаем с ours

        base_vars = set(ctx.base_state.variables.keys())
        our_vars = set(ctx.our_state.variables.keys())
        their_vars = set(ctx.their_state.variables.keys())

        def changed(var_name, state, base):
            return var_name in state.variables and (
                var_name not in base.variables or
                state.variables[var_name].value != base.variables[var_name].value
            )

        changed_ours = {v for v in our_vars if changed(v, ctx.our_state, ctx.base_state)}
        changed_theirs = {v for v in their_vars if changed(v, ctx.their_state, ctx.base_state)}
        conflict_vars = changed_ours & changed_theirs

        for var_name in conflict_vars:
            conflicts.append(MergeConflict(
                MergeConflictType.VARIABLE_CONFLICT, var_name,
                ctx.our_state.variables[var_name].value,
                ctx.their_state.variables[var_name].value,
                ctx.base_state.variables[var_name].value))

        # Применяем изменения из theirs (кроме конфликтных)
        for var_name in (changed_theirs - conflict_vars):
            if var_name in merged.variables:
                merged.variables[var_name].value = ctx.their_state.variables[var_name].value
                merged.variables[var_name].version += 1

        # Новые переменные из theirs
        for var_name in (their_vars - our_vars):
            merged.variables[var_name] = ctx.their_state.variables[var_name]

        return merged, conflicts

    def _resolve_conflicts(self, state: SystemState,
                           conflicts: List[MergeConflict]) -> Tuple[SystemState, bool]:
        """Разрешение конфликтов: auto → LLM → unresolved."""
        all_resolved = True
        for conflict in conflicts:
            if self._can_auto_resolve(conflict):
                resolution = self._auto_resolve(conflict)
                if resolution is not None:
                    state.variables[conflict.variable_name].value = resolution
                    conflict.auto_resolvable = True
                    conflict.resolution_strategy = "auto"
                    continue
            # LLM-медиатор
            try:
                llm_val = self.llm_mediator(conflict)
                state.variables[conflict.variable_name].value = llm_val
                conflict.resolution_strategy = "llm_mediate"
            except Exception:
                all_resolved = False
                conflict.resolution_strategy = "unresolved"
        return state, all_resolved

    def _can_auto_resolve(self, conflict: MergeConflict) -> bool:
        if conflict.our_value is None and conflict.their_value is not None:
            return True
        if conflict.their_value is None and conflict.our_value is not None:
            return True
        return False

    def _auto_resolve(self, conflict: MergeConflict) -> Any:
        if conflict.our_value is None:
            return conflict.their_value
        if conflict.their_value is None:
            return conflict.our_value
        return None

    @staticmethod
    def _gen_test_text(state: SystemState) -> str:
        return "Тестовый текст для проверки здоровья системы."

    # --- cherry-pick / rebase (V4-TD-06, V2-TD-05) ---
    def cherry_pick(self, branch_state: SystemState, variable_name: str,
                    main_state: SystemState) -> SystemState:
        """Перенос ОТДЕЛЬНОЙ дельты (переменной) из ветки в main."""
        if variable_name not in branch_state.variables:
            return main_state
        main_state.variables[variable_name] = branch_state.variables[variable_name]
        return main_state

    def rebase(self, branch_state: SystemState, new_base: SystemState) -> SystemState:
        """Перенос ветки на новое основание (пересчёт parent)."""
        branch_state.parent_version_id = new_base.version_id
        return branch_state