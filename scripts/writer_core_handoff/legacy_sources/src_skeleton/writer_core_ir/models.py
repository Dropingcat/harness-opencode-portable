from __future__ import annotations

from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field

class Freshness(StrEnum):
    FRESH='FRESH'; STALE='STALE'; REVERIFY_REQUIRED='REVERIFY_REQUIRED'; REBUILD_REQUIRED='REBUILD_REQUIRED'; INVALID='INVALID'

class Mutability(StrEnum):
    IMMUTABLE_SOURCE='IMMUTABLE_SOURCE'; DERIVED_REBUILDABLE='DERIVED_REBUILDABLE'; EDITABLE_VERSIONED='EDITABLE_VERSIONED'; LOCKED_APPROVED='LOCKED_APPROVED'

class BlockerSeverity(StrEnum):
    INFO='INFO'; WORK_BLOCKING='WORK_BLOCKING'; SECTION_BLOCKING='SECTION_BLOCKING'; RELEASE_BLOCKING='RELEASE_BLOCKING'

class ValidationClass(StrEnum):
    STRUCTURAL='STRUCTURAL'; SYMBOLIC='SYMBOLIC'; RULE_BASED='RULE_BASED'; MODEL_ASSISTED='MODEL_ASSISTED'; HUMAN='HUMAN'; EXPERT='EXPERT'

class SemanticClaimType(StrEnum):
    OBSERVATION='OBSERVATION'; MEASUREMENT='MEASUREMENT'; QUANTITATIVE='QUANTITATIVE'; COMPARISON='COMPARISON'; ASSOCIATION='ASSOCIATION'; CAUSAL='CAUSAL'; MECHANISTIC='MECHANISTIC'; DEFINITION='DEFINITION'; CLASSIFICATION='CLASSIFICATION'; METHODOLOGICAL='METHODOLOGICAL'; INTERPRETIVE='INTERPRETIVE'; RECOMMENDATION='RECOMMENDATION'; NORMATIVE='NORMATIVE'

class InlineText(BaseModel):
    type: Literal['text']='text'
    value: str

class InlineRef(BaseModel):
    type: Literal['claim_ref','quantity_ref','formula_ref','citation_ref','term_ref','cross_ref','artifact_ref']
    ref: str
    realization: str|None=None

class DocumentNode(BaseModel):
    id: str
    type: Literal['document','section','paragraph','sentence','figure','table','equation','list','appendix']
    parent: str|None=None
    order: int=0
    children: list[str]=Field(default_factory=list)

class ClaimWritingContract(BaseModel):
    claim_id: str
    proposition: str
    claim_type: SemanticClaimType
    writer_eligibility: Literal['ALLOWED','QUALIFIED','FORBIDDEN']
    scope_ref: str|None=None
    modality: str|None=None
    causal_level: str|None=None
    required_qualifiers: list[str]=Field(default_factory=list)
    forbidden_transformations: list[str]=Field(default_factory=list)
    evidence_refs: list[str]=Field(default_factory=list)
    numeric_refs: list[str]=Field(default_factory=list)
    uncertainty_refs: list[str]=Field(default_factory=list)

class Quantity(BaseModel):
    id: str
    dimension: str
    unit: str
    raw_value: str|None=None
    computed_value: str|None=None
    reported_value: str|None=None
    uncertainty_ref: str|None=None
    provenance: list[str]=Field(default_factory=list)
    freshness: Freshness=Freshness.FRESH

class Blocker(BaseModel):
    id: str
    type: str
    severity: BlockerSeverity
    target_refs: list[str]
    origin_ref: str
    resolution_options: list[str]=Field(default_factory=list)
    state: Literal['OPEN','IN_PROGRESS','RESOLVED','WAIVED_WITH_DECISION']='OPEN'
