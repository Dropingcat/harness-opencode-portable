from __future__ import annotations

import unittest

from researcher_core.r0.commands import ActorRef, CommandEnvelope, CommandResult
from researcher_core.r0.idempotency import IdempotencyConflict, InMemoryIdempotencyStore
from researcher_core.r0.ids import EntityId


RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
COMMAND_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CORRELATION_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")
EVENT_ID = EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="bubble")


def make_command(payload: dict[str, object] | None = None) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=COMMAND_ID,
        command_type="ADMIT_PROPOSAL_BATCH",
        run_id=RUN_ID,
        actor=ACTOR,
        idempotency_key="idem-1",
        expected_revisions={CLAIM_ID: 1},
        causation_id=None,
        correlation_id=CORRELATION_ID,
        payload=payload or {"proposal": "claim"},
    )


def make_result() -> CommandResult:
    return CommandResult(
        command_id=COMMAND_ID,
        accepted_ids=(CLAIM_ID,),
        event_ids=(EVENT_ID,),
        new_revisions={CLAIM_ID: 2},  # debt-scan: ignore-line -- bubble fixture revision after one mutation.
        replayed=False,
    )


class CommandBubbleTests(unittest.TestCase):
    def test_command_rejects_wrong_command_id_prefix(self) -> None:
        with self.assertRaises(ValueError):
            CommandEnvelope(
                command_id=EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                command_type="ADMIT_PROPOSAL_BATCH",
                run_id=RUN_ID,
                actor=ACTOR,
                idempotency_key="idem-1",
                expected_revisions={},
                causation_id=None,
                correlation_id=CORRELATION_ID,
                payload={},
            )

    def test_command_payload_is_snapshot_immutable(self) -> None:
        nested: list[str] = []
        command = make_command({"nested": nested})
        before = command.request_hash()

        nested.append("late")

        self.assertEqual(command.payload["nested"], ())
        self.assertEqual(command.request_hash(), before)

    def test_command_hash_is_deterministic(self) -> None:
        self.assertEqual(make_command().request_hash(), make_command().request_hash())

    def test_idempotency_store_replays_same_hash(self) -> None:
        store = InMemoryIdempotencyStore()
        first = store.record_or_replay(make_command(), make_result())
        second = store.record_or_replay(make_command(), make_result())

        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        self.assertEqual(second.accepted_ids, first.accepted_ids)

    def test_idempotency_store_rejects_same_key_different_hash(self) -> None:
        store = InMemoryIdempotencyStore()
        store.record_or_replay(make_command(), make_result())

        with self.assertRaises(IdempotencyConflict):
            store.record_or_replay(make_command({"proposal": "changed"}), make_result())


if __name__ == "__main__":
    unittest.main()
