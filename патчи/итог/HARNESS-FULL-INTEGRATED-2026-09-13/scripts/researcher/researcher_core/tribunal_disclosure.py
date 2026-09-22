"""R4.4 L2b generic branch disclosure and typed question targeting.

This module owns *what prior dialectic artifacts a role may see* for one
argument-graph branch.  It does not execute roles, mutate Claim/GraphEdge
truth, or infer scientific weakness from prose.
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
    ArgumentRelationState,
    validate_argument_graph_integrity,
)
from researcher_core.tribunal_composition import AssessmentNeedRef
from researcher_core.tribunal_inquiry import ArgumentArtifact, InquiryTurn, InquiryTurnKind
from researcher_core.tribunal_role_handbook import (
    RoleInstructionPack,
    RoleVariantKind,
    validate_role_instruction_pack_integrity,
)


class TribunalDisclosureError(RuntimeError):
    pass


class DisclosurePurpose(StrEnum):
    CHALLENGE = "CHALLENGE"
    DIRECT_QUESTION = "DIRECT_QUESTION"
    QUESTION_ON_ANSWER = "QUESTION_ON_ANSWER"
    DEFENSE = "DEFENSE"
    CROSS_EXAM = "CROSS_EXAM"


@dataclass(frozen=True, slots=True)
class DialecticBranchRef:
    """Stable branch identity plus the graph snapshot currently being viewed.

    ``branch_key`` deliberately excludes graph revision and current head so a
    branch can survive new replies/research and still retain its history.
    """

    branch_key: str
    argument_graph_id: EntityId
    graph_revision: int
    graph_fingerprint: str
    root_argument_id: EntityId
    anchor_argument_id: EntityId
    anchor_relation_id: EntityId | None
    head_argument_id: EntityId
    issue_signature: str = ""

    def __post_init__(self) -> None:
        if not self.branch_key.startswith("DBR-"):
            raise ValueError("branch_key must use DBR- prefix")
        if self.argument_graph_id.namespace != "AGP":
            raise ValueError("branch argument_graph_id must use AGP prefix")
        for ref in (self.root_argument_id, self.anchor_argument_id, self.head_argument_id):
            if ref.namespace != "ARG":
                raise ValueError("branch argument refs must use ARG prefix")
        if self.anchor_relation_id is not None and self.anchor_relation_id.namespace != "ARL":
            raise ValueError("branch anchor_relation_id must use ARL prefix")
        if self.graph_revision < 1 or not self.graph_fingerprint.startswith("sha256:"):
            raise ValueError("branch graph snapshot is invalid")


@dataclass(frozen=True, slots=True)
class DialecticDisclosurePolicy:
    """Small deterministic policy for prior-artifact disclosure."""

    policy_id: str = "researcher-r4-dialectic-disclosure"
    version: str = "0.4.4-l2b"
    include_branch_history: bool = True
    include_argument_evidence: bool = True
    include_argument_targets: bool = True
    hide_sibling_branches: bool = True
    max_visible_arguments: int = 12

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.version.strip():
            raise ValueError("disclosure policy id/version are required")
        if self.max_visible_arguments < 1:
            raise ValueError("max_visible_arguments must be positive")

    @property
    def policy_hash(self) -> str:
        payload = {
            "policy_id": self.policy_id,
            "version": self.version,
            "include_branch_history": self.include_branch_history,
            "include_argument_evidence": self.include_argument_evidence,
            "include_argument_targets": self.include_argument_targets,
            "hide_sibling_branches": self.hide_sibling_branches,
            "max_visible_arguments": self.max_visible_arguments,
        }
        return _fingerprint(payload)


@dataclass(frozen=True, slots=True)
class DialecticDisclosureContract:
    meta: EntityMeta
    role_id: str
    purpose: DisclosurePurpose
    branch: DialecticBranchRef
    focus_argument_id: EntityId
    focus_relation_id: EntityId | None
    focus_turn_id: EntityId | None
    focus_issue_signature: str
    visible_argument_ids: tuple[EntityId, ...]
    visible_turn_ids: tuple[EntityId, ...]
    visible_relation_ids: tuple[EntityId, ...]
    visible_evidence_refs: tuple[EntityId, ...]
    visible_target_refs: tuple[EntityId, ...]
    hidden_argument_ids: tuple[EntityId, ...]
    assigned_need_refs: tuple[AssessmentNeedRef, ...]
    disclosure_policy_version: str
    disclosure_policy_hash: str
    disclosure_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "DDC":
            raise ValueError("DialecticDisclosureContract id must use DDC prefix")
        if not self.role_id or self.focus_argument_id.namespace != "ARG":
            raise ValueError("disclosure role/focus argument are required")
        if self.focus_relation_id is not None and self.focus_relation_id.namespace != "ARL":
            raise ValueError("focus_relation_id must use ARL prefix")
        if self.focus_turn_id is not None and self.focus_turn_id.namespace != "IQT":
            raise ValueError("focus_turn_id must use IQT prefix")
        if not self.visible_argument_ids or not self.assigned_need_refs:
            raise ValueError("disclosure requires visible arguments and assigned needs")
        if not self.disclosure_policy_version or not self.disclosure_policy_hash.startswith("sha256:"):
            raise ValueError("disclosure policy identity is invalid")
        if not self.disclosure_fingerprint.startswith("sha256:"):
            raise ValueError("disclosure fingerprint is invalid")
        object.__setattr__(self, "visible_argument_ids", tuple(dict.fromkeys(self.visible_argument_ids)))
        object.__setattr__(self, "visible_turn_ids", tuple(dict.fromkeys(self.visible_turn_ids)))
        object.__setattr__(self, "visible_relation_ids", tuple(dict.fromkeys(self.visible_relation_ids)))
        object.__setattr__(self, "visible_evidence_refs", tuple(dict.fromkeys(self.visible_evidence_refs)))
        object.__setattr__(self, "visible_target_refs", tuple(dict.fromkeys(self.visible_target_refs)))
        object.__setattr__(self, "hidden_argument_ids", tuple(dict.fromkeys(self.hidden_argument_ids)))
        object.__setattr__(self, "assigned_need_refs", tuple(dict.fromkeys(self.assigned_need_refs)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))

    # Compatibility properties for the R4.4 L2a Advocate contract.
    @property
    def argument_graph_id(self) -> EntityId:
        return self.branch.argument_graph_id

    @property
    def graph_fingerprint(self) -> str:
        return self.branch.graph_fingerprint


class QuestionPurpose(StrEnum):
    DIRECT_QUESTION = "DIRECT_QUESTION"
    QUESTION_ON_ANSWER = "QUESTION_ON_ANSWER"


class QuestionTargetKind(StrEnum):
    ARGUMENT_JUSTIFICATION = "ARGUMENT_JUSTIFICATION"
    EMERGENT_ISSUE = "EMERGENT_ISSUE"


@dataclass(frozen=True, slots=True)
class DialecticQuestionContract:
    meta: EntityMeta
    role_id: str
    answer_role_id: str
    purpose: QuestionPurpose
    target_kind: QuestionTargetKind
    branch: DialecticBranchRef
    disclosure_contract_id: EntityId
    disclosure_fingerprint: str
    target_argument_id: EntityId
    target_turn_id: EntityId | None
    target_issue_signature: str
    parent_turn_id: EntityId
    assigned_need_refs: tuple[AssessmentNeedRef, ...]
    allowed_evidence_refs: tuple[EntityId, ...]
    allowed_target_refs: tuple[EntityId, ...]
    expected_closure_surface: tuple[str, ...]
    max_response_tokens: int
    max_followups: int
    role_instruction_id: str
    role_instruction_fingerprint: str
    policy_version: str
    policy_hash: str
    contract_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "DQC":
            raise ValueError("DialecticQuestionContract id must use DQC prefix")
        if not self.role_id or not self.answer_role_id:
            raise ValueError("questioner and answer role ids are required")
        if self.disclosure_contract_id.namespace != "DDC":
            raise ValueError("question disclosure_contract_id must use DDC prefix")
        if self.target_argument_id.namespace != "ARG" or self.parent_turn_id.namespace != "IQT":
            raise ValueError("question target/parent namespaces are invalid")
        if self.target_turn_id is not None and self.target_turn_id.namespace != "IQT":
            raise ValueError("question target_turn_id must use IQT prefix")
        if not self.assigned_need_refs or self.max_response_tokens < 1 or self.max_followups < 0:
            raise ValueError("question contract limits/need coverage are invalid")
        if not self.role_instruction_fingerprint.startswith("sha256:") or not self.contract_fingerprint.startswith("sha256:"):
            raise ValueError("question fingerprints are invalid")
        object.__setattr__(self, "assigned_need_refs", tuple(dict.fromkeys(self.assigned_need_refs)))
        object.__setattr__(self, "allowed_evidence_refs", tuple(dict.fromkeys(self.allowed_evidence_refs)))
        object.__setattr__(self, "allowed_target_refs", tuple(dict.fromkeys(self.allowed_target_refs)))
        object.__setattr__(self, "expected_closure_surface", tuple(dict.fromkeys(x for x in self.expected_closure_surface if x)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


def compile_branch_ref(
    *,
    graph: ArgumentGraphProjection,
    arguments: Mapping[EntityId, ArgumentArtifact],
    anchor_argument_id: EntityId,
    head_argument_id: EntityId | None = None,
    anchor_relation_id: EntityId | None = None,
    issue_signature: str = "",
) -> DialecticBranchRef:
    validate_argument_graph_integrity(graph, tuple(arguments.values()))
    if anchor_argument_id not in arguments:
        raise TribunalDisclosureError("branch anchor argument is absent from graph")
    head = head_argument_id or anchor_argument_id
    if head not in arguments:
        raise TribunalDisclosureError("branch head argument is absent from graph")
    if anchor_relation_id is not None:
        relation = _relation_by_id(graph, anchor_relation_id)
        if relation.state is not ArgumentRelationState.ACTIVE:
            raise TribunalDisclosureError("branch anchor relation is not active")
        if anchor_argument_id not in {relation.source_argument_id, relation.target_argument_id}:
            raise TribunalDisclosureError("branch anchor argument is not an endpoint of anchor relation")
    reachable = _reachable_targets(graph, head)
    roots = tuple(x for x in graph.root_argument_ids if x in reachable)
    if len(roots) != 1:
        raise TribunalDisclosureError("branch head must resolve to exactly one graph root")
    root = roots[0]
    if anchor_argument_id not in reachable:
        raise TribunalDisclosureError("branch head does not belong to anchor lineage")
    seed = {
        "graph_id": str(graph.meta.id),
        "root": str(root),
        "anchor_argument": str(anchor_argument_id),
        "anchor_relation": str(anchor_relation_id) if anchor_relation_id else None,
        "issue_signature": issue_signature,
    }
    digest = hashlib.sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return DialecticBranchRef(
        branch_key=f"DBR-{digest[:24]}",
        argument_graph_id=graph.meta.id,
        graph_revision=graph.meta.revision,
        graph_fingerprint=graph.graph_fingerprint,
        root_argument_id=root,
        anchor_argument_id=anchor_argument_id,
        anchor_relation_id=anchor_relation_id,
        head_argument_id=head,
        issue_signature=issue_signature,
    )


def refresh_branch_ref(
    *,
    branch: DialecticBranchRef,
    graph: ArgumentGraphProjection,
    arguments: Mapping[EntityId, ArgumentArtifact],
    head_argument_id: EntityId,
) -> DialecticBranchRef:
    refreshed = compile_branch_ref(
        graph=graph,
        arguments=arguments,
        anchor_argument_id=branch.anchor_argument_id,
        anchor_relation_id=branch.anchor_relation_id,
        head_argument_id=head_argument_id,
        issue_signature=branch.issue_signature,
    )
    if refreshed.branch_key != branch.branch_key:
        raise TribunalDisclosureError("refreshed graph no longer represents the same dialectic branch")
    return refreshed


def compile_dialectic_disclosure(
    *,
    role_id: str,
    purpose: DisclosurePurpose,
    branch: DialecticBranchRef,
    graph: ArgumentGraphProjection,
    arguments: Mapping[EntityId, ArgumentArtifact],
    assigned_need_refs: Sequence[AssessmentNeedRef],
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
    focus_argument_id: EntityId | None = None,
    focus_relation_id: EntityId | None = None,
    focus_turn_id: EntityId | None = None,
    focus_issue_signature: str = "",
    base_evidence_refs: Sequence[EntityId] = (),
    base_target_refs: Sequence[EntityId] = (),
    policy: DialecticDisclosurePolicy = DialecticDisclosurePolicy(),
) -> DialecticDisclosureContract:
    validate_argument_graph_integrity(graph, tuple(arguments.values()))
    _validate_branch_snapshot(branch, graph)
    focus_arg = focus_argument_id or branch.head_argument_id
    if focus_arg not in arguments:
        raise TribunalDisclosureError("focus argument is absent from graph")
    if focus_relation_id is not None:
        relation = _relation_by_id(graph, focus_relation_id)
        if relation.state is not ArgumentRelationState.ACTIVE:
            raise TribunalDisclosureError("focus relation is not active")
        if focus_arg not in {relation.source_argument_id, relation.target_argument_id}:
            raise TribunalDisclosureError("focus argument is not on focus relation")

    branch_args = _branch_arguments(graph, branch)
    if focus_arg not in branch_args:
        raise TribunalDisclosureError("focus argument is outside selected branch")
    if purpose is DisclosurePurpose.CHALLENGE:
        visible_args = (focus_arg,)
    elif purpose is DisclosurePurpose.DEFENSE and focus_relation_id is not None:
        relation = _relation_by_id(graph, focus_relation_id)
        visible_args = tuple(dict.fromkeys((relation.target_argument_id, relation.source_argument_id)))
    else:
        visible_args = tuple(branch_args)
    if len(visible_args) > policy.max_visible_arguments:
        raise TribunalDisclosureError("branch disclosure exceeds visible-argument limit")

    visible_arg_set = set(visible_args)
    visible_relations = tuple(
        r.meta.id for r in graph.relations
        if r.state is ArgumentRelationState.ACTIVE
        and r.source_argument_id in visible_arg_set
        and r.target_argument_id in visible_arg_set
    )
    visible_turns = tuple(dict.fromkeys(arguments[x].source_turn_id for x in visible_args))
    evidence = list(base_evidence_refs)
    targets = list(base_target_refs)
    if policy.include_argument_evidence:
        for arg_id in visible_args:
            evidence.extend(arguments[arg_id].cited_evidence_refs)
    if policy.include_argument_targets:
        for arg_id in visible_args:
            targets.extend(arguments[arg_id].cited_target_refs)
    hidden = tuple(x for x in graph.argument_ids if x not in visible_arg_set) if policy.hide_sibling_branches else ()
    needs = tuple(dict.fromkeys(assigned_need_refs))
    if not needs:
        raise TribunalDisclosureError("disclosure requires AssessmentNeed coverage")
    common_needs = set(needs)
    for arg_id in visible_args:
        if not common_needs.intersection(arguments[arg_id].assigned_need_refs):
            raise TribunalDisclosureError("visible argument does not overlap disclosure AssessmentNeed coverage")

    payload = _disclosure_payload(
        role_id=role_id,
        purpose=purpose,
        branch=branch,
        focus_argument_id=focus_arg,
        focus_relation_id=focus_relation_id,
        focus_turn_id=focus_turn_id,
        focus_issue_signature=focus_issue_signature,
        visible_argument_ids=visible_args,
        visible_turn_ids=visible_turns,
        visible_relation_ids=visible_relations,
        visible_evidence_refs=tuple(dict.fromkeys(evidence)),
        visible_target_refs=tuple(dict.fromkeys(targets)),
        hidden_argument_ids=hidden,
        assigned_need_refs=needs,
        disclosure_policy_version=policy.version,
        disclosure_policy_hash=policy.policy_hash,
    )
    return DialecticDisclosureContract(
        meta=EntityMeta(id_factory.new("DDC"), "dialectic-disclosure-contract/1.1", 1, graph.meta.run_id, created_at, actor),
        role_id=role_id,
        purpose=purpose,
        branch=branch,
        focus_argument_id=focus_arg,
        focus_relation_id=focus_relation_id,
        focus_turn_id=focus_turn_id,
        focus_issue_signature=focus_issue_signature,
        visible_argument_ids=visible_args,
        visible_turn_ids=visible_turns,
        visible_relation_ids=visible_relations,
        visible_evidence_refs=tuple(dict.fromkeys(evidence)),
        visible_target_refs=tuple(dict.fromkeys(targets)),
        hidden_argument_ids=hidden,
        assigned_need_refs=needs,
        disclosure_policy_version=policy.version,
        disclosure_policy_hash=policy.policy_hash,
        disclosure_fingerprint=_fingerprint(payload),
        metadata={
            "authority_boundary": "branch-local prior-artifact disclosure only; no truth mutation",
            "branch_key": branch.branch_key,
        },
    )


def validate_disclosure_contract_integrity(
    disclosure: DialecticDisclosureContract,
    *,
    graph: ArgumentGraphProjection | None = None,
) -> None:
    if set(disclosure.visible_argument_ids).intersection(disclosure.hidden_argument_ids):
        raise TribunalDisclosureError("disclosure visible/hidden arguments overlap")
    if disclosure.focus_argument_id not in disclosure.visible_argument_ids:
        raise TribunalDisclosureError("disclosure focus argument is not visible")
    if graph is not None:
        _validate_branch_snapshot(disclosure.branch, graph)
        if not set(disclosure.visible_argument_ids).issubset(graph.argument_ids):
            raise TribunalDisclosureError("disclosure references arguments outside graph")
    payload = _disclosure_payload(
        role_id=disclosure.role_id,
        purpose=disclosure.purpose,
        branch=disclosure.branch,
        focus_argument_id=disclosure.focus_argument_id,
        focus_relation_id=disclosure.focus_relation_id,
        focus_turn_id=disclosure.focus_turn_id,
        focus_issue_signature=disclosure.focus_issue_signature,
        visible_argument_ids=disclosure.visible_argument_ids,
        visible_turn_ids=disclosure.visible_turn_ids,
        visible_relation_ids=disclosure.visible_relation_ids,
        visible_evidence_refs=disclosure.visible_evidence_refs,
        visible_target_refs=disclosure.visible_target_refs,
        hidden_argument_ids=disclosure.hidden_argument_ids,
        assigned_need_refs=disclosure.assigned_need_refs,
        disclosure_policy_version=disclosure.disclosure_policy_version,
        disclosure_policy_hash=disclosure.disclosure_policy_hash,
    )
    if _fingerprint(payload) != disclosure.disclosure_fingerprint:
        raise TribunalDisclosureError("DialecticDisclosureContract fingerprint mismatch")


def compile_question_contract(
    *,
    purpose: QuestionPurpose,
    role_id: str,
    answer_role_id: str,
    disclosure: DialecticDisclosureContract,
    instruction: RoleInstructionPack,
    parent_turn_id: EntityId,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
    policy_version: str,
    policy_hash: str,
    target_argument_id: EntityId | None = None,
    target_turn_id: EntityId | None = None,
    target_issue_signature: str = "",
    admitted_new_issue_signatures: Sequence[str] = (),
    expected_closure_surface: Sequence[str] = (),
    max_response_tokens: int = 1800,
    max_followups: int = 1,
) -> DialecticQuestionContract:
    validate_disclosure_contract_integrity(disclosure)
    validate_role_instruction_pack_integrity(instruction)
    if instruction.role_id != role_id:
        raise TribunalDisclosureError("question role/instruction mismatch")
    if not answer_role_id.strip():
        raise TribunalDisclosureError("question answer_role_id is required")
    if answer_role_id == role_id:
        raise TribunalDisclosureError("questioner and answer role must be distinct in bounded dialectic")
    if parent_turn_id.namespace != "IQT":
        raise TribunalDisclosureError("question parent_turn_id must use IQT prefix")
    if parent_turn_id not in disclosure.visible_turn_ids:
        raise TribunalDisclosureError("question parent turn is outside branch disclosure")
    expected_variant = RoleVariantKind.CROSS_EXAM if purpose is QuestionPurpose.QUESTION_ON_ANSWER else None
    if expected_variant is not None and instruction.variant is not expected_variant:
        raise TribunalDisclosureError("question-on-answer requires cross_exam handbook variant")
    if purpose is QuestionPurpose.DIRECT_QUESTION and instruction.variant not in {RoleVariantKind.CHALLENGER, RoleVariantKind.CROSS_EXAM}:
        raise TribunalDisclosureError("direct question requires challenger or cross_exam handbook variant")
    expected_disclosure = (
        DisclosurePurpose.QUESTION_ON_ANSWER if purpose is QuestionPurpose.QUESTION_ON_ANSWER
        else DisclosurePurpose.DIRECT_QUESTION
    )
    if disclosure.purpose is not expected_disclosure:
        raise TribunalDisclosureError("question purpose/disclosure purpose mismatch")
    target_arg = target_argument_id or disclosure.focus_argument_id
    if target_arg not in disclosure.visible_argument_ids:
        raise TribunalDisclosureError("question target argument is outside disclosure")
    issue = target_issue_signature.strip()
    if purpose is QuestionPurpose.QUESTION_ON_ANSWER:
        if not issue:
            raise TribunalDisclosureError("question-on-answer requires typed issue target")
        if issue not in set(admitted_new_issue_signatures):
            raise TribunalDisclosureError("Q2 target must be a newly admitted issue surface from the prior answer")
        if target_turn_id is None or target_turn_id not in disclosure.visible_turn_ids:
            raise TribunalDisclosureError("Q2 target turn must be disclosed")
    elif issue and admitted_new_issue_signatures and issue not in set(admitted_new_issue_signatures):
        raise TribunalDisclosureError("direct question issue target is not admitted")
    target_kind = (
        QuestionTargetKind.EMERGENT_ISSUE
        if purpose is QuestionPurpose.QUESTION_ON_ANSWER or issue
        else QuestionTargetKind.ARGUMENT_JUSTIFICATION
    )

    payload = {
        "role_id": role_id,
        "answer_role_id": answer_role_id,
        "purpose": purpose.value,
        "target_kind": target_kind.value,
        "branch_key": disclosure.branch.branch_key,
        "graph_fingerprint": disclosure.branch.graph_fingerprint,
        "disclosure_id": str(disclosure.meta.id),
        "disclosure_fingerprint": disclosure.disclosure_fingerprint,
        "target_argument_id": str(target_arg),
        "target_turn_id": str(target_turn_id) if target_turn_id else None,
        "target_issue_signature": issue,
        "parent_turn_id": str(parent_turn_id),
        "needs": [(x.key, x.ordinal) for x in disclosure.assigned_need_refs],
        "evidence": [str(x) for x in disclosure.visible_evidence_refs],
        "targets": [str(x) for x in disclosure.visible_target_refs],
        "closure": list(expected_closure_surface),
        "max_response_tokens": max_response_tokens,
        "max_followups": max_followups,
        "instruction_id": instruction.instruction_id,
        "instruction_fingerprint": instruction.instruction_fingerprint,
        "policy_version": policy_version,
        "policy_hash": policy_hash,
    }
    return DialecticQuestionContract(
        meta=EntityMeta(id_factory.new("DQC"), "dialectic-question-contract/1.1", 1, disclosure.meta.run_id, created_at, actor),
        role_id=role_id,
        answer_role_id=answer_role_id,
        purpose=purpose,
        target_kind=target_kind,
        branch=disclosure.branch,
        disclosure_contract_id=disclosure.meta.id,
        disclosure_fingerprint=disclosure.disclosure_fingerprint,
        target_argument_id=target_arg,
        target_turn_id=target_turn_id,
        target_issue_signature=issue,
        parent_turn_id=parent_turn_id,
        assigned_need_refs=disclosure.assigned_need_refs,
        allowed_evidence_refs=disclosure.visible_evidence_refs,
        allowed_target_refs=disclosure.visible_target_refs,
        expected_closure_surface=tuple(expected_closure_surface),
        max_response_tokens=max_response_tokens,
        max_followups=max_followups,
        role_instruction_id=instruction.instruction_id,
        role_instruction_fingerprint=instruction.instruction_fingerprint,
        policy_version=policy_version,
        policy_hash=policy_hash,
        contract_fingerprint=_fingerprint(payload),
        metadata={
            "authority_boundary": "one bounded question target; no branch jump or truth mutation",
            "branch_key": disclosure.branch.branch_key,
        },
    )


def validate_question_contract_integrity(
    contract: DialecticQuestionContract,
    disclosure: DialecticDisclosureContract,
) -> None:
    validate_disclosure_contract_integrity(disclosure)
    if contract.disclosure_contract_id != disclosure.meta.id or contract.disclosure_fingerprint != disclosure.disclosure_fingerprint:
        raise TribunalDisclosureError("question contract/disclosure mismatch")
    if contract.branch.branch_key != disclosure.branch.branch_key:
        raise TribunalDisclosureError("question contract changed dialectic branch")
    payload = {
        "role_id": contract.role_id,
        "answer_role_id": contract.answer_role_id,
        "purpose": contract.purpose.value,
        "target_kind": contract.target_kind.value,
        "branch_key": contract.branch.branch_key,
        "graph_fingerprint": contract.branch.graph_fingerprint,
        "disclosure_id": str(contract.disclosure_contract_id),
        "disclosure_fingerprint": contract.disclosure_fingerprint,
        "target_argument_id": str(contract.target_argument_id),
        "target_turn_id": str(contract.target_turn_id) if contract.target_turn_id else None,
        "target_issue_signature": contract.target_issue_signature,
        "parent_turn_id": str(contract.parent_turn_id),
        "needs": [(x.key, x.ordinal) for x in contract.assigned_need_refs],
        "evidence": [str(x) for x in contract.allowed_evidence_refs],
        "targets": [str(x) for x in contract.allowed_target_refs],
        "closure": list(contract.expected_closure_surface),
        "max_response_tokens": contract.max_response_tokens,
        "max_followups": contract.max_followups,
        "instruction_id": contract.role_instruction_id,
        "instruction_fingerprint": contract.role_instruction_fingerprint,
        "policy_version": contract.policy_version,
        "policy_hash": contract.policy_hash,
    }
    if _fingerprint(payload) != contract.contract_fingerprint:
        raise TribunalDisclosureError("DialecticQuestionContract fingerprint mismatch")


def materialize_question_turn(
    *,
    contract: DialecticQuestionContract,
    disclosure: DialecticDisclosureContract,
    question: str,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> InquiryTurn:
    validate_question_contract_integrity(contract, disclosure)
    if not question.strip():
        raise TribunalDisclosureError("question text is required")
    kind = (
        InquiryTurnKind.QUESTION_ON_ANSWER
        if contract.purpose is QuestionPurpose.QUESTION_ON_ANSWER
        else InquiryTurnKind.QUESTION
    )
    cited = tuple(dict.fromkeys((contract.target_argument_id, *(contract.allowed_target_refs))))
    if contract.target_turn_id is not None:
        cited = tuple(dict.fromkeys((*cited, contract.target_turn_id)))
    return InquiryTurn(
        meta=EntityMeta(id_factory.new("IQT"), "inquiry-turn/1.0", 1, contract.meta.run_id, created_at, actor),
        contract_id=contract.meta.id,
        role_id=contract.role_id,
        kind=kind,
        content=question,
        parent_turn_id=contract.parent_turn_id,
        cited_refs=cited,
        metadata={
            "branch_key": contract.branch.branch_key,
            "target_issue_signature": contract.target_issue_signature,
            "disclosure_contract_id": str(contract.disclosure_contract_id),
        },
    )


def validate_answer_against_question_contract(
    *,
    contract: DialecticQuestionContract,
    disclosure: DialecticDisclosureContract,
    question_turn: InquiryTurn,
    answer_turn: InquiryTurn,
    answer_argument: ArgumentArtifact,
) -> None:
    validate_question_contract_integrity(contract, disclosure)
    if question_turn.contract_id != contract.meta.id:
        raise TribunalDisclosureError("question turn is not owned by question contract")
    if answer_turn.contract_id != contract.meta.id or answer_argument.contract_id != contract.meta.id:
        raise TribunalDisclosureError("answer artifacts are not owned by question contract")
    if answer_argument.source_turn_id != answer_turn.meta.id or answer_turn.parent_turn_id != question_turn.meta.id:
        raise TribunalDisclosureError("answer turn/argument lineage does not bind to the question")
    if answer_turn.role_id != contract.answer_role_id or answer_argument.role_id != contract.answer_role_id:
        raise TribunalDisclosureError("answer role does not match addressed question role")
    if answer_turn.kind not in {InquiryTurnKind.ANSWER, InquiryTurnKind.REBUTTAL}:
        raise TribunalDisclosureError("question answer must use ANSWER/REBUTTAL turn kind")
    allowed_turn_refs = set(contract.allowed_evidence_refs) | set(contract.allowed_target_refs) | set(disclosure.visible_argument_ids) | set(disclosure.visible_turn_ids) | set(disclosure.visible_relation_ids) | {question_turn.meta.id}
    if not set(answer_turn.cited_refs).issubset(allowed_turn_refs):
        raise TribunalDisclosureError("answer turn cites ref outside question disclosure")
    if not set(answer_argument.assigned_need_refs).issubset(contract.assigned_need_refs):
        raise TribunalDisclosureError("answer widens AssessmentNeed coverage")
    if not set(answer_argument.cited_evidence_refs).issubset(contract.allowed_evidence_refs):
        raise TribunalDisclosureError("answer cites evidence outside question disclosure")
    if not set(answer_argument.cited_target_refs).issubset(contract.allowed_target_refs):
        raise TribunalDisclosureError("answer cites targets outside question disclosure")
    for discovery in answer_argument.discoveries:
        if not set(discovery.need_refs).issubset(contract.assigned_need_refs):
            raise TribunalDisclosureError("answer discovery widens AssessmentNeed coverage")
        if not set(discovery.evidence_refs).issubset(contract.allowed_evidence_refs):
            raise TribunalDisclosureError("answer discovery references hidden evidence")
        if not set(discovery.target_refs).issubset(contract.allowed_target_refs):
            raise TribunalDisclosureError("answer discovery references hidden target")
    for request in answer_argument.additional_evidence_requests:
        if not set(request.need_refs).issubset(contract.assigned_need_refs):
            raise TribunalDisclosureError("answer evidence request widens AssessmentNeed coverage")
        if not set(request.target_refs).issubset(contract.allowed_target_refs):
            raise TribunalDisclosureError("answer evidence request references hidden target")


def disclosure_contract_to_dict(contract: DialecticDisclosureContract) -> dict[str, Any]:
    return {
        "schema_version": "dialectic-disclosure-contract/1.1",
        "meta": _meta_to_dict(contract.meta),
        "id": str(contract.meta.id),
        "role_id": contract.role_id,
        "purpose": contract.purpose.value,
        "branch": branch_ref_to_dict(contract.branch),
        "focus_argument_id": str(contract.focus_argument_id),
        "focus_relation_id": str(contract.focus_relation_id) if contract.focus_relation_id else None,
        "focus_turn_id": str(contract.focus_turn_id) if contract.focus_turn_id else None,
        "focus_issue_signature": contract.focus_issue_signature,
        "visible_argument_ids": [str(x) for x in contract.visible_argument_ids],
        "visible_turn_ids": [str(x) for x in contract.visible_turn_ids],
        "visible_relation_ids": [str(x) for x in contract.visible_relation_ids],
        "visible_evidence_refs": [str(x) for x in contract.visible_evidence_refs],
        "visible_target_refs": [str(x) for x in contract.visible_target_refs],
        "hidden_argument_ids": [str(x) for x in contract.hidden_argument_ids],
        "assigned_need_refs": [{"key": x.key, "ordinal": x.ordinal} for x in contract.assigned_need_refs],
        "disclosure_policy_version": contract.disclosure_policy_version,
        "disclosure_policy_hash": contract.disclosure_policy_hash,
        "disclosure_fingerprint": contract.disclosure_fingerprint,
        "metadata": dict(contract.metadata),
    }


def question_contract_to_dict(contract: DialecticQuestionContract) -> dict[str, Any]:
    return {
        "schema_version": "dialectic-question-contract/1.1",
        "meta": _meta_to_dict(contract.meta),
        "id": str(contract.meta.id),
        "role_id": contract.role_id,
        "answer_role_id": contract.answer_role_id,
        "purpose": contract.purpose.value,
        "target_kind": contract.target_kind.value,
        "branch": branch_ref_to_dict(contract.branch),
        "disclosure_contract_id": str(contract.disclosure_contract_id),
        "disclosure_fingerprint": contract.disclosure_fingerprint,
        "target_argument_id": str(contract.target_argument_id),
        "target_turn_id": str(contract.target_turn_id) if contract.target_turn_id else None,
        "target_issue_signature": contract.target_issue_signature,
        "parent_turn_id": str(contract.parent_turn_id),
        "assigned_need_refs": [{"key": x.key, "ordinal": x.ordinal} for x in contract.assigned_need_refs],
        "allowed_evidence_refs": [str(x) for x in contract.allowed_evidence_refs],
        "allowed_target_refs": [str(x) for x in contract.allowed_target_refs],
        "expected_closure_surface": list(contract.expected_closure_surface),
        "max_response_tokens": contract.max_response_tokens,
        "max_followups": contract.max_followups,
        "role_instruction_id": contract.role_instruction_id,
        "role_instruction_fingerprint": contract.role_instruction_fingerprint,
        "policy_version": contract.policy_version,
        "policy_hash": contract.policy_hash,
        "contract_fingerprint": contract.contract_fingerprint,
        "metadata": dict(contract.metadata),
    }


def disclosure_contract_from_dict(payload: Mapping[str, Any]) -> DialecticDisclosureContract:
    if payload.get("schema_version") != "dialectic-disclosure-contract/1.1":
        raise TribunalDisclosureError("unsupported DialecticDisclosureContract schema")
    try:
        contract = DialecticDisclosureContract(
            meta=_meta_from_dict(payload["meta"]),
            role_id=str(payload["role_id"]),
            purpose=DisclosurePurpose(str(payload["purpose"])),
            branch=branch_ref_from_dict(payload["branch"]),
            focus_argument_id=EntityId(str(payload["focus_argument_id"])),
            focus_relation_id=(EntityId(str(payload["focus_relation_id"])) if payload.get("focus_relation_id") else None),
            focus_turn_id=(EntityId(str(payload["focus_turn_id"])) if payload.get("focus_turn_id") else None),
            focus_issue_signature=str(payload.get("focus_issue_signature") or ""),
            visible_argument_ids=tuple(EntityId(str(x)) for x in payload.get("visible_argument_ids", ())),
            visible_turn_ids=tuple(EntityId(str(x)) for x in payload.get("visible_turn_ids", ())),
            visible_relation_ids=tuple(EntityId(str(x)) for x in payload.get("visible_relation_ids", ())),
            visible_evidence_refs=tuple(EntityId(str(x)) for x in payload.get("visible_evidence_refs", ())),
            visible_target_refs=tuple(EntityId(str(x)) for x in payload.get("visible_target_refs", ())),
            hidden_argument_ids=tuple(EntityId(str(x)) for x in payload.get("hidden_argument_ids", ())),
            assigned_need_refs=tuple(AssessmentNeedRef(str(x["key"]), int(x["ordinal"])) for x in payload.get("assigned_need_refs", ())),
            disclosure_policy_version=str(payload["disclosure_policy_version"]),
            disclosure_policy_hash=str(payload["disclosure_policy_hash"]),
            disclosure_fingerprint=str(payload["disclosure_fingerprint"]),
            metadata=dict(payload.get("metadata") or {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TribunalDisclosureError("invalid serialized DialecticDisclosureContract") from exc
    validate_disclosure_contract_integrity(contract)
    return contract


def question_contract_from_dict(payload: Mapping[str, Any]) -> DialecticQuestionContract:
    if payload.get("schema_version") == "dialectic-question-contract/1.0":
        raise TribunalDisclosureError("legacy DialecticQuestionContract/1.0 lacks explicit answer_role_id; recompile from branch context")
    if payload.get("schema_version") != "dialectic-question-contract/1.1":
        raise TribunalDisclosureError("unsupported DialecticQuestionContract schema")
    try:
        contract = DialecticQuestionContract(
            meta=_meta_from_dict(payload["meta"]),
            role_id=str(payload["role_id"]),
            answer_role_id=str(payload["answer_role_id"]),
            purpose=QuestionPurpose(str(payload["purpose"])),
            target_kind=QuestionTargetKind(str(payload["target_kind"])),
            branch=branch_ref_from_dict(payload["branch"]),
            disclosure_contract_id=EntityId(str(payload["disclosure_contract_id"])),
            disclosure_fingerprint=str(payload["disclosure_fingerprint"]),
            target_argument_id=EntityId(str(payload["target_argument_id"])),
            target_turn_id=(EntityId(str(payload["target_turn_id"])) if payload.get("target_turn_id") else None),
            target_issue_signature=str(payload.get("target_issue_signature") or ""),
            parent_turn_id=EntityId(str(payload["parent_turn_id"])),
            assigned_need_refs=tuple(AssessmentNeedRef(str(x["key"]), int(x["ordinal"])) for x in payload.get("assigned_need_refs", ())),
            allowed_evidence_refs=tuple(EntityId(str(x)) for x in payload.get("allowed_evidence_refs", ())),
            allowed_target_refs=tuple(EntityId(str(x)) for x in payload.get("allowed_target_refs", ())),
            expected_closure_surface=tuple(str(x) for x in payload.get("expected_closure_surface", ())),
            max_response_tokens=int(payload["max_response_tokens"]),
            max_followups=int(payload["max_followups"]),
            role_instruction_id=str(payload["role_instruction_id"]),
            role_instruction_fingerprint=str(payload["role_instruction_fingerprint"]),
            policy_version=str(payload["policy_version"]),
            policy_hash=str(payload["policy_hash"]),
            contract_fingerprint=str(payload["contract_fingerprint"]),
            metadata=dict(payload.get("metadata") or {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TribunalDisclosureError("invalid serialized DialecticQuestionContract") from exc
    return contract


def branch_ref_to_dict(branch: DialecticBranchRef) -> dict[str, Any]:
    return {
        "branch_key": branch.branch_key,
        "argument_graph_id": str(branch.argument_graph_id),
        "graph_revision": branch.graph_revision,
        "graph_fingerprint": branch.graph_fingerprint,
        "root_argument_id": str(branch.root_argument_id),
        "anchor_argument_id": str(branch.anchor_argument_id),
        "anchor_relation_id": str(branch.anchor_relation_id) if branch.anchor_relation_id else None,
        "head_argument_id": str(branch.head_argument_id),
        "issue_signature": branch.issue_signature,
    }


def branch_ref_from_dict(payload: Mapping[str, Any]) -> DialecticBranchRef:
    try:
        return DialecticBranchRef(
            branch_key=str(payload["branch_key"]),
            argument_graph_id=EntityId(str(payload["argument_graph_id"])),
            graph_revision=int(payload["graph_revision"]),
            graph_fingerprint=str(payload["graph_fingerprint"]),
            root_argument_id=EntityId(str(payload["root_argument_id"])),
            anchor_argument_id=EntityId(str(payload["anchor_argument_id"])),
            anchor_relation_id=(EntityId(str(payload["anchor_relation_id"])) if payload.get("anchor_relation_id") else None),
            head_argument_id=EntityId(str(payload["head_argument_id"])),
            issue_signature=str(payload.get("issue_signature") or ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TribunalDisclosureError("invalid serialized DialecticBranchRef") from exc


def _branch_arguments(graph: ArgumentGraphProjection, branch: DialecticBranchRef) -> tuple[EntityId, ...]:
    reachable = _reachable_targets(graph, branch.head_argument_id)
    if branch.root_argument_id not in reachable:
        raise TribunalDisclosureError("branch root is no longer reachable from head")
    return tuple(x for x in graph.argument_ids if x in reachable)


def _reachable_targets(graph: ArgumentGraphProjection, start: EntityId) -> set[EntityId]:
    adjacency: dict[EntityId, list[EntityId]] = {x: [] for x in graph.argument_ids}
    for relation in graph.relations:
        if relation.state is ArgumentRelationState.ACTIVE:
            adjacency[relation.source_argument_id].append(relation.target_argument_id)
    seen: set[EntityId] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, ()))
    return seen


def _relation_by_id(graph: ArgumentGraphProjection, relation_id: EntityId) -> ArgumentRelation:
    relation = next((x for x in graph.relations if x.meta.id == relation_id), None)
    if relation is None:
        raise TribunalDisclosureError("argument relation is absent from graph")
    return relation


def _validate_branch_snapshot(branch: DialecticBranchRef, graph: ArgumentGraphProjection) -> None:
    if branch.argument_graph_id != graph.meta.id:
        raise TribunalDisclosureError("branch belongs to a different argument graph")
    if branch.graph_revision != graph.meta.revision or branch.graph_fingerprint != graph.graph_fingerprint:
        raise TribunalDisclosureError("branch snapshot is stale for current argument graph")


def _disclosure_payload(**kwargs: Any) -> dict[str, Any]:
    branch: DialecticBranchRef = kwargs["branch"]
    purpose: DisclosurePurpose = kwargs["purpose"]
    return {
        "role_id": kwargs["role_id"],
        "purpose": purpose.value,
        "branch": branch_ref_to_dict(branch),
        "focus_argument_id": str(kwargs["focus_argument_id"]),
        "focus_relation_id": str(kwargs["focus_relation_id"]) if kwargs["focus_relation_id"] else None,
        "focus_turn_id": str(kwargs["focus_turn_id"]) if kwargs["focus_turn_id"] else None,
        "focus_issue_signature": kwargs["focus_issue_signature"],
        "visible_arguments": [str(x) for x in kwargs["visible_argument_ids"]],
        "visible_turns": [str(x) for x in kwargs["visible_turn_ids"]],
        "visible_relations": [str(x) for x in kwargs["visible_relation_ids"]],
        "visible_evidence": [str(x) for x in kwargs["visible_evidence_refs"]],
        "visible_targets": [str(x) for x in kwargs["visible_target_refs"]],
        "hidden_arguments": [str(x) for x in kwargs["hidden_argument_ids"]],
        "needs": [(x.key, x.ordinal) for x in kwargs["assigned_need_refs"]],
        "disclosure_policy_version": kwargs["disclosure_policy_version"],
        "disclosure_policy_hash": kwargs["disclosure_policy_hash"],
    }


def _meta_to_dict(meta: EntityMeta) -> dict[str, Any]:
    return {
        "id": str(meta.id),
        "schema_version": meta.schema_version,
        "revision": meta.revision,
        "run_id": str(meta.run_id),
        "created_at": meta.created_at.isoformat(),
        "created_by": {"kind": meta.created_by.actor_type, "id": meta.created_by.actor_id},
    }


def _meta_from_dict(payload: Mapping[str, Any]) -> EntityMeta:
    try:
        created_by = payload["created_by"]
        return EntityMeta(
            EntityId(str(payload["id"])),
            str(payload["schema_version"]),
            int(payload["revision"]),
            EntityId(str(payload["run_id"])),
            datetime.fromisoformat(str(payload["created_at"])),
            ActorRef(str(created_by["kind"]), str(created_by["id"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TribunalDisclosureError("invalid serialized EntityMeta") from exc


def _fingerprint(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
