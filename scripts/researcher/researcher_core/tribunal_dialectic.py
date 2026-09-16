"""R4.4 L1 bounded dialectic control and emergent-issue observation.

The module deliberately separates semantic proposals from control decisions:
roles may emit typed discoveries/requests, while code tracks novelty, repetition,
depth and escalation boundaries.  It does not infer scientific weakness from
free prose and it does not mutate Claim/GraphEdge/Gap truth state.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any, Iterable, Mapping, Sequence

from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId
from researcher_core.r0.enums import GapState
from researcher_core.r1_entities import Gap
from researcher_core.tribunal_composition import AssessmentNeedRef
from researcher_core.tribunal_disclosure import DialecticBranchRef, branch_ref_from_dict, branch_ref_to_dict
from researcher_core.tribunal_inquiry import (
    AdditionalEvidenceRequest,
    ArgumentArtifact,
    ArgumentPosition,
    DiscoveryKind,
    InquiryDiscovery,
    InquiryTurn,
    InquiryTurnKind,
)


class TribunalDialecticError(RuntimeError):
    pass


class DialecticLevel(IntEnum):
    """Process depth, not scientific confidence or truth."""

    L0_INDEPENDENT = 0
    L1_CHALLENGE = 1
    L2_DIRECT_QA = 2
    L3_QUESTION_ON_ANSWER = 3
    L4_LOCAL_RESEARCH_ESCALATION = 4
    L5_EXTERNAL_ESCALATION = 5


class EmergentIssueKind(StrEnum):
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    METHOD_LIMITATION = "METHOD_LIMITATION"
    POSSIBLE_COUNTEREXAMPLE = "POSSIBLE_COUNTEREXAMPLE"
    SCOPE_ISSUE = "SCOPE_ISSUE"
    CAUSALITY_PROBLEM = "CAUSALITY_PROBLEM"
    NUMERIC_DISCREPANCY = "NUMERIC_DISCREPANCY"
    ASSUMPTION_ISSUE = "ASSUMPTION_ISSUE"
    SOURCE_PROVENANCE_ISSUE = "SOURCE_PROVENANCE_ISSUE"
    FRESHNESS_ISSUE = "FRESHNESS_ISSUE"
    CONTRADICTION = "CONTRADICTION"
    ANSWER_EVASION = "ANSWER_EVASION"
    ROLE_CAPABILITY_GAP = "ROLE_CAPABILITY_GAP"


class DialecticAction(StrEnum):
    CONTINUE_CHALLENGE = "CONTINUE_CHALLENGE"
    CONTINUE_QA = "CONTINUE_QA"
    CONTINUE_QUESTION_ON_ANSWER = "CONTINUE_QUESTION_ON_ANSWER"
    REQUEST_LOCAL_RESEARCH = "REQUEST_LOCAL_RESEARCH"
    RECOMPOSE_PANEL = "RECOMPOSE_PANEL"
    STOP_CONVERGED = "STOP_CONVERGED"
    STOP_NO_PROGRESS = "STOP_NO_PROGRESS"
    STOP_DEPTH_LIMIT = "STOP_DEPTH_LIMIT"
    STOP_TURN_LIMIT = "STOP_TURN_LIMIT"
    STOP_BUDGET_LIMIT = "STOP_BUDGET_LIMIT"
    STOP_OPEN = "STOP_OPEN"


class DialecticIssueDisposition(StrEnum):
    RESOLVED = "RESOLVED"
    STILL_OPEN = "STILL_OPEN"


_DISCOVERY_MAP: dict[DiscoveryKind, EmergentIssueKind] = {
    DiscoveryKind.MISSING_EVIDENCE: EmergentIssueKind.MISSING_EVIDENCE,
    DiscoveryKind.METHOD_LIMITATION: EmergentIssueKind.METHOD_LIMITATION,
    DiscoveryKind.POSSIBLE_COUNTEREXAMPLE: EmergentIssueKind.POSSIBLE_COUNTEREXAMPLE,
    DiscoveryKind.SCOPE_ISSUE: EmergentIssueKind.SCOPE_ISSUE,
    DiscoveryKind.CAUSALITY_PROBLEM: EmergentIssueKind.CAUSALITY_PROBLEM,
    DiscoveryKind.NUMERIC_DISCREPANCY: EmergentIssueKind.NUMERIC_DISCREPANCY,
    DiscoveryKind.ASSUMPTION_ISSUE: EmergentIssueKind.ASSUMPTION_ISSUE,
    DiscoveryKind.SOURCE_PROVENANCE_ISSUE: EmergentIssueKind.SOURCE_PROVENANCE_ISSUE,
    DiscoveryKind.FRESHNESS_ISSUE: EmergentIssueKind.FRESHNESS_ISSUE,
}


@dataclass(frozen=True, slots=True)
class DialecticPolicy:
    max_level: DialecticLevel = DialecticLevel.L3_QUESTION_ON_ANSWER
    max_turns: int = 6
    max_question_answer_pairs: int = 2
    max_no_progress_streak: int = 1
    max_new_issues_per_turn: int = 6
    token_budget: int = 6000
    escalate_blocking_discovery: bool = True
    require_novelty_for_followup: bool = True
    # Opt-in bounded follow-up beyond the default Q/A pair limit. When enabled,
    # the L3 observer may admit one more question-on-answer (Q3) IF the response
    # surfaced a NEW non-blocking issue and the turn/token limits are not
    # exhausted. Deliberately off by default: the canonical dialectic bounds the
    # process at L3 / two Q/A pairs, and Q3 must be an explicit Core decision.
    allow_bounded_followup: bool = False

    def __post_init__(self) -> None:
        if self.max_turns < 1 or self.max_question_answer_pairs < 1:
            raise ValueError("dialectic turn/pair limits must be positive")
        if self.max_no_progress_streak < 0 or self.max_new_issues_per_turn < 1:
            raise ValueError("dialectic progress/fanout limits are invalid")
        if self.token_budget < 1:
            raise ValueError("dialectic token budget must be positive")


@dataclass(frozen=True, slots=True)
class EmergentIssue:
    kind: EmergentIssueKind
    statement: str
    need_refs: tuple[AssessmentNeedRef, ...]
    target_refs: tuple[EntityId, ...] = ()
    evidence_refs: tuple[EntityId, ...] = ()
    blocking: bool = False
    source_argument_id: EntityId | None = None
    source_turn_id: EntityId | None = None
    signature: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.statement.strip():
            raise ValueError("emergent issue statement is required")
        if not self.need_refs:
            raise ValueError("emergent issue requires at least one need ref")
        if self.source_argument_id is not None and self.source_argument_id.namespace != "ARG":
            raise ValueError("source_argument_id must use ARG prefix")
        if self.source_turn_id is not None and self.source_turn_id.namespace != "IQT":
            raise ValueError("source_turn_id must use IQT prefix")
        object.__setattr__(self, "need_refs", tuple(self.need_refs))
        object.__setattr__(self, "target_refs", tuple(dict.fromkeys(self.target_refs)))
        object.__setattr__(self, "evidence_refs", tuple(dict.fromkeys(self.evidence_refs)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))
        if not self.signature:
            object.__setattr__(self, "signature", _issue_signature(self))


@dataclass(frozen=True, slots=True)
class DialecticIssueProposal:
    """Typed semantic proposal from a bounded turn-observer role.

    Proposals may describe interaction-only problems (e.g. answer evasion or
    contradiction) that are not represented by the R4.3 InquiryDiscovery enum.
    They remain proposals until this control-plane module validates and folds
    them into the observation.
    """

    kind: EmergentIssueKind
    statement: str
    need_refs: tuple[AssessmentNeedRef, ...]
    target_refs: tuple[EntityId, ...] = ()
    evidence_refs: tuple[EntityId, ...] = ()
    blocking: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.statement.strip() or not self.need_refs:
            raise ValueError("dialectic issue proposal requires statement and need refs")
        object.__setattr__(self, "need_refs", tuple(self.need_refs))
        object.__setattr__(self, "target_refs", tuple(dict.fromkeys(self.target_refs)))
        object.__setattr__(self, "evidence_refs", tuple(dict.fromkeys(self.evidence_refs)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DialecticIssueResolutionProposal:
    issue_signature: str
    disposition: DialecticIssueDisposition
    rationale: str

    def __post_init__(self) -> None:
        if not self.issue_signature.startswith("sha256:") or not self.rationale.strip():
            raise ValueError("issue resolution proposal requires signature and rationale")


@dataclass(frozen=True, slots=True)
class DialecticObservation:
    level: DialecticLevel
    turn_count: int
    qa_pair_count: int
    token_spent: int
    current_argument_id: EntityId
    current_turn_id: EntityId
    current_position: ArgumentPosition
    new_issues: tuple[EmergentIssue, ...]
    reopened_issues: tuple[EmergentIssue, ...]
    repeated_issue_signatures: tuple[str, ...]
    issue_resolution_proposals: tuple[DialecticIssueResolutionProposal, ...]
    resolved_issue_signatures: tuple[str, ...]
    all_active_issue_signatures: tuple[str, ...]
    position_changed: bool
    evidence_frontier_changed: bool
    no_progress_streak: int
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.current_argument_id.namespace != "ARG" or self.current_turn_id.namespace != "IQT":
            raise ValueError("observation argument/turn namespaces are invalid")
        if self.turn_count < 1 or self.qa_pair_count < 0 or self.token_spent < 0:
            raise ValueError("observation counters are invalid")
        object.__setattr__(self, "new_issues", tuple(self.new_issues))
        object.__setattr__(self, "reopened_issues", tuple(self.reopened_issues))
        object.__setattr__(self, "repeated_issue_signatures", tuple(dict.fromkeys(self.repeated_issue_signatures)))
        object.__setattr__(self, "issue_resolution_proposals", tuple(self.issue_resolution_proposals))
        object.__setattr__(self, "resolved_issue_signatures", tuple(dict.fromkeys(self.resolved_issue_signatures)))
        object.__setattr__(self, "all_active_issue_signatures", tuple(dict.fromkeys(self.all_active_issue_signatures)))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))


@dataclass(frozen=True, slots=True)
class DialecticControlDecision:
    action: DialecticAction
    next_level: DialecticLevel
    reason_codes: tuple[str, ...]
    issue_signatures: tuple[str, ...]
    authority_boundary: str = "control decision only; no claim/graph truth mutation"

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        object.__setattr__(self, "issue_signatures", tuple(dict.fromkeys(self.issue_signatures)))


@dataclass(frozen=True, slots=True)
class DialecticHistory:
    """Minimal history needed by the control observer.

    Full artifacts remain canonical elsewhere; this structure intentionally stores
    only IDs/fingerprints/signatures and counters.
    """

    argument_ids: tuple[EntityId, ...] = ()
    turn_ids: tuple[EntityId, ...] = ()
    issue_signatures: tuple[str, ...] = ()
    resolved_issue_signatures: tuple[str, ...] = ()
    last_position: ArgumentPosition | None = None
    visible_ref_fingerprint: str = ""
    no_progress_streak: int = 0
    qa_pair_count: int = 0
    token_spent: int = 0


@dataclass(frozen=True, slots=True)
class DialecticStepResult:
    observation: DialecticObservation
    decision: DialecticControlDecision
    next_history: DialecticHistory


@dataclass(frozen=True, slots=True)
class DialecticBranchHistory:
    """Branch-scoped wrapper around the local dialectic control history.

    The branch key is stable across graph revisions; graph snapshot/head fields
    move forward only through ``advance_branch_history``.  This prevents two
    sibling branches from sharing no-progress, Q/A counts, budgets or issue
    lifecycle.
    """

    branch: DialecticBranchRef
    history: DialecticHistory = field(default_factory=DialecticHistory)
    history_fingerprint: str = ""

    def __post_init__(self) -> None:
        fp = _branch_history_fingerprint(self.branch, self.history)
        if self.history_fingerprint and self.history_fingerprint != fp:
            raise ValueError("DialecticBranchHistory fingerprint mismatch")
        object.__setattr__(self, "history_fingerprint", fp)


@dataclass(frozen=True, slots=True)
class BranchDialecticStepResult:
    observation: DialecticObservation
    decision: DialecticControlDecision
    next_branch_history: DialecticBranchHistory


@dataclass(frozen=True, slots=True)
class DialecticResearchResumeAnchor:
    research_challenge_id: EntityId
    source_gap_id: EntityId
    branch_key: str
    argument_graph_id: EntityId
    graph_revision: int
    graph_fingerprint: str
    issue_signature: str
    history_fingerprint: str
    anchor_fingerprint: str

    def __post_init__(self) -> None:
        if self.research_challenge_id.namespace != "RCH" or self.source_gap_id.namespace != "GAP":
            raise ValueError("research resume ids must use RCH/GAP prefixes")
        if not self.branch_key.startswith("DBR-") or self.argument_graph_id.namespace != "AGP":
            raise ValueError("research resume branch identity is invalid")
        if not self.issue_signature or not self.history_fingerprint.startswith("sha256:") or not self.anchor_fingerprint.startswith("sha256:"):
            raise ValueError("research resume fingerprints/issue are required")


def new_branch_history(branch: DialecticBranchRef) -> DialecticBranchHistory:
    return DialecticBranchHistory(branch=branch)


def dialectic_branch_history_to_dict(value: DialecticBranchHistory) -> dict[str, Any]:
    validate_branch_history_integrity(value)
    h = value.history
    return {
        "schema_version": "dialectic-branch-history/1.0",
        "branch": branch_ref_to_dict(value.branch),
        "history": {
            "argument_ids": [str(x) for x in h.argument_ids],
            "turn_ids": [str(x) for x in h.turn_ids],
            "issue_signatures": list(h.issue_signatures),
            "resolved_issue_signatures": list(h.resolved_issue_signatures),
            "last_position": h.last_position.value if h.last_position else None,
            "visible_ref_fingerprint": h.visible_ref_fingerprint,
            "no_progress_streak": h.no_progress_streak,
            "qa_pair_count": h.qa_pair_count,
            "token_spent": h.token_spent,
        },
        "history_fingerprint": value.history_fingerprint,
    }


def restore_dialectic_branch_history(payload: Mapping[str, Any]) -> DialecticBranchHistory:
    if payload.get("schema_version") != "dialectic-branch-history/1.0":
        raise TribunalDialecticError("unsupported dialectic branch history schema")
    try:
        branch = branch_ref_from_dict(payload["branch"])
        raw = payload["history"]
        last_position = ArgumentPosition(str(raw["last_position"])) if raw.get("last_position") else None
        history = DialecticHistory(
            argument_ids=tuple(EntityId(str(x)) for x in raw.get("argument_ids", ())),
            turn_ids=tuple(EntityId(str(x)) for x in raw.get("turn_ids", ())),
            issue_signatures=tuple(str(x) for x in raw.get("issue_signatures", ())),
            resolved_issue_signatures=tuple(str(x) for x in raw.get("resolved_issue_signatures", ())),
            last_position=last_position,
            visible_ref_fingerprint=str(raw.get("visible_ref_fingerprint") or ""),
            no_progress_streak=int(raw.get("no_progress_streak", 0)),
            qa_pair_count=int(raw.get("qa_pair_count", 0)),
            token_spent=int(raw.get("token_spent", 0)),
        )
        restored = DialecticBranchHistory(
            branch=branch, history=history, history_fingerprint=str(payload.get("history_fingerprint") or ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TribunalDialecticError("invalid serialized dialectic branch history") from exc
    validate_branch_history_integrity(restored)
    return restored


def validate_branch_history_integrity(value: DialecticBranchHistory) -> None:
    if _branch_history_fingerprint(value.branch, value.history) != value.history_fingerprint:
        raise TribunalDialecticError("DialecticBranchHistory fingerprint mismatch")
    if len(set(value.history.argument_ids)) != len(value.history.argument_ids):
        raise TribunalDialecticError("duplicate argument id in branch history")
    if len(set(value.history.turn_ids)) != len(value.history.turn_ids):
        raise TribunalDialecticError("duplicate turn id in branch history")
    if set(value.history.issue_signatures).intersection(value.history.resolved_issue_signatures):
        raise TribunalDialecticError("branch issue cannot be active and resolved simultaneously")


def observe_branch_dialectic_step(
    *,
    branch: DialecticBranchRef,
    argument: ArgumentArtifact,
    turn: InquiryTurn,
    branch_history: DialecticBranchHistory,
    visible_refs: Sequence[EntityId] = (),
    issue_proposals: Sequence[DialecticIssueProposal] = (),
    issue_resolutions: Sequence[DialecticIssueResolutionProposal] = (),
    chain_turn_count: int | None = None,
    token_cost: int = 0,
    policy: DialecticPolicy = DialecticPolicy(),
) -> BranchDialecticStepResult:
    if branch.branch_key != branch_history.branch.branch_key:
        raise TribunalDialecticError("dialectic history belongs to a different argument branch")
    if branch.argument_graph_id != branch_history.branch.argument_graph_id:
        raise TribunalDialecticError("dialectic branch graph identity changed")
    if branch.graph_revision < branch_history.branch.graph_revision:
        raise TribunalDialecticError("dialectic branch graph revision moved backwards")
    if branch_history.history.argument_ids and branch.head_argument_id != argument.meta.id:
        raise TribunalDialecticError("observed argument is not the current branch head")
    step = observe_dialectic_step(
        level=level_for_turn(turn.kind),
        argument=argument,
        turn=turn,
        history=branch_history.history,
        visible_refs=visible_refs,
        issue_proposals=issue_proposals,
        issue_resolutions=issue_resolutions,
        chain_turn_count=chain_turn_count,
        token_cost=token_cost,
        policy=policy,
    )
    return BranchDialecticStepResult(
        observation=step.observation,
        decision=step.decision,
        next_branch_history=DialecticBranchHistory(branch=branch, history=step.next_history),
    )


def level_for_turn(kind: InquiryTurnKind) -> DialecticLevel:
    return {
        InquiryTurnKind.FIRST_PASS_ASSESSMENT: DialecticLevel.L0_INDEPENDENT,
        InquiryTurnKind.CHALLENGE: DialecticLevel.L1_CHALLENGE,
        InquiryTurnKind.QUESTION: DialecticLevel.L2_DIRECT_QA,
        InquiryTurnKind.ANSWER: DialecticLevel.L2_DIRECT_QA,
        InquiryTurnKind.QUESTION_ON_ANSWER: DialecticLevel.L3_QUESTION_ON_ANSWER,
        InquiryTurnKind.REBUTTAL: DialecticLevel.L3_QUESTION_ON_ANSWER,
    }[kind]


def branch_resume_dimensions(branch: DialecticBranchRef, issue_signature: str) -> dict[str, Any]:
    if not issue_signature.strip():
        raise TribunalDialecticError("branch resume requires issue signature")
    return {
        "dialectic_branch_key": branch.branch_key,
        "argument_graph_id": str(branch.argument_graph_id),
        "argument_graph_revision": branch.graph_revision,
        "argument_graph_fingerprint": branch.graph_fingerprint,
        "branch_root_argument_id": str(branch.root_argument_id),
        "branch_anchor_argument_id": str(branch.anchor_argument_id),
        "branch_anchor_relation_id": str(branch.anchor_relation_id) if branch.anchor_relation_id else None,
        "branch_head_argument_id": str(branch.head_argument_id),
        "dialectic_issue_signature": issue_signature,
    }


def validate_branch_resume_dimensions(
    *,
    dimensions: Mapping[str, Any],
    branch: DialecticBranchRef,
    issue_signature: str,
) -> None:
    expected = branch_resume_dimensions(branch, issue_signature)
    for key, value in expected.items():
        if dimensions.get(key) != value:
            raise TribunalDialecticError(f"research return does not resume exact dialectic branch:{key}")


def compile_research_resume_anchor(
    *,
    research_challenge_id: EntityId,
    source_gap_id: EntityId,
    branch_history: DialecticBranchHistory,
    issue_signature: str,
    challenge_dimensions: Mapping[str, Any],
) -> DialecticResearchResumeAnchor:
    validate_branch_history_integrity(branch_history)
    validate_branch_resume_dimensions(
        dimensions=challenge_dimensions, branch=branch_history.branch, issue_signature=issue_signature,
    )
    payload = {
        "research_challenge_id": str(research_challenge_id),
        "source_gap_id": str(source_gap_id),
        "branch_key": branch_history.branch.branch_key,
        "argument_graph_id": str(branch_history.branch.argument_graph_id),
        "graph_revision": branch_history.branch.graph_revision,
        "graph_fingerprint": branch_history.branch.graph_fingerprint,
        "issue_signature": issue_signature,
        "history_fingerprint": branch_history.history_fingerprint,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return DialecticResearchResumeAnchor(
        research_challenge_id=research_challenge_id,
        source_gap_id=source_gap_id,
        branch_key=branch_history.branch.branch_key,
        argument_graph_id=branch_history.branch.argument_graph_id,
        graph_revision=branch_history.branch.graph_revision,
        graph_fingerprint=branch_history.branch.graph_fingerprint,
        issue_signature=issue_signature,
        history_fingerprint=branch_history.history_fingerprint,
        anchor_fingerprint="sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )


def validate_research_resume_anchor(
    *,
    anchor: DialecticResearchResumeAnchor,
    research_challenge_id: EntityId,
    source_gap_id: EntityId,
    branch_history: DialecticBranchHistory,
    issue_signature: str,
) -> None:
    rebuilt = compile_research_resume_anchor(
        research_challenge_id=research_challenge_id, source_gap_id=source_gap_id,
        branch_history=branch_history, issue_signature=issue_signature,
        challenge_dimensions=branch_resume_dimensions(branch_history.branch, issue_signature),
    )
    if rebuilt != anchor:
        raise TribunalDialecticError("research result does not match dialectic resume anchor")


def _branch_history_fingerprint(branch: DialecticBranchRef, history: DialecticHistory) -> str:
    payload = {
        "branch_key": branch.branch_key,
        "graph_id": str(branch.argument_graph_id),
        "graph_revision": branch.graph_revision,
        "graph_fingerprint": branch.graph_fingerprint,
        "head": str(branch.head_argument_id),
        "arguments": [str(x) for x in history.argument_ids],
        "turns": [str(x) for x in history.turn_ids],
        "issues": list(history.issue_signatures),
        "resolved": list(history.resolved_issue_signatures),
        "last_position": history.last_position.value if history.last_position else None,
        "visible_ref_fingerprint": history.visible_ref_fingerprint,
        "no_progress_streak": history.no_progress_streak,
        "qa_pair_count": history.qa_pair_count,
        "token_spent": history.token_spent,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def observe_dialectic_step(
    *,
    level: DialecticLevel,
    argument: ArgumentArtifact,
    turn: InquiryTurn,
    history: DialecticHistory,
    visible_refs: Sequence[EntityId] = (),
    issue_proposals: Sequence[DialecticIssueProposal] = (),
    issue_resolutions: Sequence[DialecticIssueResolutionProposal] = (),
    chain_turn_count: int | None = None,
    token_cost: int = 0,
    policy: DialecticPolicy = DialecticPolicy(),
) -> DialecticStepResult:
    """Observe one admitted semantic response and choose the next bounded action.

    No free-text scientific classifier is run here.  Emergent issues come only
    from typed discoveries and typed AdditionalEvidenceRequest objects already
    admitted on the ArgumentArtifact.
    """
    if argument.source_turn_id != turn.meta.id:
        raise TribunalDialecticError("ArgumentArtifact does not bind to supplied InquiryTurn")
    if turn.meta.id in history.turn_ids or argument.meta.id in history.argument_ids:
        raise TribunalDialecticError("dialectic step already observed")
    if token_cost < 0:
        raise TribunalDialecticError("token_cost must be non-negative")

    issues = tuple((*_issues_from_argument(argument), *_issues_from_proposals(argument, issue_proposals)))
    prior_active = set(history.issue_signatures)
    prior_resolved = set(history.resolved_issue_signatures)
    new_issues = tuple(x for x in issues if x.signature not in prior_active and x.signature not in prior_resolved)
    reopened_issues = tuple(x for x in issues if x.signature in prior_resolved)
    repeated = tuple(x.signature for x in issues if x.signature in prior_active)
    resolved, still_open = _validate_issue_resolutions(prior_active, issue_resolutions)
    current_issue_sig_set = {x.signature for x in issues}
    if any(sig in current_issue_sig_set for sig in resolved):
        raise TribunalDialecticError("a dialectic issue cannot be reasserted and resolved in the same response")

    current_visible_fp = _refs_fingerprint(visible_refs)
    evidence_changed = bool(current_visible_fp and current_visible_fp != history.visible_ref_fingerprint)
    position_changed = history.last_position is not None and argument.position is not history.last_position

    semantic_progress = bool(new_issues or reopened_issues or resolved or evidence_changed or position_changed)
    no_progress = 0 if semantic_progress else history.no_progress_streak + 1
    if chain_turn_count is not None and chain_turn_count < 1:
        raise TribunalDialecticError("chain_turn_count must be positive when provided")
    turn_count = chain_turn_count if chain_turn_count is not None else len(history.turn_ids) + 1
    if chain_turn_count is None:
        reasons_turn_count = "CHAIN_TURN_COUNT_APPROXIMATED"
    else:
        reasons_turn_count = "CHAIN_TURN_COUNT_EXPLICIT"
    qa_pairs = history.qa_pair_count + (1 if turn.kind in {InquiryTurnKind.ANSWER, InquiryTurnKind.REBUTTAL} else 0)
    token_spent = history.token_spent + token_cost

    reasons: list[str] = [reasons_turn_count]
    if new_issues:
        reasons.append("NEW_TYPED_ISSUE")
    if reopened_issues:
        reasons.append("ISSUE_REOPENED")
    if repeated:
        reasons.append("REPEATED_TYPED_ISSUE")
    if resolved:
        reasons.append("ISSUE_RESOLVED")
    if still_open:
        reasons.append("ISSUE_CONFIRMED_STILL_OPEN")
    if evidence_changed:
        reasons.append("EVIDENCE_FRONTIER_CHANGED")
    if position_changed:
        reasons.append("ARGUMENT_POSITION_CHANGED")
    if not semantic_progress:
        reasons.append("NO_SEMANTIC_PROGRESS")
    actionable_issue_count = len(new_issues) + len(reopened_issues)
    if any(x.blocking for x in (*new_issues, *reopened_issues)):
        reasons.append("NEW_BLOCKING_ISSUE")
    if actionable_issue_count > policy.max_new_issues_per_turn:
        reasons.append("ISSUE_FANOUT_LIMIT_EXCEEDED")
    if argument.additional_evidence_requests:
        reasons.append("ADDITIONAL_EVIDENCE_REQUESTED")

    current_issue_signatures = tuple(x.signature for x in issues)
    active = tuple(
        sig for sig in dict.fromkeys((*history.issue_signatures, *current_issue_signatures))
        if sig not in resolved
    )
    resolved_history = tuple(
        sig for sig in dict.fromkeys((*history.resolved_issue_signatures, *resolved))
        if sig not in current_issue_signatures
    )
    observation = DialecticObservation(
        level=level,
        turn_count=turn_count,
        qa_pair_count=qa_pairs,
        token_spent=token_spent,
        current_argument_id=argument.meta.id,
        current_turn_id=turn.meta.id,
        current_position=argument.position,
        new_issues=new_issues,
        reopened_issues=reopened_issues,
        repeated_issue_signatures=repeated,
        issue_resolution_proposals=tuple(issue_resolutions),
        resolved_issue_signatures=resolved,
        all_active_issue_signatures=active,
        position_changed=position_changed,
        evidence_frontier_changed=evidence_changed,
        no_progress_streak=no_progress,
        reason_codes=tuple(reasons),
    )
    decision = decide_dialectic_control(observation=observation, argument=argument, policy=policy)
    next_history = DialecticHistory(
        argument_ids=(*history.argument_ids, argument.meta.id),
        turn_ids=(*history.turn_ids, turn.meta.id),
        issue_signatures=active,
        resolved_issue_signatures=resolved_history,
        last_position=argument.position,
        visible_ref_fingerprint=current_visible_fp or history.visible_ref_fingerprint,
        no_progress_streak=no_progress,
        qa_pair_count=qa_pairs,
        token_spent=token_spent,
    )
    return DialecticStepResult(observation, decision, next_history)


def decide_dialectic_control(
    *,
    observation: DialecticObservation,
    argument: ArgumentArtifact,
    policy: DialecticPolicy,
) -> DialecticControlDecision:
    issues = (*observation.new_issues, *observation.reopened_issues)
    issue_sigs = tuple(x.signature for x in issues)

    if policy.escalate_blocking_discovery and any(x.blocking for x in issues):
        if any(x.kind is EmergentIssueKind.ROLE_CAPABILITY_GAP for x in issues):
            return _decision(DialecticAction.RECOMPOSE_PANEL, DialecticLevel.L4_LOCAL_RESEARCH_ESCALATION, "BLOCKING_CAPABILITY_GAP", issue_sigs)
        if argument.additional_evidence_requests or any(x.kind is EmergentIssueKind.MISSING_EVIDENCE for x in issues):
            return _decision(DialecticAction.REQUEST_LOCAL_RESEARCH, DialecticLevel.L4_LOCAL_RESEARCH_ESCALATION, "BLOCKING_RESEARCH_NEED", issue_sigs)

    if len(issues) > policy.max_new_issues_per_turn:
        return _decision(DialecticAction.STOP_OPEN, observation.level, "ISSUE_FANOUT_LIMIT_EXCEEDED", issue_sigs)

    if observation.resolved_issue_signatures and not observation.all_active_issue_signatures and not issues:
        return _decision(DialecticAction.STOP_CONVERGED, observation.level, "ALL_TRACKED_ISSUES_RESOLVED", observation.resolved_issue_signatures)

    if observation.token_spent >= policy.token_budget:
        return _decision(DialecticAction.STOP_BUDGET_LIMIT, observation.level, "TOKEN_BUDGET_EXHAUSTED", issue_sigs)
    if observation.turn_count >= policy.max_turns:
        return _decision(DialecticAction.STOP_TURN_LIMIT, observation.level, "TURN_LIMIT_REACHED", issue_sigs)
    if observation.no_progress_streak > policy.max_no_progress_streak:
        return _decision(DialecticAction.STOP_NO_PROGRESS, observation.level, "NO_PROGRESS_LIMIT_REACHED", issue_sigs)

    if policy.require_novelty_for_followup and not issues and not observation.resolved_issue_signatures and not observation.position_changed and not observation.evidence_frontier_changed:
        return _decision(DialecticAction.STOP_NO_PROGRESS, observation.level, "FOLLOWUP_REQUIRES_NOVELTY", issue_sigs)

    if observation.level >= policy.max_level:
        # Opt-in bounded follow-up: Q3 is admitted only as an explicit Core
        # decision when the response surfaced a NEW non-blocking issue, the
        # QA-pair slot is available, and the current level is exactly the max.
        # It stays on the same level (never re-enters L2) and the turn/token
        # budgets are already enforced above.
        if (
            policy.allow_bounded_followup
            and observation.level is policy.max_level
            and observation.qa_pair_count <= policy.max_question_answer_pairs
            and issues
            and not any(x.blocking for x in issues)
        ):
            return _decision(
                DialecticAction.CONTINUE_QUESTION_ON_ANSWER,
                observation.level,
                "BOUNDED_FOLLOWUP_QA_EXTENSION",
                issue_sigs,
            )
        return _decision(DialecticAction.STOP_DEPTH_LIMIT, observation.level, "DIALECTIC_DEPTH_LIMIT_REACHED", issue_sigs)

    if argument.position is ArgumentPosition.OPEN and not issues:
        return _decision(DialecticAction.STOP_OPEN, observation.level, "OPEN_WITHOUT_NEW_ACTIONABLE_ISSUE", issue_sigs)

    if observation.level is DialecticLevel.L0_INDEPENDENT:
        return _decision(DialecticAction.CONTINUE_CHALLENGE, DialecticLevel.L1_CHALLENGE, "MATERIAL_FIRST_PASS_REQUIRES_CHALLENGE", issue_sigs)
    if observation.level is DialecticLevel.L1_CHALLENGE:
        return _decision(DialecticAction.CONTINUE_QA, DialecticLevel.L2_DIRECT_QA, "CHALLENGE_REQUIRES_DIRECT_ANSWER", issue_sigs)
    if observation.level is DialecticLevel.L2_DIRECT_QA:
        if observation.qa_pair_count >= policy.max_question_answer_pairs:
            return _decision(DialecticAction.STOP_CONVERGED, observation.level, "QA_PAIR_LIMIT_REACHED", issue_sigs)
        return _decision(DialecticAction.CONTINUE_QUESTION_ON_ANSWER, DialecticLevel.L3_QUESTION_ON_ANSWER, "ANSWER_EXPOSED_FOLLOWUP_SURFACE", issue_sigs)
    if observation.level is DialecticLevel.L3_QUESTION_ON_ANSWER:
        return _decision(DialecticAction.STOP_CONVERGED, observation.level, "BOUNDED_CROSS_EXAM_COMPLETE", issue_sigs)

    return _decision(DialecticAction.STOP_OPEN, observation.level, "NO_ADMITTED_CONTINUATION", issue_sigs)


def emergent_issue_from_capability_gap(
    *,
    statement: str,
    need_refs: Sequence[AssessmentNeedRef],
    source_argument_id: EntityId,
    source_turn_id: EntityId,
    metadata: Mapping[str, Any] | None = None,
) -> EmergentIssue:
    return EmergentIssue(
        kind=EmergentIssueKind.ROLE_CAPABILITY_GAP,
        statement=statement,
        need_refs=tuple(need_refs),
        blocking=True,
        source_argument_id=source_argument_id,
        source_turn_id=source_turn_id,
        metadata=metadata or {},
    )




def validate_dialectic_turn_chain(turns: Sequence[InquiryTurn]) -> None:
    """Validate a bounded linear Q/A chain without assigning semantic truth."""
    if not turns:
        raise TribunalDialecticError("dialectic turn chain must not be empty")
    ids = [x.meta.id for x in turns]
    if len(set(ids)) != len(ids):
        raise TribunalDialecticError("duplicate InquiryTurn id in dialectic chain")
    allowed: dict[InquiryTurnKind, set[InquiryTurnKind]] = {
        InquiryTurnKind.FIRST_PASS_ASSESSMENT: {InquiryTurnKind.CHALLENGE, InquiryTurnKind.QUESTION},
        InquiryTurnKind.CHALLENGE: {InquiryTurnKind.QUESTION},
        InquiryTurnKind.QUESTION: {InquiryTurnKind.ANSWER},
        InquiryTurnKind.ANSWER: {InquiryTurnKind.QUESTION_ON_ANSWER},
        InquiryTurnKind.QUESTION_ON_ANSWER: {InquiryTurnKind.REBUTTAL},
        InquiryTurnKind.REBUTTAL: {InquiryTurnKind.QUESTION_ON_ANSWER},
    }
    for i, turn in enumerate(turns):
        if i == 0:
            if turn.parent_turn_id is not None:
                raise TribunalDialecticError("first turn in bounded chain must not have a parent")
            continue
        prev = turns[i - 1]
        if turn.parent_turn_id != prev.meta.id:
            raise TribunalDialecticError("dialectic chain must use immediate historical parent links")
        if turn.kind not in allowed.get(prev.kind, set()):
            raise TribunalDialecticError(f"invalid dialectic turn transition {prev.kind.value}->{turn.kind.value}")


def gap_from_emergent_issue(
    *,
    issue: EmergentIssue,
    target_claim_ids: Sequence[EntityId],
    gap_id: EntityId,
) -> Gap:
    """Project an actionable Tribunal issue into the existing canonical Gap path.

    This is an explicit admission/projection helper; the observer itself never
    writes knowledge state.  A caller/reducer decides whether to invoke it.
    """
    if gap_id.namespace != "GAP":
        raise ValueError("gap_id must use GAP prefix")
    claims = tuple(dict.fromkeys(target_claim_ids))
    if not claims or any(x.namespace != "CLM" for x in claims):
        raise TribunalDialecticError("dialectic Gap projection requires Claim targets")
    severity = "blocking" if issue.blocking else "material"
    return Gap(
        id=gap_id,
        gap_type=f"TRIBUNAL_{issue.kind.value}",
        target_claim_ids=claims,
        severity=severity,
        blocks=claims if issue.blocking else (),
        resolution_requirements=(
            issue.statement,
            f"resolve Tribunal issue {issue.signature}",
        ),
        status=GapState.OPEN_BLOCKING_GAPS if issue.blocking else GapState.OPEN_NONBLOCKING_GAPS,
    )

def dialectic_observation_to_dict(observation: DialecticObservation) -> dict[str, Any]:
    return {
        "schema_version": "dialectic-observation/1.0",
        "level": int(observation.level),
        "level_name": observation.level.name,
        "turn_count": observation.turn_count,
        "qa_pair_count": observation.qa_pair_count,
        "token_spent": observation.token_spent,
        "current_argument_id": str(observation.current_argument_id),
        "current_turn_id": str(observation.current_turn_id),
        "current_position": observation.current_position.value,
        "new_issues": [_issue_to_dict(x) for x in observation.new_issues],
        "reopened_issues": [_issue_to_dict(x) for x in observation.reopened_issues],
        "repeated_issue_signatures": list(observation.repeated_issue_signatures),
        "issue_resolution_proposals": [
            {"issue_signature": x.issue_signature, "disposition": x.disposition.value, "rationale": x.rationale}
            for x in observation.issue_resolution_proposals
        ],
        "resolved_issue_signatures": list(observation.resolved_issue_signatures),
        "all_active_issue_signatures": list(observation.all_active_issue_signatures),
        "position_changed": observation.position_changed,
        "evidence_frontier_changed": observation.evidence_frontier_changed,
        "no_progress_streak": observation.no_progress_streak,
        "reason_codes": list(observation.reason_codes),
    }


def dialectic_decision_to_dict(decision: DialecticControlDecision) -> dict[str, Any]:
    return {
        "schema_version": "dialectic-control-decision/1.0",
        "action": decision.action.value,
        "next_level": int(decision.next_level),
        "next_level_name": decision.next_level.name,
        "reason_codes": list(decision.reason_codes),
        "issue_signatures": list(decision.issue_signatures),
        "authority_boundary": decision.authority_boundary,
    }



def _validate_issue_resolutions(
    prior_signatures: set[str],
    proposals: Sequence[DialecticIssueResolutionProposal],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    resolved: list[str] = []
    still_open: list[str] = []
    seen: set[str] = set()
    for proposal in proposals:
        if proposal.issue_signature not in prior_signatures:
            raise TribunalDialecticError("issue resolution references an unknown prior issue signature")
        if proposal.issue_signature in seen:
            raise TribunalDialecticError("duplicate issue resolution proposal in one dialectic step")
        seen.add(proposal.issue_signature)
        if proposal.disposition is DialecticIssueDisposition.RESOLVED:
            resolved.append(proposal.issue_signature)
        else:
            still_open.append(proposal.issue_signature)
    return tuple(resolved), tuple(still_open)


def _issues_from_proposals(
    argument: ArgumentArtifact,
    proposals: Sequence[DialecticIssueProposal],
) -> Iterable[EmergentIssue]:
    allowed_needs = {(x.key, x.ordinal) for x in argument.assigned_need_refs}
    allowed_refs = set((*argument.cited_target_refs, *argument.cited_evidence_refs))
    for proposal in proposals:
        if any((x.key, x.ordinal) not in allowed_needs for x in proposal.need_refs):
            raise TribunalDialecticError("dialectic issue proposal references an unassigned AssessmentNeed")
        if any(x not in allowed_refs for x in (*proposal.target_refs, *proposal.evidence_refs)):
            raise TribunalDialecticError("dialectic issue proposal references material outside admitted argument refs")
        yield EmergentIssue(
            kind=proposal.kind,
            statement=proposal.statement,
            need_refs=proposal.need_refs,
            target_refs=proposal.target_refs,
            evidence_refs=proposal.evidence_refs,
            blocking=proposal.blocking,
            source_argument_id=argument.meta.id,
            source_turn_id=argument.source_turn_id,
            metadata={"origin": "DialecticIssueProposal", **dict(proposal.metadata)},
        )


def _issues_from_argument(argument: ArgumentArtifact) -> Iterable[EmergentIssue]:
    for discovery in argument.discoveries:
        yield _issue_from_discovery(argument, discovery)
    for request in argument.additional_evidence_requests:
        yield _issue_from_request(argument, request)


def _issue_from_discovery(argument: ArgumentArtifact, discovery: InquiryDiscovery) -> EmergentIssue:
    return EmergentIssue(
        kind=_DISCOVERY_MAP[discovery.kind],
        statement=discovery.statement,
        need_refs=discovery.need_refs,
        target_refs=discovery.target_refs,
        evidence_refs=discovery.evidence_refs,
        blocking=discovery.blocking,
        source_argument_id=argument.meta.id,
        source_turn_id=argument.source_turn_id,
        metadata={"origin": "InquiryDiscovery"},
    )


def _issue_from_request(argument: ArgumentArtifact, request: AdditionalEvidenceRequest) -> EmergentIssue:
    return EmergentIssue(
        kind=EmergentIssueKind.MISSING_EVIDENCE,
        statement=f"{request.question} :: {request.reason}",
        need_refs=request.need_refs,
        target_refs=request.target_refs,
        blocking=True,
        source_argument_id=argument.meta.id,
        source_turn_id=argument.source_turn_id,
        metadata={"origin": "AdditionalEvidenceRequest", "requested_evidence_kinds": request.requested_evidence_kinds},
    )


def _issue_signature(issue: EmergentIssue) -> str:
    payload = {
        "kind": issue.kind.value,
        "statement": " ".join(issue.statement.lower().split()),
        "need_refs": sorted((x.key, x.ordinal) for x in issue.need_refs),
        "target_refs": sorted(str(x) for x in issue.target_refs),
        "evidence_refs": sorted(str(x) for x in issue.evidence_refs),
        "blocking": issue.blocking,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _refs_fingerprint(refs: Sequence[EntityId]) -> str:
    if not refs:
        return ""
    raw = json.dumps(sorted(str(x) for x in set(refs)), separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _decision(action: DialecticAction, next_level: DialecticLevel, reason: str, issue_sigs: Sequence[str]) -> DialecticControlDecision:
    return DialecticControlDecision(action, next_level, (reason,), tuple(issue_sigs))


def _issue_to_dict(issue: EmergentIssue) -> dict[str, Any]:
    return {
        "kind": issue.kind.value,
        "statement": issue.statement,
        "need_refs": [{"key": x.key, "ordinal": x.ordinal} for x in issue.need_refs],
        "target_refs": [str(x) for x in issue.target_refs],
        "evidence_refs": [str(x) for x in issue.evidence_refs],
        "blocking": issue.blocking,
        "source_argument_id": None if issue.source_argument_id is None else str(issue.source_argument_id),
        "source_turn_id": None if issue.source_turn_id is None else str(issue.source_turn_id),
        "signature": issue.signature,
        "metadata": dict(issue.metadata),
    }
