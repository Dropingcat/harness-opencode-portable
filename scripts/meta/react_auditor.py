# -*- coding: utf-8 -*-
"""
react_auditor.py — TD-163: ReAct-подцикл с внешним аудитором.

Интерфейс Repair-агента (LLM) к детерминированным валидаторам:
  modify_slot / add_slot / submit_final.
Каждое действие вызывает валидатор и возвращает Observation (PASS/NEW/PERSISTENT).
Вся история Thought→Action→Observation сохраняется для трассировки.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class AuditError:
    """Ошибка валидации от одного движка."""

    __slots__ = ("severity", "engine", "rule_id", "message", "context")

    def __init__(self, severity: str, engine: str, rule_id: str,
                 message: str, context: str = "") -> None:
        self.severity = severity      # CRITICAL | MEDIUM | LOW
        self.engine = engine          # physics | citation | style | ...
        self.rule_id = rule_id        # RULE_REL_04, AP-M03, ...
        self.message = message
        self.context = context

    def to_observation_line(self) -> str:
        return (f"- [{self.severity}] {self.engine} ({self.rule_id}): "
                f"{self.message}" + (f" Context: {self.context}" if self.context else ""))


class AuditResult:
    """Результат валидации."""

    __slots__ = ("status", "errors")

    def __init__(self, status: ValidationStatus, errors: List[AuditError]) -> None:
        self.status = status
        self.errors = errors

    def to_observation(self) -> str:
        if self.status == ValidationStatus.PASS:
            return "Observation: PASS. No validation errors."
        obs = "Observation: VALIDATION FAILED.\n"
        for e in self.errors:
            obs += e.to_observation_line() + "\n"
        return obs


class AuditorInstance:
    """Текущий инстанс (граф слотов), который модифицирует repair-агент."""

    def __init__(self, slots: Optional[Dict[str, Any]] = None) -> None:
        self.slots = slots or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"slots": self.slots}


class ReactStep:
    """Один шаг ReAct-цикла: Thought → Action → Observation."""

    __slots__ = ("step_id", "thought", "action", "observation", "timestamp")

    def __init__(self, thought: str, action: str, observation: str) -> None:
        self.step_id = str(uuid.uuid4())
        self.thought = thought
        self.action = action
        self.observation = observation
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step_id, "thought": self.thought,
                "action": self.action, "observation": self.observation,
                "timestamp": self.timestamp}


class ReactAuditorTools:
    """
    Внешний аудитор для ReAct-подцикла (TD-163).
    LLM НЕ редактирует JSON напрямую — только через эти инструменты.
    Каждый вызов автоматически валидирует и возвращает Observation.
    """

    def __init__(self, current_instance: AuditorInstance,
                 validator: Callable[[AuditorInstance], AuditResult],
                 max_iterations: int = 5) -> None:
        self.instance = current_instance
        self.validator = validator          # детерминированный аудитор
        self.max_iterations = max_iterations
        self.history: List[ReactStep] = []  # replay_history
        self.iteration = 0

    def modify_slot(self, slot_name: str, entity_id: str,
                    modality: Optional[str] = None) -> str:
        """Изменяет сущность/модальность в существующем слоте."""
        self.iteration += 1
        if self.iteration > self.max_iterations:
            return "Observation: MAX_ITERATIONS. Branch FAILED_REPAIR."
        if slot_name not in self.instance.slots:
            return f"Observation: ERROR. Slot '{slot_name}' does not exist."
        self.instance.slots[slot_name] = {"entity_id": entity_id}
        if modality:
            self.instance.slots[slot_name]["modality"] = modality
        return self._run_audit("modify_slot", f"{slot_name}={entity_id}")

    def add_slot(self, slot_name: str, entity_id: str,
                 modality: Optional[str] = None) -> str:
        """Добавляет отсутствующий обязательный слот (warrant и т.п.)."""
        self.iteration += 1
        if self.iteration > self.max_iterations:
            return "Observation: MAX_ITERATIONS. Branch FAILED_REPAIR."
        self.instance.slots[slot_name] = {"entity_id": entity_id}
        if modality:
            self.instance.slots[slot_name]["modality"] = modality
        return self._run_audit("add_slot", f"{slot_name}={entity_id}")

    def submit_final(self) -> str:
        """Финальная проверка перед закрытием ветки."""
        result = self._run_audit("submit_final", "")
        if "PASS" in result:
            return "Observation: SUCCESS. Branch is ready for merge."
        return f"Observation: REJECTED. Cannot submit with errors:\n{result}"

    # --- внутренние ---
    def _run_audit(self, action: str, target: str) -> str:
        """Вызов валидатора, формирование Observation + запись в history."""
        result = self.validator(self.instance)
        obs = result.to_observation()
        thought = f"[auto] {action}: {target}"
        self.history.append(ReactStep(thought, f"{action}({target})", obs))
        return obs

    # --- трассировка ---
    def replay_history(self) -> List[Dict[str, Any]]:
        """История ReAct-шагов для трассировки/дебага."""
        return [s.to_dict() for s in self.history]

    def export(self) -> Dict[str, Any]:
        return {
            "instance": self.instance.to_dict(),
            "history": self.replay_history(),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
        }