import hashlib
import tempfile
import unittest
from pathlib import Path

from knowledge_pilot.catalog import Catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.corpus = self.base / "corpus"
        self.corpus.mkdir()
        self.catalog = Catalog(self.base / "pilot", {"test": self.corpus})

    def test_scan_is_read_only_and_repeated_scan_reuses_text(self):
        source = self.corpus / "source.md"
        source.write_text("Nitrogen diffusion: the measurement is described here.", encoding="utf-8")
        before = source.read_bytes()
        first = self.catalog.scan()
        second = self.catalog.scan()
        self.assertEqual(first["extracted"], 1)
        self.assertEqual(second["extracted"], 0)
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(source.read_bytes(), before)
        found = self.catalog.lookup("nitrogen diffusion")
        self.assertTrue(found["candidates"])
        self.assertNotEqual(found["action"], "REUSE")

    def test_accepted_report_reuses_until_dependency_changes(self):
        source = self.corpus / "source.md"
        report = self.corpus / "report.md"
        source.write_text("Original measurement.", encoding="utf-8")
        report.write_text("Diffusion analysis with [source](source.md).", encoding="utf-8")
        self.catalog.scan()
        self.catalog.register(report, coverage=["diffusion analysis"], inputs=[source], status="accepted")
        self.assertEqual(self.catalog.lookup("diffusion analysis")["action"], "REUSE")
        source.write_text("Updated measurement.", encoding="utf-8")
        self.catalog.scan()
        answer = self.catalog.lookup("diffusion analysis")
        self.assertEqual(answer["action"], "REVALIDATE")
        self.assertTrue(answer["stale_reasons"])

    def test_trace_preserves_registered_input_revision(self):
        source = self.corpus / "source.md"
        report = self.corpus / "report.md"
        source.write_text("Primary evidence.", encoding="utf-8")
        report.write_text("Derived analysis.", encoding="utf-8")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        self.catalog.scan()
        self.catalog.register(report, coverage=["analysis"], inputs=[source], status="accepted")
        trace = self.catalog.trace(str(report))
        self.assertTrue(any(edge["target_hash"] == digest and edge["relation"] == "derived_from" for edge in trace["edges"]))

    def test_secrets_dependencies_and_unsupported_are_accounted(self):
        (self.corpus / ".env").write_text("TOKEN=private", encoding="utf-8")
        dep = self.corpus / "node_modules"
        dep.mkdir()
        (dep / "hidden.md").write_text("Do not index", encoding="utf-8")
        (self.corpus / "image.opaque").write_bytes(b"opaque")
        result = self.catalog.scan()
        self.assertGreaterEqual(result["excluded"], 2)
        self.assertEqual(result["unsupported"], 1)
        self.assertFalse(self.catalog.lookup("private")["candidates"])
        self.assertEqual(self.catalog.lookup("missing fact")["action"], "INDEX_INCOMPLETE")

    def test_registration_cannot_escape_scope_or_promote_missing_evidence(self):
        outside = self.base / "outside.md"
        outside.write_text("Outside corpus", encoding="utf-8")
        self.catalog.scan()
        with self.assertRaises(ValueError):
            self.catalog.register(outside, coverage=["outside"], inputs=[], status="accepted")

    def test_latest_rejected_registration_prevents_old_accepted_reuse(self):
        source = self.corpus / "source.md"
        report = self.corpus / "report.md"
        source.write_text("Evidence", encoding="utf-8")
        report.write_text("Analysis", encoding="utf-8")
        self.catalog.scan()
        self.catalog.register(report, coverage=["analysis"], inputs=[source], status="accepted")
        self.catalog.register(report, coverage=["analysis"], inputs=[source], status="rejected")
        self.assertNotEqual(self.catalog.lookup("analysis")["action"], "REUSE")

    def test_duplicate_content_is_returned_once_with_other_locations(self):
        for name in ("original.md", "copy.md", "third.md"):
            (self.corpus / name).write_text("Unique nitrogen measurement", encoding="utf-8")
        self.catalog.scan()
        answer = self.catalog.lookup("nitrogen measurement")
        self.assertEqual(len(answer["candidates"]), 1)
        self.assertEqual(len(answer["candidates"][0]["duplicate_locations"]), 2)

    def test_provenance_sidecar_links_primary_file_to_its_url(self):
        import json
        source = self.corpus / "source.md"
        source.write_text("Primary measurement", encoding="utf-8")
        sidecar = self.corpus / "source.md.prov.json"
        sidecar.write_text(json.dumps({"file": "source.md", "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "source_url": "https://example.com/paper"}), encoding="utf-8")
        self.catalog.scan()
        trace = self.catalog.trace(str(source))
        self.assertTrue(any(edge["relation"] == "downloaded_from" for edge in trace["edges"]))
        self.assertTrue(any(node.get("uri") == "https://example.com/paper" for node in trace["nodes"]))

    def test_explicit_managed_result_is_searchable_but_not_automatically_accepted(self):
        source = self.corpus / "source.md"
        source.write_text("Primary measurement", encoding="utf-8")
        self.catalog.scan()
        result = self.catalog.home / "artifacts/results/profile.json"
        result.parent.mkdir(parents=True)
        result.write_text('{"method": "profile", "finding": "measurement summary"}', encoding="utf-8")
        self.catalog.register(result, coverage=["measurement summary"], inputs=[source], status="draft")
        self.assertTrue(self.catalog.lookup("measurement summary")["candidates"])
        self.assertNotEqual(self.catalog.lookup("measurement summary")["action"], "REUSE")
        self.catalog.scan()
        self.assertTrue(self.catalog.lookup("measurement summary")["candidates"])

    def test_explicit_input_hash_cannot_be_silently_rebound(self):
        source = self.corpus / "source.md"
        report = self.corpus / "report.md"
        source.write_text("Changed input", encoding="utf-8")
        report.write_text("Old analysis", encoding="utf-8")
        self.catalog.scan()
        with self.assertRaises(ValueError):
            self.catalog.register(report, coverage=["analysis"], inputs=[{"path": str(source), "sha256": "0" * 64}], status="draft")


if __name__ == "__main__":
    unittest.main()
