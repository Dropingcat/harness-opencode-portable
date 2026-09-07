from __future__ import annotations

import unittest

from researcher_core.artifact import check_artifact_text
from researcher_core.ports import ArtifactBuilderPort, CapabilityRegistryPort, ClockPort, CommandHandlerPort, IdFactoryPort, UnitOfWorkPort
from researcher_core.runtime import build_in_memory_runtime
from researcher_core.r0.commands import ActorRef, CommandEnvelope
from researcher_core.r0.ids import EntityId
from researcher_core.r0.registry import SequenceClock, make_numeric_dry_run_batch
from researcher_core.r0.transactions import InMemoryUnitOfWork


RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OPR_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
TXN_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="ports-bubble")


class PortsRuntimeBubbleTests(unittest.TestCase):
    def test_current_in_memory_components_satisfy_ports(self) -> None:
        runtime = build_in_memory_runtime()

        self.assertIsInstance(SequenceClock(), ClockPort)
        self.assertIsInstance(runtime.id_factory, IdFactoryPort)
        self.assertIsInstance(runtime.command_handler, CommandHandlerPort)
        self.assertIsInstance(runtime.capability_registry, CapabilityRegistryPort)
        self.assertIsInstance(runtime.artifact_builder, ArtifactBuilderPort)
        self.assertIsInstance(InMemoryUnitOfWork(), UnitOfWorkPort)

    def test_runtime_ports_can_execute_and_render_artifact(self) -> None:
        runtime = build_in_memory_runtime()
        command = CommandEnvelope(
            command_id=OPR_ID,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=RUN_ID,
            actor=ACTOR,
            idempotency_key="ports-runtime-flow",
            expected_revisions={},
            causation_id=None,
            correlation_id=TXN_ID,
            payload={"proposal_batch": make_numeric_dry_run_batch(OPR_ID)},
        )

        result = runtime.command_handler.execute(command)
        registry = runtime.command_handler
        snapshot = registry.snapshots[-1]
        artifact = runtime.artifact_builder.build(snapshot, registry.state_snapshot(), "Ports runtime")
        rendered = runtime.artifact_builder.render(artifact)

        self.assertFalse(result.replayed)
        self.assertEqual(check_artifact_text(rendered), [])


if __name__ == "__main__":
    unittest.main()
