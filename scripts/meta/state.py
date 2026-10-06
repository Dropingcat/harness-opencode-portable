# -*- coding: utf-8 -*-
"""
state.py — V1 State Ontology.

Уровни устойчивости (Invariant > Policy > Tactic), StateVariable с версионированием,
ErrorVector (Парето), SystemState (immutable, SHA-256 hash), Promotion Tactic→Policy.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class StabilityLevel(str, Enum):
    INVARIANT = "invariant"
    POLICY = "policy"
    TACTIC = "tactic"


class StateVariable:
    """Атомарная переменная состояния с версионированием."""

    __slots__ = ("var_id", "name", "value", "stability", "causal_links",
                 "version", "created_at", "last_modified", "success_count")

    def __init__(self, name: str, value: Any, stability: StabilityLevel,
                 causal_links: Optional[List[str]] = None) -> None:
        self.var_id = str(uuid.uuid4())
        self.name = name
        self.value = value
        self.stability = stability
        self.causal_links = causal_links or []
        self.version = 1
        self.created_at = datetime.now().isoformat()
        self.last_modified = self.created_at
        self.success_count = 0  # для Promotion

    def update(self, new_value: Any) -> None:
        """Immutable Snapshot: новая версия, не мутация."""
        self.value = new_value
        self.version += 1
        self.last_modified = datetime.now().isoformat()

    def record_success(self) -> None:
        self.success_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "var_id": self.var_id, "name": self.name, "value": self.value,
            "stability": self.stability.value if hasattr(self.stability, 'value') else str(self.stability),
            "causal_links": self.causal_links, "version": self.version,
            "success_count": self.success_count,
        }


class ErrorVector:
    """Многомерный вектор ошибок (Парето вместо Trust Score)."""

    AXES = ("factual", "logical", "citation", "methodological", "coverage",
            "dimensional", "stylistic")

    def __init__(self, **kwargs) -> None:
        for axis in self.AXES:
            setattr(self, axis, float(kwargs.get(axis, 0.0)))

    def is_better_than(self, other: "ErrorVector", tolerance: float = 0.05) -> bool:
        improvements = 0
        degradations = 0
        for axis in self.AXES:
            diff = getattr(other, axis) - getattr(self, axis)
            if diff > tolerance:
                improvements += 1
            elif diff < -tolerance:
                degradations += 1
        return improvements > 0 and degradations == 0

    def to_dict(self) -> Dict[str, float]:
        return {axis: getattr(self, axis) for axis in self.AXES}


class SystemState:
    """Неизменяемый снимок состояния S_t (immutable + hash)."""

    __slots__ = ("version_id", "parent_version_id", "timestamp", "variables",
                 "error_vector", "active_tactics_ttl", "state_hash")

    def __init__(self, variables: Optional[Dict[str, StateVariable]] = None,
                 error_vector: Optional[ErrorVector] = None,
                 active_tactics_ttl: Optional[Dict[str, int]] = None,
                 parent_version_id: Optional[str] = None) -> None:
        self.version_id = str(uuid.uuid4())
        self.parent_version_id = parent_version_id
        self.timestamp = datetime.now().isoformat()
        self.variables = variables or {}
        self.error_vector = error_vector or ErrorVector()
        self.active_tactics_ttl = active_tactics_ttl or {}
        self.state_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        content = json.dumps({
            "variables": {k: v.to_dict() for k, v in self.variables.items()},
            "error_vector": self.error_vector.to_dict(),
            "tactics": self.active_tactics_ttl,
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "parent_version_id": self.parent_version_id,
            "timestamp": self.timestamp,
            "variables": {k: v.to_dict() for k, v in self.variables.items()},
            "error_vector": self.error_vector.to_dict(),
            "active_tactics_ttl": self.active_tactics_ttl,
            "state_hash": self.state_hash,
        }


class StateManager:
    """Управление состоянием: Promotion Tactic→Policy, decay, миграция."""

    PROMOTION_THRESHOLD = 3   # success_count >= 3 → Policy (V1-TD-01)
    TTL_DEFAULT = 5            # циклов жизни тактики (V1-TD-02)

    def __init__(self, initial_state: Optional[SystemState] = None) -> None:
        self.current = initial_state or SystemState()
        self.history: List[Dict[str, Any]] = []

    def promote_tactics(self) -> List[str]:
        """Tactic с success_count >= threshold → Policy."""
        promoted = []
        for name, var in list(self.current.variables.items()):
            if var.stability == StabilityLevel.TACTIC and var.success_count >= self.PROMOTION_THRESHOLD:
                var.stability = StabilityLevel.POLICY
                promoted.append(name)
                self.current.active_tactics_ttl.pop(name, None)
        if promoted:
            self._commit("promote_tactics", promoted)
        return promoted

    def decay_tactics(self) -> List[str]:
        """TTL тактик: ttl -= 1; при 0 → promote или delete."""
        expired = []
        for name, ttl in list(self.current.active_tactics_ttl.items()):
            new_ttl = ttl - 1
            if new_ttl <= 0:
                var = self.current.variables.get(name)
                if var and var.success_count >= self.PROMOTION_THRESHOLD:
                    var.stability = StabilityLevel.POLICY
                else:
                    self.current.variables.pop(name, None)
                self.current.active_tactics_ttl.pop(name, None)
                expired.append(name)
            else:
                self.current.active_tactics_ttl[name] = new_ttl
        if expired:
            self._commit("decay_tactics", expired)
        return expired

    def set_variable(self, name: str, value: Any, stability: StabilityLevel,
                     ttl: Optional[int] = None) -> StateVariable:
        """Установить/обновить переменную с immutable-версионированием."""
        if name in self.current.variables:
            var = self.current.variables[name]
            var.update(value)
        else:
            var = StateVariable(name, value, stability)
            self.current.variables[name] = var
        if stability == StabilityLevel.TACTIC:
            self.current.active_tactics_ttl[name] = ttl or self.TTL_DEFAULT
        self._commit("set_variable", name)
        return var

    def apply_delta(self, delta: Dict[str, Any]) -> SystemState:
        """Применить дельту → новое состояние (parent = текущее)."""
        new_vars = {k: v for k, v in self.current.variables.items()}
        new_ttl = dict(self.current.active_tactics_ttl)
        for path, new_val in delta.items():
            # поддержка "var.name" и "active_tactics_ttl.name"
            parts = path.split(".")
            if parts[0] == "var" and len(parts) >= 2:
                vname = parts[1]
                if vname in new_vars:
                    new_vars[vname].update(new_val)
                else:
                    new_vars[vname] = StateVariable(vname, new_val, StabilityLevel.TACTIC)
            elif parts[0] == "active_tactics_ttl" and len(parts) >= 2:
                new_ttl[parts[1]] = new_val
        self.current = SystemState(
            variables=new_vars,
            error_vector=self.current.error_vector,
            active_tactics_ttl=new_ttl,
            parent_version_id=self.current.version_id,
        )
        self._commit("apply_delta", list(delta.keys()))
        return self.current

    def _commit(self, action: str, detail: Any) -> None:
        self.history.append({
            "action": action, "detail": detail,
            "version_id": self.current.version_id, "timestamp": datetime.now().isoformat(),
        })