# -*- coding: utf-8 -*-
"""
contracts.py — контракты Debt-Driven Cycle (V2).

Pydantic-модели: SectionDebt, AcademicParagraph, DraftSection, StateDelta.
Ядро: Draft → Gates → Debt → Surgery → ReGate, max_iterations=3.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    # фоллбэк: простые dataclass-подобные классы (без pydantic)
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self):
            return {k: v for k, v in self.__dict__.items()}

        def model_dump(self):
            return self.dict()

    def Field(default=None, **kw):
        return default


class DebtType(str, Enum):
    CITATION_MISSING = "citation_missing"
    CITATION_MISMATCH = "citation_mismatch"
    CLAIM_UNVERIFIED = "claim_unverified"
    LOGIC_GAP = "logic_gap"
    STYLE_VIOLATION = "style_violation"


class DebtSeverity(str, Enum):
    CRITICAL = "critical"
    MEDIUM = "medium"
    LOW = "low"


class ThreatLevel(str, Enum):
    """Иерархия угроз (V2-TD-NEW-01): уровень 0 = физические инварианты."""
    L0_PHYSICS = "L0_physics"          # нарушение физики (CatastrophicFailure)
    L1_FACTS = "L1_facts"              # неподтверждённые данные/цитаты
    L2_LOGIC = "L2_logic"              # логические разрывы
    L3_STYLE = "L3_style"              # стилистика


class SectionDebt(BaseModel):
    """Технический долг, обнаруженный гейтами."""
    debt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    paragraph_index: int = 0
    debt_type: DebtType = DebtType.LOGIC_GAP
    severity: DebtSeverity = DebtSeverity.MEDIUM
    threat_level: ThreatLevel = ThreatLevel.L2_LOGIC
    description: str = ""
    gate_source: str = ""              # "citation_trace", "verify_claims", ...
    suggested_fix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "debt_id": self.debt_id,
            "paragraph_index": self.paragraph_index,
            "debt_type": self.debt_type.value if hasattr(self.debt_type, 'value') else str(self.debt_type),
            "severity": self.severity.value if hasattr(self.severity, 'value') else str(self.severity),
            "threat_level": self.threat_level.value if hasattr(self.threat_level, 'value') else str(self.threat_level),
            "description": self.description,
            "gate_source": self.gate_source,
            "suggested_fix": self.suggested_fix,
        }


class AcademicParagraph(BaseModel):
    """Контракт абзаца: текст + клаймы + цитаты + долги."""
    paragraph_index: int = 0
    text: str = ""
    claims: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    debts: List[SectionDebt] = Field(default_factory=list)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paragraph_index": self.paragraph_index,
            "text": self.text,
            "claims": self.claims,
            "citations": self.citations,
            "debts": [d.to_dict() for d in self.debts],
            "version": self.version,
        }


class DraftSection(BaseModel):
    """Черновик секции: абзацы + итерации."""
    section_id: str = ""
    paragraphs: List[AcademicParagraph] = Field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 3

    @property
    def critical_debts(self) -> List[SectionDebt]:
        return [d for p in self.paragraphs for d in p.debts
                if d.severity == DebtSeverity.CRITICAL]

    @property
    def all_debts(self) -> List[SectionDebt]:
        return [d for p in self.paragraphs for d in p.debts]

    @property
    def is_approved(self) -> bool:
        return len(self.critical_debts) == 0

    def sorted_debts(self) -> List[SectionDebt]:
        """Сортировка по иерархии угроз (V2-TD-NEW-01)."""
        order = {ThreatLevel.L0_PHYSICS: 0, ThreatLevel.L1_FACTS: 1,
                 ThreatLevel.L2_LOGIC: 2, ThreatLevel.L3_STYLE: 3}
        return sorted(self.all_debts, key=lambda d: order.get(d.threat_level, 99))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
        }


class StateDelta(BaseModel):
    """Атомарное изменение состояния (для V2/V8)."""
    delta_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_component: str = "prose"      # "dom" | "prose" | "policy"
    variable_name: str = ""
    old_value: Any = None
    new_value: Any = None
    semantic_rationale: str = ""


class CatastrophicFailure(Exception):
    """Уровень 0: нарушение физических инвариантов (V2-TD-NEW-03)."""
    pass


class GateResult:
    """Результат прогона гейта: список ошибок."""
    def __init__(self) -> None:
        self.errors: List[Dict[str, Any]] = []

    def add(self, error_type: str, message: str, is_critical: bool = False,
            suggested_fix: Optional[str] = None) -> None:
        self.errors.append({
            "type": error_type,
            "message": message,
            "is_critical": is_critical,
            "suggested_fix": suggested_fix,
        })

    @property
    def ok(self) -> bool:
        return not self.errors