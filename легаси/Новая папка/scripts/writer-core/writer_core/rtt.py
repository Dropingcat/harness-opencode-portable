"""Runtime-owned round-trip semantic validation result contract."""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RTTReason(StrEnum):
    EXACT = "EXACT"
    PARAPHRASE_SAFE = "PARAPHRASE_SAFE"
    CLAIM_OMISSION = "CLAIM_OMISSION"
    UNAUTHORIZED_CLAIM = "UNAUTHORIZED_CLAIM"
    SCOPE_EXPANSION = "SCOPE_EXPANSION"
    SCOPE_NARROWING = "SCOPE_NARROWING"
    SCOPE_SHIFT_MAJOR = "SCOPE_SHIFT_MAJOR"
    MODALITY_UPGRADE = "MODALITY_UPGRADE"
    MODALITY_DOWNGRADE = "MODALITY_DOWNGRADE"
    CAUSALITY_UPGRADE = "CAUSALITY_UPGRADE"
    CAUSALITY_LOSS = "CAUSALITY_LOSS"
    QUALIFIER_LOSS = "QUALIFIER_LOSS"
    QUALIFIER_DROPPED = "QUALIFIER_DROPPED"
    NEGATION_FLIP = "NEGATION_FLIP"
    ENTITY_SUBSTITUTION = "ENTITY_SUBSTITUTION"
    TEMPORAL_SHIFT = "TEMPORAL_SHIFT"
    NUMERIC_DRIFT = "NUMERIC_DRIFT"
    UNIT_DRIFT = "UNIT_DRIFT"
    PRECISION_INFLATION = "PRECISION_INFLATION"
    UNCERTAINTY_LOSS = "UNCERTAINTY_LOSS"
    EVIDENCE_MISATTRIBUTION = "EVIDENCE_MISATTRIBUTION"
    DISCOURSE_CONNECTIVE_UNJUSTIFIED = "DISCOURSE_CONNECTIVE_UNJUSTIFIED"
    REFORMULATION_DRIFT = "REFORMULATION_DRIFT"


class RTTResult(BaseModel):
    """Stable JSON-serializable sentence RTT result."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    realization_id: str
    level: Literal["sentence", "paragraph", "section", "document"]
    verdict: Literal["PASS", "FAIL"]
    reason_codes: list[RTTReason] = Field(default_factory=list)
    unauthorized_claims: list[str] = Field(default_factory=list)
    omitted_claims: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
