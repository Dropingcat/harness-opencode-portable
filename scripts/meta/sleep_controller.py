# -*- coding: utf-8 -*-
"""
sleep_controller.py — ПРИНУДИТЕЛЬНЫЙ СОН оркестратора (через pipeline).

Когда внешний аудитор фиксирует КРИТИЧЕСКИЙ демедж:
  1. SleepController получает приказ (order) от аудитора.
  2. Формирует авто-контракт сна: техдолги (от аудитора) → ветки.
  3. Оркестратор «засыпает»: его задача приостанавливается, активируется спец-агент.
  4. Спец-агент (sub-агент) разбирает техдолги в git-ветках, устраняет причины урона.
  5. Критерий выхода: ВСЕ ветки слиты без багов и без увода от исходной задачи.
  6. Ветка сна сливается с главной; оркестратор «просыпается» и продолжает.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from external_auditor import ExternalAuditor
from orchestrator_integration import OrchestratorIntegration
from trace_store import TraceEntry


class SleepContract:
    """Авто-контракт сна: техдолги → ветки, критерий выхода."""

    def __init__(self, orchestrator: str, debts: List[Dict[str, Any]],
                 exit_criteria: str, auditor_id: str) -> None:
        self.contract_id = str(uuid.uuid4())[:8]
        self.orchestrator = orchestrator
        self.debts = debts                      # [{debt_id, source, target, description, repair_hint}]
        self.exit_criteria = exit_criteria
        self.auditor_id = auditor_id
        self.branches: List[str] = []           # git-ветки, по одной на долг
        self.merged = False
        self.created_at = datetime.now().isoformat()

    def assign_branches(self) -> List[str]:
        """Каждому техдолгу — своя ветка fix/<debt_id>."""
        self.branches = [f"fix/{d['debt_id']}" for d in self.debts]
        return self.branches

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "orchestrator": self.orchestrator,
            "debts": self.debts,
            "branches": self.branches,
            "exit_criteria": self.exit_criteria,
            "auditor_id": self.auditor_id,
            "merged": self.merged,
        }


class SleepController:
    """Управляет циклом сна оркестратора (через pipeline)."""

    def __init__(self, orchestrator_integration: OrchestratorIntegration,
                 auditor: ExternalAuditor,
                 special_agent_fn: Optional[Any] = None) -> None:
        self.meta = orchestrator_integration
        self.auditor = auditor
        # спец-агент: функция разбора техдолгов (внедряемая)
        #   fn(contract) -> {merged: bool, result: str}
        self.special_agent = special_agent_fn or self._default_special_agent
        self.sleeps: List[Dict[str, Any]] = []
        self.force_sleep_threshold = -50.0

    # ------------------------------------------------------ основной цикл

    def check_and_force_sleep(self, artifact: Any,
                              orchestrator_task: str) -> Optional[SleepContract]:
        """
        ﻿Наблюдатель (аудитор) → критический демедж → принудительный сон.
        Возвращает SleepContract, если сон начат; None — если всё в норме.
        """
        # 1. Аудитор наблюдает (независимо)
        findings = self.auditor.observe(artifact)
        if not self.auditor.should_force_sleep(self.force_sleep_threshold):
            return None

        # 2. Приказ на сон (авто-контракт)
        order = self.auditor.order_sleep(self.meta.orchestrator,
                                         reason=findings[-1].message if findings else "критический демедж")
        contract = SleepContract(
            orchestrator=self.meta.orchestrator,
            debts=order['contract']['debts'],
            exit_criteria=order['contract']['exit_criteria'],
            auditor_id=self.auditor.auditor_id,
        )
        contract.assign_branches()

        # 3. Оркестратор уходит в сон
        sleep_id = self.meta.sleep_begin(orchestrator_task, branches=contract.branches)
        contract.contract_id = sleep_id

        # 4. Спец-агент разбирает техдолги (ветки)
        result = self.special_agent(contract)

        # 5. Критерий выхода: все ветки слиты без багов
        if result.get('merged'):
            self.meta.sleep_merge(success=True, result_summary=result.get('result', ''))
            contract.merged = True
        else:
            self.meta.sleep_merge(success=False, result_summary=result.get('result', 'не слито'))
        self.sleeps.append(contract.to_dict())
        return contract

    def resume(self, orchestrator_task: str) -> None:
        """После сна оркестратор просыпается и продолжает."""
        self.meta.trace.append(TraceEntry('V2', 'sleep_resume',
                                          {'task': orchestrator_task[:60]}))

    # ------------------------------------------------------ спец-агент по умолчанию

    def _default_special_agent(self, contract: SleepContract) -> Dict[str, Any]:
        """Заглушка: в реальной системе — sub-агент с git-ветками.
        Здесь: имитация merge без багов."""
        # ветки: каждая устраняет свой долг
        for debt in contract.debts:
            self.meta.on_failure(f"[sleep-fix] {debt['debt_id']}: {debt['description']}",
                                 task=f"fix {debt['target']}",
                                 tags=['sleep', debt['source']])
        return {"merged": True, "result": f"merged {len(contract.branches)} branches"}