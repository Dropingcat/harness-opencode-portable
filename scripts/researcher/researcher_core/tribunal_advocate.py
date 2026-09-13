"""Conditional Advocate/defense contracts for R4.4 branching dialectic.

Advocate is not a permanent pro-claim voter.  It is activated only for one
material admitted challenge against one still-defensible ArgumentArtifact.
The defense receives an explicit disclosure envelope and cannot widen evidence
or mutate epistemic state.  Its response becomes another historical argument
branch which the normal dialectic observer/reducers handle downstream.
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
from researcher_core.tribunal_argument_graph import (
    ArgumentGraphProjection,
    ArgumentRelation,
    ArgumentRelationKind,
    ArgumentRelationState,
    append_argument_branch,
    validate_argument_graph_integrity,
)
from researcher_core.tribunal_composition import AssessmentNeedRef, TribunalCompositionPolicy
from researcher_core.tribunal_disclosure import (
    DialecticBranchRef,
    DialecticDisclosureContract,
    DisclosurePurpose,
    compile_branch_ref,
    compile_dialectic_disclosure,
    disclosure_contract_to_dict as _generic_disclosure_to_dict,
    validate_disclosure_contract_integrity as _validate_generic_disclosure,
    refresh_branch_ref,
)
from researcher_core.tribunal_inquiry import (
    AdditionalEvidenceRequest,
    ArgumentArtifact,
    ArgumentPosition,
    InquiryDiscovery,
    InquiryTurn,
    InquiryTurnKind,
    ResponseGroundingItem,
    ResponseGroundingState,
    characterize_response_grounding,
)
from researcher_core.tribunal_role_handbook import RoleInstructionPack, RoleVariantKind, validate_role_instruction_pack_integrity


class TribunalAdvocateError(RuntimeError):
    pass


class AdvocateOutcome(StrEnum):
    DEFEND = "DEFEND"
    QUALIFY = "QUALIFY"
    CONCEDE_LOCAL_POINT = "CONCEDE_LOCAL_POINT"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    OPEN = "OPEN"


class AdvocateNextAction(StrEnum):
    CONTINUE_CROSS_EXAM = "CONTINUE_CROSS_EXAM"
    RETURN_TO_DIALECTIC_CONTROL = "RETURN_TO_DIALECTIC_CONTROL"
    REQUEST_LOCAL_RESEARCH = "REQUEST_LOCAL_RESEARCH"
    STOP_OPEN = "STOP_OPEN"


@dataclass(frozen=True, slots=True)
class AdvocateActivationPolicy:
    role_id: str = "advocate"
    require_material_challenge: bool = True
    require_visible_support: bool = True
    max_defenses_per_challenge: int = 1

    def __post_init__(self) -> None:
        if not self.role_id.strip() or self.max_defenses_per_challenge < 1:
            raise ValueError("invalid Advocate activation policy")


@dataclass(frozen=True, slots=True)
class AdvocateActivationDecision:
    activate: bool
    role_id: str
    challenge_relation_id: EntityId
    challenge_argument_id: EntityId
    defended_argument_id: EntityId
    assigned_need_refs: tuple[AssessmentNeedRef, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.challenge_relation_id.namespace != "ARL":
            raise ValueError("challenge_relation_id must use ARL prefix")
        if self.challenge_argument_id.namespace != "ARG" or self.defended_argument_id.namespace != "ARG":
            raise ValueError("Advocate decision argument ids must use ARG prefix")
        object.__setattr__(self, "assigned_need_refs", tuple(dict.fromkeys(self.assigned_need_refs)))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))


@dataclass(frozen=True, slots=True)
class AdvocateDefenseContract:
    meta: EntityMeta
    role_id: str
    disclosure_contract_id: EntityId
    disclosure_fingerprint: str
    challenge_relation_id: EntityId
    challenge_argument_id: EntityId
    defended_argument_id: EntityId
    challenge_turn_id: EntityId
    defended_turn_id: EntityId
    assigned_need_refs: tuple[AssessmentNeedRef, ...]
    allowed_evidence_refs: tuple[EntityId, ...]
    allowed_target_refs: tuple[EntityId, ...]
    allowed_capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_outcomes: tuple[AdvocateOutcome, ...]
    token_budget: int
    role_instruction_id: str
    role_instruction_fingerprint: str
    policy_version: str
    policy_hash: str
    contract_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "ADC":
            raise ValueError("AdvocateDefenseContract id must use ADC prefix")
        if self.disclosure_contract_id.namespace != "DDC" or self.challenge_relation_id.namespace != "ARL":
            raise ValueError("Advocate defense linkage namespaces are invalid")
        if self.challenge_argument_id.namespace != "ARG" or self.defended_argument_id.namespace != "ARG":
            raise ValueError("Advocate defense argument ids must use ARG prefix")
        if self.challenge_turn_id.namespace != "IQT" or self.defended_turn_id.namespace != "IQT":
            raise ValueError("Advocate defense turn ids must use IQT prefix")
        if not self.assigned_need_refs or self.token_budget < 1:
            raise ValueError("Advocate defense requires needs and positive token budget")
        if not self.role_instruction_fingerprint.startswith("sha256:") or not self.contract_fingerprint.startswith("sha256:"):
            raise ValueError("Advocate defense fingerprints are invalid")
        object.__setattr__(self, "assigned_need_refs", tuple(dict.fromkeys(self.assigned_need_refs)))
        object.__setattr__(self, "allowed_evidence_refs", tuple(dict.fromkeys(self.allowed_evidence_refs)))
        object.__setattr__(self, "allowed_target_refs", tuple(dict.fromkeys(self.allowed_target_refs)))
        object.__setattr__(self, "allowed_capabilities", tuple(dict.fromkeys(self.allowed_capabilities)))
        object.__setattr__(self, "allowed_tools", tuple(dict.fromkeys(self.allowed_tools)))
        object.__setattr__(self, "allowed_outcomes", tuple(dict.fromkeys(self.allowed_outcomes)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdvocateWorkerDraft:
    outcome: AdvocateOutcome
    summary: str
    justification: str
    cited_evidence_refs: tuple[EntityId, ...] = ()
    cited_target_refs: tuple[EntityId, ...] = ()
    discoveries: tuple[InquiryDiscovery, ...] = ()
    additional_evidence_requests: tuple[AdditionalEvidenceRequest, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    grounding_items: tuple[ResponseGroundingItem, ...] = ()

    def __post_init__(self) -> None:
        if not self.summary.strip() or not self.justification.strip():
            raise ValueError("Advocate draft requires summary and justification")
        object.__setattr__(self, "cited_evidence_refs", tuple(dict.fromkeys(self.cited_evidence_refs)))
        object.__setattr__(self, "cited_target_refs", tuple(dict.fromkeys(self.cited_target_refs)))
        object.__setattr__(self, "discoveries", tuple(self.discoveries))
        object.__setattr__(self, "additional_evidence_requests", tuple(self.additional_evidence_requests))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))
        object.__setattr__(self, "grounding_items", tuple(self.grounding_items))


@dataclass(frozen=True, slots=True)
class AdvocateResponse:
    contract_id: EntityId
    outcome: AdvocateOutcome
    turn: InquiryTurn
    argument: ArgumentArtifact
    relations: tuple[ArgumentRelation, ...]
    next_action: AdvocateNextAction
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_id.namespace != "ADC":
            raise ValueError("AdvocateResponse contract_id must use ADC prefix")
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))


def decide_advocate_activation(
    *,
    graph: ArgumentGraphProjection,
    arguments: Mapping[EntityId, ArgumentArtifact],
    challenge_relation: ArgumentRelation,
    composition_policy: TribunalCompositionPolicy,
    policy: AdvocateActivationPolicy = AdvocateActivationPolicy(),
) -> AdvocateActivationDecision:
    reasons: list[str] = []
    validate_argument_graph_integrity(graph, tuple(arguments.values()))
    if policy.role_id not in composition_policy.roles:
        raise TribunalAdvocateError("Advocate role is not admitted by composition policy")
    if challenge_relation.meta.id not in {x.meta.id for x in graph.relations}:
        raise TribunalAdvocateError("challenge relation is not present in supplied argument graph")
    if challenge_relation.state is not ArgumentRelationState.ACTIVE:
        return _activation(False, policy, challenge_relation, (), "CHALLENGE_RELATION_NOT_ACTIVE")
    if challenge_relation.kind not in {ArgumentRelationKind.ATTACKS, ArgumentRelationKind.UNDERCUTS}:
        return _activation(False, policy, challenge_relation, (), "RELATION_NOT_ADVOCATE_ELIGIBLE")
    challenge = arguments.get(challenge_relation.source_argument_id)
    defended = arguments.get(challenge_relation.target_argument_id)
    if challenge is None or defended is None:
        raise TribunalAdvocateError("challenge relation endpoints are unavailable")
    if challenge.position is not ArgumentPosition.CHALLENGE:
        return _activation(False, policy, challenge_relation, (), "SOURCE_NOT_CHALLENGE_POSITION")
    if defended.position not in {ArgumentPosition.SUPPORT, ArgumentPosition.QUALIFY}:
        return _activation(False, policy, challenge_relation, (), "TARGET_NOT_DEFENSIBLE_POSITION")
    overlap = tuple(x for x in challenge_relation.need_refs if x in challenge.assigned_need_refs and x in defended.assigned_need_refs)
    if not overlap:
        return _activation(False, policy, challenge_relation, (), "NO_SHARED_ASSESSMENT_NEED")
    if policy.require_material_challenge and not challenge_relation.material:
        return _activation(False, policy, challenge_relation, overlap, "CHALLENGE_NOT_MATERIAL")
    if policy.require_visible_support and not defended.cited_evidence_refs:
        return _activation(False, policy, challenge_relation, overlap, "NO_VISIBLE_SUPPORT_TO_DEFEND")

    prior_defenses = 0
    for relation in graph.relations:
        if relation.state is not ArgumentRelationState.ACTIVE or relation.kind is not ArgumentRelationKind.REPLIES_TO:
            continue
        if relation.target_argument_id != challenge.meta.id:
            continue
        source = arguments.get(relation.source_argument_id)
        if source is not None and source.role_id == policy.role_id:
            prior_defenses += 1
    if prior_defenses >= policy.max_defenses_per_challenge:
        return _activation(False, policy, challenge_relation, overlap, "ADVOCATE_DEFENSE_LIMIT_REACHED")

    reasons.extend(("MATERIAL_ADMITTED_CHALLENGE", "DEFENSIBLE_ARGUMENT", "VISIBLE_SUPPORT_PRESENT", "ADVOCATE_CONDITIONAL_ACTIVATION"))
    return AdvocateActivationDecision(
        activate=True,
        role_id=policy.role_id,
        challenge_relation_id=challenge_relation.meta.id,
        challenge_argument_id=challenge.meta.id,
        defended_argument_id=defended.meta.id,
        assigned_need_refs=overlap,
        reason_codes=tuple(reasons),
    )


def compile_advocate_disclosure(
    *,
    activation: AdvocateActivationDecision,
    graph: ArgumentGraphProjection,
    arguments: Mapping[EntityId, ArgumentArtifact],
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> DialecticDisclosureContract:
    if not activation.activate:
        raise TribunalAdvocateError("cannot compile Advocate disclosure for inactive decision")
    focus = next((x for x in graph.relations if x.meta.id == activation.challenge_relation_id), None)
    if focus is None or focus.state is not ArgumentRelationState.ACTIVE:
        raise TribunalAdvocateError("Advocate disclosure focus relation is unavailable")
    if focus.source_argument_id != activation.challenge_argument_id or focus.target_argument_id != activation.defended_argument_id:
        raise TribunalAdvocateError("Advocate activation does not match focus relation endpoints")
    branch = compile_branch_ref(
        graph=graph,
        arguments=arguments,
        anchor_argument_id=activation.challenge_argument_id,
        head_argument_id=activation.challenge_argument_id,
        anchor_relation_id=activation.challenge_relation_id,
    )
    try:
        return compile_dialectic_disclosure(
            role_id=activation.role_id,
            purpose=DisclosurePurpose.DEFENSE,
            branch=branch,
            graph=graph,
            arguments=arguments,
            assigned_need_refs=activation.assigned_need_refs,
            id_factory=id_factory,
            actor=actor,
            created_at=created_at,
            focus_argument_id=activation.challenge_argument_id,
            focus_relation_id=activation.challenge_relation_id,
        )
    except Exception as exc:
        if isinstance(exc, TribunalAdvocateError):
            raise
        raise TribunalAdvocateError(str(exc)) from exc


def validate_disclosure_contract_integrity(disclosure: DialecticDisclosureContract) -> None:
    try:
        _validate_generic_disclosure(disclosure)
    except Exception as exc:
        raise TribunalAdvocateError(str(exc)) from exc


def compile_advocate_defense_contract(
    *,
    activation: AdvocateActivationDecision,
    disclosure: DialecticDisclosureContract,
    composition_policy: TribunalCompositionPolicy,
    instruction: RoleInstructionPack,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
    token_budget: int | None = None,
) -> AdvocateDefenseContract:
    if not activation.activate or activation.role_id != disclosure.role_id:
        raise TribunalAdvocateError("Advocate activation/disclosure mismatch")
    validate_disclosure_contract_integrity(disclosure)
    validate_role_instruction_pack_integrity(instruction)
    if activation.challenge_argument_id not in disclosure.visible_argument_ids or activation.defended_argument_id not in disclosure.visible_argument_ids:
        raise TribunalAdvocateError("Advocate disclosure does not expose both challenge and defended arguments")
    role = composition_policy.roles.get(activation.role_id)
    if role is None:
        raise TribunalAdvocateError("Advocate role is not admitted by composition policy")
    if instruction.role_id != activation.role_id or instruction.variant is not RoleVariantKind.DEFENSE:
        raise TribunalAdvocateError("Advocate requires admitted defense handbook variant")
    if instruction.expected_output_contract != role.expected_output_contract:
        raise TribunalAdvocateError("Advocate instruction/output contract mismatch")
    budget = token_budget if token_budget is not None else composition_policy.token_budget_per_role
    allowed_outcomes = tuple(AdvocateOutcome)
    payload = {
        "role_id": activation.role_id,
        "disclosure_contract_id": str(disclosure.meta.id),
        "disclosure_fingerprint": disclosure.disclosure_fingerprint,
        "challenge_relation_id": str(activation.challenge_relation_id),
        "challenge_argument_id": str(activation.challenge_argument_id),
        "defended_argument_id": str(activation.defended_argument_id),
        "challenge_turn_id": str(disclosure.visible_turn_ids[1]),
        "defended_turn_id": str(disclosure.visible_turn_ids[0]),
        "needs": [(x.key, x.ordinal) for x in activation.assigned_need_refs],
        "evidence": [str(x) for x in disclosure.visible_evidence_refs],
        "targets": [str(x) for x in disclosure.visible_target_refs],
        "capabilities": list(role.allowed_capabilities),
        "tools": list(role.allowed_tools),
        "outcomes": [x.value for x in allowed_outcomes],
        "token_budget": budget,
        "instruction_id": instruction.instruction_id,
        "instruction_fingerprint": instruction.instruction_fingerprint,
        "policy_version": composition_policy.version,
        "policy_hash": composition_policy.policy_hash,
    }
    return AdvocateDefenseContract(
        meta=EntityMeta(id_factory.new("ADC"), "advocate-defense-contract/1.0", 1, disclosure.meta.run_id, created_at, actor),
        role_id=activation.role_id,
        disclosure_contract_id=disclosure.meta.id,
        disclosure_fingerprint=disclosure.disclosure_fingerprint,
        challenge_relation_id=activation.challenge_relation_id,
        challenge_argument_id=activation.challenge_argument_id,
        defended_argument_id=activation.defended_argument_id,
        challenge_turn_id=disclosure.visible_turn_ids[1],
        defended_turn_id=disclosure.visible_turn_ids[0],
        assigned_need_refs=activation.assigned_need_refs,
        allowed_evidence_refs=disclosure.visible_evidence_refs,
        allowed_target_refs=disclosure.visible_target_refs,
        allowed_capabilities=role.allowed_capabilities,
        allowed_tools=role.allowed_tools,
        allowed_outcomes=allowed_outcomes,
        token_budget=budget,
        role_instruction_id=instruction.instruction_id,
        role_instruction_fingerprint=instruction.instruction_fingerprint,
        policy_version=composition_policy.version,
        policy_hash=composition_policy.policy_hash,
        contract_fingerprint=_fingerprint(payload),
        metadata={
            "authority_boundary": "conditional defense argument only; no truth mutation and no new role admission",
            "activation_relation": str(activation.challenge_relation_id),
        },
    )


def materialize_advocate_draft(
    *,
    contract: AdvocateDefenseContract,
    disclosure: DialecticDisclosureContract,
    draft: AdvocateWorkerDraft,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> AdvocateResponse:
    validate_advocate_contract_integrity(contract, disclosure)
    if draft.outcome not in contract.allowed_outcomes:
        raise TribunalAdvocateError("Advocate outcome is not allowed by contract")
    if not set(draft.cited_evidence_refs).issubset(contract.allowed_evidence_refs):
        raise TribunalAdvocateError("Advocate cited evidence outside disclosure")
    if not set(draft.cited_target_refs).issubset(contract.allowed_target_refs):
        raise TribunalAdvocateError("Advocate cited target outside disclosure")
    allowed_grounding_refs = (
        set(disclosure.visible_argument_ids)
        | set(disclosure.visible_turn_ids)
        | set(contract.allowed_evidence_refs)
        | set(contract.allowed_target_refs)
    )
    grounding_state = characterize_response_grounding(draft.grounding_items)
    if draft.outcome is AdvocateOutcome.DEFEND and grounding_state in {
        ResponseGroundingState.MODEL_PRIOR_ONLY,
        ResponseGroundingState.UNGROUNDED,
        ResponseGroundingState.VISIBLE_CONTEXT_ONLY,
    }:
        raise TribunalAdvocateError("Advocate cannot DEFEND without disclosed evidence grounding")
    for item in draft.grounding_items:
        if not set(item.refs).issubset(allowed_grounding_refs):
            raise TribunalAdvocateError("Advocate grounding references hidden material")
        if item.kind.name == "DISCLOSED_EVIDENCE" and not set(item.refs).issubset(contract.allowed_evidence_refs):
            raise TribunalAdvocateError("Advocate evidence grounding references hidden or non-evidence material")
        if item.kind.name == "DISCLOSED_TARGET" and not set(item.refs).issubset(contract.allowed_target_refs):
            raise TribunalAdvocateError("Advocate target grounding references hidden or non-target material")
        if item.kind.name == "PRIOR_ARGUMENT" and not set(item.refs).issubset(disclosure.visible_argument_ids):
            raise TribunalAdvocateError("Advocate argument grounding references hidden material")
        if item.kind.name == "PRIOR_TURN" and not set(item.refs).issubset(disclosure.visible_turn_ids):
            raise TribunalAdvocateError("Advocate turn grounding references hidden material")
    for discovery in draft.discoveries:
        if not set(discovery.need_refs).issubset(contract.assigned_need_refs):
            raise TribunalAdvocateError("Advocate discovery widens assigned AssessmentNeed")
        if not set(discovery.evidence_refs).issubset(contract.allowed_evidence_refs):
            raise TribunalAdvocateError("Advocate discovery references hidden evidence")
    for request in draft.additional_evidence_requests:
        if not set(request.need_refs).issubset(contract.assigned_need_refs):
            raise TribunalAdvocateError("Advocate evidence request widens assigned AssessmentNeed")
        if not set(request.target_refs).issubset(contract.allowed_target_refs):
            raise TribunalAdvocateError("Advocate evidence request references hidden target")

    turn = InquiryTurn(
        meta=EntityMeta(id_factory.new("IQT"), "inquiry-turn/1.0", 1, contract.meta.run_id, created_at, actor),
        contract_id=contract.meta.id,
        role_id=contract.role_id,
        kind=InquiryTurnKind.REBUTTAL,
        content=draft.summary,
        parent_turn_id=contract.challenge_turn_id,
        cited_refs=tuple(dict.fromkeys((*draft.cited_target_refs, *draft.cited_evidence_refs))),
        metadata={
            "phase": "CONDITIONAL_ADVOCATE_DEFENSE",
            "challenge_argument_id": str(contract.challenge_argument_id),
            "defended_argument_id": str(contract.defended_argument_id),
        },
    )
    position = _position_for_outcome(draft.outcome)
    argument = ArgumentArtifact(
        meta=EntityMeta(id_factory.new("ARG"), "argument-artifact/1.0", 1, contract.meta.run_id, created_at, actor),
        contract_id=contract.meta.id,
        source_turn_id=turn.meta.id,
        role_id=contract.role_id,
        position=position,
        assigned_need_refs=contract.assigned_need_refs,
        summary=draft.summary,
        justification=draft.justification,
        cited_evidence_refs=draft.cited_evidence_refs,
        cited_target_refs=draft.cited_target_refs,
        discoveries=draft.discoveries,
        additional_evidence_requests=draft.additional_evidence_requests,
        grounding_items=draft.grounding_items,
        grounding_state=grounding_state,
        metadata={
            **dict(draft.metadata),
            "advocate_outcome": draft.outcome.value,
            "disclosure_contract_id": str(contract.disclosure_contract_id),
            "disclosure_fingerprint": contract.disclosure_fingerprint,
            "authority_boundary": "conditional defense argument; reducers/dialectic control own downstream state",
        },
    )

    reply = ArgumentRelation(
        meta=EntityMeta(id_factory.new("ARL"), "argument-relation/1.0", 1, contract.meta.run_id, created_at, actor),
        kind=ArgumentRelationKind.REPLIES_TO,
        source_argument_id=argument.meta.id,
        target_argument_id=contract.challenge_argument_id,
        need_refs=contract.assigned_need_refs,
        material=True,
        reason_codes=("ADVOCATE_REPLY_TO_CHALLENGE",),
        metadata={"advocate_outcome": draft.outcome.value},
    )
    relations: list[ArgumentRelation] = [reply]
    if draft.outcome in {AdvocateOutcome.DEFEND, AdvocateOutcome.QUALIFY}:
        relations.append(ArgumentRelation(
            meta=EntityMeta(id_factory.new("ARL"), "argument-relation/1.0", 1, contract.meta.run_id, created_at, actor),
            kind=ArgumentRelationKind.DEFENDS,
            source_argument_id=argument.meta.id,
            target_argument_id=contract.defended_argument_id,
            need_refs=contract.assigned_need_refs,
            material=True,
            reason_codes=("ADVOCATE_DEFENSE_BRANCH",),
            metadata={"advocate_outcome": draft.outcome.value},
        ))

    next_action, reasons = _route_advocate_output(draft)
    return AdvocateResponse(
        contract_id=contract.meta.id,
        outcome=draft.outcome,
        turn=turn,
        argument=argument,
        relations=tuple(relations),
        next_action=next_action,
        reason_codes=reasons,
    )


def admit_advocate_response_to_argument_graph(
    *,
    graph: ArgumentGraphProjection,
    arguments: Mapping[EntityId, ArgumentArtifact],
    disclosure: DialecticDisclosureContract,
    response: AdvocateResponse,
    actor: ActorRef,
    created_at: datetime,
) -> tuple[ArgumentGraphProjection, dict[EntityId, ArgumentArtifact], DialecticBranchRef]:
    """Admit a validated Advocate response without changing epistemic state."""
    if graph.meta.id != disclosure.branch.argument_graph_id:
        raise TribunalAdvocateError("Advocate admission branch/graph identity mismatch")
    if graph.meta.revision != disclosure.branch.graph_revision or graph.graph_fingerprint != disclosure.branch.graph_fingerprint:
        raise TribunalAdvocateError("Advocate admission requires current branch graph snapshot")
    if response.contract_id.namespace != "ADC" or response.argument.contract_id != response.contract_id:
        raise TribunalAdvocateError("Advocate response contract lineage mismatch")
    if response.argument.meta.id in arguments or response.argument.meta.id in graph.argument_ids:
        raise TribunalAdvocateError("Advocate argument is already admitted")
    if response.argument.meta.run_id != graph.meta.run_id:
        raise TribunalAdvocateError("Advocate admission cannot cross run lineage")
    if not response.relations or any(relation.source_argument_id != response.argument.meta.id for relation in response.relations):
        raise TribunalAdvocateError("Advocate response relations do not originate from its argument")

    merged = dict(arguments)
    merged[response.argument.meta.id] = response.argument
    new_graph = append_argument_branch(
        graph=graph,
        new_meta=EntityMeta(graph.meta.id, graph.meta.schema_version, graph.meta.revision + 1, graph.meta.run_id, created_at, actor),
        arguments=tuple(merged.values()),
        new_relations=response.relations,
    )
    new_branch = refresh_branch_ref(
        branch=disclosure.branch,
        graph=new_graph,
        arguments=merged,
        head_argument_id=response.argument.meta.id,
    )
    return new_graph, merged, new_branch


def validate_advocate_contract_integrity(
    contract: AdvocateDefenseContract,
    disclosure: DialecticDisclosureContract,
) -> None:
    if contract.disclosure_contract_id != disclosure.meta.id or contract.disclosure_fingerprint != disclosure.disclosure_fingerprint:
        raise TribunalAdvocateError("Advocate contract/disclosure mismatch")
    if contract.challenge_relation_id != disclosure.focus_relation_id:
        raise TribunalAdvocateError("Advocate challenge relation/disclosure mismatch")
    payload = {
        "role_id": contract.role_id,
        "disclosure_contract_id": str(contract.disclosure_contract_id),
        "disclosure_fingerprint": contract.disclosure_fingerprint,
        "challenge_relation_id": str(contract.challenge_relation_id),
        "challenge_argument_id": str(contract.challenge_argument_id),
        "defended_argument_id": str(contract.defended_argument_id),
        "challenge_turn_id": str(contract.challenge_turn_id),
        "defended_turn_id": str(contract.defended_turn_id),
        "needs": [(x.key, x.ordinal) for x in contract.assigned_need_refs],
        "evidence": [str(x) for x in contract.allowed_evidence_refs],
        "targets": [str(x) for x in contract.allowed_target_refs],
        "capabilities": list(contract.allowed_capabilities),
        "tools": list(contract.allowed_tools),
        "outcomes": [x.value for x in contract.allowed_outcomes],
        "token_budget": contract.token_budget,
        "instruction_id": contract.role_instruction_id,
        "instruction_fingerprint": contract.role_instruction_fingerprint,
        "policy_version": contract.policy_version,
        "policy_hash": contract.policy_hash,
    }
    if _fingerprint(payload) != contract.contract_fingerprint:
        raise TribunalAdvocateError("AdvocateDefenseContract fingerprint mismatch")


def _activation(
    activate: bool,
    policy: AdvocateActivationPolicy,
    relation: ArgumentRelation,
    needs: Sequence[AssessmentNeedRef],
    reason: str,
) -> AdvocateActivationDecision:
    return AdvocateActivationDecision(
        activate=activate,
        role_id=policy.role_id,
        challenge_relation_id=relation.meta.id,
        challenge_argument_id=relation.source_argument_id,
        defended_argument_id=relation.target_argument_id,
        assigned_need_refs=tuple(needs),
        reason_codes=(reason,),
    )


def _position_for_outcome(outcome: AdvocateOutcome) -> ArgumentPosition:
    if outcome is AdvocateOutcome.DEFEND:
        return ArgumentPosition.SUPPORT
    if outcome in {AdvocateOutcome.QUALIFY, AdvocateOutcome.CONCEDE_LOCAL_POINT}:
        return ArgumentPosition.QUALIFY
    return ArgumentPosition.OPEN


def _route_advocate_output(draft: AdvocateWorkerDraft) -> tuple[AdvocateNextAction, tuple[str, ...]]:
    if draft.additional_evidence_requests or draft.outcome is AdvocateOutcome.REQUEST_EVIDENCE:
        return AdvocateNextAction.REQUEST_LOCAL_RESEARCH, ("ADVOCATE_REQUESTS_EVIDENCE",)
    if draft.outcome in {AdvocateOutcome.DEFEND, AdvocateOutcome.QUALIFY}:
        return AdvocateNextAction.CONTINUE_CROSS_EXAM, ("ADVOCATE_POSITION_REQUIRES_ADVERSARIAL_TEST",)
    if draft.outcome is AdvocateOutcome.CONCEDE_LOCAL_POINT:
        return AdvocateNextAction.RETURN_TO_DIALECTIC_CONTROL, ("ADVOCATE_CONCEDES_LOCAL_POINT",)
    return AdvocateNextAction.STOP_OPEN, ("ADVOCATE_REMAINS_OPEN",)



def disclosure_contract_to_dict(contract: DialecticDisclosureContract) -> dict[str, Any]:
    return _generic_disclosure_to_dict(contract)


def advocate_defense_contract_to_dict(contract: AdvocateDefenseContract) -> dict[str, Any]:
    return {
        "schema_version": "advocate-defense-contract/1.0",
        "id": str(contract.meta.id),
        "role_id": contract.role_id,
        "disclosure_contract_id": str(contract.disclosure_contract_id),
        "disclosure_fingerprint": contract.disclosure_fingerprint,
        "challenge_relation_id": str(contract.challenge_relation_id),
        "challenge_argument_id": str(contract.challenge_argument_id),
        "defended_argument_id": str(contract.defended_argument_id),
        "challenge_turn_id": str(contract.challenge_turn_id),
        "defended_turn_id": str(contract.defended_turn_id),
        "assigned_need_refs": [{"key": x.key, "ordinal": x.ordinal} for x in contract.assigned_need_refs],
        "allowed_evidence_refs": [str(x) for x in contract.allowed_evidence_refs],
        "allowed_target_refs": [str(x) for x in contract.allowed_target_refs],
        "allowed_capabilities": list(contract.allowed_capabilities),
        "allowed_tools": list(contract.allowed_tools),
        "allowed_outcomes": [x.value for x in contract.allowed_outcomes],
        "token_budget": contract.token_budget,
        "role_instruction_id": contract.role_instruction_id,
        "role_instruction_fingerprint": contract.role_instruction_fingerprint,
        "policy_version": contract.policy_version,
        "policy_hash": contract.policy_hash,
        "contract_fingerprint": contract.contract_fingerprint,
        "metadata": dict(contract.metadata),
    }


def advocate_response_to_dict(response: AdvocateResponse) -> dict[str, Any]:
    return {
        "schema_version": "advocate-response/1.0",
        "contract_id": str(response.contract_id),
        "outcome": response.outcome.value,
        "turn_id": str(response.turn.meta.id),
        "argument_id": str(response.argument.meta.id),
        "relation_ids": [str(x.meta.id) for x in response.relations],
        "relation_kinds": [x.kind.value for x in response.relations],
        "next_action": response.next_action.value,
        "reason_codes": list(response.reason_codes),
    }


def _fingerprint(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
