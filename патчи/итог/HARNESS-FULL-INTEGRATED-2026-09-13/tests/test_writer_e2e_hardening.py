from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

from scripts.writer.drafting.draft_loop import _graph_signature, _suggest_refs


class WriterE2EHardeningTests(unittest.TestCase):
    def test_cli_aliases_do_not_emit_runpy_warning(self):
        for command in ("research-adapt", "release-check"):
            cp = subprocess.run(
                [sys.executable, "scripts/writer/cli.py", command, "--help"],
                cwd=ROOT, text=True, capture_output=True,
            )
            self.assertEqual(0, cp.returncode, cp.stderr)
            self.assertNotIn("RuntimeWarning", cp.stderr)

    def test_graph_signature_accepts_nested_writer_graph_artifact(self):
        nested = {
            "graphs": {
                "P1": {
                    "graphs": {
                        "G13": {
                            "edges": [
                                {"graph": "G13", "relation": "HEAD_OF"},
                                {"graph": "G13", "relation": "NEXT"},
                            ]
                        }
                    }
                }
            }
        }
        self.assertEqual(("G13:HEAD_OF", "G13:NEXT"), _graph_signature(nested))

    def test_reference_selection_consumes_nested_cli_shape(self):
        para = {"edges": [{"graph": "G13", "relation": "HEAD_OF"}]}
        refs = [{
            "id": "R1", "title": "real graph artifact",
            "graphs": {"P1": {"graphs": {"G13": {"edges": [
                {"graph": "G13", "relation": "HEAD_OF"},
                {"graph": "G13", "relation": "NEXT"},
            ]}}}},
        }]
        out = _suggest_refs(para, refs)
        self.assertEqual("R1", out[0]["ref"])
        self.assertEqual(0.5, out[0]["graph_similarity"])

    def test_draft_loop_falls_back_when_semantic_extractor_returns_zero_claims(self):
        from unittest.mock import patch
        from scripts.writer.drafting import draft_loop as dl

        class Empty:
            claims = []
            objects = []

        with patch("scripts.writer.extractor.extract_all", return_value=Empty()):
            claims, graph = dl._decompose(
                "Первое утверждение. [C-101] Второе утверждение. [C-102]", "P1"
            )
        self.assertGreaterEqual(len(claims), 2)
        self.assertTrue(all(c.get("degraded_extraction") for c in claims))
        self.assertIn("[C-101]", claims[0]["span"])

    def test_rtt_uses_sentence_fallback_when_hybrid_returns_digest_only(self):
        from unittest.mock import patch
        from scripts.writer.core.factory_process import draftcheck

        contracts = [
            {"claim_id": "C1", "proposition": "Первое утверждение.", "forbidden_transformations": ["CLAIM_OMISSION"]},
            {"claim_id": "C2", "proposition": "второе утверждение.", "forbidden_transformations": ["CLAIM_OMISSION"]},
        ]
        fake = {"claims": [], "digest": {"main_statement": {"text": "x"}}}
        with patch("scripts.writer.extraction.hybrid.hybrid_extract_paragraph", return_value=fake):
            out = draftcheck("Первое утверждение. второе утверждение.", contracts)
        self.assertEqual("PASS", out["verdict"])
        self.assertEqual(2, len(out["re_extraction"]["claims"]))
        self.assertTrue(all(c["qa_status"] == "DEGRADED_FALLBACK" for c in out["re_extraction"]["claims"]))

    def test_draft_loop_splits_after_citation_before_lowercase_technical_sentence(self):
        from unittest.mock import patch
        from scripts.writer.drafting import draft_loop as dl
        class Empty:
            claims = []
            objects = []
        with patch("scripts.writer.extractor.extract_all", return_value=Empty()):
            claims, _ = dl._decompose("Первое. [C-1] [S-1] handoff содержит 2 файла. [C-2] [S-2]", "P1")
        self.assertEqual(2, len(claims))
        self.assertIn("[S-1]", claims[0]["span"])
        self.assertTrue(claims[1]["span"].startswith("handoff"))


if __name__ == "__main__":
    unittest.main()
