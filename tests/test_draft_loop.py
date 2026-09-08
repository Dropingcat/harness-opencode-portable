"""Tests for draft_loop.py (WS-18 writer draft loop)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "writer"))

import draft_loop as dl  # noqa: E402


def _dom():
    return {
        "product": {"id": "PROD-T", "kind": "dissertation"},
        "structure": {"chapters": [{"id": "CH-01", "title": "В", "sections": [
            {"id": "SEC-01-01", "title": "Акт", "paragraphs": [{"id": "PAR-01", "claims": [], "text": ""}]}
        ]}]},
        "claims": [
            {"id": "C-001", "text": "гуматы повышают эффективность удобрений на 15–30%", "kind": "factual",
             "evidence": [{"source_id": "S-001", "span": "p.47"}],
             "verification": {"verdict": "SUPPORTED", "confidence": 0.8}},
        ],
        "graphs": [{"id": "GRAPH-01", "kind": "dependency", "edges": []}],
        "uncertainty": {"C-001": {"level": "established"}},
        "sources": [{"id": "S-001", "ref": "Иванов. 2020"}],
    }


class TestDraftLoop(unittest.TestCase):
    def test_decompose_finds_claims(self):
        text = "Согласно исследованию, гуматы повышают эффективность удобрений. Также они снижают кислотность почвы."
        claims, graphs = dl._decompose(text, "PAR-01")
        self.assertGreaterEqual(len(claims), 1)

    def test_match_known_claim(self):
        claims = [{"text": "гуматы повышают эффективность удобрений на 15–30%"}]
        known, new = dl._match_to_dom(claims, _dom()["claims"])
        self.assertEqual(len(known), 1)
        self.assertEqual(known[0]["dom_id"], "C-001")
        self.assertEqual(new, [])

    def test_match_new_claim_needs_source(self):
        claims = [{"text": "гуматы снижают кислотность почвы на 20%"}]
        known, new = dl._match_to_dom(claims, _dom()["claims"])
        self.assertEqual(known, [])
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0]["needs_source"])

    def test_link_binding_via_c_ref(self):
        # фрагмент содержит явную ссылку [C-406] -> связывается напрямую,
        # даже если markdown-разметка искажает текстовое сходство
        dom = _dom()
        dom["claims"].append({"id": "C-406",
                              "text": "Энергия образования нитридов W и Mo на 0,8–1,2 эВ выше, чем у карбидов"})
        claims = [{"text": "Наблюдаемое сближение параметров решёток",  # обрезанный вид
                   "span": "Наблюдаемое сближение параметров решёток карбидной и нитридной фаз "
                           "**может быть связано** с частичным замещением углерода азотом, "
                           "возможно, [C-406]."}]
        known, new = dl._match_to_dom(claims, dom["claims"])
        self.assertEqual(len(known), 1, known)
        self.assertEqual(known[0]["dom_id"], "C-406")
        self.assertEqual(known[0]["match_mode"], "link")
        self.assertEqual(new, [])  # дубль C-NEW не создаётся

    def test_markdown_normalization_keeps_similarity(self):
        # фрагмент без ссылки, но с markdown-разметкой; нормализация убирает
        # **...**, [LEGACY] и не ломает текстовое сходство с DOM-claim
        dom = _dom()
        dom["claims"].append({"id": "C-406",
                              "text": "Энергия образования нитридов W и Mo на 0,8–1,2 эВ выше, чем у карбидов"})
        claims = [{"text": "энергия образования нитридов",
                   "span": "По данным литературы, энергия образования нитридов W и Mo на 0,8–1,2 эВ выше, "
                           "чем у соответствующих карбидов. Наблюдаемое сближение решёток **может быть "
                           "связано** с замещением углерода азотом [LEGACY]."}]
        known, new = dl._match_to_dom(claims, dom["claims"])
        self.assertEqual(len(known), 1, known)
        self.assertEqual(known[0]["dom_id"], "C-406")
        self.assertEqual(known[0]["match_mode"], "text")
        self.assertGreaterEqual(known[0]["match_score"], 0.55)
        self.assertEqual(new, [])

    def test_norm_for_match_strips_markdown_and_refs(self):
        raw = "**Наблюдаемое** сближение параметров решёток `может быть связано` с замещением [C-406] [LEGACY]"
        n = dl._norm_for_match(raw)
        self.assertNotIn("*", n)
        self.assertNotIn("`", n)
        self.assertNotIn("[c-406]", n)
        self.assertNotIn("legacy", n)
        self.assertIn("сближение", n)
        self.assertIn("может быть связано", n)

    def test_norm_for_match_removes_strikethrough_content(self):
        raw = "Старый тезис ~~удалённый фрагмент текста~~ остаётся"
        n = dl._norm_for_match(raw)
        self.assertNotIn("удалённый", n)
        self.assertNotIn("~~", n)

    def test_fragment_without_ref_genuinely_new_needs_source(self):
        # фрагмент без ссылки, реально новый (нет в DOM) -> needs_source, как раньше
        claims = [{"text": "гуматы снижают кислотность почвы на 20%",
                   "span": "Гуматы снижают кислотность почвы на 20% в кислых дерново-подзолистых почвах."}]
        known, new = dl._match_to_dom(claims, _dom()["claims"])
        self.assertEqual(known, [])
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0]["needs_source"])

    def test_paragraph_status_complete(self):
        known = [{"text": "x", "dom_id": "C-001"}]
        new = []
        st = dl._paragraph_status(known, new)
        self.assertTrue(st["complete"])
        self.assertEqual(st["needs_source"], 0)

    def test_paragraph_status_needs_source(self):
        known = []
        new = [{"text": "y", "needs_source": True}]
        st = dl._paragraph_status(known, new)
        self.assertFalse(st["complete"])
        self.assertEqual(st["needs_source"], 1)

    def test_apply_appends_to_dom(self):
        with tempfile.TemporaryDirectory() as td:
            dom_path = Path(td) / "dom.yaml"
            import yaml
            with open(dom_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(_dom(), f, allow_unicode=True)
            dom = dl._load_yaml(dom_path)
            text = "Новый факт: гуматы повышают pH почвы на 0.5."
            claims, _ = dl._decompose(text, "PAR-01")
            known, new = dl._match_to_dom(claims, dom["claims"])
            res = dl._apply(dom, "PAR-01", text, known, new, dom_path)
            self.assertGreaterEqual(res["claims_added"], 0)
            # перечитаем
            dom2 = dl._load_yaml(dom_path)
            para = dl._find_paragraph(dom2, "PAR-01")
            self.assertEqual(para["text"], text)
            self.assertIn("draft_log", dom2)
            self.assertGreaterEqual(len(dom2.get("claims", [])), 1)

    def test_apply_unknown_paragraph_raises(self):
        with tempfile.TemporaryDirectory() as td:
            dom_path = Path(td) / "dom.yaml"
            import yaml
            with open(dom_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(_dom(), f, allow_unicode=True)
            dom = dl._load_yaml(dom_path)
            with self.assertRaises(ValueError):
                dl._apply(dom, "PAR-XXX", "text", [], [], dom_path)

    def test_suggest_refs_by_graph(self):
        refs = [
            {"id": "REF-1", "title": "Монография", "graphs": {"edges": [
                {"graph": "G5", "relation": "SUPPORTED_BY"}, {"graph": "G4", "relation": "CONCLUDES"}]}},
        ]
        para_graph = {"edges": [{"graph": "G5", "relation": "SUPPORTED_BY"}]}
        sug = dl._suggest_refs(para_graph, refs)
        self.assertGreaterEqual(len(sug), 1)


if __name__ == "__main__":
    unittest.main()