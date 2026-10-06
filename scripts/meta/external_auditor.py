# -*- coding: utf-8 -*-
"""
external_auditor.py — ВНЕШНИЙ АУДИТОР (независимый параллельный агент).

КРИТИЧЕСКИ ВАЖНО: аудитор НЕ связан с оркестратором.
- разные переменные (auditor_* vs orchestrator_*)
- разные промпты, скиллы, тулзы, задачи
- работает ВСЕГДА (наблюдает), независимо от оркестратора
- при критическом демедже ИНИЦИИРУЕТ принудительный сон оркестратора

Каналы (по спецификации ReAct-валидатора):
  1. CompletenessChecker   (RULE_CMP_*)
  2. RelationGraphValidator (RULE_REL_*)
  3. EpistemicModalityChecker (RULE_EPI_*)
  4. BoundaryConditionValidator (RULE_BND_*)
  5. OntologyTypeChecker   (RULE_ONT_*)
  + Физический валидатор (размерности)
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# аудитор имеет СОБСТВЕННЫЙ state (не пересекается с оркестраторным)
_AUDITOR_STATE = Path(os.environ.get(
    'HARNESS_AUDITOR_STATE', str(Path(__file__).parent.parent.parent / '.auditor_state')))


class AuditFinding:
    """Находка аудитора (причина урона)."""

    __slots__ = ("finding_id", "engine", "rule_id", "severity", "message",
                 "context", "target", "timestamp")

    def __init__(self, engine: str, rule_id: str, severity: str,
                 message: str, context: Optional[Dict[str, Any]] = None,
                 target: str = "") -> None:
        self.finding_id = str(uuid.uuid4())
        self.engine = engine
        self.rule_id = rule_id
        self.severity = severity          # CRITICAL | WARNING
        self.message = message
        self.context = context or {}
        self.target = target              # что именно (абзац/клайм/слот)
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {"finding_id": self.finding_id, "engine": self.engine,
                "rule_id": self.rule_id, "severity": self.severity,
                "message": self.message, "context": self.context,
                "target": self.target, "timestamp": self.timestamp}


class ExternalAuditor:
    """
    Параллельный наблюдатель. НЕ вызывается оркестратором — работает сам.
    Имеет собственные движки, state, переменные, промпт.
    """

    def __init__(self, auditor_id: str = "external",
                 validator_fn: Optional[Callable[[Any], List[AuditFinding]]] = None,
                 state_dir: Optional[str] = None) -> None:
        self.auditor_id = auditor_id
        self._validator = validator_fn    # внедряемый валидатор (5 движков)
        self.state_dir = Path(state_dir) if state_dir else _AUDITOR_STATE
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f'{auditor_id}_state.json'
        self.findings: List[AuditFinding] = []
        self.observations = 0
        self.last_verdict = "OK"
        self.sleep_orders: List[Dict[str, Any]] = []   # приказы на сон оркестратору
        self._load()

    # ------------------------------------------------------ независимый цикл

    def observe(self, artifact: Any) -> List[AuditFinding]:
        """Наблюдение за артефактом оркестратора (независимо)."""
        self.observations += 1
        if self._validator:
            new = self._validator(artifact)
        else:
            new = self._default_scan(artifact)
        self.findings.extend(new)
        self.last_verdict = "FAIL" if any(f.severity == "CRITICAL" for f in new) else "OK"
        self._save()
        return new

    def critical_damage(self) -> float:
        """Суммарный критический урон от текущих находок (для решения о сне)."""
        crit = [f for f in self.findings if f.severity == "CRITICAL"]
        return -25.0 * len(crit[-5:])   # последние 5 критических

    def should_force_sleep(self, threshold: float = -50.0) -> bool:
        """Критический демедж → принудительный сон оркестратора."""
        return self.critical_damage() <= threshold

    def order_sleep(self, orchestrator: str, reason: str) -> Dict[str, Any]:
        """Выдать приказ на сон (авто-контракт для спец-агента)."""
        order = {
            "order_id": str(uuid.uuid4())[:8],
            "orchestrator": orchestrator,
            "reason": reason,
            "findings": [f.to_dict() for f in self.findings[-10:]],
            "issued_at": datetime.now().isoformat(),
            "contract": self._build_sleep_contract(),
        }
        self.sleep_orders.append(order)
        self._save()
        return order

    # ------------------------------------------------------ контракт сна

    def _build_sleep_contract(self) -> Dict[str, Any]:
        """Авто-контракт: техдолги, разобранные из находок аудитора."""
        debts = []
        for f in self.findings[-10:]:
            if f.severity == "CRITICAL":
                debts.append({
                    "debt_id": f.rule_id,
                    "source": f.engine,
                    "target": f.target,
                    "description": f.message,
                    "repair_hint": f"устранить {f.rule_id} в {f.target}",
                })
        return {
            "orchestrator": "SLEEP",
            "debts": debts,
            "exit_criteria": "все ветки слиты без багов и без увода от задачи",
            "auditor": self.auditor_id,
        }

    # ------------------------------------------------------ независимый промпт

    @property
    def auditor_prompt(self) -> str:
        """Собственный промпт аудитора (НЕ общий с оркестратором)."""
        return (
            f"[EXTERNAL-AUDITOR:{self.auditor_id}] observations={self.observations} "
            f"verdict={self.last_verdict} critical_findings={sum(1 for f in self.findings if f.severity=='CRITICAL')}"
        )

    @property
    def auditor_variables(self) -> Dict[str, Any]:
        """Собственные переменные (auditor_* namespace)."""
        return {
            "auditor_id": self.auditor_id,
            "auditor_observations": self.observations,
            "auditor_verdict": self.last_verdict,
            "auditor_critical": sum(1 for f in self.findings if f.severity == "CRITICAL"),
            "auditor_damage": self.critical_damage(),
        }

    # ------------------------------------------------------ внутренние

    def _default_scan(self, artifact: Any) -> List[AuditFinding]:
        """Сканирование по умолчанию: ищем 'ошибку'/'доказывает' в тексте."""
        findings = []
        text = str(artifact)
        if 'доказывает' in text.lower() and 'XRD' in text:
            findings.append(AuditFinding('RelationGraph', 'RULE_REL_04', 'CRITICAL',
                                         "XRD не может 'доказывать' механизм",
                                         target='claim'))
        if 'warrant' not in text.lower() and 'обоснован' not in text.lower():
            findings.append(AuditFinding('Completeness', 'RULE_CMP_01', 'WARNING',
                                         "нет warrant/обоснования", target='paragraph'))
        return findings

    def _save(self) -> None:
        data = {
            'auditor_id': self.auditor_id,
            'observations': self.observations,
            'last_verdict': self.last_verdict,
            'findings': [f.to_dict() for f in self.findings[-50:]],
            'sleep_orders': self.sleep_orders[-10:],
            'saved_at': datetime.now().isoformat(),
        }
        self.state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                   encoding='utf-8')

    def _load(self) -> None:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding='utf-8'))
                self.observations = data.get('observations', 0)
                self.last_verdict = data.get('last_verdict', 'OK')
                for f in data.get('findings', []):
                    self.findings.append(AuditFinding(
                        f['engine'], f['rule_id'], f['severity'],
                        f['message'], f.get('context'), f.get('target', '')))
                self.sleep_orders = data.get('sleep_orders', [])
            except Exception:
                pass