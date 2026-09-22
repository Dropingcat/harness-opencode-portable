from __future__ import annotations

import unittest

from researcher_core.artifact import check_artifact_text
from researcher_core.offline_pipeline import OfflineResearchPipeline
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EvidenceSpan, Source
from researcher_core.r0.ids import EntityId


RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OPR_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
TXN_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="offline-pipeline-bubble")


class OfflinePipelineBubbleTests(unittest.TestCase):
    def test_document_to_artifact_flow_contains_core_sections(self) -> None:
        pipeline = OfflineResearchPipeline()

        result = pipeline.run_document(
            run_id=RUN_ID,
            operation_id=OPR_ID,
            correlation_id=TXN_ID,
            actor=ACTOR,
            title="R0 pipeline fixture",
            text="The measured indicator increased by 12%.",
            locator="fixture://pipeline-doc",
        )

        self.assertEqual(check_artifact_text(result.artifact_yaml), [])
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(len(result.evidence_spans), 1)
        self.assertIsInstance(pipeline.registry.state[result.sources[0].meta.id], Source)
        self.assertIsInstance(pipeline.registry.state[result.evidence_spans[0].meta.id], EvidenceSpan)
        self.assertEqual(result.artifact["service_summary"]["claim_count"], 1)
        self.assertEqual(result.artifact["service_summary"]["quantity_count"], 1)
        self.assertIn("source_registry:", result.artifact_yaml)
        self.assertIn("evidence_spans:", result.artifact_yaml)

    def test_artifact_source_evidence_records_are_hash_tagged_and_registry_admitted(self) -> None:
        pipeline = OfflineResearchPipeline()

        result = pipeline.run_document(
            run_id=RUN_ID,
            operation_id=OPR_ID,
            correlation_id=TXN_ID,
            actor=ACTOR,
            title="R0 pipeline fixture",
            text="The measured indicator increased by 12%.",
            locator="fixture://pipeline-doc",
        )

        source = result.sources[0]
        evidence = result.evidence_spans[0]
        source_key = str(source.meta.id)
        evidence_key = str(evidence.meta.id)
        artifact_sources = result.artifact["source_registry"]
        artifact_evidence = result.artifact["evidence_spans"]

        self.assertIn(source_key, artifact_sources)
        self.assertIn(evidence_key, artifact_evidence)
        self.assertEqual(artifact_evidence[evidence_key]["source_id"], source_key)
        self.assertTrue(source.content_hash.startswith("sha256:"))
        self.assertTrue(evidence.text_hash.startswith("sha256:"))
        self.assertTrue(artifact_sources[source_key]["content_hash"].startswith("sha256:"))
        self.assertTrue(artifact_evidence[evidence_key]["text_hash"].startswith("sha256:"))
        self.assertIn(source.meta.id, result.command_result.accepted_ids)
        self.assertIn(evidence.meta.id, result.command_result.accepted_ids)
        self.assertIs(pipeline.registry.state[source.meta.id], source)
        self.assertIs(pipeline.registry.state[evidence.meta.id], evidence)
        self.assertIn("SOURCE_ADMITTED", [event.event_type for event in pipeline.registry.events])
        self.assertIn("EVIDENCE_ADMITTED", [event.event_type for event in pipeline.registry.events])

    def test_replaying_same_document_operation_does_not_duplicate_registry_state(self) -> None:
        pipeline = OfflineResearchPipeline()
        kwargs = dict(
            run_id=RUN_ID,
            operation_id=OPR_ID,
            correlation_id=TXN_ID,
            actor=ACTOR,
            title="R0 pipeline fixture",
            text="The measured indicator increased by 12%.",
            locator="fixture://pipeline-doc",
        )

        first = pipeline.run_document(**kwargs)
        second = pipeline.run_document(**kwargs)

        self.assertFalse(first.command_result.replayed)
        self.assertTrue(second.command_result.replayed)
        self.assertEqual(len(pipeline.registry.state), 4)  # debt-scan: ignore-line -- dry-run source+evidence+claim+quantity.
        self.assertEqual(len(pipeline.registry.events), 4)  # debt-scan: ignore-line -- dry-run one event per entity.
        self.assertEqual([event.event_type for event in pipeline.registry.events].count("SOURCE_ADMITTED"), 1)
        self.assertEqual([event.event_type for event in pipeline.registry.events].count("EVIDENCE_ADMITTED"), 1)


if __name__ == "__main__":
    unittest.main()
