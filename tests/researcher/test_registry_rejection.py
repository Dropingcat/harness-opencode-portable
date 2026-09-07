from __future__ import annotations

import unittest

from researcher_core.r0.commands import ActorRef, CommandEnvelope
from researcher_core.r0.ids import EntityId
from researcher_core.r0.registry import InMemoryClaimRegistry, ProposalBatch, SequenceClock, CycleRandom
from researcher_core.r0.validation import RegistryValidationError
from researcher_core.r0.entities import ClaimProposal
from researcher_core.runtime import build_sqlite_runtime


class RegistryRejectionDurableTests(unittest.TestCase):
    def test_invalid_batch_is_persisted_as_rejection_in_memory(self) -> None:
        clock = SequenceClock()
        rnd = CycleRandom()
        registry = InMemoryClaimRegistry(clock, rnd)
        run_id = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        opr_id = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        # Empty batch → invalid (non-empty required)
        batch = ProposalBatch(claims=(), quantities=(), sources=(), evidence_spans=(), edges=())
        cmd = CommandEnvelope(
            command_id=opr_id,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=run_id,
            actor=ActorRef(actor_type="test", actor_id="rejection-test"),
            idempotency_key="rejection-1",
            expected_revisions={},
            causation_id=None,
            correlation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            payload={"proposal_batch": batch},
        )
        with self.assertRaises(RegistryValidationError):
            registry.execute(cmd)
        self.assertEqual(len(registry.rejections), 1)
        self.assertEqual(registry.rejections[0][0], opr_id)
        self.assertEqual(len(registry.state), 0)
        # REJECTION_RECORDED event durable
        self.assertTrue(any(e.event_type == "REJECTION_RECORDED" for e in registry.events))

    def test_invalid_batch_persisted_via_sqlite_uow(self) -> None:
        runtime = build_sqlite_runtime(":memory:")
        registry = runtime.command_handler
        run_id = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        opr_id = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        batch = ProposalBatch(claims=(), quantities=(), sources=(), evidence_spans=(), edges=())
        cmd = CommandEnvelope(
            command_id=opr_id,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=run_id,
            actor=ActorRef(actor_type="test", actor_id="rejection-sqlite"),
            idempotency_key="rejection-sqlite-1",
            expected_revisions={},
            causation_id=None,
            correlation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            payload={"proposal_batch": batch},
        )
        with self.assertRaises(RegistryValidationError):
            registry.execute(cmd)  # type: ignore[attr-defined]
        self.assertEqual(len(registry.rejections), 1)  # type: ignore[attr-defined]
        self.assertTrue(any(e.event_type == "REJECTION_RECORDED" for e in registry.events))  # type: ignore[attr-defined]
        # Check sqlite has rejection row + event
        conn = getattr(registry, "_sqlite_conn", None)
        if conn is not None:
            row = conn.execute("SELECT data FROM rejections WHERE id = ?", (str(opr_id),)).fetchone()
            self.assertIsNotNone(row)
            ev_row = conn.execute("SELECT data FROM events WHERE data LIKE ?", ('%REJECTION_RECORDED%',)).fetchone()
            self.assertIsNotNone(ev_row)


if __name__ == "__main__":
    unittest.main()
