"""R4.3 typed inquiry contracts and role-output admission.

This module binds one admitted Tribunal role to one R4.2 evidence slice and
turns an untrusted semantic worker draft into typed historical inquiry and
argument artifacts.  It does not schedule workers and it does not mutate
knowledge state.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Sequence

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.tribunal_composition import (
    AssessmentNeedRef,
    RoleBriefContract,
    TribunalCompositionPlan,
    TribunalCompositionError,
    validate_tribunal_composition_plan_integrity,
)
from researcher_core.tribunal_evidence import (
    EvidenceSliceStatus,
    PriorReviewArtifact,
    TribunalEvidenceSlice,
)
from researcher_core.uncertainty_field import ReviewWorkField


class TribunalInquiryError(RuntimeError):
    pass


class InquiryPhase(StrEnum):
    INDEPENDENT_FIRST_PASS = "INDEPENDENT_FIRST_PASS"


class InquiryTurnKind(StrEnum):
    FIRST_PASS_ASSESSMENT = "FIRST_PASS_ASSESSMENT"
    CHALLENGE = "CHALLENGE"
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"
    QUESTION_ON_ANSWER = "QUESTION_ON_ANSWER"
    REBUTTAL = "REBUTTAL"


class ArgumentPosition(StrEnum):
    SUPPORT = "SUPPORT"
    CHALLENGE = "CHALLENGE"
    QUALIFY = "QUALIFY"
    OPEN = "OPEN"


class DiscoveryKind(StrEnum):
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    METHOD_LIMITATION = "METHOD_LIMITATION"
    POSSIBLE_COUNTEREXAMPLE = "POSSIBLE_COUNTEREXAMPLE"
    SCOPE_ISSUE = "SCOPE_ISSUE"
    CAUSALITY_PROBLEM = "CAUSALITY_PROBLEM"
    NUMERIC_DISCREPANCY = "NUMERIC_DISCREPANCY"
    ASSUMPTION_ISSUE = "ASSUMPTION_ISSUE"
    SOURCE_PROVENANCE_ISSUE = "SOURCE_PROVENANCE_ISSUE"
    FRESHNESS_ISSUE = "FRESHNESS_ISSUE"


class ResponseGroundingKind(StrEnum):
    DISCLOSED_EVIDENCE = "DISCLOSED_EVIDENCE"
    DISCLOSED_TARGET = "DISCLOSED_TARGET"
    PRIOR_ARGUMENT = "PRIOR_ARGUMENT"
    PRIOR_TURN = "PRIOR_TURN"
    DERIVATION_FROM_VISIBLE = "DERIVATION_FROM_VISIBLE"
    EXPLICIT_ASSUMPTION = "EXPLICIT_ASSUMPTION"
    MODEL_PRIOR = "MODEL_PRIOR"


class ResponseGroundingState(StrEnum):
    DOCUMENTED = "DOCUMENTED"
    MIXED = "MIXED"
    VISIBLE_CONTEXT_ONLY = "VISIBLE_CONTEXT_ONLY"
    MODEL_PRIOR_ONLY = "MODEL_PRIOR_ONLY"
    UNGROUNDED = "UNGROUNDED"
    UNCHARACTERIZED = "UNCHARACTERIZED"


@dataclass(frozen=True, slots=True)
class ResponseGroundingItem:
    kind: ResponseGroundingKind
    statement: str
    refs: tuple[EntityId, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ResponseGroundingKind):
            raise TypeError("grounding kind must be ResponseGroundingKind")
        if not self.statement.strip():
            raise ValueError("grounding statement is required")
        refs = tuple(dict.fromkeys(self.refs))
        if self.kind in {ResponseGroundingKind.MODEL_PRIOR, ResponseGroundingKind.EXPLICIT_ASSUMPTION} and refs:
            raise ValueError("MODEL_PRIOR and EXPLICIT_ASSUMPTION cannot carry source or evidence refs")
        if self.kind in {
            ResponseGroundingKind.DISCLOSED_EVIDENCE,
            ResponseGroundingKind.DISCLOSED_TARGET,
            ResponseGroundingKind.PRIOR_ARGUMENT,
            ResponseGroundingKind.PRIOR_TURN,
            ResponseGroundingKind.DERIVATION_FROM_VISIBLE,
        } and not refs:
            raise ValueError(f"{self.kind.value} grounding requires visible refs")
        object.__setattr__(self, "refs", refs)


def characterize_response_grounding(items: Sequence[ResponseGroundingItem]) -> ResponseGroundingState:
    kinds = {item.kind for item in items}
    if not kinds:
        return ResponseGroundingState.UNGROUNDED
    prior_kinds = {ResponseGroundingKind.MODEL_PRIOR, ResponseGroundingKind.EXPLICIT_ASSUMPTION}
    visible_kinds = {
        ResponseGroundingKind.DISCLOSED_TARGET,
        ResponseGroundingKind.PRIOR_ARGUMENT,
        ResponseGroundingKind.PRIOR_TURN,
        ResponseGroundingKind.DERIVATION_FROM_VISIBLE,
    }
    if ResponseGroundingKind.DISCLOSED_EVIDENCE in kinds:
        return ResponseGroundingState.MIXED if kinds.intersection(prior_kinds) else ResponseGroundingState.DOCUMENTED
    if kinds.issubset(prior_kinds):
        return ResponseGroundingState.MODEL_PRIOR_ONLY
    if kinds.issubset(visible_kinds):
        return ResponseGroundingState.VISIBLE_CONTEXT_ONLY
    return ResponseGroundingState.MIXED


@dataclass(frozen=True, slots=True)
class InquiryContract:
    meta: EntityMeta
    request_id: EntityId
    work_field_id: EntityId
    role_id: str
    phase: InquiryPhase
    composition_fingerprint: str
    evidence_slice_fingerprint: str
    assigned_need_refs: tuple[AssessmentNeedRef, ...]
    allowed_capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    expected_output_contract: str
    inquiry_depth: int
    token_budget: int
    role_instruction_id: str
    role_instruction_fingerprint: str
    contract_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "IQC":
            raise ValueError("InquiryContract id must use IQC prefix")
        if self.request_id.namespace != "RRQ":
            raise ValueError("request_id must use RRQ prefix")
        if self.work_field_id.namespace != "RWF":
            raise ValueError("work_field_id must use RWF prefix")
        if not self.role_id or not self.composition_fingerprint or not self.evidence_slice_fingerprint:
            raise ValueError("role and fingerprints are required")
        if not self.role_instruction_id or not self.role_instruction_fingerprint.startswith("sha256:"):
            raise ValueError("role instruction id/fingerprint are required")
        if self.inquiry_depth < 1 or self.token_budget < 1:
            raise ValueError("inquiry depth/token budget must be positive")
        if self.expected_output_contract != "ArgumentArtifact/1.0":
            raise ValueError("R4.3 requires ArgumentArtifact/1.0 output")
        object.__setattr__(self, "assigned_need_refs", tuple(self.assigned_need_refs))
        object.__setattr__(self, "allowed_capabilities", tuple(self.allowed_capabilities))
        object.__setattr__(self, "allowed_tools", tuple(self.allowed_tools))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InquiryDiscovery:
    kind: DiscoveryKind
    statement: str
    need_refs: tuple[AssessmentNeedRef, ...]
    target_refs: tuple[EntityId, ...] = ()
    evidence_refs: tuple[EntityId, ...] = ()
    blocking: bool = False

    def __post_init__(self) -> None:
        if not self.statement.strip():
            raise ValueError("discovery statement is required")
        if not self.need_refs:
            raise ValueError("discovery requires at least one AssessmentNeedRef")
        object.__setattr__(self, "need_refs", tuple(self.need_refs))
        object.__setattr__(self, "target_refs", tuple(self.target_refs))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class AdditionalEvidenceRequest:
    question: str
    reason: str
    need_refs: tuple[AssessmentNeedRef, ...]
    target_refs: tuple[EntityId, ...] = ()
    requested_evidence_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.question.strip() or not self.reason.strip():
            raise ValueError("additional-evidence request requires question and reason")
        if not self.need_refs:
            raise ValueError("additional-evidence request requires at least one need ref")
        object.__setattr__(self, "need_refs", tuple(self.need_refs))
        object.__setattr__(self, "target_refs", tuple(self.target_refs))
        object.__setattr__(self, "requested_evidence_kinds", tuple(dict.fromkeys(x.strip() for x in self.requested_evidence_kinds if x.strip())))


@dataclass(frozen=True, slots=True)
class RoleWorkerDraft:
    position: ArgumentPosition
    summary: str
    justification: str
    cited_evidence_refs: tuple[EntityId, ...] = ()
    cited_target_refs: tuple[EntityId, ...] = ()
    discoveries: tuple[InquiryDiscovery, ...] = ()
    additional_evidence_requests: tuple[AdditionalEvidenceRequest, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.summary.strip() or not self.justification.strip():
            raise ValueError("role worker draft requires summary and justification")
        object.__setattr__(self, "cited_evidence_refs", tuple(dict.fromkeys(self.cited_evidence_refs)))
        object.__setattr__(self, "cited_target_refs", tuple(dict.fromkeys(self.cited_target_refs)))
        object.__setattr__(self, "discoveries", tuple(self.discoveries))
        object.__setattr__(self, "additional_evidence_requests", tuple(self.additional_evidence_requests))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InquiryTurn:
    meta: EntityMeta
    contract_id: EntityId
    role_id: str
    kind: InquiryTurnKind
    content: str
    parent_turn_id: EntityId | None
    cited_refs: tuple[EntityId, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "IQT":
            raise ValueError("InquiryTurn id must use IQT prefix")
        if self.contract_id.namespace not in {"IQC", "ADC", "DQC"}:
            raise ValueError("contract_id must use IQC, ADC or DQC prefix")
        if self.parent_turn_id is not None and self.parent_turn_id.namespace != "IQT":
            raise ValueError("parent_turn_id must use IQT prefix")
        if not self.role_id or not self.content.strip():
            raise ValueError("role_id/content are required")
        object.__setattr__(self, "cited_refs", tuple(dict.fromkeys(self.cited_refs)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ArgumentArtifact:
    meta: EntityMeta
    contract_id: EntityId
    source_turn_id: EntityId
    role_id: str
    position: ArgumentPosition
    assigned_need_refs: tuple[AssessmentNeedRef, ...]
    summary: str
    justification: str
    cited_evidence_refs: tuple[EntityId, ...]
    cited_target_refs: tuple[EntityId, ...]
    discoveries: tuple[InquiryDiscovery, ...]
    additional_evidence_requests: tuple[AdditionalEvidenceRequest, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    grounding_items: tuple[ResponseGroundingItem, ...] = ()
    grounding_state: ResponseGroundingState = ResponseGroundingState.UNCHARACTERIZED

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "ARG":
            raise ValueError("ArgumentArtifact id must use ARG prefix")
        if self.contract_id.namespace not in {"IQC", "ADC", "DQC"}:
            raise ValueError("contract_id must use IQC, ADC or DQC prefix")
        if self.source_turn_id.namespace != "IQT":
            raise ValueError("source_turn_id must use IQT prefix")
        if not self.role_id or not self.summary.strip() or not self.justification.strip():
            raise ValueError("role/summary/justification are required")
        object.__setattr__(self, "assigned_need_refs", tuple(self.assigned_need_refs))
        object.__setattr__(self, "cited_evidence_refs", tuple(self.cited_evidence_refs))
        object.__setattr__(self, "cited_target_refs", tuple(self.cited_target_refs))
        object.__setattr__(self, "discoveries", tuple(self.discoveries))
        object.__setattr__(self, "additional_evidence_requests", tuple(self.additional_evidence_requests))
        object.__setattr__(self, "grounding_items", tuple(self.grounding_items))
        if not isinstance(self.grounding_state, ResponseGroundingState):
            raise TypeError("grounding_state must be ResponseGroundingState")
        if self.grounding_items and self.grounding_state is not ResponseGroundingState.UNCHARACTERIZED:
            expected_grounding = characterize_response_grounding(self.grounding_items)
            if expected_grounding is not self.grounding_state:
                raise ValueError("argument grounding_state does not match grounding_items")
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InquiryExecutionArtifacts:
    turn: InquiryTurn
    argument: ArgumentArtifact


def compile_inquiry_contract(
    *,
    plan: TribunalCompositionPlan,
    evidence_slice: TribunalEvidenceSlice,
    work_field: ReviewWorkField,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
    role_instruction_id: str,
    role_instruction_fingerprint: str,
) -> InquiryContract:
    try:
        validate_tribunal_composition_plan_integrity(plan)
    except TribunalCompositionError as exc:
        raise TribunalInquiryError(f"invalid composition plan:{exc}") from exc
    if work_field.meta.id != plan.work_field_id or work_field.meta.id != evidence_slice.work_field_id:
        raise TribunalInquiryError("work field/plan/evidence slice mismatch")
    if evidence_slice.status is EvidenceSliceStatus.BLOCKED:
        raise TribunalInquiryError("BLOCKED evidence slice cannot execute")
    if evidence_slice.work_field_id != plan.work_field_id:
        raise TribunalInquiryError("evidence slice/work field mismatch")
    if evidence_slice.composition_fingerprint != plan.composition_fingerprint:
        raise TribunalInquiryError("evidence slice/composition fingerprint mismatch")

    brief = _role_brief(plan, evidence_slice.role_id)
    if tuple(brief.assigned_need_refs) != tuple(evidence_slice.assigned_need_refs):
        raise TribunalInquiryError("evidence slice widens/narrows assigned needs")
    if brief.expected_output_contract != "ArgumentArtifact/1.0":
        raise TribunalInquiryError(
            f"unsupported expected output contract:{brief.expected_output_contract}"
        )

    payload = {
        "request_id": str(work_field.request_id),
        "work_field_id": str(plan.work_field_id),
        "role_id": brief.role_id,
        "phase": InquiryPhase.INDEPENDENT_FIRST_PASS.value,
        "composition_fingerprint": plan.composition_fingerprint,
        "evidence_slice_fingerprint": evidence_slice.slice_fingerprint,
        "assigned_need_refs": [(x.key, x.ordinal) for x in brief.assigned_need_refs],
        "allowed_capabilities": list(brief.allowed_capabilities),
        "allowed_tools": list(brief.allowed_tools),
        "expected_output_contract": brief.expected_output_contract,
        "inquiry_depth": brief.inquiry_depth,
        "token_budget": brief.token_budget,
        "role_instruction_id": role_instruction_id,
        "role_instruction_fingerprint": role_instruction_fingerprint,
    }
    return InquiryContract(
        meta=EntityMeta(
            id_factory.new("IQC"),
            "inquiry-contract/1.0",
            1,
            work_field.meta.run_id,
            created_at,
            actor,
        ),
        request_id=work_field.request_id,
        work_field_id=plan.work_field_id,
        role_id=brief.role_id,
        phase=InquiryPhase.INDEPENDENT_FIRST_PASS,
        composition_fingerprint=plan.composition_fingerprint,
        evidence_slice_fingerprint=evidence_slice.slice_fingerprint,
        assigned_need_refs=brief.assigned_need_refs,
        allowed_capabilities=brief.allowed_capabilities,
        allowed_tools=brief.allowed_tools,
        expected_output_contract=brief.expected_output_contract,
        inquiry_depth=brief.inquiry_depth,
        token_budget=brief.token_budget,
        role_instruction_id=role_instruction_id,
        role_instruction_fingerprint=role_instruction_fingerprint,
        contract_fingerprint=_fingerprint(payload),
        metadata={
            "authority_boundary": "independent role execution only; output is non-authoritative argument/proposal",
            "evidence_authority": "worker may cite only refs present in bound TribunalEvidenceSlice",
        },
    )


def validate_inquiry_contract_integrity(contract: InquiryContract) -> None:
    payload = {
        "request_id": str(contract.request_id),
        "work_field_id": str(contract.work_field_id),
        "role_id": contract.role_id,
        "phase": contract.phase.value,
        "composition_fingerprint": contract.composition_fingerprint,
        "evidence_slice_fingerprint": contract.evidence_slice_fingerprint,
        "assigned_need_refs": [(x.key, x.ordinal) for x in contract.assigned_need_refs],
        "allowed_capabilities": list(contract.allowed_capabilities),
        "allowed_tools": list(contract.allowed_tools),
        "expected_output_contract": contract.expected_output_contract,
        "inquiry_depth": contract.inquiry_depth,
        "token_budget": contract.token_budget,
        "role_instruction_id": contract.role_instruction_id,
        "role_instruction_fingerprint": contract.role_instruction_fingerprint,
    }
    expected = _fingerprint(payload)
    if expected != contract.contract_fingerprint:
        raise TribunalInquiryError("InquiryContract fingerprint mismatch")


def materialize_role_worker_draft(
    *,
    contract: InquiryContract,
    evidence_slice: TribunalEvidenceSlice,
    draft: RoleWorkerDraft,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> InquiryExecutionArtifacts:
    validate_inquiry_contract_integrity(contract)
    _validate_contract_slice_binding(contract, evidence_slice)
    _validate_worker_draft(contract, evidence_slice, draft)

    cited_refs = tuple(dict.fromkeys((*draft.cited_target_refs, *draft.cited_evidence_refs)))
    turn = InquiryTurn(
        meta=EntityMeta(id_factory.new("IQT"), "inquiry-turn/1.0", 1, contract.meta.run_id, created_at, actor),
        contract_id=contract.meta.id,
        role_id=contract.role_id,
        kind=InquiryTurnKind.FIRST_PASS_ASSESSMENT,
        content=draft.summary,
        parent_turn_id=None,
        cited_refs=cited_refs,
        metadata={"phase": contract.phase.value, "contract_fingerprint": contract.contract_fingerprint},
    )
    argument = ArgumentArtifact(
        meta=EntityMeta(id_factory.new("ARG"), "argument-artifact/1.0", 1, contract.meta.run_id, created_at, actor),
        contract_id=contract.meta.id,
        source_turn_id=turn.meta.id,
        role_id=contract.role_id,
        position=draft.position,
        assigned_need_refs=contract.assigned_need_refs,
        summary=draft.summary,
        justification=draft.justification,
        cited_evidence_refs=draft.cited_evidence_refs,
        cited_target_refs=draft.cited_target_refs,
        discoveries=draft.discoveries,
        additional_evidence_requests=draft.additional_evidence_requests,
        metadata={
            **dict(draft.metadata),
            "authority_boundary": "argument only; reducers/admission own epistemic state transitions",
            "evidence_slice_fingerprint": evidence_slice.slice_fingerprint,
            "role_instruction_id": contract.role_instruction_id,
            "role_instruction_fingerprint": contract.role_instruction_fingerprint,
        },
    )
    return InquiryExecutionArtifacts(turn=turn, argument=argument)



def prior_review_artifact_from_argument(argument: ArgumentArtifact) -> PriorReviewArtifact:
    """Project a canonical R4.3 argument into the R4.2 prior-review visibility envelope.

    The projection does not change evidence authority.  A later EvidenceViewPolicy
    still decides whether another role may see this prior conclusion.
    """
    targets = tuple(dict.fromkeys((*argument.cited_target_refs, *argument.cited_evidence_refs)))
    return PriorReviewArtifact(
        artifact_id=str(argument.meta.id),
        artifact_type="ArgumentArtifact/1.0",
        target_refs=targets,
        payload={
            "role_id": argument.role_id,
            "position": argument.position.value,
            "summary": argument.summary,
            "justification": argument.justification,
            "source_turn_id": str(argument.source_turn_id),
            "discovery_kinds": [x.kind.value for x in argument.discoveries],
            "grounding_state": argument.grounding_state.value,
            "grounding_kinds": [x.kind.value for x in argument.grounding_items],
        },
    )

def inquiry_contract_to_dict(contract: InquiryContract) -> dict[str, Any]:
    return {
        "schema_version": "inquiry-contract/1.0",
        "meta": _meta_to_dict(contract.meta),
        "request_id": str(contract.request_id),
        "work_field_id": str(contract.work_field_id),
        "role_id": contract.role_id,
        "phase": contract.phase.value,
        "composition_fingerprint": contract.composition_fingerprint,
        "evidence_slice_fingerprint": contract.evidence_slice_fingerprint,
        "assigned_need_refs": [_need_ref_to_dict(x) for x in contract.assigned_need_refs],
        "allowed_capabilities": list(contract.allowed_capabilities),
        "allowed_tools": list(contract.allowed_tools),
        "expected_output_contract": contract.expected_output_contract,
        "inquiry_depth": contract.inquiry_depth,
        "token_budget": contract.token_budget,
        "role_instruction_id": contract.role_instruction_id,
        "role_instruction_fingerprint": contract.role_instruction_fingerprint,
        "contract_fingerprint": contract.contract_fingerprint,
        "metadata": dict(contract.metadata),
    }


def inquiry_turn_to_dict(turn: InquiryTurn) -> dict[str, Any]:
    return {
        "schema_version": "inquiry-turn/1.0",
        "meta": _meta_to_dict(turn.meta),
        "contract_id": str(turn.contract_id),
        "role_id": turn.role_id,
        "kind": turn.kind.value,
        "content": turn.content,
        "parent_turn_id": None if turn.parent_turn_id is None else str(turn.parent_turn_id),
        "cited_refs": [str(x) for x in turn.cited_refs],
        "metadata": dict(turn.metadata),
    }


def argument_artifact_to_dict(argument: ArgumentArtifact) -> dict[str, Any]:
    return {
        "schema_version": "argument-artifact/1.0",
        "meta": _meta_to_dict(argument.meta),
        "contract_id": str(argument.contract_id),
        "source_turn_id": str(argument.source_turn_id),
        "role_id": argument.role_id,
        "position": argument.position.value,
        "assigned_need_refs": [_need_ref_to_dict(x) for x in argument.assigned_need_refs],
        "summary": argument.summary,
        "justification": argument.justification,
        "cited_evidence_refs": [str(x) for x in argument.cited_evidence_refs],
        "cited_target_refs": [str(x) for x in argument.cited_target_refs],
        "discoveries": [
            {
                "kind": d.kind.value,
                "statement": d.statement,
                "need_refs": [_need_ref_to_dict(x) for x in d.need_refs],
                "target_refs": [str(x) for x in d.target_refs],
                "evidence_refs": [str(x) for x in d.evidence_refs],
                "blocking": d.blocking,
            }
            for d in argument.discoveries
        ],
        "additional_evidence_requests": [
            {
                "question": r.question,
                "reason": r.reason,
                "need_refs": [_need_ref_to_dict(x) for x in r.need_refs],
                "target_refs": [str(x) for x in r.target_refs],
                "requested_evidence_kinds": list(r.requested_evidence_kinds),
            }
            for r in argument.additional_evidence_requests
        ],
        "grounding_items": [
            {
                "kind": item.kind.value,
                "statement": item.statement,
                "refs": [str(ref) for ref in item.refs],
            }
            for item in argument.grounding_items
        ],
        "grounding_state": argument.grounding_state.value,
        "metadata": dict(argument.metadata),
    }


def _role_brief(plan: TribunalCompositionPlan, role_id: str) -> RoleBriefContract:
    briefs = [x for x in plan.role_briefs if x.role_id == role_id]
    if len(briefs) != 1:
        raise TribunalInquiryError(f"expected exactly one role brief for:{role_id}")
    return briefs[0]


def _validate_contract_slice_binding(contract: InquiryContract, slice_: TribunalEvidenceSlice) -> None:
    if slice_.role_id != contract.role_id:
        raise TribunalInquiryError("InquiryContract role/evidence slice mismatch")
    if slice_.work_field_id != contract.work_field_id:
        raise TribunalInquiryError("InquiryContract work field/evidence slice mismatch")
    if slice_.composition_fingerprint != contract.composition_fingerprint:
        raise TribunalInquiryError("InquiryContract composition/evidence slice mismatch")
    if slice_.slice_fingerprint != contract.evidence_slice_fingerprint:
        raise TribunalInquiryError("InquiryContract evidence slice fingerprint mismatch")
    if tuple(slice_.assigned_need_refs) != tuple(contract.assigned_need_refs):
        raise TribunalInquiryError("InquiryContract/evidence slice need mismatch")
    if slice_.status is EvidenceSliceStatus.BLOCKED:
        raise TribunalInquiryError("BLOCKED evidence slice cannot execute")


def _validate_worker_draft(contract: InquiryContract, slice_: TribunalEvidenceSlice, draft: RoleWorkerDraft) -> None:
    allowed_evidence = {x.evidence_id for x in slice_.evidence_items}
    allowed_targets = {x.target_id for x in slice_.target_projections}
    allowed_needs = {(x.key, x.ordinal) for x in contract.assigned_need_refs}

    unknown_evidence = set(draft.cited_evidence_refs).difference(allowed_evidence)
    if unknown_evidence:
        raise TribunalInquiryError(f"worker cited evidence outside slice:{sorted(map(str, unknown_evidence))}")
    unknown_targets = set(draft.cited_target_refs).difference(allowed_targets)
    if unknown_targets:
        raise TribunalInquiryError(f"worker cited targets outside slice:{sorted(map(str, unknown_targets))}")

    if draft.position is not ArgumentPosition.OPEN and not (draft.cited_evidence_refs or draft.cited_target_refs):
        raise TribunalInquiryError("non-OPEN argument requires at least one visible cited ref")

    for discovery in draft.discoveries:
        _validate_need_refs(discovery.need_refs, allowed_needs, "discovery")
        if set(discovery.evidence_refs).difference(allowed_evidence):
            raise TribunalInquiryError("discovery references evidence outside slice")
        if set(discovery.target_refs).difference(allowed_targets):
            raise TribunalInquiryError("discovery references target outside slice")

    for request in draft.additional_evidence_requests:
        _validate_need_refs(request.need_refs, allowed_needs, "additional-evidence request")
        if set(request.target_refs).difference(allowed_targets):
            raise TribunalInquiryError("additional-evidence request references target outside slice")

    forbidden = _authority_like_keys(draft.metadata)
    if forbidden:
        raise TribunalInquiryError(f"worker metadata contains authority-like keys:{sorted(forbidden)}")


def _validate_need_refs(refs: Sequence[AssessmentNeedRef], allowed: set[tuple[str, int]], label: str) -> None:
    unknown = [(x.key, x.ordinal) for x in refs if (x.key, x.ordinal) not in allowed]
    if unknown:
        raise TribunalInquiryError(f"{label} references unassigned AssessmentNeedRef:{unknown}")


def _authority_like_keys(value: object) -> set[str]:
    forbidden = {
        "claim_status",
        "graph_edge_state",
        "gap_status",
        "conflict_status",
        "authoritative",
        "state_write",
        "commit",
        "admitted",
        "truth",
    }
    if isinstance(value, Mapping):
        present = forbidden.intersection(str(x) for x in value)
        for nested in value.values():
            present.update(_authority_like_keys(nested))
        return present
    if isinstance(value, (tuple, list)):
        out: set[str] = set()
        for nested in value:
            out.update(_authority_like_keys(nested))
        return out
    return set()


def _need_ref_to_dict(ref: AssessmentNeedRef) -> dict[str, Any]:
    return {"key": ref.key, "ordinal": ref.ordinal}


def _meta_to_dict(meta: EntityMeta) -> dict[str, Any]:
    return {
        "id": str(meta.id),
        "schema_version": meta.schema_version,
        "revision": meta.revision,
        "run_id": str(meta.run_id),
        "created_at": meta.created_at.isoformat(),
        "created_by": {"actor_type": meta.created_by.actor_type, "actor_id": meta.created_by.actor_id},
    }


def _fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
