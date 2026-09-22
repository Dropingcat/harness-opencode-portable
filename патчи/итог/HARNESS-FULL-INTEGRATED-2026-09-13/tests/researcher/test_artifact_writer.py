from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from researcher_core.artifact import check_artifact_text
from researcher_core.artifact_builder import build_minimal_service_artifact, render_artifact_yaml, write_artifact_atomic
from researcher_core.policy import load_policy
from researcher_core.r0.projections import Snapshot
from researcher_core.r0.ids import EntityId


def _snapshot_stub() -> Snapshot:
    return Snapshot(snapshot_id=EntityId("SNP_01J7K6Y5T4D3R2A1B0C9E8F7G6"), event_offset=1, entity_revisions={}, stop_reason="writer_test")


class ArtifactWriterProdTests(unittest.TestCase):
    def test_writer_embeds_policy_hash(self) -> None:
        policy = load_policy(Path.cwd())
        artifact = build_minimal_service_artifact(_snapshot_stub(), {}, "with policy", policy=policy)
        self.assertEqual(artifact["policy"]["policy_hash"], policy.policy_hash)
        self.assertEqual(artifact["artifact_manifest"]["policy_hash"], policy.policy_hash)
        rendered = render_artifact_yaml(artifact)
        self.assertIn(policy.policy_hash, rendered)
        self.assertEqual(check_artifact_text(rendered), [])

    def test_writer_without_policy_still_valid(self) -> None:
        artifact = build_minimal_service_artifact(_snapshot_stub(), {}, "no policy")
        self.assertEqual(artifact["policy"], {})
        rendered = render_artifact_yaml(artifact)
        self.assertEqual(check_artifact_text(rendered), [])

    def test_atomic_write_is_parseable(self) -> None:
        policy = load_policy(Path.cwd())
        artifact = build_minimal_service_artifact(_snapshot_stub(), {}, "atomic", policy=policy)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.yaml"
            write_artifact_atomic(path, artifact)
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
            self.assertEqual(data["schema_version"], "research-service-artifact/0.2")
            self.assertEqual(data["policy"]["policy_hash"], policy.policy_hash)

    def test_yaml_renderer_handles_unicode_and_quotes(self) -> None:
        artifact = build_minimal_service_artifact(_snapshot_stub(), {}, "unicode")
        # inject unicode and quotes via direct dict — render should not crash and be valid yaml
        artifact["source_registry"] = {"SRC_01": {"title": 'Doc "alpha:beta" at C:\\path\\doc.txt — тест', "locator": "x"}}
        rendered = render_artifact_yaml(artifact)
        data = yaml.safe_load(rendered)
        self.assertIn("alpha:beta", data["source_registry"]["SRC_01"]["title"])


if __name__ == "__main__":
    unittest.main()
