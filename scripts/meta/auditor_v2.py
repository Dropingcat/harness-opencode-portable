# -*- coding: utf-8 -*-
"""
auditor_v2.py — ВНЕШНИЙ АУДИТОР с ДИНАМИЧЕСКИМИ КОНТРАКТАМИ.

Ключевые принципы (жёсткая критика агентных систем):
1. Аудитор НЕ может договориться с оркестратором:
   - нет shared-переменных, нет общего контекста
   - только канал: аудитор → корзина урона (файл)
   - промпт аудитора формируется ИЗВНЕ (скриптом), не оркестратором
2. Динамические контракты: привязаны к ТЕКУЩИМ промптам оркестратора
   (валидируются на соответствие инвариантам оркестратора).
3. Изоляция контекста: аудитор видит только артефакт + свои правила;
   никогда — внутреннее состояние оркестратора.
4. Аудитор бросает техдолги в корзину; урон считает скрипт (DamageBasket);
   при пороге 100 — скрипт сна (SleepController).
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_META = Path(__file__).parent
if str(_META) not in sys.path:
    sys.path.insert(0, str(_META))

from damage_basket import DamageBasket, DamageEntry


class AuditorContract:
    """Динамический контракт аудита (генерируется скриптом под промпт оркестратора)."""

    def __init__(self, orchestrator: str, orchestrator_prompt_hash: str,
                 rules: List[Dict[str, Any]],
                 scope: List[str]) -> None:
        self.contract_id = str(uuid.uuid4())[:8]
        self.orchestrator = orchestrator
        self.prompt_hash = orchestrator_prompt_hash   # хэш промпта оркестратора
        self.rules = rules                            # [{rule_id, engine, severity, check}]
        self.scope = scope                            # что проверять
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {"contract_id": self.contract_id, "orchestrator": self.orchestrator,
                "prompt_hash": self.prompt_hash, "rules": self.rules,
                "scope": self.scope, "created_at": self.created_at}


class ExternalAuditorV2:
    """
    Изолированный аудитор. Работает всегда. НЕ имеет доступа к состоянию оркестратора.
    Канал наружу — ТОЛЬКО корзина урона.
    """

    def __init__(self, auditor_id: str = "external-v2",
                 basket: Optional[DamageBasket] = None,
                 rules_loader: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None,
                 state_dir: Optional[str] = None,
                 hardcore: bool = False) -> None:
        self.auditor_id = auditor_id
        self.basket = basket or DamageBasket(state_dir)
        self.rules_loader = rules_loader or (self._hardcore_rules if hardcore else self._default_rules)
        self.hardcore = hardcore
        self.state_dir = Path(state_dir) if state_dir else Path(os.environ.get(
            'HARNESS_AUDITOR_V2_STATE', str(Path(__file__).parent.parent.parent / '.auditor_v2_state')))
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.contract: Optional[AuditorContract] = None
        self.observations = 0
        # хардкор: всегда гоняем 5 движков на структуру
        self._pipe = self._build_validation_pipe()

    # ------------------------------------------------------ цикл наблюдения

    def bind_contract(self, orchestrator: str, orchestrator_prompt: str,
                      scope: Optional[List[str]] = None) -> AuditorContract:
        """Скрипт формирует контракт ПОД ТЕКУЩИЙ промпт оркестратора."""
        prompt_hash = self._hash(orchestrator_prompt)
        rules = self.rules_loader(orchestrator, prompt_hash)
        self.contract = AuditorContract(orchestrator, prompt_hash, rules,
                                        scope or self._default_scope(orchestrator))
        return self.contract

    def observe_and_audit(self, artifact: Any) -> List[DamageEntry]:
        """
        ХАРДКОР-наблюдение: 5 движков (структура) + все правила + эскалация.
        Каждый такт — максимальное давление.
        """
        self.observations += 1
        if self.contract is None:
            self.bind_contract('unknown', str(artifact))
        dropped: List[DamageEntry] = []

        # 1. Структурные находки от 5 движков (всегда, если dict)
        struct = self._struct_findings(artifact)
        for f in struct:
            entry = DamageEntry(f['rule_id'], f['engine'], f['severity'],
                                f['message'], f['target'], self.auditor_id)
            self.basket.drop(entry)
            dropped.append(entry)

        # 2. Текстовые правила контракта
        text = str(artifact) if not isinstance(artifact, dict) else json.dumps(artifact, ensure_ascii=False)
        for rule in self.contract.rules:
            if rule.get('check_fn') and rule['rule_id'] == 'RULE_STRUCT':
                continue  # структура уже проверена выше
            try:
                if self._check_rule(rule, artifact):
                    entry = DamageEntry(
                        rule_id=rule['rule_id'], engine=rule['engine'],
                        severity=rule['severity'], message=rule['message'],
                        target=rule.get('target', ''), auditor_id=self.auditor_id)
                    self.basket.drop(entry)
                    dropped.append(entry)
            except Exception:
                continue

        # 2b. Текстовые эвристики (TD-180): даже для строковых артефактов
        # TODO/FIXME/XXX, отсутствие чисел, «который»/вода -> DamageEntry
        import re as _re
        _txt = text.lower()
        _heuristics = []
        if _re.search(r"\b(todo|fixme|xxx)\b", _txt):
            _heuristics.append(("TEXT_TODO", "CRITICAL",
                                "Найдены незакрытые TODO/FIXME/XXX — артефакт неполон"))
        if not _re.search(r"\d", _txt) and len(text) > 20:
            _heuristics.append(("TEXT_NO_NUMBERS", "WARNING",
                                "Нет числовых данных/обоснований (для научного текста)"))
        if _re.search(r"который|которая|которые|и является|представляет собой", _txt):
            _heuristics.append(("TEXT_WATER", "WARNING",
                                "Водянистые конструкции («который», «является») — снижают точность"))
        for rid, sev, msg in _heuristics:
            entry = DamageEntry(rule_id=rid, engine="text_heuristics", severity=sev,
                                message=msg, target="text", auditor_id=self.auditor_id)
            self.basket.drop(entry)
            dropped.append(entry)

        # 3. Хардкор: дополнительный прогон по всем хардкор-правилам (эскалация)
        if self.hardcore and self.contract:
            for rule in self._hardcore_rules(self.contract.orchestrator, self.contract.prompt_hash):
                if rule['rule_id'] == 'RULE_STRUCT':
                    continue
                try:
                    if self._check_rule(rule, artifact):
                        entry = DamageEntry(
                            rule_id=rule['rule_id'], engine=rule['engine'],
                            severity=rule['severity'], message=rule['message'],
                            target=rule.get('target', ''), auditor_id=self.auditor_id)
                        self.basket.drop(entry)
                        dropped.append(entry)
                except Exception:
                    continue
        return dropped

    def basket_damage(self) -> int:
        """Текущий урон (считает скрипт)."""
        return self.basket.total_damage()

    # ------------------------------------------------------ динамические правила

    def _check_rule(self, rule: Dict[str, Any], artifact: Any) -> bool:
        """Проверка правила. Может использовать детерминированные движки
        (validation_engines) или callback."""
        check_fn = rule.get('check_fn')
        if check_fn:
            return bool(check_fn(artifact))
        # дефолт: текстовая проверка
        text = str(artifact)
        pattern = rule.get('pattern')
        if pattern:
            return pattern.lower() in text.lower()
        return False

    def _build_validation_pipe(self):
        """Конвейер 5 движков (Ontology/Relation/Epistemic/Boundary/Completeness)."""
        try:
            from validation_engines import KnowledgeBase, ValidationPipeline
            kb = KnowledgeBase()
            kb.add_entity('OBS_XRD_FWHM', 'Observable')
            kb.add_entity('OBS_XRD_PHASE', 'Observable')
            kb.add_entity('CLAIM_MECH', 'Mechanism')
            kb.add_entity('CLAIM_PROP', 'PhysicalProperty')
            kb.set_allowed_slot_types('data', ['Observable', 'PhysicalProperty'])
            kb.set_allowed_slot_types('claim', ['Mechanism', 'PhysicalProperty'])
            kb.forbid_relation('OBS_XRD_FWHM', 'proves', 'Mechanism')
            kb.forbid_relation('OBS_XRD_PHASE', 'proves', 'Mechanism')
            kb.allow_relation('OBS_XRD_FWHM', 'indicates', 'PhysicalProperty')
            kb.allow_relation('OBS_XRD_PHASE', 'indicates', 'PhysicalProperty')
            kb.set_evidence_type('OBS_XRD_FWHM', 'indirect')
            kb.set_evidence_type('OBS_XRD_PHASE', 'indirect')
            return ValidationPipeline(kb)
        except Exception:
            return None

    def _struct_findings(self, artifact):
        """Прогон 5 движков на структуру (dict со слотами)."""
        if self._pipe is None or not isinstance(artifact, dict):
            return []
        result = self._pipe.validate_instance(artifact)
        findings = []
        for e in result.errors:
            sev = 'CRITICAL' if e.severity == 'CRITICAL' else 'WARNING'
            findings.append({
                'rule_id': e.rule_id, 'engine': e.engine, 'severity': sev,
                'message': e.message, 'target': e.context.get('missing_slot')
                or e.context.get('target') or e.context.get('source') or 'slots',
            })
        return findings

    def _hardcore_rules(self, orchestrator: str, prompt_hash: str) -> List[Dict[str, Any]]:
        """ХАРДКОР-правила: агрессивные, больше нарушений, эскалация."""
        return [
            # структура (5 движков) — критично
            {"rule_id": "RULE_STRUCT", "engine": "Structure", "severity": "CRITICAL",
             "message": "структура нарушает 5 движков", "target": "slots", "check_fn": None},
            # физика
            {"rule_id": "RULE_REL_04", "engine": "RelationGraph", "severity": "CRITICAL",
             "message": "XRD не может 'доказывать' механизм", "pattern": "доказывает", "target": "claim"},
            {"rule_id": "RULE_REL_01", "engine": "RelationGraph", "severity": "CRITICAL",
             "message": "связь не разрешена в графе знаний", "pattern": "указывает", "target": "claim"},
            # epistemic
            {"rule_id": "RULE_EPI_02", "engine": "Epistemic", "severity": "WARNING",
             "message": "косвенное с сильной модальностью", "pattern": "устанавливает", "target": "claim"},
            {"rule_id": "RULE_EPI_03", "engine": "Epistemic", "severity": "WARNING",
             "message": "claim требует cross-check", "pattern": "демонстрирует", "target": "claim"},
            # completeness
            {"rule_id": "RULE_CMP_01", "engine": "Completeness", "severity": "CRITICAL",
             "message": "нет warrant/обоснования", "pattern": "warrant", "target": "paragraph"},
            # style — хардкор: больше воды ловим
            {"rule_id": "AP_T01", "engine": "Style", "severity": "LOW",
             "message": "вода", "pattern": "как известно", "target": "style"},
            {"rule_id": "AP_T01b", "engine": "Style", "severity": "LOW",
             "message": "вода", "pattern": "в последние годы", "target": "style"},
            {"rule_id": "AP_T02", "engine": "Style", "severity": "LOW",
             "message": "ложная скромность", "pattern": "очевидно", "target": "style"},
        ]

    def _default_rules(self, orchestrator: str, prompt_hash: str) -> List[Dict[str, Any]]:
        """Правила по умолчанию: текст + структура (5 движков)."""
        try:
            from validation_engines import KnowledgeBase, ValidationPipeline
            kb = KnowledgeBase()
            kb.add_entity('OBS_XRD_FWHM', 'Observable')
            kb.add_entity('OBS_XRD_PHASE', 'Observable')
            kb.add_entity('CLAIM_MECH', 'Mechanism')
            kb.add_entity('CLAIM_PROP', 'PhysicalProperty')
            kb.set_allowed_slot_types('data', ['Observable', 'PhysicalProperty'])
            kb.set_allowed_slot_types('claim', ['Mechanism', 'PhysicalProperty'])
            kb.forbid_relation('OBS_XRD_FWHM', 'proves', 'Mechanism')
            kb.forbid_relation('OBS_XRD_PHASE', 'proves', 'Mechanism')
            kb.allow_relation('OBS_XRD_FWHM', 'indicates', 'PhysicalProperty')
            kb.allow_relation('OBS_XRD_PHASE', 'indicates', 'PhysicalProperty')
            kb.set_evidence_type('OBS_XRD_FWHM', 'indirect')
            kb.set_evidence_type('OBS_XRD_PHASE', 'indirect')
            pipe = ValidationPipeline(kb)

            def struct_check(artifact):
                """Проверка структуры: если dict со слотами — 5 движков."""
                if not isinstance(artifact, dict):
                    return False
                result = pipe.validate_instance(artifact)
                return result.status == 'FAIL'

            struct_rule = {
                "rule_id": "RULE_STRUCT", "engine": "Structure",
                "severity": "CRITICAL", "message": "структура нарушает 5 движков",
                "target": "slots", "check_fn": struct_check,
            }
        except Exception:
            struct_rule = None

        rules = [
            {"rule_id": "RULE_CMP_01", "engine": "Completeness", "severity": "CRITICAL",
             "message": "нет warrant/обоснования", "pattern": "warrant", "target": "paragraph"},
            {"rule_id": "RULE_REL_04", "engine": "RelationGraph", "severity": "CRITICAL",
             "message": "XRD не может 'доказывать' механизм", "pattern": "доказывает", "target": "claim"},
            {"rule_id": "RULE_EPI_02", "engine": "Epistemic", "severity": "WARNING",
             "message": "косвенное свидетельство с сильной модальностью", "pattern": "устанавливает", "target": "claim"},
            {"rule_id": "AP_T01", "engine": "Style", "severity": "LOW",
             "message": "вода/фраза-заполнитель", "pattern": "как известно", "target": "style"},
        ]
        if struct_rule:
            rules.append(struct_rule)
        return rules

    def _default_scope(self, orchestrator: str) -> List[str]:
        return ["claims", "citations", "physics", "style"]

    # ------------------------------------------------------ изоляция

    @property
    def auditor_prompt(self) -> str:
        """Промпт аудитора (формируется ИЗВНЕ, не оркестратором)."""
        if self.contract is None:
            return f"[EXTERNAL-AUDITOR:{self.auditor_id}] no contract"
        return (f"[EXTERNAL-AUDITOR:{self.auditor_id}] contract={self.contract.contract_id} "
                f"orchestrator={self.contract.orchestrator} rules={len(self.contract.rules)}")

    def auditor_variables(self) -> Dict[str, Any]:
        """Переменные аудитора (namespace auditor_*; НЕ пересекаются с оркестраторными)."""
        return {
            "auditor_id": self.auditor_id,
            "auditor_observations": self.observations,
            "auditor_contract": self.contract.contract_id if self.contract else None,
            "auditor_basket_damage": self.basket_damage(),
        }

    @staticmethod
    def _hash(text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]