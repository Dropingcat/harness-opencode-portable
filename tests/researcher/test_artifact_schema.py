from __future__ import annotations

import unittest

from researcher_core.artifact import check_artifact_dict, check_artifact_text


class ArtifactSchemaProdTests(unittest.TestCase):
    def test_yaml_parse_error_is_finding(self) -> None:
        text = "schema_version: [unclosed"
        findings = check_artifact_text(text)
        kinds = {f.kind for f in findings}
        self.assertIn("yaml_parse_error", kinds)

    def test_dict_forbidden_key_detected(self) -> None:
        data = {
            "schema_version": "research-service-artifact/0.2",
            "artifact_type": "MINIMAL_FIXTURE",
            "artifact_id": "SNP_01",
            "fixture_id": "f1",
            "artifact_manifest": {},
            "policy": {},
            "source_versions": {},
            "document_registry": {},
            "source_registry": {},
            "report_spans": {},
            "evidence_spans": {},
            "claims": {"C1": {"depends_on": ["C0"], "claim_kind": "q", "origin_type": "t", "states": {}}},
            "quantities": {},
            "graph_edges": [],
            "gaps": {},
            "writer_context": {},
            "service_summary": {},
        }
        kinds = {f.kind for f in check_artifact_dict(data)}
        self.assertIn("forbidden_claim_link", kinds)

    def test_dict_missing_keys_detected(self) -> None:
        data = {"schema_version": "research-service-artifact/0.2", "claims": {}}
        kinds = {f.kind for f in check_artifact_dict(data)}
        self.assertIn("missing_top_level_key", kinds)

    def test_dict_minimal_passes(self) -> None:
        data = {
            "schema_version": "research-service-artifact/0.2",
            "artifact_type": "MINIMAL_FIXTURE",
            "artifact_id": "SNP_01",
            "fixture_id": "f1",
            "artifact_manifest": {},
            "policy": {},
            "source_versions": {},
            "document_registry": {},
            "source_registry": {},
            "report_spans": {},
            "evidence_spans": {},
            "claims": {"C1": {"claim_kind": "qualitative", "origin_type": "derived", "states": {}}},
            "quantities": {},
            "graph_edges": [],
            "gaps": {},
            "writer_context": {},
            "service_summary": {},
        }
        self.assertEqual(check_artifact_dict(data), [])


if __name__ == "__main__":
    unittest.main()
