from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ControlClass(str, Enum):
    HARD_INVARIANT = "HARD_INVARIANT"
    CONSTRAINT = "CONSTRAINT"
    SIGNAL = "SIGNAL"
    LEARNED_PREFERENCE = "LEARNED_PREFERENCE"


class Impact(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LinguisticIssue(BaseModel):
    id: str
    type: str
    target: str
    impact: Impact
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class AffordanceSet(BaseModel):
    target: str
    hard_invariants: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    learned_preferences: list[dict[str, Any]] = Field(default_factory=list)
    affordances: list[str] = Field(default_factory=list)
    unavailable_actions: list[str] = Field(default_factory=list)


class LinguisticDigest(BaseModel):
    id: str
    main_statement: dict[str, Any]
    scope: dict[str, Any] = Field(default_factory=dict)
    modality: str | None = None
    causal_force: str | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)
    ambiguities: list[LinguisticIssue] = Field(default_factory=list)
    discourse_role: str | None = None
    affordances: list[str] = Field(default_factory=list)


class SentencePlan(BaseModel):
    id: str
    semantic_refs: list[str]
    frame: str
    clauses: list[dict[str, Any]]
    theme_rheme: dict[str, Any] = Field(default_factory=dict)
    lexical_choices: dict[str, Any] = Field(default_factory=dict)
    forbidden_upgrades: list[str] = Field(default_factory=list)


class LinguisticEpisode(BaseModel):
    id: str
    context: dict[str, Any]
    variants: list[dict[str, Any]] = Field(default_factory=list)
    outcome: dict[str, Any]
    features: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any]
