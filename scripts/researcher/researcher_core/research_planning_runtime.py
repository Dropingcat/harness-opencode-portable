"""R1.1 runtime helpers for ResearchDOM gates, persistence, replay and trace links.

This module deliberately contains no search or LLM logic.  It makes the planning
side durable and auditable before ResearchDOM is connected to the knowledge graph.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import EventEnvelope
from researcher_core.r0.ids import EntityId
from researcher_core.r0.sqlite_store import SqliteUnitOfWork
from researcher_core.research_planning import (
    ResearchCard,
    ResearchCardKind,
    ResearchCardStatus,
    ResearchDOM,
)


class PlanningGateState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass(frozen=True, slots=True)
class PlanningGateIssue:
    code: str
    state: PlanningGateState
    message: str
    card_ids: tuple[EntityId, ...] = ()

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("gate issue code is required")
        if not self.message:
            raise ValueError("gate issue message is required")
        object.__setattr__(self, "card_ids", tuple(self.card_ids))


@dataclass(frozen=True, slots=True)
class PlanningGateReport:
    state: PlanningGateState
    issues: tuple[PlanningGateIssue, ...]
    metrics: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


@dataclass(frozen=True, slots=True)
class PlanningGatePolicy:
    max_cards: int = 80
    max_depth: int = 8
    require_direction: bool = True
    require_executable_leaf: bool = True

    def __post_init__(self) -> None:
        if self.max_cards < 1 or self.max_depth < 1:
            raise ValueError("planning gate limits must be positive")


def planning_gate_policy_from_policy(policy) -> PlanningGatePolicy:
    """Build PlanningGatePolicy from config/research_policy.yaml heuristics."""
    def one(key: str, default: int) -> int:
        heuristic = policy.heuristics.get(key)
        if heuristic is None or not heuristic.value:
            return default
        return int(heuristic.value[0])
    return PlanningGatePolicy(
        max_cards=one("research.planning.max_cards", 80),
        max_depth=one("research.planning.max_depth", 8),
    )


EXECUTABLE_CAPABILITY_KEYS = frozenset({"capability", "delegation_target"})


def evaluate_planning_gate(dom: ResearchDOM, policy: PlanningGatePolicy = PlanningGatePolicy()) -> PlanningGateReport:
    """Evaluate structural executability, not scientific truth or completeness."""
    issues: list[PlanningGateIssue] = []
    cards = tuple(dom.cards.values())
    directions = tuple(c for c in cards if c.kind == ResearchCardKind.DIRECTION)
    leaves = tuple(c for c in cards if not dom.children_of(c.meta.id))
    executable_leaves = tuple(c for c in leaves if _is_executable_leaf(c))
    max_depth = max(len(dom.lineage(c.meta.id)) - 1 for c in cards)

    if policy.require_direction and not directions:
        issues.append(PlanningGateIssue("NO_DIRECTION", PlanningGateState.FAIL, "ResearchDOM has no DIRECTION card."))

    if policy.require_executable_leaf:
        bad_leaves = tuple(c for c in leaves if c.kind != ResearchCardKind.OBJECTIVE and not _is_executable_leaf(c))
        if bad_leaves:
            issues.append(
                PlanningGateIssue(
                    "NON_EXECUTABLE_LEAF",
                    PlanningGateState.FAIL,
                    "Leaf cards must resolve to TASK/DELEGATION with an executable capability.",
                    tuple(c.meta.id for c in bad_leaves),
                )
            )

    if len(cards) > policy.max_cards:
        issues.append(PlanningGateIssue("CARD_BUDGET_EXCEEDED", PlanningGateState.FAIL, f"Card count {len(cards)} exceeds {policy.max_cards}."))
    elif len(cards) > int(policy.max_cards * 0.8):
        issues.append(PlanningGateIssue("CARD_BUDGET_NEAR_LIMIT", PlanningGateState.WARN, f"Card count {len(cards)} is near limit {policy.max_cards}."))

    if max_depth > policy.max_depth:
        issues.append(PlanningGateIssue("DEPTH_BUDGET_EXCEEDED", PlanningGateState.FAIL, f"Tree depth {max_depth} exceeds {policy.max_depth}."))

    # ResearchDOM constructor already guarantees parent existence + acyclicity.
    # Here we detect semantic duplicate siblings across the authoritative tree.
    duplicate_ids: list[EntityId] = []
    sibling_seen: set[tuple[str, str, str]] = set()
    for card in cards:
        if card.parent_id is None:
            continue
        signature = (str(card.parent_id), card.kind.value, " ".join(card.title.lower().split()))
        if signature in sibling_seen:
            duplicate_ids.append(card.meta.id)
        else:
            sibling_seen.add(signature)
    if duplicate_ids:
        issues.append(PlanningGateIssue("DUPLICATE_SIBLING", PlanningGateState.FAIL, "ResearchDOM contains duplicate sibling cards.", tuple(duplicate_ids)))

    state = PlanningGateState.FAIL if any(i.state == PlanningGateState.FAIL for i in issues) else (
        PlanningGateState.WARN if any(i.state == PlanningGateState.WARN for i in issues) else PlanningGateState.PASS
    )
    return PlanningGateReport(
        state=state,
        issues=tuple(issues),
        metrics={
            "cards": len(cards),
            "directions": len(directions),
            "leaves": len(leaves),
            "executable_leaves": len(executable_leaves),
            "max_depth": max_depth,
        },
    )



def evaluate_planning_subtree_gate(
    dom: ResearchDOM,
    root_card_id: EntityId,
    policy: PlanningGatePolicy = PlanningGatePolicy(require_direction=False),
) -> PlanningGateReport:
    """Evaluate executability of one local ResearchDOM subtree.

    This is used for adaptive feedback branches.  A CHALLENGE subtree does not
    need to introduce a new DIRECTION, but it must terminate in executable
    TASK/DELEGATION leaves and respect local depth/card limits.
    """
    if root_card_id not in dom.cards:
        raise KeyError(str(root_card_id))

    scoped_ids: set[EntityId] = set()
    pending = [root_card_id]
    while pending:
        current = pending.pop()
        if current in scoped_ids:
            continue
        scoped_ids.add(current)
        pending.extend(card.meta.id for card in dom.children_of(current))

    cards = tuple(dom.cards[card_id] for card_id in scoped_ids)
    leaves = tuple(
        card for card in cards
        if not any(child.parent_id == card.meta.id for child in cards)
    )
    executable_leaves = tuple(card for card in leaves if _is_executable_leaf(card))
    root_depth = len(dom.lineage(root_card_id)) - 1
    max_depth = max((len(dom.lineage(card.meta.id)) - 1 - root_depth) for card in cards)
    issues: list[PlanningGateIssue] = []

    if policy.require_direction and not any(card.kind == ResearchCardKind.DIRECTION for card in cards):
        issues.append(PlanningGateIssue("NO_DIRECTION", PlanningGateState.FAIL, "Planning subtree has no DIRECTION card."))

    if policy.require_executable_leaf:
        bad = tuple(
            card for card in leaves
            if card.meta.id != root_card_id and not _is_executable_leaf(card)
        )
        # A still-leaf root challenge is also non-executable.
        if len(cards) == 1 and not _is_executable_leaf(dom.cards[root_card_id]):
            bad = (dom.cards[root_card_id],)
        if bad:
            issues.append(PlanningGateIssue(
                "NON_EXECUTABLE_LEAF", PlanningGateState.FAIL,
                "Subtree leaves must resolve to TASK/DELEGATION with an executable capability.",
                tuple(card.meta.id for card in bad),
            ))

    if len(cards) > policy.max_cards:
        issues.append(PlanningGateIssue("CARD_BUDGET_EXCEEDED", PlanningGateState.FAIL, f"Subtree card count {len(cards)} exceeds {policy.max_cards}."))
    elif len(cards) > int(policy.max_cards * 0.8):
        issues.append(PlanningGateIssue("CARD_BUDGET_NEAR_LIMIT", PlanningGateState.WARN, f"Subtree card count {len(cards)} is near limit {policy.max_cards}."))
    if max_depth > policy.max_depth:
        issues.append(PlanningGateIssue("DEPTH_BUDGET_EXCEEDED", PlanningGateState.FAIL, f"Subtree depth {max_depth} exceeds {policy.max_depth}."))

    seen: set[tuple[str, str, str]] = set()
    duplicates: list[EntityId] = []
    for card in cards:
        if card.parent_id is None or card.parent_id not in scoped_ids:
            continue
        signature = (str(card.parent_id), card.kind.value, " ".join(card.title.lower().split()))
        if signature in seen:
            duplicates.append(card.meta.id)
        else:
            seen.add(signature)
    if duplicates:
        issues.append(PlanningGateIssue("DUPLICATE_SIBLING", PlanningGateState.FAIL, "Planning subtree contains duplicate sibling cards.", tuple(duplicates)))

    state = PlanningGateState.FAIL if any(i.state == PlanningGateState.FAIL for i in issues) else (
        PlanningGateState.WARN if any(i.state == PlanningGateState.WARN for i in issues) else PlanningGateState.PASS
    )
    return PlanningGateReport(
        state=state,
        issues=tuple(issues),
        metrics={
            "cards": len(cards),
            "leaves": len(leaves),
            "executable_leaves": len(executable_leaves),
            "max_depth": max_depth,
        },
    )

def _is_executable_leaf(card: ResearchCard) -> bool:
    if card.kind not in {ResearchCardKind.TASK, ResearchCardKind.DELEGATION}:
        return False
    return any(bool(card.dimensions.get(key)) for key in EXECUTABLE_CAPABILITY_KEYS)


class ResearchTraceRelation(StrEnum):
    PRODUCED = "PRODUCED"
    DISCOVERED = "DISCOVERED"
    CREATED_CHALLENGE = "CREATED_CHALLENGE"
    RESOLVED_BY = "RESOLVED_BY"
    VALIDATED = "VALIDATED"
    ADDRESSES = "ADDRESSES"


@dataclass(frozen=True, slots=True)
class ResearchTraceLink:
    id: EntityId
    research_card_id: EntityId
    target_id: EntityId
    relation: ResearchTraceRelation
    run_id: EntityId
    created_at: datetime
    created_by: ActorRef
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.id.namespace != "RTL":
            raise ValueError("trace link id must use RTL prefix")
        if self.research_card_id.namespace != "RCD":
            raise ValueError("research_card_id must use RCD prefix")
        if self.target_id.namespace not in {"CLM", "EVD", "GAP", "CNF", "ASM", "DRV", "SRC", "RCD", "RCH", "RRS", "QTY", "EDG"}:
            raise ValueError("unsupported trace target namespace")
        if self.run_id.namespace != "RUN":
            raise ValueError("run_id must use RUN prefix")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class ResearchDOMRepository:
    """Small durable adapter over the existing R0 SQLite UnitOfWork."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def save(self, dom: ResearchDOM, events: Sequence[EventEnvelope] = ()) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(dom.meta.id, research_dom_to_dict(dom))
            for event in events:
                uow.append_event(event)
            uow.commit()

    def load(self, dom_id: EntityId) -> ResearchDOM | None:
        view = SqliteUnitOfWork(self._conn).state_view()
        raw = view.get(str(dom_id))
        return research_dom_from_dict(raw) if raw is not None else None



def research_trace_link_to_dict(link: ResearchTraceLink) -> dict[str, Any]:
    return {
        "schema_version": "research-trace-link/1.0",
        "id": str(link.id),
        "research_card_id": str(link.research_card_id),
        "target_id": str(link.target_id),
        "relation": link.relation.value,
        "run_id": str(link.run_id),
        "created_at": link.created_at.isoformat(),
        "created_by": _actor_to_dict(link.created_by),
        "metadata": _plain(link.metadata),
    }


def research_trace_link_from_dict(raw: Mapping[str, Any]) -> ResearchTraceLink:
    return ResearchTraceLink(
        id=EntityId(str(raw["id"])),
        research_card_id=EntityId(str(raw["research_card_id"])),
        target_id=EntityId(str(raw["target_id"])),
        relation=ResearchTraceRelation(str(raw["relation"])),
        run_id=EntityId(str(raw["run_id"])),
        created_at=datetime.fromisoformat(str(raw["created_at"])),
        created_by=_actor_from_dict(raw["created_by"]),
        metadata=dict(raw.get("metadata", {})),
    )


class ResearchTraceRepository:
    def __init__(self, conn) -> None:
        self._conn = conn

    def save(self, links: Sequence[ResearchTraceLink]) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            for link in links:
                uow.put_state(link.id, research_trace_link_to_dict(link))
            uow.commit()

    def all(self) -> tuple[ResearchTraceLink, ...]:
        view = SqliteUnitOfWork(self._conn).state_view()
        links = []
        for raw in view.values():
            if raw.get("schema_version") == "research-trace-link/1.0":
                links.append(research_trace_link_from_dict(raw))
        return tuple(sorted(links, key=lambda link: str(link.id)))

    def for_card(self, card_id: EntityId) -> tuple[ResearchTraceLink, ...]:
        return tuple(link for link in self.all() if link.research_card_id == card_id)

def research_dom_to_dict(dom: ResearchDOM) -> dict[str, Any]:
    return {
        "schema_version": "research-dom-snapshot/1.0",
        "meta": _meta_to_dict(dom.meta),
        "request_id": str(dom.request_id),
        "root_card_id": str(dom.root_card_id),
        "applied_patch_ids": [str(x) for x in dom.applied_patch_ids],
        "cards": [_card_to_dict(card) for card in dom.cards.values()],
    }


def research_dom_from_dict(raw: Mapping[str, Any]) -> ResearchDOM:
    cards = tuple(_card_from_dict(item) for item in raw["cards"])
    card_map = {card.meta.id: card for card in cards}
    return ResearchDOM(
        meta=_meta_from_dict(raw["meta"]),
        request_id=EntityId(raw["request_id"]),
        root_card_id=EntityId(raw["root_card_id"]),
        cards=card_map,
        applied_patch_ids=tuple(EntityId(v) for v in raw.get("applied_patch_ids", ())),
    )


def replay_research_dom(initial_dom: ResearchDOM, events: Sequence[EventEnvelope]) -> ResearchDOM:
    """Rebuild ResearchDOM from planning events after the known initial root snapshot."""
    cards = dict(initial_dom.cards)
    applied: list[EntityId] = list(initial_dom.applied_patch_ids)
    revision = initial_dom.meta.revision
    for event in events:
        if event.aggregate_id != initial_dom.meta.id:
            continue
        if event.event_type == "RESEARCH_CARD_ADDED":
            card_raw = event.payload.get("card")
            if not isinstance(card_raw, Mapping):
                raise ValueError("RESEARCH_CARD_ADDED event lacks replayable card payload")
            card = _card_from_dict(card_raw)
            cards[card.meta.id] = card
        elif event.event_type == "RESEARCH_CARD_STATE_CHANGED":
            card_id = EntityId(str(event.payload["card_id"]))
            current = cards[card_id]
            cards[card_id] = replace(
                current,
                meta=replace(current.meta, revision=current.meta.revision + 1),
                status=ResearchCardStatus(str(event.payload["to_status"])),
            )
        elif event.event_type == "RESEARCH_PATCH_APPLIED":
            patch_id = EntityId(str(event.payload["patch_id"]))
            if patch_id not in applied:
                applied.append(patch_id)
            revision = event.aggregate_revision
    return ResearchDOM(
        meta=replace(initial_dom.meta, revision=revision),
        request_id=initial_dom.request_id,
        root_card_id=initial_dom.root_card_id,
        cards=cards,
        applied_patch_ids=tuple(applied),
    )


def card_to_event_payload(card: ResearchCard) -> Mapping[str, Any]:
    return _card_to_dict(card)


def _actor_to_dict(actor: ActorRef) -> dict[str, str]:
    return {"actor_type": actor.actor_type, "actor_id": actor.actor_id}


def _actor_from_dict(raw: Mapping[str, Any]) -> ActorRef:
    return ActorRef(actor_type=str(raw["actor_type"]), actor_id=str(raw["actor_id"]))


def _meta_to_dict(meta: EntityMeta) -> dict[str, Any]:
    return {
        "id": str(meta.id),
        "schema_version": meta.schema_version,
        "revision": meta.revision,
        "run_id": str(meta.run_id),
        "created_at": meta.created_at.isoformat(),
        "created_by": _actor_to_dict(meta.created_by),
    }


def _meta_from_dict(raw: Mapping[str, Any]) -> EntityMeta:
    return EntityMeta(
        id=EntityId(str(raw["id"])),
        schema_version=str(raw["schema_version"]),
        revision=int(raw["revision"]),
        run_id=EntityId(str(raw["run_id"])),
        created_at=datetime.fromisoformat(str(raw["created_at"])),
        created_by=_actor_from_dict(raw["created_by"]),
    )


def _card_to_dict(card: ResearchCard) -> dict[str, Any]:
    return {
        "meta": _meta_to_dict(card.meta),
        "request_id": str(card.request_id),
        "kind": card.kind.value,
        "title": card.title,
        "parent_id": str(card.parent_id) if card.parent_id else None,
        "description": card.description,
        "status": card.status.value,
        "dimensions": _plain(card.dimensions),
        "created_from": [str(x) for x in card.created_from],
    }


def _card_from_dict(raw: Mapping[str, Any]) -> ResearchCard:
    return ResearchCard(
        meta=_meta_from_dict(raw["meta"]),
        request_id=EntityId(str(raw["request_id"])),
        kind=ResearchCardKind(str(raw["kind"])),
        title=str(raw["title"]),
        parent_id=EntityId(str(raw["parent_id"])) if raw.get("parent_id") else None,
        description=str(raw.get("description", "")),
        status=ResearchCardStatus(str(raw.get("status", ResearchCardStatus.PLANNED.value))),
        dimensions=dict(raw.get("dimensions", {})),
        created_from=tuple(EntityId(str(x)) for x in raw.get("created_from", ())),
    )


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    if isinstance(value, EntityId):
        return str(value)
    return value
