"""Command boundary contracts for R0 application mutations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId
from researcher_core.r0.serialization import canonical_json


@dataclass(frozen=True, slots=True)
class ActorRef:
    actor_type: str
    actor_id: str

    def __post_init__(self) -> None:
        if not self.actor_type:
            raise ValueError("actor_type is required")
        if not self.actor_id:
            raise ValueError("actor_id is required")


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    command_id: EntityId
    command_type: str
    run_id: EntityId
    actor: ActorRef
    idempotency_key: str
    expected_revisions: Mapping[EntityId, int]
    causation_id: EntityId | None
    correlation_id: EntityId
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.command_id.namespace != "OPR":
            raise ValueError("command_id must use OPR prefix")
        if not self.command_type:
            raise ValueError("command_type is required")
        if self.run_id.namespace != "RUN":
            raise ValueError("run_id must use RUN prefix")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")
        if not isinstance(self.correlation_id, EntityId):
            raise TypeError("correlation_id is required")

        normalized_revisions: dict[EntityId, int] = {}
        for entity_id, revision in self.expected_revisions.items():
            if not isinstance(entity_id, EntityId):
                raise TypeError("expected_revisions keys must be EntityId values")
            if revision < 1:
                raise ValueError("expected revision must be positive")
            normalized_revisions[entity_id] = revision

        object.__setattr__(self, "expected_revisions", MappingProxyType(normalized_revisions))
        object.__setattr__(self, "payload", _deep_freeze(self.payload))

    def request_hash(self) -> str:
        """Deterministic hash used by idempotency records."""

        body = canonical_json(
            {
                "command_type": self.command_type,
                "run_id": self.run_id,
                "actor": self.actor,
                "expected_revisions": {str(key): value for key, value in self.expected_revisions.items()},
                "causation_id": self.causation_id,
                "correlation_id": self.correlation_id,
                "payload": self.payload,
            }
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CommandResult:
    command_id: EntityId
    accepted_ids: tuple[EntityId, ...]
    event_ids: tuple[EntityId, ...]
    new_revisions: Mapping[EntityId, int]
    replayed: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "accepted_ids", tuple(self.accepted_ids))
        object.__setattr__(self, "event_ids", tuple(self.event_ids))
        object.__setattr__(self, "new_revisions", MappingProxyType(dict(self.new_revisions)))
