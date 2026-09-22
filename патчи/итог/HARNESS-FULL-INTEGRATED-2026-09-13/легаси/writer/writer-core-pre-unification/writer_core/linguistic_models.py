"""Minimal runtime models consumed by the deterministic linguistic digest."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Impact(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LinguisticIssue(_StrictModel):
    id: str
    type: str
    target: str
    impact: Impact
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class AffordanceSet(_StrictModel):
    target: str
    hard_invariants: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    learned_preferences: list[dict[str, Any]] = Field(default_factory=list)
    affordances: list[str] = Field(default_factory=list)
    unavailable_actions: list[str] = Field(default_factory=list)


class LinguisticDigest(_StrictModel):
    id: str
    main_statement: dict[str, Any]
    scope: dict[str, Any] = Field(default_factory=dict)
    modality: str | None = None
    causal_force: str | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)
    ambiguities: list[LinguisticIssue] = Field(default_factory=list)
    discourse_role: str | None = None
    affordances: list[str] = Field(default_factory=list)
