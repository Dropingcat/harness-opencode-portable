from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Tuple

from .enums import EvidenceKind, ReasonCode
from .ids import ActorId, EvidenceId, require_id


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Reason:
    code: ReasonCode
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.code, ReasonCode):
            raise TypeError("code must be a ReasonCode")


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: EvidenceId
    kind: EvidenceKind
    uri: str
    digest: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", EvidenceId(require_id(str(self.evidence_id), field_name="evidence_id")))
        object.__setattr__(self, "uri", require_id(self.uri, field_name="uri"))


@dataclass(frozen=True)
class AuditMetadata:
    actor_id: ActorId
    recorded_at: str = field(default_factory=utc_now_iso)
    tags: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_id", ActorId(require_id(str(self.actor_id), field_name="actor_id")))
