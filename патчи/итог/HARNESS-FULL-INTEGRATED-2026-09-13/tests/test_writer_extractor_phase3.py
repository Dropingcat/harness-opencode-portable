from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "writer_extractor_phase3" / "fixtures.json"
BASELINE_FIX = ROOT / "experiments" / "writer_extractor_phase3" / "fixtures_baseline_7case.json"
BASELINE = ROOT / "experiments" / "writer_extractor_phase3" / "baseline.json"
AFTER = ROOT / "experiments" / "writer_extractor_phase3" / "after_merge.json"
SCRIPT = ROOT / "scripts" / "writer" / "extractor_experiment.py"

sys.path.insert(0, str(ROOT / "scripts" / "writer"))
import extractor  # noqa: E402


class WriterExtractorPhase3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = json.loads(FIX.read_text(encoding="utf-8"))["cases"]
        cls.by_id = {x["id"]: x for x in cls.fixtures}
        cls.baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        cls.after = json.loads(AFTER.read_text(encoding="utf-8"))

    def test_frozen_baseline_is_bound_to_fixture_hash(self):
        import hashlib
        self.assertEqual(
            self.baseline["fixtures_sha256"],
            hashlib.sha256(BASELINE_FIX.read_bytes()).hexdigest(),
        )
        self.assertEqual(self.baseline["schema"], "writer-extractor-experiment/1.0")

    def test_baseline_records_real_design_differences(self):
        diffs = {x["id"] for x in self.baseline["comparison"]["differences"]}
        self.assertEqual(
            diffs,
            {"ocr_newline", "ocr_nbsp", "word_boundary_false_positive", "scientific_objects"},
        )

    def test_canonical_accepts_ocr_whitespace_equivalence(self):
        for cid in ("ocr_newline", "ocr_nbsp"):
            c = self.by_id[cid]
            loc = extractor.span_locate(c["claim"], c["source"])
            self.assertEqual(loc["method"], "exact", cid)
            self.assertEqual(loc["start"], 0, cid)

    def test_canonical_rejects_match_inside_word(self):
        c = self.by_id["word_boundary_false_positive"]
        loc = extractor.span_locate(c["claim"], c["source"])
        self.assertEqual(loc["method"], "none")

    def test_canonical_finds_later_valid_exact_occurrence(self):
        c = self.by_id["second_valid_occurrence"]
        loc = extractor.span_locate(c["claim"], c["source"])
        self.assertEqual(loc["method"], "exact")
        self.assertEqual(c["source"][loc["start"]:loc["end"]], c["claim"])
        self.assertGreater(loc["start"], 20)

    def test_canonical_accepts_punctuation_as_boundary(self):
        c = self.by_id["scientific_objects"]
        loc = extractor.span_locate(c["claim"], c["source"])
        self.assertEqual(loc["method"], "exact")
        self.assertEqual(c["source"][loc["start"]:loc["end"]], c["claim"])

    def test_extraction_output_has_behavioral_parity(self):
        w = {x["id"]: x["extract"] for x in self.after["writer"]["cases"]}
        v = {x["id"]: x["extract"] for x in self.after["v2"]["cases"]}
        self.assertEqual(w, v)

    def test_remaining_difference_is_explained_v2_boundary_defect(self):
        diffs = self.after["comparison"]["differences"]
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]["id"], "scientific_objects")
        self.assertEqual(set(diffs[0]["fields"]), {"span", "qa"})
        self.assertEqual(diffs[0]["writer"]["span"]["method"], "exact")
        self.assertEqual(diffs[0]["v2"]["span"]["method"], "none")

    def test_canonical_common_extractor_has_no_pymupdf_import(self):
        for p in (ROOT / "scripts" / "writer" / "extractor").glob("*.py"):
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("import pymupdf", text, p.name)
            self.assertNotIn("from pymupdf", text, p.name)

    def test_experiment_runner_is_reproducible_for_behavior(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        current = json.loads(proc.stdout)
        self.assertEqual(current["comparison"], self.after["comparison"])


if __name__ == "__main__":
    unittest.main()
