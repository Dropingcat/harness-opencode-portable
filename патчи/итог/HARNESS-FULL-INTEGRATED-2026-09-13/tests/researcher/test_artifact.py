from __future__ import annotations

import unittest

from researcher_core.artifact import check_artifact_text


class ArtifactBubbleTests(unittest.TestCase):
    def test_fixture_shape_gap_is_machine_visible(self) -> None:
        text = """schema_version: "research-service-fixture/0.1"
claims:
  C1:
    claim_type: "INFERENCE"
    status: "DERIVED"
    derived_from: ["C0"]
graph_edges: []
writer_context: {}
"""

        kinds = {finding.kind for finding in check_artifact_text(text)}

        self.assertIn("schema_version_gap", kinds)
        self.assertIn("forbidden_claim_link", kinds)
        self.assertIn("legacy_claim_type", kinds)
        self.assertIn("legacy_claim_status", kinds)

    def test_incomplete_target_shape_reports_missing_fixture_keys(self) -> None:
        text = """schema_version: "research-service-artifact/0.2"
artifact_manifest: {}
policy: {}
source_versions: {}
claims:
  C1:
    claim_kind: "qualitative"
    origin_type: "derived"
    states: {}
graph_edges: []
writer_context: {}
"""

        kinds = {finding.kind for finding in check_artifact_text(text)}

        self.assertIn("missing_top_level_key", kinds)

    def test_target_minimal_fixture_shape_has_no_gap(self) -> None:
        text = """schema_version: "research-service-artifact/0.2"
artifact_type: "MINIMAL_FIXTURE"
artifact_id: "SNP_01J7K6Y5T4D3R2A1B0C9E8F7G6"
fixture_id: "minimal-fixture"
artifact_manifest: {}
policy: {}
source_versions: {}
document_registry: {}
source_registry: {}
report_spans: {}
evidence_spans: {}
claims:
  C1:
    claim_kind: "qualitative"
    origin_type: "derived"
    states: {}
quantities: {}
graph_edges: []
gaps: {}
writer_context: {}
service_summary: {}
"""

        self.assertEqual(check_artifact_text(text), [])


if __name__ == "__main__":
    unittest.main()
