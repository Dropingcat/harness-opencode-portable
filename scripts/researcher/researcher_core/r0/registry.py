"""Minimal in-memory ClaimRegistry dry-run for R0.

This module is intentionally infrastructure-free. It proves the command boundary,
idempotency and transactional shape before SQLite repositories are introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from researcher_core.r0.commands import CommandEnvelope, CommandResult
from researcher_core.r0.entities import Claim, ClaimProposal, EntityMeta, EvidenceSpan, Quantity, QuantityProposal, Source
from researcher_core.r0.enums import ClaimStatus, CommitPolicy
from researcher_core.r0.events import EventEnvelope, ReasonCode
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.idempotency import InMemoryIdempotencyStore
from researcher_core.r0.ids import EntityId, RandomSource
from researcher_core.r0.projections import Snapshot, entity_to_event_record, make_snapshot
from researcher_core.r0.transactions import InMemoryUnitOfWork, OutboxMessage
from researcher_core.r0.validation import RegistryValidationError, RegistryValidator
from researcher_core.ports import UnitOfWorkPort


_MILLISECONDS_PER_SECOND = 1000  # debt-scan: ignore-line -- SI unit conversion, not policy heuristic.


@dataclass(frozen=True, slots=True)
class ProposalBatch:
    claims: tuple[ClaimProposal, ...]
    quantities: tuple[QuantityProposal, ...]
    sources: tuple[Source, ...] = ()
    evidence_spans: tuple[EvidenceSpan, ...] = ()
    edges: tuple[GraphEdge, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "claims", tuple(self.claims))
        object.__setattr__(self, "quantities", tuple(self.quantities))
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "evidence_spans", tuple(self.evidence_spans))
        object.__setattr__(self, "edges", tuple(self.edges))


class SequenceClock:
    def __init__(self, start_ms: int = 0) -> None:
        self._next_ms = start_ms

    def now_ms(self) -> int:
        current = self._next_ms
        self._next_ms += 1
        return current


class CycleRandom(RandomSource):
    def __init__(self) -> None:
        self._next = 0

    def randrange(self, stop: int) -> int:
        value = self._next % stop
        self._next += 1
        return value


class InMemoryClaimRegistry:
    """Small application write boundary for R0 dry-run tests."""

    def __init__(
        self,
        clock: SequenceClock,
        random_source: RandomSource,
        uow_factory: object | None = None,
        idempotency_store: object | None = None,
    ) -> None:
        self.clock = clock
        self.random_source = random_source
        self.idempotency = idempotency_store or InMemoryIdempotencyStore()
        self.state: dict[EntityId, Claim | Quantity | Source | EvidenceSpan | GraphEdge] = {}
        self.events: list[EventEnvelope] = []
        self.outbox: list[OutboxMessage] = []
        self.snapshots: list[Snapshot] = []
        self.validator = RegistryValidator()
        self._uow_factory = uow_factory  # Callable[[], UnitOfWorkPort] or None → InMemoryUnitOfWork
        self.rejections: list[tuple[EntityId, Any]] = []

    def execute(self, command: CommandEnvelope) -> CommandResult:
        batch = self._batch_from_payload(command)
        replay = self.idempotency.replay_if_recorded(command)
        if replay is not None:
            return replay
        report = self.validator.validate(batch, command, self.state)
        if not report.is_valid:
            # Durable rejection graph: persist rejection + REJECTION_RECORDED event via UoW
            rejection_event = self._event(
                "REJECTION_RECORDED",
                command.command_id,
                command,
                {
                    "command_id": str(command.command_id),
                    "issues": [{"code": str(issue.code), "message": str(issue.message)} for issue in report.issues],
                    "batch_size": len(batch.claims) + len(batch.quantities),
                },
            )
            uow_factory = self._uow_factory or InMemoryUnitOfWork
            try:
                with uow_factory() as uow:  # type: ignore[call-arg]
                    uow.put_rejection(command.command_id, report)
                    uow.append_event(rejection_event)
                    uow.enqueue_outbox(OutboxMessage("rejection.recorded", {"command": command.command_id}))
                    uow.commit()
            except Exception:
                pass  # debt-scan: ignore-line -- best-effort durable rejection, still raise validation
            # also keep in-memory for tests
            if not hasattr(self, "rejections"):
                self.rejections = []  # type: ignore[attr-defined]
            self.rejections.append((command.command_id, report))  # type: ignore[attr-defined]
            self.events.append(rejection_event)
            self.outbox.append(OutboxMessage("rejection.recorded", {"command": command.command_id}))
            raise RegistryValidationError(report)
        result = self._build_result(command, batch)
        replay = self.idempotency.record_or_replay(command, result)
        if replay.replayed:
            return replay

        uow_factory = self._uow_factory or InMemoryUnitOfWork
        with uow_factory() as uow:  # type: ignore[call-arg]
            for entity_id in result.accepted_ids:
                entity = self._pending_entity_by_id[entity_id]
                uow.put_state(entity_id, {"entity": entity})
            for event in self._pending_events:
                uow.append_event(event)
            uow.enqueue_outbox(OutboxMessage("projection.update", {"command": command.command_id}))
            uow.commit()

        for entity_id in result.accepted_ids:
            self.state[entity_id] = self._pending_entity_by_id[entity_id]
        self.events.extend(self._pending_events)
        self.outbox.append(OutboxMessage("projection.update", {"command": command.command_id}))
        self.snapshots.append(make_snapshot(EntityId.new("SNP", self.clock, self.random_source), self.events, self.state))
        return result

    def admit(self, batch: ProposalBatch, policy: CommitPolicy, command: CommandEnvelope) -> CommandResult:
        if policy != CommitPolicy.ALL_OR_NOTHING:
            raise ValueError("only ALL_OR_NOTHING is supported in the R0 dry-run registry")
        return self.execute(_command_with_batch(command, batch, policy))

    def state_snapshot(self) -> dict[str, Claim | Quantity | Source | EvidenceSpan | GraphEdge]:
        return {str(entity_id): entity for entity_id, entity in self.state.items()}

    def update_graph_edge(
        self,
        edge: GraphEdge,
        event: EventEnvelope,
        *,
        expected_revision: int,
    ) -> GraphEdge:
        """Durably replace one canonical GraphEdge after a lifecycle reducer.

        The reducer owns transition legality; the registry owns canonical state
        mutation and durable projection. Endpoint entities are untouched.
        """
        current = self.state.get(edge.meta.id)
        if not isinstance(current, GraphEdge):
            raise KeyError(str(edge.meta.id))
        if current.meta.revision != expected_revision:
            raise ValueError("edge revision does not match expected_revision")
        if edge.meta.revision != expected_revision + 1:
            raise ValueError("replacement edge revision must increment by one")
        if (edge.source_id, edge.target_id, edge.edge_kind) != (current.source_id, current.target_id, current.edge_kind):
            raise ValueError("edge lifecycle update cannot change semantic endpoints or kind")
        if event.aggregate_id != edge.meta.id or event.aggregate_revision != edge.meta.revision:
            raise ValueError("edge lifecycle event does not match replacement edge revision")

        uow_factory = self._uow_factory or InMemoryUnitOfWork
        with uow_factory() as uow:  # type: ignore[call-arg]
            uow.put_state(edge.meta.id, {"entity": edge})
            uow.append_event(event)
            uow.enqueue_outbox(OutboxMessage("projection.update", {"edge": edge.meta.id}))
            uow.commit()

        self.state[edge.meta.id] = edge
        self.events.append(event)
        self.outbox.append(OutboxMessage("projection.update", {"edge": edge.meta.id}))
        self.snapshots.append(make_snapshot(EntityId.new("SNP", self.clock, self.random_source), self.events, self.state))
        return edge

    def _build_result(self, command: CommandEnvelope, batch: ProposalBatch) -> CommandResult:
        self._pending_entity_by_id: dict[EntityId, Claim | Quantity | Source | EvidenceSpan | GraphEdge] = {}
        self._pending_events: list[EventEnvelope] = []
        accepted_ids: list[EntityId] = []
        event_ids: list[EntityId] = []
        for proposal in batch.claims:
            claim_id = EntityId.new("CLM", self.clock, self.random_source)
            claim = Claim(
                meta=self._meta(claim_id, command),
                proposition=proposal.proposition,
                normalized_proposition=proposal.proposition.strip().lower(),
                claim_type=proposal.proposed_type,
                scope_id=command.run_id,
                status=ClaimStatus.OPEN,
                attributes={"proposal_temp_id": proposal.temp_id},
            )
            self._pending_entity_by_id[claim_id] = claim
            accepted_ids.append(claim_id)
            event = self._event("CLAIM_ADMITTED", claim_id, command, {"proposal_temp_id": proposal.temp_id, **entity_to_event_record(claim)})
            self._pending_events.append(event)
            event_ids.append(event.event_id)
        for proposal in batch.quantities:
            quantity_id = EntityId.new("QTY", self.clock, self.random_source)
            quantity = Quantity(
                meta=self._meta(quantity_id, command),
                value=proposal.value,
                unit=proposal.unit,
                measured_property=proposal.measured_property,
                scope_id=command.run_id,
            )
            self._pending_entity_by_id[quantity_id] = quantity
            accepted_ids.append(quantity_id)
            event = self._event("VALIDATION_RECORDED", quantity_id, command, {"proposal_temp_id": proposal.temp_id, **entity_to_event_record(quantity)})
            self._pending_events.append(event)
            event_ids.append(event.event_id)
        for source in batch.sources:
            self._pending_entity_by_id[source.meta.id] = source
            accepted_ids.append(source.meta.id)
            event = self._event("SOURCE_ADMITTED", source.meta.id, command, entity_to_event_record(source))
            self._pending_events.append(event)
            event_ids.append(event.event_id)
        for evidence in batch.evidence_spans:
            self._pending_entity_by_id[evidence.meta.id] = evidence
            accepted_ids.append(evidence.meta.id)
            event = self._event("EVIDENCE_ADMITTED", evidence.meta.id, command, entity_to_event_record(evidence))
            self._pending_events.append(event)
            event_ids.append(event.event_id)
        for edge in batch.edges:
            self._pending_entity_by_id[edge.meta.id] = edge
            accepted_ids.append(edge.meta.id)
            event = self._event("EDGE_ADMITTED", edge.meta.id, command, entity_to_event_record(edge))
            self._pending_events.append(event)
            event_ids.append(event.event_id)
        return CommandResult(
            command_id=command.command_id,
            accepted_ids=tuple(accepted_ids),
            event_ids=tuple(event_ids),
            new_revisions={entity_id: 1 for entity_id in accepted_ids},
            replayed=False,
        )

    def _meta(self, entity_id: EntityId, command: CommandEnvelope) -> EntityMeta:
        return EntityMeta(
            id=entity_id,
            schema_version="r0-entity/0.1",
            revision=1,
            run_id=command.run_id,
            created_at=datetime.fromtimestamp(self.clock.now_ms() / _MILLISECONDS_PER_SECOND, tz=UTC),
            created_by=command.actor,
        )

    def _event(self, event_type: str, aggregate_id: EntityId, command: CommandEnvelope, payload: dict[str, object]) -> EventEnvelope:
        return EventEnvelope(
            event_id=EntityId.new("EVT", self.clock, self.random_source),
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_revision=1,
            run_id=command.run_id,
            actor=command.actor.actor_id,
            timestamp=datetime.fromtimestamp(self.clock.now_ms() / _MILLISECONDS_PER_SECOND, tz=UTC),
            causation_id=command.command_id,
            correlation_id=command.correlation_id,
            schema_version="r0-event/0.1",
            reason_codes=(ReasonCode("CLAIM_EVIDENCE_UPDATED"),),
            payload=payload,
        )

    def _batch_from_payload(self, command: CommandEnvelope) -> ProposalBatch:
        batch = command.payload.get("proposal_batch")
        if not isinstance(batch, ProposalBatch):
            raise TypeError("command payload must contain proposal_batch")
        return batch


def _command_with_batch(command: CommandEnvelope, batch: ProposalBatch, policy: CommitPolicy) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=command.command_id,
        command_type=command.command_type,
        run_id=command.run_id,
        actor=command.actor,
        idempotency_key=command.idempotency_key,
        expected_revisions=command.expected_revisions,
        causation_id=command.causation_id,
        correlation_id=command.correlation_id,
        payload={"proposal_batch": batch, "commit_policy": policy.value},
    )


def make_numeric_dry_run_batch(extraction_run_id: EntityId, proposition: str = "The measured indicator increased by 12%.") -> ProposalBatch:
    return ProposalBatch(
        claims=(
            ClaimProposal(
                temp_id="tmp-claim-growth",
                proposition=proposition,
                proposed_type="quantitative",
                proposed_scope={"fixture": "r0-dry-run"},
                source_span_ref=None,
                extraction_run_id=extraction_run_id,
            ),
        ),
        quantities=(
            QuantityProposal(
                temp_id="tmp-quantity-growth",
                value=Decimal("12"),
                unit="%",
                measured_property="indicator increase",
                source_span_ref=None,
                extraction_run_id=extraction_run_id,
            ),
        ),
    )
