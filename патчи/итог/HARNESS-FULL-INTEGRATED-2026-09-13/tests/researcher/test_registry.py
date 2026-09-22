from __future__ import annotations

import unittest

from researcher_core.r0.commands import ActorRef, CommandEnvelope
from researcher_core.r0.idempotency import IdempotencyConflict
from researcher_core.r0.ids import EntityId
from datetime import datetime

from researcher_core.r0.entities import EntityMeta, EvidenceSpan, Source
from researcher_core.r0.enums import EdgeKind
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.registry import CycleRandom, InMemoryClaimRegistry, ProposalBatch, RegistryValidationError, SequenceClock, make_numeric_dry_run_batch
from researcher_core.r0.serialization import canonical_json


RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
COMMAND_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CORRELATION_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="registry-bubble")
CREATED_AT = datetime.fromisoformat("2026-08-29T00:00:00+00:00")
EDGE_ID = EntityId("EDG_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OTHER_CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G7")
SOURCE_ID = EntityId("SRC_01J7K6Y5T4D3R2A1B0C9E8F7G6")
EVIDENCE_ID = EntityId("EVD_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OTHER_RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G7")


def make_command(batch: object, idempotency_key: str = "r0-dry-run") -> CommandEnvelope:
    return CommandEnvelope(
        command_id=COMMAND_ID,
        command_type="ADMIT_PROPOSAL_BATCH",
        run_id=RUN_ID,
        actor=ACTOR,
        idempotency_key=idempotency_key,
        expected_revisions={},
        causation_id=None,
        correlation_id=CORRELATION_ID,
        payload={"proposal_batch": batch},
    )


def make_source(source_id: EntityId = SOURCE_ID, run_id: EntityId = RUN_ID, title: str = "Doc") -> Source:
    return Source(
        meta=EntityMeta(source_id, "r0-entity/0.1", 1, run_id, CREATED_AT, ACTOR),
        source_type="local_document",
        title=title,
        locator="fixture://doc",
        content_hash="sha256:source",
    )


class RegistryBubbleTests(unittest.TestCase):
    def test_dry_run_admits_claim_and_quantity_with_events(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        batch = make_numeric_dry_run_batch(COMMAND_ID)

        result = registry.execute(make_command(batch))

        self.assertFalse(result.replayed)
        self.assertEqual(len(result.accepted_ids), 2)  # debt-scan: ignore-line -- dry-run fixture has claim and quantity.
        self.assertEqual(len(result.event_ids), 2)  # debt-scan: ignore-line -- dry-run fixture emits one event per accepted entity.
        self.assertEqual(len(registry.state), 2)  # debt-scan: ignore-line -- dry-run fixture state size.
        self.assertEqual(len(registry.events), 2)  # debt-scan: ignore-line -- dry-run fixture event count.
        self.assertEqual(len(registry.outbox), 1)

    def test_replaying_same_command_adds_no_entities_or_events(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        command = make_command(make_numeric_dry_run_batch(COMMAND_ID))

        first = registry.execute(command)
        state_before = canonical_json(registry.state_snapshot())
        events_before = canonical_json(registry.events)
        second = registry.execute(command)

        self.assertTrue(second.replayed)
        self.assertEqual(second.accepted_ids, first.accepted_ids)
        self.assertEqual(canonical_json(registry.state_snapshot()), state_before)
        self.assertEqual(canonical_json(registry.events), events_before)

    def test_same_idempotency_key_with_changed_batch_is_conflict(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        first_batch = make_numeric_dry_run_batch(COMMAND_ID)
        changed_batch = make_numeric_dry_run_batch(COMMAND_ID, proposition="The measured indicator increased by 13%.")
        command = make_command(first_batch)
        registry.execute(command)

        with self.assertRaises(IdempotencyConflict):
            registry.execute(make_command(changed_batch, idempotency_key="r0-dry-run"))

    def test_command_without_batch_is_rejected(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        bad_command = make_command(batch="not-a-batch")

        with self.assertRaises(TypeError):
            registry.execute(bad_command)

    def test_edges_are_admitted_with_edge_event(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        source = Source(
            meta=EntityMeta(SOURCE_ID, "r0-entity/0.1", 1, RUN_ID, CREATED_AT, ACTOR),
            source_type="local_document",
            title="Doc",
            locator="fixture://doc",
            content_hash="sha256:source",
        )
        evidence = EvidenceSpan(
            meta=EntityMeta(EVIDENCE_ID, "r0-entity/0.1", 1, RUN_ID, CREATED_AT, ACTOR),
            source_id=SOURCE_ID,
            exact_text="The measured indicator increased by 12%.",
            locator="fixture://doc#line=1",
            text_hash="sha256:evidence",
        )
        edge = GraphEdge(
            meta=EntityMeta(
                id=EDGE_ID,
                schema_version="r0-entity/0.1",
                revision=1,
                run_id=RUN_ID,
                created_at=CREATED_AT,
                created_by=ACTOR,
            ),
            source_id=SOURCE_ID,
            target_id=EVIDENCE_ID,
            edge_kind=EdgeKind.DEPENDS_ON,
        )
        edge_batch = ProposalBatch(claims=(), quantities=(), sources=(source,), evidence_spans=(evidence,), edges=(edge,))

        result = registry.execute(make_command(edge_batch))

        self.assertIn(EDGE_ID, result.accepted_ids)
        self.assertEqual(registry.events[-1].event_type, "EDGE_ADMITTED")

    def test_sources_and_evidence_are_admitted_with_events(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        source = Source(
            meta=EntityMeta(SOURCE_ID, "r0-entity/0.1", 1, RUN_ID, CREATED_AT, ACTOR),
            source_type="local_document",
            title="Doc",
            locator="fixture://doc",
            content_hash="sha256:source",
        )
        evidence = EvidenceSpan(
            meta=EntityMeta(EVIDENCE_ID, "r0-entity/0.1", 1, RUN_ID, CREATED_AT, ACTOR),
            source_id=SOURCE_ID,
            exact_text="The measured indicator increased by 12%.",
            locator="fixture://doc#line=1",
            text_hash="sha256:evidence",
        )
        batch = ProposalBatch(claims=(), quantities=(), sources=(source,), evidence_spans=(evidence,))

        result = registry.execute(make_command(batch))

        self.assertEqual(result.accepted_ids, (SOURCE_ID, EVIDENCE_ID))
        self.assertEqual([event.event_type for event in registry.events], ["SOURCE_ADMITTED", "EVIDENCE_ADMITTED"])
        self.assertIn(str(SOURCE_ID), registry.state_snapshot())
        self.assertIn(str(EVIDENCE_ID), registry.state_snapshot())

    def test_dangling_evidence_source_is_rejected_without_side_effects(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        evidence = EvidenceSpan(
            meta=EntityMeta(EVIDENCE_ID, "r0-entity/0.1", 1, RUN_ID, CREATED_AT, ACTOR),
            source_id=SOURCE_ID,
            exact_text="Evidence",
            locator="line:1",
            text_hash="sha256:evidence",
        )

        with self.assertRaises(RegistryValidationError):
            registry.execute(make_command(ProposalBatch(claims=(), quantities=(), evidence_spans=(evidence,))))

        self.assertEqual(registry.state, {})
        self.assertEqual([e.event_type for e in registry.events], ["REJECTION_RECORDED"])
        self.assertEqual([m.message_type for m in registry.outbox], ["rejection.recorded"])
        self.assertEqual(len(registry.rejections), 1)

    def test_dangling_edge_endpoint_is_rejected_without_side_effects(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        edge = GraphEdge(
            meta=EntityMeta(EDGE_ID, "r0-entity/0.1", 1, RUN_ID, CREATED_AT, ACTOR),
            source_id=CLAIM_ID,
            target_id=OTHER_CLAIM_ID,
            edge_kind=EdgeKind.DEPENDS_ON,
        )

        with self.assertRaises(RegistryValidationError):
            registry.execute(make_command(ProposalBatch(claims=(), quantities=(), edges=(edge,))))

        self.assertEqual(registry.state, {})
        self.assertEqual([e.event_type for e in registry.events], ["REJECTION_RECORDED"])
        self.assertEqual([m.message_type for m in registry.outbox], ["rejection.recorded"])
        self.assertEqual(len(registry.rejections), 1)

    def test_duplicate_prebuilt_ids_in_batch_are_rejected(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        first_source = make_source(title="Doc A")
        second_source = make_source(title="Doc B")
        batch = ProposalBatch(claims=(), quantities=(), sources=(first_source, second_source))

        with self.assertRaises(RegistryValidationError) as raised:
            registry.execute(make_command(batch))

        self.assertIn("R0V_DUPLICATE_BATCH_ENTITY_ID", raised.exception.report.issue_codes)
        self.assertEqual(registry.state, {})
        self.assertEqual([e.event_type for e in registry.events], ["REJECTION_RECORDED"])
        self.assertEqual([m.message_type for m in registry.outbox], ["rejection.recorded"])
        self.assertEqual(len(registry.rejections), 1)

    def test_existing_prebuilt_id_is_rejected(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        source = make_source()
        registry.state[SOURCE_ID] = source
        batch = ProposalBatch(claims=(), quantities=(), sources=(make_source(),))

        with self.assertRaises(RegistryValidationError) as raised:
            registry.execute(make_command(batch))

        self.assertIn("R0V_DUPLICATE_EXISTING_ENTITY_ID", raised.exception.report.issue_codes)
        self.assertEqual(registry.state, {SOURCE_ID: source})
        self.assertEqual([e.event_type for e in registry.events], ["REJECTION_RECORDED"])
        self.assertEqual([m.message_type for m in registry.outbox], ["rejection.recorded"])
        self.assertEqual(len(registry.rejections), 1)

    def test_prebuilt_run_id_mismatch_is_rejected(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        batch = ProposalBatch(claims=(), quantities=(), sources=(make_source(run_id=OTHER_RUN_ID),))

        with self.assertRaises(RegistryValidationError) as raised:
            registry.execute(make_command(batch))

        self.assertIn("R0V_RUN_ID_MISMATCH", raised.exception.report.issue_codes)
        self.assertEqual(registry.state, {})
        self.assertEqual([e.event_type for e in registry.events], ["REJECTION_RECORDED"])
        self.assertEqual([m.message_type for m in registry.outbox], ["rejection.recorded"])
        self.assertEqual(len(registry.rejections), 1)

    def test_wrong_object_type_inside_batch_is_rejected(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        batch = ProposalBatch(claims=("not-a-claim-proposal",), quantities=())

        with self.assertRaises(RegistryValidationError) as raised:
            registry.execute(make_command(batch))

        self.assertIn("R0V_BATCH_MEMBER_TYPE", raised.exception.report.issue_codes)
        self.assertEqual(registry.state, {})
        self.assertEqual([e.event_type for e in registry.events], ["REJECTION_RECORDED"])
        self.assertEqual([m.message_type for m in registry.outbox], ["rejection.recorded"])
        self.assertEqual(len(registry.rejections), 1)

    def test_validation_report_has_issue_codes_and_invalid_execute_has_no_side_effects(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        empty_batch = ProposalBatch(claims=(), quantities=())

        with self.assertRaises(RegistryValidationError) as raised:
            registry.execute(make_command(empty_batch))

        report = raised.exception.report
        self.assertFalse(report.is_valid)
        self.assertEqual(report.issue_codes, ("R0V_BATCH_EMPTY",))
        self.assertIn("R0V_BATCH_EMPTY", str(raised.exception))
        self.assertEqual(registry.state, {})
        self.assertEqual([e.event_type for e in registry.events], ["REJECTION_RECORDED"])
        self.assertEqual([m.message_type for m in registry.outbox], ["rejection.recorded"])
        self.assertEqual(len(registry.rejections), 1)

        result = registry.execute(make_command(make_numeric_dry_run_batch(COMMAND_ID)))

        self.assertFalse(result.replayed)


if __name__ == "__main__":
    unittest.main()
