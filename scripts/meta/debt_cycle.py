# -*- coding: utf-8 -*-
"""
debt_cycle.py — V2 Debt-Driven Cycle.

Draft → Gates → Debt → Surgery → ReGate (max_iterations=3).
Поверх существующих гейтов (citation_trace, verify_claims) через GateAdapter.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from contracts import (AcademicParagraph, CatastrophicFailure, DraftSection,
                       DebtSeverity, DebtType, GateResult, SectionDebt,
                       ThreatLevel)


class GateAdapter:
    """Адаптирует существующий гейт к интерфейсу Debt-Driven Cycle."""

    def __init__(self, gate_function: Callable, gate_name: str,
                 error_map: Optional[dict] = None) -> None:
        self.gate_function = gate_function
        self.gate_name = gate_name
        # маппинг типов ошибок гейта -> DebtType
        self.error_map = error_map or {
            "missing_citation": DebtType.CITATION_MISSING,
            "citation_mismatch": DebtType.CITATION_MISMATCH,
            "unverified_claim": DebtType.CLAIM_UNVERIFIED,
        }

    def __call__(self, draft: DraftSection) -> GateResult:
        """Прогон гейта по всем абзацам, сбор долгов в draft."""
        result = GateResult()
        for para in draft.paragraphs:
            try:
                # гейт возвращает GateResult (или объект с .errors)
                gate_result = self.gate_function(para.text, para.citations, para.claims)
                if gate_result is None:
                    continue
                errors = gate_result.errors if hasattr(gate_result, 'errors') else gate_result
                for err in errors:
                    etype = err.get('type', 'logic_gap')
                    debt = SectionDebt(
                        paragraph_index=para.paragraph_index,
                        debt_type=self.error_map.get(etype, DebtType.LOGIC_GAP),
                        severity=DebtSeverity.CRITICAL if err.get('is_critical') else DebtSeverity.MEDIUM,
                        threat_level=self._map_threat(etype),
                        description=err.get('message', ''),
                        gate_source=self.gate_name,
                        suggested_fix=err.get('suggested_fix'),
                    )
                    para.debts.append(debt)
                    result.add(etype, err.get('message', ''), err.get('is_critical', False))
            except CatastrophicFailure:
                raise
            except Exception as e:
                result.add('gate_error', f'[{self.gate_name}] {e}', is_critical=True)
        return result

    @staticmethod
    def _map_threat(error_type: str) -> ThreatLevel:
        if error_type in ('dimensional_mismatch', 'physics_error'):
            return ThreatLevel.L0_PHYSICS
        if error_type in ('unverified_claim', 'missing_citation', 'citation_mismatch'):
            return ThreatLevel.L1_FACTS
        if error_type in ('logic_gap', 'transition_break'):
            return ThreatLevel.L2_LOGIC
        return ThreatLevel.L3_STYLE


class DebtDrivenCycle:
    """Цикл: гейты → долги → точечная хирургия → перегейт."""

    def __init__(self, gates: List[Callable], resolver: Callable,
                 max_iterations: int = 3) -> None:
        self.gates = gates
        self.resolver = resolver          # resolver(draft, debt) -> DraftSection
        self.max_iterations = max_iterations
        self.history: List[dict] = []

    def run(self, initial_draft: DraftSection) -> DraftSection:
        draft = initial_draft
        draft.max_iterations = self.max_iterations

        for iteration in range(self.max_iterations):
            draft.iteration = iteration

            # 1. Прогон через гейты
            for gate in self.gates:
                try:
                    gate(draft)
                except CatastrophicFailure as cf:
                    # Level 0: немедленная остановка (V2-TD-NEW-03)
                    self.history.append({'iteration': iteration,
                                         'action': 'catastrophic_failure',
                                         'reason': str(cf)})
                    raise

            # 2. Проверка сходимости
            if draft.is_approved:
                self.history.append({'iteration': iteration,
                                     'action': 'approved',
                                     'debts': len(draft.all_debts)})
                break

            # 3. Точечная хирургия (по иерархии угроз)
            sorted_debts = draft.sorted_debts()
            self.history.append({'iteration': iteration,
                                 'action': 'surgery',
                                 'debts': len(sorted_debts)})
            for debt in sorted_debts:
                if debt.severity == DebtSeverity.CRITICAL:
                    draft = self.resolver(draft, debt)

            # 4. Очистка решённых CRITICAL
            for para in draft.paragraphs:
                para.debts = [d for d in para.debts
                              if d.severity != DebtSeverity.CRITICAL]

        # Откат при несходимости: последний валидный + нерешённые долги
        self.history.append({'iteration': draft.iteration,
                             'action': 'final',
                             'approved': draft.is_approved,
                             'remaining_debts': len(draft.all_debts)})
        return draft

    def summary(self) -> List[dict]:
        return self.history


class ParagraphResolver:
    """Типичный resolver: перегенерировать абзац по долгу.

    Требует функцию regenerate(para_text, debt) -> new_text.
    """

    def __init__(self, regenerate: Callable, flashback_depth: int = 3) -> None:
        self._regenerate = regenerate
        self.flashback_depth = flashback_depth
        self._attempts = {}

    def __call__(self, draft: DraftSection, debt: SectionDebt) -> DraftSection:
        para = draft.paragraphs[debt.paragraph_index]
        key = (debt.paragraph_index, debt.debt_id)
        self._attempts[key] = self._attempts.get(key, 0) + 1

        if self._attempts[key] > self.flashback_depth:
            # Flashback: возвращаем как есть (долг останется)
            return draft

        new_text = self._regenerate(para.text, debt)
        if new_text and new_text != para.text:
            para.text = new_text
            para.version += 1
        return draft