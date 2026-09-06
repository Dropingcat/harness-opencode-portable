from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import Iterable, Iterator

from audit_graph.domain.entities import Claim
from audit_graph.domain.enums import ClaimStatus, EventType, EvidenceKind, ReasonCode
from audit_graph.domain.events import ClaimRegistered, ClaimStatusChanged, DomainEvent, EvidenceAttached
from audit_graph.domain.ids import ActorId, ClaimId, EventId, EvidenceId, TaskId
from audit_graph.domain.value_objects import AuditMetadata, EvidenceRef, Reason
from audit_graph.ports.repositories import ClaimRepository, EventRepository


def _claim_to_record(claim: Claim) -> tuple[str, str, str, str, str, str]:
    reasons_json = json.dumps([{"code": item.code.value, "detail": item.detail} for item in claim.reasons], sort_keys=True)
    evidence_json = json.dumps(
        [
            {
                "evidence_id": str(item.evidence_id),
                "kind": item.kind.value,
                "uri": item.uri,
                "digest": item.digest,
                "metadata": dict(item.metadata),
            }
            for item in claim.evidence
        ],
        sort_keys=True,
    )
    return (str(claim.claim_id), str(claim.task_id), claim.text, claim.status.value, reasons_json, evidence_json)


def _claim_from_row(row: sqlite3.Row) -> Claim:
    reasons = tuple(Reason(code=ReasonCode(item["code"]), detail=item.get("detail", "")) for item in json.loads(row["reasons_json"]))
    evidence = tuple(
        EvidenceRef(
            evidence_id=EvidenceId(item["evidence_id"]),
            kind=EvidenceKind(item["kind"]),
            uri=item["uri"],
            digest=item.get("digest", ""),
            metadata=item.get("metadata", {}),
        )
        for item in json.loads(row["evidence_json"])
    )
    return Claim(
        claim_id=ClaimId(row["claim_id"]),
        task_id=TaskId(row["task_id"]),
        text=row["text"],
        status=ClaimStatus(row["status"]),
        reasons=reasons,
        evidence=evidence,
    )


class SqliteClaimRepository(ClaimRepository):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def get(self, claim_id: ClaimId) -> Claim:
        row = self._connection.execute(
            "SELECT claim_id, task_id, text, status, reasons_json, evidence_json FROM claims WHERE claim_id = ?",
            (str(claim_id),),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown claim_id: {claim_id}")
        return _claim_from_row(row)

    def upsert(self, claim: Claim) -> None:
        self._connection.execute(
            """
            INSERT INTO claims (claim_id, task_id, text, status, reasons_json, evidence_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(claim_id) DO UPDATE SET
                task_id = excluded.task_id,
                text = excluded.text,
                status = excluded.status,
                reasons_json = excluded.reasons_json,
                evidence_json = excluded.evidence_json
            """,
            _claim_to_record(claim),
        )

    def list_by_task(self, task_id: TaskId | str) -> Iterable[Claim]:
        rows = self._connection.execute(
            "SELECT claim_id, task_id, text, status, reasons_json, evidence_json FROM claims WHERE task_id = ? ORDER BY claim_id",
            (str(task_id),),
        ).fetchall()
        return [_claim_from_row(row) for row in rows]


class SqliteEventRepository(EventRepository):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def append(self, event: DomainEvent) -> None:
        payload = json.dumps(asdict(event), sort_keys=True)
        self._connection.execute(
            "INSERT INTO events (event_id, claim_id, event_type, occurred_at, payload_json) VALUES (?, ?, ?, ?, ?)",
            (str(event.event_id), str(event.claim_id), event.event_type.value, event.occurred_at, payload),
        )

    def list_for_claim(self, claim_id: ClaimId) -> Iterable[DomainEvent]:
        rows = self._connection.execute(
            "SELECT event_id, claim_id, event_type, occurred_at, payload_json FROM events WHERE claim_id = ? ORDER BY occurred_at, event_id",
            (str(claim_id),),
        ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def _event_from_row(self, row: sqlite3.Row) -> DomainEvent:
        payload = json.loads(row["payload_json"])
        event_type = EventType(row["event_type"])
        metadata = AuditMetadata(
            actor_id=ActorId(payload.get("metadata", {}).get("actor_id", "system")),
            recorded_at=payload.get("metadata", {}).get("recorded_at", row["occurred_at"]),
            tags=tuple(payload.get("metadata", {}).get("tags", ())),
        )
        if event_type is EventType.CLAIM_REGISTERED:
            claim_payload = payload["claim"]
            claim = Claim(
                claim_id=ClaimId(claim_payload["claim_id"]),
                task_id=TaskId(claim_payload["task_id"]),
                text=claim_payload["text"],
                status=ClaimStatus(claim_payload["status"]),
                reasons=tuple(
                    Reason(code=ReasonCode(item["code"]), detail=item.get("detail", ""))
                    for item in claim_payload.get("reasons", ())
                ),
                evidence=tuple(),
            )
            return ClaimRegistered(
                event_id=EventId(row["event_id"]),
                event_type=event_type,
                claim_id=ClaimId(row["claim_id"]),
                occurred_at=row["occurred_at"],
                claim=claim,
                metadata=metadata,
            )
        if event_type is EventType.EVIDENCE_ATTACHED:
            evidence_payload = payload["evidence"]
            return EvidenceAttached(
                event_id=EventId(row["event_id"]),
                event_type=event_type,
                claim_id=ClaimId(row["claim_id"]),
                occurred_at=row["occurred_at"],
                evidence=EvidenceRef(
                    evidence_id=EvidenceId(evidence_payload["evidence_id"]),
                    kind=EvidenceKind(evidence_payload["kind"]),
                    uri=evidence_payload["uri"],
                    digest=evidence_payload.get("digest", ""),
                    metadata=evidence_payload.get("metadata", {}),
                ),
                reason=Reason(**payload["reason"]),
                metadata=metadata,
            )
        return ClaimStatusChanged(
            event_id=EventId(row["event_id"]),
            event_type=event_type,
            claim_id=ClaimId(row["claim_id"]),
            occurred_at=row["occurred_at"],
            from_status=ClaimStatus(payload["from_status"]),
            to_status=ClaimStatus(payload["to_status"]),
            reason=Reason(code=ReasonCode(payload["reason"]["code"]), detail=payload["reason"].get("detail", "")),
            metadata=metadata,
        )


class SqliteTransaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def __enter__(self) -> "SqliteTransaction":
        self._connection.execute("BEGIN")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool | None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return None

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()
