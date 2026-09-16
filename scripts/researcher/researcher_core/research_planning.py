"""Research planning contracts and deterministic ResearchDOM reducer.

R1 planning layer.  The LLM may propose a decomposition, but authoritative
ResearchDOM state is changed only by applying a validated ResearchPatch.

The planning tree answers "what are we investigating?".  It is deliberately
separate from the knowledge graph, which answers "what do we know?".
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import EventEnvelope, ReasonCode, _deep_freeze
from researcher_core.r0.ids import EntityId, EntityIdFactory


class ResearchCardKind(StrEnum):
    OBJECTIVE = "OBJECTIVE"
    DIRECTION = "DIRECTION"
    DISCIPLINARY_VIEW = "DISCIPLINARY_VIEW"
    QUESTION = "QUESTION"
    METHOD_VIEW = "METHOD_VIEW"
    TASK = "TASK"
    CHALLENGE = "CHALLENGE"
    TRIBUNAL_SESSION = "TRIBUNAL_SESSION"
    DELEGATION = "DELEGATION"


class ResearchCardStatus(StrEnum):
    PLANNED = "PLANNED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    SUPERSEDED = "SUPERSEDED"
    ABANDONED = "ABANDONED"
    MERGED = "MERGED"


class PlanningTurnKind(StrEnum):
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"


class PlanningRole(StrEnum):
    PLANNER = "PLANNER"
    DECOMPOSITION_CRITIC = "DECOMPOSITION_CRITIC"
    METHODOLOGIST = "METHODOLOGIST"
    PRUNER = "PRUNER"


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    meta: EntityMeta
    objective: str
    constraints: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RRQ":
            raise ValueError("research request id must use RRQ prefix")
        if not self.objective.strip():
            raise ValueError("objective is required")
        object.__setattr__(self, "constraints", _deep_freeze(self.constraints))


@dataclass(frozen=True, slots=True)
class ResearchCard:
    meta: EntityMeta
    request_id: EntityId
    kind: ResearchCardKind
    title: str
    parent_id: EntityId | None = None
    description: str = ""
    status: ResearchCardStatus = ResearchCardStatus.PLANNED
    dimensions: Mapping[str, Any] = field(default_factory=dict)
    created_from: tuple[EntityId, ...] = ()

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RCD":
            raise ValueError("research card id must use RCD prefix")
        if self.request_id.namespace != "RRQ":
            raise ValueError("request_id must use RRQ prefix")
        if self.parent_id is not None and self.parent_id.namespace != "RCD":
            raise ValueError("parent_id must use RCD prefix")
        if not isinstance(self.kind, ResearchCardKind):
            raise TypeError("kind must be ResearchCardKind")
        if not isinstance(self.status, ResearchCardStatus):
            raise TypeError("status must be ResearchCardStatus")
        if not self.title.strip():
            raise ValueError("title is required")
        if any(ref.namespace not in {"RCD", "GAP", "CNF", "CLM", "DCS", "RRQ", "RCH"} for ref in self.created_from):
            raise ValueError("created_from contains unsupported reference namespace")
        object.__setattr__(self, "dimensions", _deep_freeze(self.dimensions))
        object.__setattr__(self, "created_from", tuple(self.created_from))


@dataclass(frozen=True, slots=True)
class ResearchMap:
    meta: EntityMeta
    request_id: EntityId
    axes: Mapping[str, tuple[str, ...]]
    candidate_card_ids: tuple[EntityId, ...]

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RMP":
            raise ValueError("research map id must use RMP prefix")
        if self.request_id.namespace != "RRQ":
            raise ValueError("request_id must use RRQ prefix")
        normalized_axes = {name: tuple(values) for name, values in self.axes.items()}
        if any(not name for name in normalized_axes):
            raise ValueError("research map axis names must not be empty")
        if any(card_id.namespace != "RCD" for card_id in self.candidate_card_ids):
            raise ValueError("candidate_card_ids must use RCD prefix")
        object.__setattr__(self, "axes", MappingProxyType(normalized_axes))
        object.__setattr__(self, "candidate_card_ids", tuple(self.candidate_card_ids))


@dataclass(frozen=True, slots=True)
class PlanningInquiryTurn:
    id: EntityId
    role: PlanningRole
    kind: PlanningTurnKind
    text: str
    parent_turn_id: EntityId | None = None
    target_card_id: EntityId | None = None
    extracted: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id.namespace != "PIT":
            raise ValueError("planning turn id must use PIT prefix")
        if self.parent_turn_id is not None and self.parent_turn_id.namespace != "PIT":
            raise ValueError("parent_turn_id must use PIT prefix")
        if self.target_card_id is not None and self.target_card_id.namespace != "RCD":
            raise ValueError("target_card_id must use RCD prefix")
        if not self.text.strip():
            raise ValueError("turn text is required")
        object.__setattr__(self, "extracted", _deep_freeze(self.extracted))


@dataclass(frozen=True, slots=True)
class DecompositionSession:
    meta: EntityMeta
    request_id: EntityId
    target_card_id: EntityId | None
    turns: tuple[PlanningInquiryTurn, ...]

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "DCS":
            raise ValueError("decomposition session id must use DCS prefix")
        if self.request_id.namespace != "RRQ":
            raise ValueError("request_id must use RRQ prefix")
        if self.target_card_id is not None and self.target_card_id.namespace != "RCD":
            raise ValueError("target_card_id must use RCD prefix")
        if not self.turns:
            raise ValueError("decomposition session must contain at least one turn")
        object.__setattr__(self, "turns", tuple(self.turns))


@dataclass(frozen=True, slots=True)
class ResearchDOM:
    meta: EntityMeta
    request_id: EntityId
    root_card_id: EntityId
    cards: Mapping[EntityId, ResearchCard]
    applied_patch_ids: tuple[EntityId, ...] = ()

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RDM":
            raise ValueError("research DOM id must use RDM prefix")
        if self.request_id.namespace != "RRQ":
            raise ValueError("request_id must use RRQ prefix")
        if self.root_card_id.namespace != "RCD":
            raise ValueError("root_card_id must use RCD prefix")
        cards = dict(self.cards)
        if self.root_card_id not in cards:
            raise ValueError("root_card_id must exist in cards")
        root = cards[self.root_card_id]
        if root.kind != ResearchCardKind.OBJECTIVE or root.parent_id is not None:
            raise ValueError("root card must be a parentless OBJECTIVE card")
        for card_id, card in cards.items():
            if card_id != card.meta.id:
                raise ValueError("cards mapping key must equal card id")
            if card.request_id != self.request_id:
                raise ValueError("all cards must belong to the same request")
            if card.parent_id is not None and card.parent_id not in cards:
                raise ValueError(f"missing parent card: {card.parent_id}")
        _assert_acyclic(cards, self.root_card_id)
        if any(patch_id.namespace != "RPT" for patch_id in self.applied_patch_ids):
            raise ValueError("applied_patch_ids must use RPT prefix")
        object.__setattr__(self, "cards", MappingProxyType(cards))
        object.__setattr__(self, "applied_patch_ids", tuple(self.applied_patch_ids))

    def children_of(self, card_id: EntityId) -> tuple[ResearchCard, ...]:
        if card_id not in self.cards:
            raise KeyError(str(card_id))
        return tuple(card for card in self.cards.values() if card.parent_id == card_id)

    def lineage(self, card_id: EntityId) -> tuple[ResearchCard, ...]:
        if card_id not in self.cards:
            raise KeyError(str(card_id))
        chain: list[ResearchCard] = []
        current = self.cards[card_id]
        while True:
            chain.append(current)
            if current.parent_id is None:
                break
            current = self.cards[current.parent_id]
        chain.reverse()
        return tuple(chain)


@dataclass(frozen=True, slots=True)
class AddCardOperation:
    card: ResearchCard


@dataclass(frozen=True, slots=True)
class SetCardStatusOperation:
    card_id: EntityId
    expected_card_revision: int
    status: ResearchCardStatus

    def __post_init__(self) -> None:
        if self.card_id.namespace != "RCD":
            raise ValueError("card_id must use RCD prefix")
        if self.expected_card_revision < 1:
            raise ValueError("expected_card_revision must be positive")


PlanningOperation = AddCardOperation | SetCardStatusOperation


@dataclass(frozen=True, slots=True)
class ResearchPatch:
    id: EntityId
    request_id: EntityId
    expected_dom_revision: int
    operations: tuple[PlanningOperation, ...]
    source_session_id: EntityId | None = None

    def __post_init__(self) -> None:
        if self.id.namespace != "RPT":
            raise ValueError("research patch id must use RPT prefix")
        if self.request_id.namespace != "RRQ":
            raise ValueError("request_id must use RRQ prefix")
        if self.expected_dom_revision < 1:
            raise ValueError("expected_dom_revision must be positive")
        if not self.operations:
            raise ValueError("research patch must contain operations")
        if self.source_session_id is not None and self.source_session_id.namespace != "DCS":
            raise ValueError("source_session_id must use DCS prefix")
        object.__setattr__(self, "operations", tuple(self.operations))


class ResearchPlanningError(RuntimeError):
    pass


class ResearchDOMRevisionConflict(ResearchPlanningError):
    pass


class ResearchPatchConflict(ResearchPlanningError):
    pass


@dataclass(frozen=True, slots=True)
class PlanningReduceResult:
    dom: ResearchDOM
    events: tuple[EventEnvelope, ...]


def create_initial_dom(
    request: ResearchRequest,
    root_card: ResearchCard,
    dom_id: EntityId,
) -> ResearchDOM:
    if dom_id.namespace != "RDM":
        raise ValueError("dom_id must use RDM prefix")
    if root_card.request_id != request.meta.id:
        raise ValueError("root card belongs to a different request")
    if root_card.kind != ResearchCardKind.OBJECTIVE or root_card.parent_id is not None:
        raise ValueError("initial root card must be parentless OBJECTIVE")
    dom_meta = EntityMeta(
        id=dom_id,
        schema_version="research-dom/1.0",
        revision=1,
        run_id=request.meta.run_id,
        created_at=request.meta.created_at,
        created_by=request.meta.created_by,
    )
    return ResearchDOM(
        meta=dom_meta,
        request_id=request.meta.id,
        root_card_id=root_card.meta.id,
        cards={root_card.meta.id: root_card},
    )


def apply_research_patch(
    dom: ResearchDOM,
    patch: ResearchPatch,
    actor: ActorRef,
    id_factory: EntityIdFactory,
    timestamp,
    causation_id: EntityId,
    correlation_id: EntityId,
) -> PlanningReduceResult:
    if patch.request_id != dom.request_id:
        raise ResearchPatchConflict("patch belongs to a different research request")
    if patch.id in dom.applied_patch_ids:
        # Event-sourced replay should normally catch this before reducer invocation.
        # Fail closed here rather than applying the same structural mutation twice.
        raise ResearchPatchConflict("patch has already been applied")
    if dom.meta.revision != patch.expected_dom_revision:
        raise ResearchDOMRevisionConflict(
            f"expected DOM revision {patch.expected_dom_revision}, current {dom.meta.revision}"
        )

    cards = dict(dom.cards)
    events: list[EventEnvelope] = []
    next_dom_revision = dom.meta.revision + 1

    for operation in patch.operations:
        if isinstance(operation, AddCardOperation):
            card = operation.card
            if card.request_id != dom.request_id:
                raise ResearchPatchConflict("card belongs to a different research request")
            if card.meta.id in cards:
                raise ResearchPatchConflict(f"card already exists: {card.meta.id}")
            if card.parent_id is None:
                raise ResearchPatchConflict("only the initial OBJECTIVE card may have no parent")
            if card.parent_id not in cards:
                raise ResearchPatchConflict(f"parent does not exist: {card.parent_id}")
            cards[card.meta.id] = card
            events.append(
                _planning_event(
                    id_factory=id_factory,
                    event_type="RESEARCH_CARD_ADDED",
                    aggregate_id=dom.meta.id,
                    aggregate_revision=next_dom_revision,
                    run_id=dom.meta.run_id,
                    actor=actor,
                    timestamp=timestamp,
                    causation_id=causation_id,
                    correlation_id=correlation_id,
                    payload={
                        "patch_id": str(patch.id),
                        "card_id": str(card.meta.id),
                        "parent_id": str(card.parent_id),
                        "kind": card.kind.value,
                        "title": card.title,
                        "card": _replayable_card_payload(card),
                    },
                )
            )
        elif isinstance(operation, SetCardStatusOperation):
            if operation.card_id not in cards:
                raise ResearchPatchConflict(f"card does not exist: {operation.card_id}")
            current = cards[operation.card_id]
            if current.meta.revision != operation.expected_card_revision:
                raise ResearchPatchConflict(
                    f"card revision mismatch for {operation.card_id}: expected "
                    f"{operation.expected_card_revision}, current {current.meta.revision}"
                )
            next_meta = replace(current.meta, revision=current.meta.revision + 1)
            cards[operation.card_id] = replace(current, meta=next_meta, status=operation.status)
            events.append(
                _planning_event(
                    id_factory=id_factory,
                    event_type="RESEARCH_CARD_STATE_CHANGED",
                    aggregate_id=dom.meta.id,
                    aggregate_revision=next_dom_revision,
                    run_id=dom.meta.run_id,
                    actor=actor,
                    timestamp=timestamp,
                    causation_id=causation_id,
                    correlation_id=correlation_id,
                    payload={
                        "patch_id": str(patch.id),
                        "card_id": str(operation.card_id),
                        "from_status": current.status.value,
                        "to_status": operation.status.value,
                    },
                    reason_codes=(ReasonCode("RESEARCH_CARD_STATE_CHANGED"),),
                )
            )
        else:  # pragma: no cover - defensive boundary for future operation types
            raise TypeError(f"unsupported planning operation: {type(operation)!r}")

    _assert_acyclic(cards, dom.root_card_id)
    next_meta = replace(dom.meta, revision=next_dom_revision)
    updated = ResearchDOM(
        meta=next_meta,
        request_id=dom.request_id,
        root_card_id=dom.root_card_id,
        cards=cards,
        applied_patch_ids=(*dom.applied_patch_ids, patch.id),
    )
    events.append(
        _planning_event(
            id_factory=id_factory,
            event_type="RESEARCH_PATCH_APPLIED",
            aggregate_id=dom.meta.id,
            aggregate_revision=next_dom_revision,
            run_id=dom.meta.run_id,
            actor=actor,
            timestamp=timestamp,
            causation_id=causation_id,
            correlation_id=correlation_id,
            payload={
                "patch_id": str(patch.id),
                "source_session_id": str(patch.source_session_id) if patch.source_session_id else None,
                "operation_count": len(patch.operations),
                "card_count": len(cards),
            },
        )
    )
    return PlanningReduceResult(dom=updated, events=tuple(events))


def build_research_map(
    meta: EntityMeta,
    request_id: EntityId,
    candidate_cards: Sequence[ResearchCard],
) -> ResearchMap:
    """Build a compact multidimensional ResearchMap from candidate cards.

    This does not change ResearchDOM.  It is a planning projection used to
    inspect coverage before selected cards are inserted into the executable tree.
    """
    axes: dict[str, set[str]] = {
        "directions": set(),
        "disciplines": set(),
        "question_types": set(),
        "methods": set(),
    }
    ids: list[EntityId] = []
    for card in candidate_cards:
        if card.request_id != request_id:
            raise ValueError("candidate card belongs to a different request")
        ids.append(card.meta.id)
        if card.kind == ResearchCardKind.DIRECTION:
            axes["directions"].add(card.title)
        for key, target_axis in (
            ("disciplines", "disciplines"),
            ("question_types", "question_types"),
            ("methods", "methods"),
        ):
            values = card.dimensions.get(key, ())
            if isinstance(values, str):
                values = (values,)
            for value in values:
                axes[target_axis].add(str(value))
    return ResearchMap(
        meta=meta,
        request_id=request_id,
        axes={key: tuple(sorted(values)) for key, values in axes.items()},
        candidate_card_ids=tuple(ids),
    )



def _replayable_card_payload(card: ResearchCard) -> Mapping[str, Any]:
    """Serialize a card into event payload without importing the persistence adapter."""
    return {
        "meta": {
            "id": str(card.meta.id),
            "schema_version": card.meta.schema_version,
            "revision": card.meta.revision,
            "run_id": str(card.meta.run_id),
            "created_at": card.meta.created_at.isoformat(),
            "created_by": {
                "actor_type": card.meta.created_by.actor_type,
                "actor_id": card.meta.created_by.actor_id,
            },
        },
        "request_id": str(card.request_id),
        "kind": card.kind.value,
        "title": card.title,
        "parent_id": str(card.parent_id) if card.parent_id else None,
        "description": card.description,
        "status": card.status.value,
        "dimensions": _plain_event_value(card.dimensions),
        "created_from": [str(ref) for ref in card.created_from],
    }


def _plain_event_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_event_value(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [_plain_event_value(nested) for nested in value]
    if isinstance(value, EntityId):
        return str(value)
    return value

def _planning_event(
    *,
    id_factory: EntityIdFactory,
    event_type: str,
    aggregate_id: EntityId,
    aggregate_revision: int,
    run_id: EntityId,
    actor: ActorRef,
    timestamp,
    causation_id: EntityId,
    correlation_id: EntityId,
    payload: Mapping[str, Any],
    reason_codes: tuple[ReasonCode, ...] = (),
) -> EventEnvelope:
    return EventEnvelope(
        event_id=id_factory.new("EVT"),
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_revision=aggregate_revision,
        run_id=run_id,
        actor=actor.actor_id,
        timestamp=timestamp,
        causation_id=causation_id,
        correlation_id=correlation_id,
        schema_version="research-planning-event/1.0",
        reason_codes=reason_codes,
        payload=payload,
    )


def _assert_acyclic(cards: Mapping[EntityId, ResearchCard], root_card_id: EntityId) -> None:
    # Parent pointers make cycle detection cheap and deterministic.
    for card_id in cards:
        seen: set[EntityId] = set()
        current_id: EntityId | None = card_id
        while current_id is not None:
            if current_id in seen:
                raise ValueError(f"cycle detected in ResearchDOM at {current_id}")
            seen.add(current_id)
            current = cards.get(current_id)
            if current is None:
                raise ValueError(f"missing card referenced by tree: {current_id}")
            current_id = current.parent_id
        if root_card_id not in seen:
            raise ValueError(f"card {card_id} is not connected to root {root_card_id}")

@dataclass(frozen=True, slots=True)
class ResearchCardProposal:
    """Non-authoritative card proposed by PlanningDialectic or another planner.

    ``parent_ref`` may be an existing RCD id or a temp id from the same proposal
    batch.  Only ``compile_decomposition_proposals`` may turn proposals into
    authoritative ResearchCards.
    """

    temp_id: str
    kind: ResearchCardKind
    title: str
    parent_ref: EntityId | str
    description: str = ""
    dimensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.temp_id.strip():
            raise ValueError("temp_id is required")
        if not self.title.strip():
            raise ValueError("title is required")
        if isinstance(self.parent_ref, EntityId) and self.parent_ref.namespace != "RCD":
            raise ValueError("entity parent_ref must use RCD prefix")
        if isinstance(self.parent_ref, str) and not self.parent_ref.strip():
            raise ValueError("string parent_ref must not be empty")
        if not isinstance(self.parent_ref, (EntityId, str)):
            raise TypeError("parent_ref must be EntityId or temp-id string")
        object.__setattr__(self, "dimensions", _deep_freeze(self.dimensions))


@dataclass(frozen=True, slots=True)
class PlanningCompileResult:
    cards: tuple[ResearchCard, ...]
    research_map: ResearchMap
    patch: ResearchPatch


class PlanningCompileError(ResearchPlanningError):
    pass


def compile_decomposition_proposals(
    *,
    session: DecompositionSession,
    dom: ResearchDOM,
    proposals: Sequence[ResearchCardProposal],
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at,
) -> PlanningCompileResult:
    """Compile a planning dialectic result into cards + map + atomic patch.

    The function is deliberately semantic-dumb: it validates structure,
    duplicates and ancestry, but does not invent directions or rewrite titles.
    That remains the planner's job; authoritative tree mutation remains code's.
    """
    if session.request_id != dom.request_id:
        raise PlanningCompileError("session belongs to a different research request")
    if session.target_card_id is not None and session.target_card_id not in dom.cards:
        raise PlanningCompileError("session target card does not exist in ResearchDOM")
    if not proposals:
        raise PlanningCompileError("decomposition produced no card proposals")

    by_temp: dict[str, ResearchCardProposal] = {}
    sibling_signatures: set[tuple[str, ResearchCardKind, str]] = set()
    for proposal in proposals:
        if proposal.temp_id in by_temp:
            raise PlanningCompileError(f"duplicate proposal temp_id: {proposal.temp_id}")
        by_temp[proposal.temp_id] = proposal
        parent_key = str(proposal.parent_ref)
        signature = (parent_key, proposal.kind, _normalize_title(proposal.title))
        if signature in sibling_signatures:
            raise PlanningCompileError(
                f"duplicate sibling proposal: {proposal.kind.value} {proposal.title!r}"
            )
        sibling_signatures.add(signature)

    # Allocate ids first, so nested proposal references can be resolved in one pass.
    allocated = {temp_id: id_factory.new("RCD") for temp_id in by_temp}
    cards: list[ResearchCard] = []
    for proposal in proposals:
        if isinstance(proposal.parent_ref, EntityId):
            parent_id = proposal.parent_ref
            if parent_id not in dom.cards:
                raise PlanningCompileError(f"parent card does not exist: {parent_id}")
        else:
            if proposal.parent_ref not in allocated:
                raise PlanningCompileError(
                    f"parent temp-id is not present in proposal batch: {proposal.parent_ref}"
                )
            parent_id = allocated[proposal.parent_ref]

        meta = EntityMeta(
            id=allocated[proposal.temp_id],
            schema_version="research-card/1.0",
            revision=1,
            run_id=dom.meta.run_id,
            created_at=created_at,
            created_by=actor,
        )
        created_from = (session.meta.id,)
        card = ResearchCard(
            meta=meta,
            request_id=dom.request_id,
            kind=proposal.kind,
            title=proposal.title,
            parent_id=parent_id,
            description=proposal.description,
            dimensions=proposal.dimensions,
            created_from=created_from,
        )
        cards.append(card)

    # Validate that proposal-only ancestry does not contain cycles before emitting patch.
    shadow = dict(dom.cards)
    shadow.update({card.meta.id: card for card in cards})
    _assert_acyclic(shadow, dom.root_card_id)

    map_meta = EntityMeta(
        id=id_factory.new("RMP"),
        schema_version="research-map/1.0",
        revision=1,
        run_id=dom.meta.run_id,
        created_at=created_at,
        created_by=actor,
    )
    research_map = build_research_map(map_meta, dom.request_id, cards)
    patch = ResearchPatch(
        id=id_factory.new("RPT"),
        request_id=dom.request_id,
        expected_dom_revision=dom.meta.revision,
        operations=tuple(AddCardOperation(card) for card in cards),
        source_session_id=session.meta.id,
    )
    return PlanningCompileResult(cards=tuple(cards), research_map=research_map, patch=patch)


def _normalize_title(title: str) -> str:
    return " ".join(title.casefold().split())
