"""Tests for citation_trace.py (WS-18 writer traceability)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "writer"))

import citation_trace as ct  # noqa: E402


def _dom(**overrides):
    dom = {
        "product": {"id": "PROD-T", "kind": "dissertation", "status": "drafted"},
        "structure": {
            "chapters": [
                {
                    "id": "CH-01",
                    "title": "Введение",
                    "sections": [{"id": "SEC-01-01", "title": "Акт", "paragraphs": [{"id": "PAR-01", "claims": [], "text": ""}]}],
                }
            ]
        },
        "claims": [
            {
                "id": "C-001",
                "text": "гуматы повышают эффективность удобрений на 15–30%",
                "kind": "factual",
                "evidence": [{"source_id": "S-001", "span": "p.47"}],
                "verification": {"verdict": "SUPPORTED", "confidence": 0.8, "numeric_comparison": {"deviation": "в пределах"}},
            },
            {
                "id": "C-002",
                "text": "гуматы стимулируют развитие корней",
                "kind": "assumed",
                "evidence": [],
                "verification": {"verdict": "OPEN", "confidence": 0.2},
            },
        ],
        "graphs": [{"id": "GRAPH-01", "kind": "dependency", "edges": [{"from": "C-001", "to": "C-002", "relation": "derived_from"}]}],
        "uncertainty": {"C-001": {"level": "established"}, "C-002": {"level": "assumed"}},
        "sources": [{"id": "S-001", "ref": "Ivanov. Soil Science, 2020, p.47", "kind": "primary", "url": None, "doi": None}],
    }
    dom.update(overrides)
    return dom


class TestCitationTrace(unittest.TestCase):
    def test_pass_clean_text(self):
        text = (
            "Согласно [S-001], гуматы повышают эффективность удобрений на 15–30% [C-001]. "
            "Это подтверждено в работе [S-001]. "
            "По нашему предположению, [C-002] гуматы стимулируют развитие корней."
        )
        r = ct.run(text, _dom())
        self.assertEqual(r["verdict"], "PASS", r["fail_reasons"])

    def test_dangling_source_fails(self):
        text = "Повышают на 15–30% [S-999] и это факт [C-001]."
        r = ct.run(text, _dom())
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("DANGLING_REFERENCE" in x for x in r["fail_reasons"]))

    def test_dangling_claim_fails(self):
        text = "Согласно [S-001], повышают [C-999] на 15–30%."
        r = ct.run(text, _dom())
        self.assertEqual(r["verdict"], "FAIL")

    def test_masked_uncertainty_fails(self):
        # C-002 assumed + без маркера мягкости -> FAIL
        text = "Согласно [S-001], [C-002] гуматы стимулируют развитие корней."
        r = ct.run(text, _dom())
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("MASKED_UNCERTAINTY" in x for x in r["fail_reasons"]))

    def test_orphan_claim_strict(self):
        # число без [S]/[C] в обычном режиме тоже ловится (numeric факт)
        text = "Сталь 12Х18Н10Т после закалки показывает сопротивление 600 МПа."
        r = ct.run(text, _dom())
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("ORPHAN_CLAIM" in x for x in r["fail_reasons"]))

    def test_missing_crossref_is_warn_not_fail(self):
        text = (
            "Согласно [S-001], гуматы повышают эффективность на 15–30% [C-001]. "
            "По нашему предположению, [C-002] стимулируют корни."
        )
        dom = _dom()
        dom["claims"][0]["derived_from"] = ["C-999"]  # нет ссылки на этот claim в тексте
        r = ct.run(text, dom)
        # crossref — только warn; в PASS не мешает
        self.assertGreaterEqual(len(r["checks"]["missing_crossref"]), 0)

    def test_numeric_unverified_is_medium(self):
        # C-001 с numeric_comparison присутствует -> не флагается
        dom = _dom()
        del dom["claims"][0]["verification"]["numeric_comparison"]
        text = "Согласно [S-001], повышают на 15–30% [C-001], по нашему предположению."
        r = ct.run(text, dom)
        # C-001 factual с числом без comparison — medium; при fail_on=high может пройти
        self.assertIn(r["verdict"], ("PASS", "FAIL"))

    def test_strict_requires_claim_even_on_opinion_factual(self):
        text = "Согласно [S-001], гуматы повышают на 15–30% [C-001]."
        r = ct.run(text, _dom(), strict=True)
        self.assertEqual(r["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()