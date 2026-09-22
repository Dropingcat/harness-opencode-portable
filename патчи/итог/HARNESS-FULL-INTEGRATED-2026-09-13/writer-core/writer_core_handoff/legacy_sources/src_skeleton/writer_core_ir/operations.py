from __future__ import annotations
from pydantic import BaseModel, Field

class OperationContract(BaseModel):
    operation_id: str
    operation_type: str
    reads: list[str]=Field(default_factory=list)
    writes: list[str]=Field(default_factory=list)
    authority_required: str
    preconditions: list[str]=Field(default_factory=list)
    postconditions: list[str]=Field(default_factory=list)
    validator_set: list[str]=Field(default_factory=list)
    blocker_types_on_failure: list[str]=Field(default_factory=list)
    deterministic_part: list[str]=Field(default_factory=list)
    model_assisted_part: list[str]=Field(default_factory=list)
    idempotency_key: str|None=None

CORE_OPERATION_TYPES = (
    'CompileRequirements','ImportEpistemicProjection','BuildWritingContract',
    'DecomposeWritingObjective','BindEligibleClaim','ResolveArtifact',
    'InstantiateArgumentPattern','InstantiateDiscoursePattern','RealizeUnit',
    'BackExtractSemantics','ValidateRoundTrip','PlanSemanticRepair',
    'ComputeImpactClosure','RebuildArtifact','ValidateGlobalConsistency',
    'CreateBlocker','ResolveBlocker','OpenReviewIssue','CreateDecision',
    'BuildReleaseCandidate','ExportArtifact','ParseBackExport','RunVisualPreflight'
)
