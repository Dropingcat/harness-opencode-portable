from __future__ import annotations

import unittest
from dataclasses import is_dataclass
from types import MappingProxyType

from researcher_core.r0.commands import ActorRef, CommandEnvelope
from researcher_core.r0.ids import EntityId
from researcher_core.r0.projections import make_snapshot, rebuild_state_from_events
from researcher_core.r0.registry import CycleRandom, InMemoryClaimRegistry, SequenceClock, make_numeric_dry_run_batch
from researcher_core.r0.serialization import canonical_json


RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
COMMAND_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CORRELATION_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
SNAPSHOT_ID = EntityId("SNP_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="projection-bubble")


class ProjectionBubbleTests(unittest.TestCase):
    def test_event_log_rebuild_matches_registry_state_snapshot(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        command = CommandEnvelope(
            command_id=COMMAND_ID,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=RUN_ID,
            actor=ACTOR,
            idempotency_key="projection-dry-run",
            expected_revisions={},
            causation_id=None,
            correlation_id=CORRELATION_ID,
            payload={"proposal_batch": make_numeric_dry_run_batch(COMMAND_ID)},
        )

        registry.execute(command)
        rebuilt = rebuild_state_from_events(registry.events)

        self.assertEqual(canonical_json(rebuilt), canonical_json(registry.state_snapshot()))

    def test_registry_events_do_not_embed_dataclass_entities(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        command = CommandEnvelope(
            command_id=COMMAND_ID,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=RUN_ID,
            actor=ACTOR,
            idempotency_key="projection-stable-event-records",
            expected_revisions={},
            causation_id=None,
            correlation_id=CORRELATION_ID,
            payload={"proposal_batch": make_numeric_dry_run_batch(COMMAND_ID)},
        )

        registry.execute(command)

        for event in registry.events:
            self.assertIn("entity_type", event.payload)
            self.assertIn("entity_record", event.payload)
            self.assertNotIn("entity", event.payload)
            self.assertFalse(_contains_dataclass_instance(event.payload))

    def test_snapshot_records_event_offset_and_revisions(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        command = CommandEnvelope(
            command_id=COMMAND_ID,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=RUN_ID,
            actor=ACTOR,
            idempotency_key="snapshot-dry-run",
            expected_revisions={},
            causation_id=None,
            correlation_id=CORRELATION_ID,
            payload={"proposal_batch": make_numeric_dry_run_batch(COMMAND_ID)},
        )

        registry.execute(command)
        snapshot = make_snapshot(SNAPSHOT_ID, registry.events, registry.state)

        self.assertEqual(snapshot.event_offset, len(registry.events))
        self.assertEqual(set(snapshot.entity_revisions.keys()), set(registry.state.keys()))
        self.assertEqual(registry.snapshots[-1].event_offset, len(registry.events))

def _contains_dataclass_instance(value: object) -> bool:
    if is_dataclass(value) and not isinstance(value, type):
        return True
    if isinstance(value, MappingProxyType | dict):
        return any(_contains_dataclass_instance(key) or _contains_dataclass_instance(nested) for key, nested in value.items())
    if isinstance(value, tuple | list):
        return any(_contains_dataclass_instance(nested) for nested in value)
    return False


if __name__ == "__main__":
    unittest.main()
