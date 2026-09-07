from __future__ import annotations

import unittest
from decimal import Decimal

from researcher_core.capsules import CapsuleRequest
from researcher_core.artifact import check_artifact_text
from researcher_core.artifact_builder import build_minimal_service_artifact, render_minimal_yaml
from researcher_core.local_capsules import LocalDocumentExtractionCapsule, LocalTextClaimExtractionCapsule, observation_to_proposal_batch, observation_to_source_evidence
from researcher_core.r0.commands import ActorRef, CommandEnvelope
from researcher_core.r0.ids import EntityId
from researcher_core.r0.projections import Snapshot
from researcher_core.r0.registry import CycleRandom, InMemoryClaimRegistry, SequenceClock


RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OPR_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
TXN_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="local-capsule-bubble")


class LocalCapsuleBubbleTests(unittest.TestCase):
    def test_local_text_capsule_extracts_proposals_not_state(self) -> None:
        capsule = LocalTextClaimExtractionCapsule()
        request = CapsuleRequest(
            request_id=OPR_ID,
            run_id=RUN_ID,
            capability="text.extract_numeric_claims",
            actor=ACTOR,
            payload={"text": "The measured indicator increased by 12%."},
        )

        observation = capsule.run(request)
        batch = observation_to_proposal_batch(observation)

        self.assertEqual(batch.quantities[0].value, Decimal("12"))
        self.assertEqual(batch.quantities[0].unit, "%")
        self.assertEqual(batch.claims[0].extraction_run_id, OPR_ID)

    def test_capsule_output_can_flow_into_registry_but_registry_admits(self) -> None:
        capsule = LocalTextClaimExtractionCapsule()
        observation = capsule.run(
            CapsuleRequest(
                request_id=OPR_ID,
                run_id=RUN_ID,
                capability="text.extract_numeric_claims",
                actor=ACTOR,
                payload={"text": "The measured indicator increased by 12%."},
            )
        )
        batch = observation_to_proposal_batch(observation)
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        command = CommandEnvelope(
            command_id=OPR_ID,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=RUN_ID,
            actor=ACTOR,
            idempotency_key="local-capsule-flow",
            expected_revisions={},
            causation_id=None,
            correlation_id=TXN_ID,
            payload={"proposal_batch": batch},
        )

        result = registry.execute(command)

        self.assertFalse(result.replayed)
        self.assertEqual(len(registry.state), 2)  # debt-scan: ignore-line -- capsule fixture yields claim and quantity.

    def test_local_text_capsule_returns_empty_batch_when_no_number(self) -> None:
        capsule = LocalTextClaimExtractionCapsule()
        observation = capsule.run(
            CapsuleRequest(
                request_id=OPR_ID,
                run_id=RUN_ID,
                capability="text.extract_numeric_claims",
                actor=ACTOR,
                payload={"text": "No numeric claim here."},
            )
        )

        with self.assertRaises(ValueError):
            observation_to_proposal_batch(observation)

    def test_local_document_capsule_flows_to_artifact_source_evidence(self) -> None:
        capsule = LocalDocumentExtractionCapsule()
        observation = capsule.run(
            CapsuleRequest(
                request_id=OPR_ID,
                run_id=RUN_ID,
                capability="document.extract_source_evidence",
                actor=ACTOR,
                payload={
                    "document_id": "doc-1",
                    "title": "Fixture document",
                    "text": "The measured indicator increased by 12%.",
                    "locator": "fixture://doc-1#line=1",
                },
            )
        )

        sources, evidence_spans = observation_to_source_evidence(observation)
        state = {str(sources[0].meta.id): sources[0], str(evidence_spans[0].meta.id): evidence_spans[0]}
        artifact = build_minimal_service_artifact(registry_snapshot_stub(), state, "Local document extraction")
        rendered = render_minimal_yaml(artifact)

        self.assertEqual(check_artifact_text(rendered), [])
        self.assertEqual(evidence_spans[0].source_id, sources[0].meta.id)
        self.assertEqual(evidence_spans[0].exact_text, "The measured indicator increased by 12%.")
        self.assertEqual(evidence_spans[0].locator, "fixture://doc-1#line=1")
        self.assertTrue(sources[0].content_hash.startswith("sha256:"))
        self.assertIn("source_registry:", rendered)
        self.assertIn("evidence_spans:", rendered)


def registry_snapshot_stub() -> Snapshot:
    return Snapshot(snapshot_id=EntityId("SNP_01J7K6Y5T4D3R2A1B0C9E8F7G6"), event_offset=1, entity_revisions={}, stop_reason="local_document_test")


if __name__ == "__main__":
    unittest.main()
