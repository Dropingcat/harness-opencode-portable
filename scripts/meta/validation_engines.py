# -*- coding: utf-8 -*-
"""
validation_engines.py — 5 детерминированных движков валидации (TD-163).

Спецификация (по архитектурной сессии):
  1. OntologyTypeChecker   (RULE_ONT_*)  — типы слотов
  2. RelationGraphValidator (RULE_REL_*) — физические связи (allowed/forbidden)
  3. EpistemicModalityChecker (RULE_EPI_*) — сила утверждения vs тип evidence
  4. BoundaryConditionValidator (RULE_BND_*) — границы применимости модели
  5. CompletenessChecker   (RULE_CMP_*)  — обязательные слоты

Каждый движок: validate(instance) -> List[ValidationError] (pydantic).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    class BaseModel:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)


class ValidationError(BaseModel):
    """Ошибка валидации от одного движка (pydantic)."""
    engine: str
    rule_id: str
    severity: str = "CRITICAL"   # CRITICAL | WARNING
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)

    def to_observation_line(self) -> str:
        ctx = f" Context: {self.context}" if self.context else ""
        return f"- [{self.severity}] {self.engine} ({self.rule_id}): {self.message}{ctx}"


class ValidationResult(BaseModel):
    """Результат конвейера движков."""
    status: str = "PASS"          # PASS | FAIL
    errors: List[ValidationError] = Field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(e.severity == "CRITICAL" for e in self.errors)

    def to_observation(self) -> str:
        if self.status == "PASS":
            return "Observation: PASS. No validation errors."
        obs = "Observation: VALIDATION FAILED.\n"
        for e in self.errors:
            obs += e.to_observation_line() + "\n"
        return obs


# ---------------------------------------------------------------- база знаний

class KnowledgeBase:
    """Матрицы allowed/forbidden relations + типы + evidence requirements."""

    def __init__(self) -> None:
        # типы сущностей
        self.entity_types: Dict[str, str] = {}        # entity_id -> type
        self.allowed_slot_types: Dict[str, List[str]] = {}  # slot -> [types]
        # relations
        self.allowed_relations: Dict[str, List[Dict]] = {}  # entity -> [{relation, target_type}]
        self.forbidden_relations: Dict[str, List[Dict]] = {}
        # epistemic
        self.evidence_types: Dict[str, str] = {}      # evidence_id -> indirect/direct
        self.requires_cross_check: Set[str] = set()   # claims
        # boundaries
        self.model_boundaries: Dict[str, List[Dict]] = {}  # model -> [{param, condition}]

    def add_entity(self, eid: str, etype: str) -> None:
        self.entity_types[eid] = etype

    def allow_relation(self, eid: str, relation: str, target_type: str) -> None:
        self.allowed_relations.setdefault(eid, []).append(
            {"relation": relation, "target_type": target_type})

    def forbid_relation(self, eid: str, relation: str, target_type: str) -> None:
        self.forbidden_relations.setdefault(eid, []).append(
            {"relation": relation, "target_type": target_type})

    def set_allowed_slot_types(self, slot: str, types: List[str]) -> None:
        self.allowed_slot_types[slot] = types

    def set_evidence_type(self, eid: str, etype: str) -> None:
        self.evidence_types[eid] = etype

    def set_requires_cross_check(self, claim_id: str) -> None:
        self.requires_cross_check.add(claim_id)

    def add_model_boundary(self, model_id: str, param: str, condition: str) -> None:
        self.model_boundaries.setdefault(model_id, []).append(
            {"param": param, "condition": condition})


# ---------------------------------------------------------------- 5 движков

class OntologyTypeChecker:
    """Движок 1: типы слотов (RULE_ONT_*)."""

    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb

    def validate(self, instance: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        for slot_name, slot in instance.get('slots', {}).items():
            allowed = self.kb.allowed_slot_types.get(slot_name)
            if not allowed:
                continue
            eid = slot.get('entity_id')
            etype = self.kb.entity_types.get(eid)
            if etype and etype not in allowed:
                errors.append(ValidationError(
                    engine="OntologyTypeChecker", rule_id="RULE_ONT_01",
                    message=f"Слот '{slot_name}' не принимает тип '{etype}' (разрешены: {allowed})",
                    context={"slot": slot_name, "entity": eid, "actual_type": etype,
                             "allowed_types": allowed}))
        return errors


class RelationGraphValidator:
    """Движок 2: физические связи (RULE_REL_*)."""

    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb

    def validate(self, instance: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        slots = instance.get('slots', {})
        data_eid = slots.get('data', {}).get('entity_id')
        claim_eid = slots.get('claim', {}).get('entity_id')
        relation = slots.get('relation', {}).get('value', 'proves')

        # проверяем forbidden
        for src_eid, target_eid, rel in [(data_eid, claim_eid, relation)]:
            if not src_eid or not target_eid:
                continue
            forb = self.kb.forbidden_relations.get(src_eid, [])
            target_type = self.kb.entity_types.get(target_eid)
            for f in forb:
                if f['relation'] == rel and (not f.get('target_type') or f['target_type'] == target_type):
                    errors.append(ValidationError(
                        engine="RelationGraphValidator", rule_id="RULE_REL_04",
                        message=f"Запрещённая связь: '{src_eid}' {rel} '{target_eid}'",
                        context={"source": src_eid, "relation": rel, "target": target_eid,
                                 "target_type": target_type}))
            # allowed?
            allow = self.kb.allowed_relations.get(src_eid, [])
            if allow and not any(a['relation'] == rel for a in allow):
                errors.append(ValidationError(
                    engine="RelationGraphValidator", rule_id="RULE_REL_01",
                    message=f"Связь '{rel}' не разрешена для '{src_eid}'",
                    context={"source": src_eid, "relation": rel, "target": target_eid}))
        return errors


class EpistemicModalityChecker:
    """Движок 3: сила утверждения vs тип evidence (RULE_EPI_*)."""

    STRONG_MODALITIES = {"proves", "demonstrates", "undoubtedly", "доказывает", "устанавливает"}

    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb

    def validate(self, instance: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        slots = instance.get('slots', {})
        claim_eid = slots.get('claim', {}).get('entity_id')
        data_eid = slots.get('data', {}).get('entity_id')
        modality = slots.get('claim', {}).get('modality', 'proves')

        if data_eid and self.kb.evidence_types.get(data_eid) == 'indirect':
            if modality in self.STRONG_MODALITIES:
                errors.append(ValidationError(
                    engine="EpistemicModalityChecker", rule_id="RULE_EPI_02",
                    message=f"Косвенное свидетельство '{data_eid}' не может использовать "
                            f"модальность '{modality}'",
                    context={"evidence_type": "indirect", "modality_used": modality,
                             "required_modality": "suggests or requires cross-check"}))

        if claim_eid and claim_eid in self.kb.requires_cross_check:
            has_cross = any(s.get('type') == 'cross_check' for s in slots.values())
            if not has_cross and modality in self.STRONG_MODALITIES:
                errors.append(ValidationError(
                    engine="EpistemicModalityChecker", rule_id="RULE_EPI_03",
                    message=f"Claim '{claim_eid}' требует cross-check для сильной модальности",
                    context={"claim": claim_eid, "modality": modality}))
        return errors


class BoundaryConditionValidator:
    """Движок 4: границы применимости (RULE_BND_*)."""

    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb

    def validate(self, instance: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        slots = instance.get('slots', {})
        warrant_eid = slots.get('warrant', {}).get('entity_id')
        conditions = instance.get('conditions', {})
        if not warrant_eid:
            return errors
        for bound in self.kb.model_boundaries.get(warrant_eid, []):
            param = bound['param']
            condition = bound['condition']  # напр. "> Tc" или "< Tc"
            if param in conditions:
                val = conditions[param]
                # упрощённая проверка: condition "> Tc" => val > Tc
                if '> Tc' in condition and val <= conditions.get('Tc', val):
                    errors.append(ValidationError(
                        engine="BoundaryConditionValidator", rule_id="RULE_BND_01",
                        message=f"Модель '{warrant_eid}' неприменима при {param}={val} "
                                f"(условие {condition})",
                        context={"model": warrant_eid, "param": param,
                                 "value": val, "condition": condition}))
        return errors


class CompletenessChecker:
    """Движок 5: обязательные слоты (RULE_CMP_*)."""

    def __init__(self, kb: KnowledgeBase, mandatory_slots: Optional[List[str]] = None) -> None:
        self.kb = kb
        self.mandatory = mandatory_slots or ['data', 'claim', 'warrant']

    def validate(self, instance: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        slots = instance.get('slots', {})
        for slot_name in self.mandatory:
            if slot_name not in slots or slots[slot_name].get('entity_id') is None:
                errors.append(ValidationError(
                    engine="CompletenessChecker", rule_id="RULE_CMP_01",
                    message=f"Отсутствует обязательный слот '{slot_name}'",
                    context={"template": instance.get('template', '?'),
                             "missing_slot": slot_name}))
        return errors


# ---------------------------------------------------------------- конвейер

class ValidationPipeline:
    """Конвейер из 5 движков."""

    def __init__(self, kb: KnowledgeBase,
                 mandatory_slots: Optional[List[str]] = None) -> None:
        self.engines = [
            OntologyTypeChecker(kb),
            RelationGraphValidator(kb),
            EpistemicModalityChecker(kb),
            BoundaryConditionValidator(kb),
            CompletenessChecker(kb, mandatory_slots),
        ]

    def validate(self, instance: Dict[str, Any]) -> ValidationResult:
        errors: List[ValidationError] = []
        for engine in self.engines:
            errors.extend(engine.validate(instance))
        status = "PASS" if not errors else "FAIL"
        return ValidationResult(status=status, errors=errors)

    def validate_instance(self, inst) -> ValidationResult:
        """Принимает AuditorInstance (react_auditor) или dict."""
        if hasattr(inst, 'slots'):
            d = inst.to_dict() if hasattr(inst, 'to_dict') else {"slots": inst.slots}
        else:
            d = inst
        return self.validate(d)