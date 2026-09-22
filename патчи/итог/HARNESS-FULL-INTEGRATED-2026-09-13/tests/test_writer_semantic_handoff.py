from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]

from scripts.writer.research.verify_claims_adapter import adapt_verification
from scripts.writer.release.gate import evaluate_release


def _dom(claim_text: str, source_text: str) -> dict:
    return {
        "product": {"id": "TEST-PROD", "kind": "article", "status": "drafted", "language": "ru"},
        "structure": {"chapters": []},
        "claims": [{
            "id": "C-001", "text": claim_text, "kind": "factual",
            "evidence": [{"source_id": "S-001"}],
            "verification": {"verdict": "OPEN", "confidence": 0.0},
            "forbidden_transformations": [
                "CLAIM_OMISSION", "NUMERIC_DRIFT", "UNIT_DRIFT",
                "MODALITY_UPGRADE", "CAUSALITY_UPGRADE", "QUALIFIER_LOSS",
            ],
        }],
        "sources": [{"id": "S-001", "text": source_text, "kind": "primary"}],
    }


class SemanticHandoffTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def write_case(self, claim: str, source: str, draft: str):
        dom = self.dir / "dom.yaml"; text = self.dir / "draft.md"
        dom.write_text(yaml.safe_dump(_dom(claim, source), allow_unicode=True, sort_keys=False), encoding="utf-8")
        text.write_text(draft, encoding="utf-8")
        return dom, text

    def test_research_adapter_is_read_only_and_uses_canonical_authority(self):
        dom, _ = self.write_case("Прочность составляет 10 МПа.", "Прочность составляет 10 МПа.", "")
        before = hashlib.sha256(dom.read_bytes()).hexdigest()
        out = adapt_verification(dom)
        after = hashlib.sha256(dom.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertTrue(out["read_only"])
        self.assertEqual("scripts/researcher/verify_claims.py", out["authority"])
        self.assertEqual("SUPPORTED", out["results"][0]["verdict"])

    def test_release_pass_requires_all_three_gates(self):
        dom, text = self.write_case(
            "Прочность составляет 10 МПа.",
            "Прочность составляет 10 МПа.",
            "Прочность составляет 10 МПа. [C-001] [S-001]",
        )
        out = evaluate_release(dom, text)
        self.assertEqual("PASS", out["verdict"])
        self.assertTrue(out["release_allowed"])
        self.assertEqual([], out["blockers"])
        self.assertEqual({"evidence", "traceability", "semantic_roundtrip"}, set(out["gates"]))

    def test_evidence_failure_cannot_be_erased_by_other_gates(self):
        dom, text = self.write_case(
            "Прочность составляет 10 МПа.",
            "Прочность составляет 11 МПа.",
            "Прочность составляет 10 МПа. [C-001] [S-001]",
        )
        out = evaluate_release(dom, text)
        self.assertEqual("FAIL", out["verdict"])
        self.assertIn("evidence", out["blockers"])
        self.assertEqual("FAIL", out["gates"]["evidence"]["verdict"])

    def test_traceability_failure_blocks_release(self):
        dom, text = self.write_case(
            "Прочность составляет 10 МПа.",
            "Прочность составляет 10 МПа.",
            "Прочность составляет 10 МПа.",
        )
        out = evaluate_release(dom, text)
        self.assertEqual("FAIL", out["verdict"])
        self.assertIn("traceability", out["blockers"])

    def test_semantic_drift_blocks_release_even_with_supported_evidence(self):
        dom, text = self.write_case(
            "Прочность составляет 10 МПа.",
            "Прочность составляет 10 МПа.",
            "Прочность составляет 12 МПа. [C-001] [S-001]",
        )
        out = evaluate_release(dom, text)
        self.assertEqual("PASS", out["gates"]["evidence"]["verdict"])
        self.assertEqual("FAIL", out["gates"]["semantic_roundtrip"]["verdict"])
        self.assertIn("semantic_roundtrip", out["blockers"])

    def test_release_check_does_not_mutate_dom(self):
        dom, text = self.write_case(
            "Прочность составляет 10 МПа.",
            "Прочность составляет 10 МПа.",
            "Прочность составляет 10 МПа. [C-001] [S-001]",
        )
        before = dom.read_bytes()
        evaluate_release(dom, text)
        self.assertEqual(before, dom.read_bytes())

    def test_handoff_integration_marker_is_hash_bound(self):
        marker = json.loads((ROOT / "scripts/writer/migration/handoff_integration.json").read_text(encoding="utf-8"))
        self.assertEqual("writer-handoff-integration/1.0", marker["schema"])
        self.assertGreaterEqual(len(marker["items"]), 8)
        for item in marker["items"]:
            src = ROOT / item["source"]; dst = ROOT / item["target"]
            if not src.is_file():
                prefix = "scripts/" + "writer" + "_core_handoff/"
                archive = ROOT / marker["archive_target"]
                if item["source"].startswith(prefix):
                    src = archive / item["source"][len(prefix):]
            self.assertTrue(src.is_file(), item["source"])
            self.assertTrue(dst.is_file(), item["target"])
            hs = hashlib.sha256(src.read_bytes()).hexdigest()
            hd = hashlib.sha256(dst.read_bytes()).hexdigest()
            self.assertEqual(item["source_sha256"], hs)
            self.assertEqual(item["target_sha256"], hd)
            self.assertEqual(hs, hd)
            self.assertTrue(item["byte_identical"])


if __name__ == "__main__":
    unittest.main()
