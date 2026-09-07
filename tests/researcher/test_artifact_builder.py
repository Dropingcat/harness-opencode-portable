from __future__ import annotations

import unittest
from datetime import datetime

from researcher_core.artifact import check_artifact_text
from researcher_core.artifact_builder import build_minimal_service_artifact, render_minimal_yaml
from researcher_core.r0.commands import ActorRef, CommandEnvelope
from researcher_core.r0.entities import EntityMeta, EvidenceSpan, Source
from researcher_core.r0.enums import EdgeKind
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityId
from researcher_core.r0.registry import CycleRandom, InMemoryClaimRegistry, SequenceClock, make_numeric_dry_run_batch


RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OPR_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
TXN_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="artifact-builder-bubble")
EDGE_ID = EntityId("EDG_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OTHER_CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G7")
SOURCE_ID = EntityId("SRC_01J7K6Y5T4D3R2A1B0C9E8F7G6")
EVIDENCE_ID = EntityId("EVD_01J7K6Y5T4D3R2A1B0C9E8F7G6")


class ArtifactBuilderBubbleTests(unittest.TestCase):
    def test_registry_snapshot_renders_target_shape_without_checker_gaps(self) -> None:
        registry = InMemoryClaimRegistry(SequenceClock(), CycleRandom())
        registry.execute(
            CommandEnvelope(
                command_id=OPR_ID,
                command_type="ADMIT_PROPOSAL_BATCH",
                run_id=RUN_ID,
                actor=ACTOR,
                idempotency_key="artifact-builder-flow",
                expected_revisions={},
                causation_id=None,
                correlation_id=TXN_ID,
                payload={"proposal_batch": make_numeric_dry_run_batch(OPR_ID)},
            )
        )

        artifact = build_minimal_service_artifact(registry.snapshots[-1], registry.state_snapshot(), "R0 dry run")
        rendered = render_minimal_yaml(artifact)

        self.assertEqual(check_artifact_text(rendered), [])
        self.assertIn("claims:", rendered)
        self.assertIn("quantities:", rendered)

    def test_artifact_builder_renders_graph_edges(self) -> None:
        edge = GraphEdge(
            meta=EntityMeta(EDGE_ID, "r0-entity/0.1", 1, RUN_ID, datetime.fromisoformat("2026-08-29T00:00:00+00:00"), ACTOR),
            source_id=CLAIM_ID,
            target_id=OTHER_CLAIM_ID,
            edge_kind=EdgeKind.DERIVED_FROM,
        )
        snapshot = registry_snapshot_stub()

        rendered = render_minimal_yaml(build_minimal_service_artifact(snapshot, {str(EDGE_ID): edge}, "edge artifact"))

        self.assertEqual(check_artifact_text(rendered), [])
        self.assertIn('edge_kind: "derived_from"', rendered)

    def test_artifact_builder_renders_source_and_evidence(self) -> None:
        source = Source(meta=EntityMeta(SOURCE_ID, "r0-entity/0.1", 1, RUN_ID, datetime.fromisoformat("2026-08-29T00:00:00+00:00"), ACTOR), source_type="local_document", title="Doc", locator="fixture://doc")
        evidence = EvidenceSpan(meta=EntityMeta(EVIDENCE_ID, "r0-entity/0.1", 1, RUN_ID, datetime.fromisoformat("2026-08-29T00:00:00+00:00"), ACTOR), source_id=SOURCE_ID, exact_text="Quoted evidence", locator="line:1", text_hash="sha256:evidence")
        snapshot = registry_snapshot_stub()

        rendered = render_minimal_yaml(build_minimal_service_artifact(snapshot, {str(SOURCE_ID): source, str(EVIDENCE_ID): evidence}, "source evidence artifact"))

        self.assertEqual(check_artifact_text(rendered), [])
        self.assertIn("source_registry:", rendered)
        self.assertIn("evidence_spans:", rendered)

    def test_yaml_renderer_escapes_quote_colon_backslash_scalars(self) -> None:
        rendered = render_minimal_yaml({"title": 'Doc "alpha:beta" at C:\\fixtures\\doc.txt'})

        self.assertEqual(rendered, 'title: "Doc \\"alpha:beta\\" at C:\\\\fixtures\\\\doc.txt"')

    def test_artifact_checker_accepts_safe_escaped_source_and_evidence_text(self) -> None:
        source = Source(meta=EntityMeta(SOURCE_ID, "r0-entity/0.1", 1, RUN_ID, datetime.fromisoformat("2026-08-29T00:00:00+00:00"), ACTOR), source_type="local_document", title='Doc "alpha:beta" at C:\\fixtures\\doc.txt', locator="fixture://doc")
        evidence = EvidenceSpan(meta=EntityMeta(EVIDENCE_ID, "r0-entity/0.1", 1, RUN_ID, datetime.fromisoformat("2026-08-29T00:00:00+00:00"), ACTOR), source_id=SOURCE_ID, exact_text='Evidence says "alpha: beta" from C:\\fixtures\\doc.txt', locator="line:1", text_hash="sha256:evidence")
        snapshot = registry_snapshot_stub()

        rendered = render_minimal_yaml(build_minimal_service_artifact(snapshot, {str(SOURCE_ID): source, str(EVIDENCE_ID): evidence}, "safe scalar artifact"))

        self.assertEqual(check_artifact_text(rendered), [])
        self.assertIn('title: "Doc \\"alpha:beta\\" at C:\\\\fixtures\\\\doc.txt"', rendered)
        self.assertIn('exact_text: "Evidence says \\"alpha: beta\\" from C:\\\\fixtures\\\\doc.txt"', rendered)

    def test_yaml_renderer_escapes_newlines_inside_scalars(self) -> None:
        rendered = render_minimal_yaml({"exact_text": "first line\nsecond line"})

        self.assertEqual(rendered, 'exact_text: "first line\\nsecond line"')
        self.assertNotIn("second line\n", rendered)


def registry_snapshot_stub():
    from researcher_core.r0.projections import Snapshot

    return Snapshot(snapshot_id=EntityId("SNP_01J7K6Y5T4D3R2A1B0C9E8F7G6"), event_offset=1, entity_revisions={}, stop_reason="artifact_test")


if __name__ == "__main__":
    unittest.main()
