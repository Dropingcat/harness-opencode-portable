"""R0 event-log projection helpers."""

from __future__ import annotations

from dataclasses import dataclass

from types import MappingProxyType
from typing import Any, Mapping, Sequence

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import Claim, EvidenceSpan, Quantity, Source
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import ClaimStatus, EdgeKind
from researcher_core.r0.events import EventEnvelope
from researcher_core.r0.graph import GraphEdge, GraphEdgeState
from researcher_core.r0.ids import EntityId


ProjectableEntity = Claim | Quantity | Source | EvidenceSpan | GraphEdge
EventRecord = dict[str, Any]


def entity_to_event_record(entity: ProjectableEntity) -> EventRecord:
    """Return a stable, dataclass-free event payload record for an admitted entity."""

    meta = _meta_to_record(entity.meta)
    if isinstance(entity, Claim):
        return {
            "entity_type": "Claim",
            "entity_record": {
                "meta": meta,
                "proposition": entity.proposition,
                "normalized_proposition": entity.normalized_proposition,
                "claim_type": entity.claim_type,
                "scope_id": str(entity.scope_id),
                "status": entity.status.value,
                "attributes": _plain_value(entity.attributes),
            },
        }
    if isinstance(entity, Quantity):
        return {
            "entity_type": "Quantity",
            "entity_record": {
                "meta": meta,
                "value": entity.value,
                "unit": entity.unit,
                "measured_property": entity.measured_property,
                "scope_id": str(entity.scope_id) if entity.scope_id is not None else None,
            },
        }
    if isinstance(entity, Source):
        return {
            "entity_type": "Source",
            "entity_record": {
                "meta": meta,
                "source_type": entity.source_type,
                "title": entity.title,
                "locator": entity.locator,
                "content_hash": entity.content_hash,
            },
        }
    if isinstance(entity, EvidenceSpan):
        return {
            "entity_type": "EvidenceSpan",
            "entity_record": {
                "meta": meta,
                "source_id": str(entity.source_id),
                "exact_text": entity.exact_text,
                "locator": entity.locator,
                "text_hash": entity.text_hash,
            },
        }
    if isinstance(entity, GraphEdge):
        return {
            "entity_type": "GraphEdge",
            "entity_record": {
                "meta": meta,
                "source_id": str(entity.source_id),
                "target_id": str(entity.target_id),
                "edge_kind": entity.edge_kind.value,
                "attributes": _plain_value(entity.attributes),
                "state": entity.state.value,
            },
        }
    raise TypeError(f"unsupported projectable entity: {type(entity).__name__}")


def entity_from_event_record(record: Mapping[str, Any]) -> ProjectableEntity:
    """Rebuild an entity from a stable event payload record."""

    entity_type = record.get("entity_type")
    entity_record = record.get("entity_record")
    if not isinstance(entity_type, str) or not isinstance(entity_record, Mapping):
        raise ValueError("event record must contain entity_type and entity_record")

    meta = _meta_from_record(entity_record["meta"])
    if entity_type == "Claim":
        return Claim(
            meta=meta,
            proposition=entity_record["proposition"],
            normalized_proposition=entity_record["normalized_proposition"],
            claim_type=entity_record["claim_type"],
            scope_id=EntityId(entity_record["scope_id"]),
            status=ClaimStatus(entity_record["status"]),
            attributes=entity_record["attributes"],
        )
    if entity_type == "Quantity":
        return Quantity(
            meta=meta,
            value=entity_record["value"],
            unit=entity_record["unit"],
            measured_property=entity_record["measured_property"],
            scope_id=EntityId(entity_record["scope_id"]) if entity_record["scope_id"] is not None else None,
        )
    if entity_type == "Source":
        return Source(
            meta=meta,
            source_type=entity_record["source_type"],
            title=entity_record["title"],
            locator=entity_record["locator"],
            content_hash=entity_record["content_hash"],
        )
    if entity_type == "EvidenceSpan":
        return EvidenceSpan(
            meta=meta,
            source_id=EntityId(entity_record["source_id"]),
            exact_text=entity_record["exact_text"],
            locator=entity_record["locator"],
            text_hash=entity_record["text_hash"],
        )
    if entity_type == "GraphEdge":
        return GraphEdge(
            meta=meta,
            source_id=EntityId(entity_record["source_id"]),
            target_id=EntityId(entity_record["target_id"]),
            edge_kind=EdgeKind(entity_record["edge_kind"]),
            attributes=entity_record["attributes"],
            state=GraphEdgeState(entity_record.get("state", GraphEdgeState.ACTIVE.value)),
        )
    raise ValueError(f"unsupported event entity_type: {entity_type!r}")


@dataclass(frozen=True, slots=True)
class Snapshot:
    snapshot_id: EntityId
    event_offset: int
    entity_revisions: Mapping[EntityId, int]
    stop_reason: str

    def __post_init__(self) -> None:
        if self.snapshot_id.namespace != "SNP":
            raise ValueError("snapshot_id must use SNP prefix")
        if self.event_offset < 0:
            raise ValueError("event_offset must be non-negative")
        object.__setattr__(self, "entity_revisions", MappingProxyType(dict(self.entity_revisions)))


def rebuild_state_from_events(events: Sequence[EventEnvelope]) -> dict[str, ProjectableEntity]:
    state: dict[str, ProjectableEntity] = {}
    for event in events:
        if "entity_type" in event.payload and "entity_record" in event.payload:
            entity = entity_from_event_record(event.payload)
            state[str(entity.meta.id)] = entity
    return state


def _meta_to_record(meta: EntityMeta) -> EventRecord:
    return {
        "id": str(meta.id),
        "schema_version": meta.schema_version,
        "revision": meta.revision,
        "run_id": str(meta.run_id),
        "created_at": meta.created_at,
        "created_by": {
            "actor_type": meta.created_by.actor_type,
            "actor_id": meta.created_by.actor_id,
        },
    }


def _meta_from_record(record: Mapping[str, Any]) -> EntityMeta:
    created_by = record["created_by"]
    if not isinstance(created_by, Mapping):
        raise ValueError("meta.created_by must be a mapping")
    return EntityMeta(
        id=EntityId(record["id"]),
        schema_version=record["schema_version"],
        revision=record["revision"],
        run_id=EntityId(record["run_id"]),
        created_at=record["created_at"],
        created_by=ActorRef(actor_type=created_by["actor_type"], actor_id=created_by["actor_id"]),
    )


def _plain_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain_value(nested) for key, nested in value.items()}
    if isinstance(value, tuple | list):
        return tuple(_plain_value(nested) for nested in value)
    return value


def make_snapshot(snapshot_id: EntityId, events: Sequence[EventEnvelope], state: Mapping[EntityId, ProjectableEntity]) -> Snapshot:
    return Snapshot(
        snapshot_id=snapshot_id,
        event_offset=len(events),
        entity_revisions={entity_id: entity.meta.revision for entity_id, entity in state.items()},
        stop_reason="dry_run_complete",
    )
