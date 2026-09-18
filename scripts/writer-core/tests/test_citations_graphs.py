# -*- coding: utf-8 -*-
"""Unit-тесты TD-083 + G7/G8/G9 (writer-citations-g7-g8-g9).

Покрытие (R3 ревью):
  - hybrid_extract._extract_md_links: 3 ссылки + точные span; вложенные скобки (R4);
  - hybrid_extract._is_repo_path: таблица (repo path / URL / якорь);
  - hybrid_extract.hybrid_extract_paragraph: citations/artifact_refs/source_links
    (source_links — копия, не алиас — R5);
  - graph_builder_hybrid.build_paragraph_graphs на синтетических артефактах:
    G7 built при citations / skipped без (T8); G8 built при сигнале+файле в
    config/ / skipped без (R1: 'policy(percept)' в коде -> skipped);
    G9 built при revisions / skipped без; R2: 2 revisions одинаковый claim ->
    1 ClaimRef-нода;
  - validate_against_registry = [] для всех построенных графов;
  - legacy artifact без citations не падает.

Запуск (как test_runtime_boundary): из каталога tests/ через
  python -m unittest test_citations_graphs -v
или из корня writer-core:
  python -m unittest tests.test_citations_graphs -v
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hybrid_extract import (  # noqa: E402
    _extract_md_links,
    _is_repo_path,
    _extract_citation_markers,
)
from graph_builder_hybrid import (  # noqa: E402
    build_paragraph_graphs,
    load_graph_registry,
    validate_against_registry,
)

_REGISTRY = load_graph_registry()


def _min_artifact(text: str = "", citations=None, artifact_refs=None,
                  claims=None, revisions=None, para_id="P0") -> dict:
    """Синтетический артефакт параграфа с необязательными полями."""
    return {
        "paragraph_id": para_id,
        "page": 1,
        "text": text,
        "claims": claims or [],
        "citations": citations or [],
        "artifact_refs": artifact_refs or [],
        "revisions": revisions,
    }


class ExtractMdLinksTests(unittest.TestCase):
    def test_three_links_and_spans(self) -> None:
        text = ("См. [док](docs/a.md) и [код](scripts/x.py) и "
                "[статью](https://ex.com/a) в конце.")
        links = _extract_md_links(text)
        self.assertEqual(len(links), 3)
        self.assertEqual(links[0]["text"], "док")
        self.assertEqual(links[0]["url"], "docs/a.md")
        self.assertEqual(text[links[0]["span"][0]:links[0]["span"][1]],
                         "[док](docs/a.md)")
        self.assertEqual(links[1]["url"], "scripts/x.py")
        self.assertEqual(text[links[1]["span"][0]:links[1]["span"][1]],
                         "[код](scripts/x.py)")
        self.assertEqual(links[2]["url"], "https://ex.com/a")
        self.assertEqual(text[links[2]["span"][0]:links[2]["span"][1]],
                         "[статью](https://ex.com/a)")

    def test_nested_parens_in_url(self) -> None:
        """R4: вложенные скобки в URL не обрезают url на первой ')'."""
        links = _extract_md_links("[x](https://a/(b))")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["url"], "https://a/(b)")
        self.assertEqual(links[0]["span"], [0, 18])

    def test_unbalanced_parens_span_within_bounds(self) -> None:
        """R1-minor: несбалансированная скобка — span не выходит за len(text)."""
        text = "[x](https://a/(b)"
        self.assertEqual(len(text), 17)
        links = _extract_md_links(text)
        self.assertEqual(len(links), 1)
        start, end = links[0]["span"]
        self.assertGreaterEqual(start, 0)
        self.assertLessEqual(end, len(text))
        self.assertEqual(links[0]["url"], "https://a/(b")

    def test_no_links(self) -> None:
        self.assertEqual(_extract_md_links("просто текст"), [])


class IsRepoPathTests(unittest.TestCase):
    def test_table(self) -> None:
        cases = [
            # (url, ожидание)
            ("docs/writing/dom.md", True),
            ("scripts/writer-core/wc_cli.py", True),
            ("config/guard_policy.json", True),
            ("./docs/a.md", True),
            ("../docs/b.md", True),
            ("templates/writer-dom-dissertation.yaml", True),
            ("https://example.com/a", False),
            ("https://example.com/a.md", False),
            ("http://x/y.py", False),
            ("file:///tmp/a.py", False),
            ("mailto:a@b.c", False),
            ("#anchor", False),
            ("", False),
            ("not_a_file", False),            # нет расширения
            ("docs/a.txt", True),
            ("reports/summary.md", True),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(_is_repo_path(url), expected, url)


class ExtractCitationMarkersTests(unittest.TestCase):
    def test_citations_and_artifact_refs(self) -> None:
        text = ("Метод описан в [документации](docs/writing/dom.md) и "
                "[репозитории](https://github.com/x/y).")
        citations, artifact_refs = _extract_citation_markers(text)
        self.assertEqual(len(citations), 2)
        self.assertEqual(len(artifact_refs), 1)
        self.assertEqual(artifact_refs[0]["path"], "docs/writing/dom.md")
        self.assertEqual(citations[0]["url"], "docs/writing/dom.md")
        self.assertEqual(citations[1]["url"], "https://github.com/x/y")

    def test_hybrid_paragraph_fields(self) -> None:
        """R5: source_links — независимая копия citations, не алиас."""
        from hybrid_extract import hybrid_extract_paragraph
        art = hybrid_extract_paragraph(
            "См. [док](docs/a.md) и [сайт](https://x.com).", "P1", 1)
        self.assertIn("citations", art)
        self.assertIn("artifact_refs", art)
        self.assertIn("source_links", art)
        self.assertEqual(len(art["citations"]), 2)
        self.assertEqual(len(art["artifact_refs"]), 1)
        self.assertEqual(len(art["source_links"]), 2)
        self.assertIsNot(art["source_links"], art["citations"])  # не алиас
        art["citations"].append({"text": "x", "url": "y", "span": [0, 1]})
        self.assertEqual(len(art["source_links"]), 2)  # копия не мутировала
        # legacy-ключи на месте
        for key in ("claims", "digest", "links", "sentences", "objects",
                    "discourse", "philology", "text", "paragraph_id"):
            self.assertIn(key, art)


class GraphBuildG7Tests(unittest.TestCase):
    def test_built_with_citations(self) -> None:
        art = _min_artifact(
            text="Текст [ссылка](docs/a.md) утверждение.",
            citations=[{"text": "ссылка", "url": "docs/a.md", "span": [6, 27]}],
            artifact_refs=[{"path": "docs/a.md", "span": [6, 27]}],
            claims=[{"text": "утверждение", "start": 28, "end": 40,
                     "qa_status": "GROUNDED"}])
        g = build_paragraph_graphs(art, _REGISTRY)
        g7 = g.get("graphs", {}).get("G7_citation_provenance")
        self.assertIsNotNone(g7)
        types = {n["type"] for n in g7["nodes"]}
        self.assertTrue({"CitationMarker", "ArtifactRef", "ClaimRef"} <= types)
        self.assertNotIn("G7_citation_provenance",
                         [s["graph"] for s in g.get("skipped", [])])
        self.assertEqual(validate_against_registry(g, _REGISTRY), [])

    def test_cit_only_no_claims(self) -> None:
        art = _min_artifact(
            text="[ссылка](docs/a.md)",
            citations=[{"text": "ссылка", "url": "docs/a.md", "span": [0, 21]}],
            artifact_refs=[{"path": "docs/a.md", "span": [0, 21]}])
        g = build_paragraph_graphs(art, _REGISTRY)
        g7 = g.get("graphs", {}).get("G7_citation_provenance")
        self.assertIsNotNone(g7)
        self.assertTrue(g7["nodes"])  # ноды есть (не пуст)
        self.assertEqual(validate_against_registry(g, _REGISTRY), [])

    def test_claims_only_skipped(self) -> None:
        """T8: G7 skipped если есть только claims, без citations/artifact_refs."""
        art = _min_artifact(
            text="Утверждение о стабильности контура.",
            claims=[{"text": "Утверждение о стабильности контура",
                     "start": 0, "end": 37, "qa_status": "GROUNDED"}])
        g = build_paragraph_graphs(art, _REGISTRY)
        self.assertNotIn("G7_citation_provenance", g.get("graphs", {}))
        self.assertIn("G7_citation_provenance",
                      [s["graph"] for s in g.get("skipped", [])])

    def test_empty_skipped(self) -> None:
        art = _min_artifact(text="Пусто.")
        g = build_paragraph_graphs(art, _REGISTRY)
        self.assertNotIn("G7_citation_provenance", g.get("graphs", {}))


class GraphBuildG8Tests(unittest.TestCase):
    def test_built_with_signal_and_config(self) -> None:
        """G8 built при русском сигнале + реальном policy-файле в config/."""
        art = _min_artifact(
            text="Guard-политика требует блокировать недоверенный ввод "
                 "до проверки.",
            claims=[{"text": "Guard-политика требует блокировать недоверенный "
                             "ввод", "start": 0, "end": 55,
                     "qa_status": "GROUNDED"}])
        g = build_paragraph_graphs(art, _REGISTRY)
        g8 = g.get("graphs", {}).get("G8_policy_constraint")
        self.assertIsNotNone(g8)
        self.assertTrue(any(n["type"] == "GlobalPolicy" for n in g8["nodes"]))
        self.assertEqual(validate_against_registry(g, _REGISTRY), [])

    def test_code_ident_skipped(self) -> None:
        """R1: 'action = policy(percept)' в коде без русского контекста ->
        G8 skipped (нет ложной DomainPolicy-ноды)."""
        art = _min_artifact(
            text="for step in steps:\n    percept = sense(state)\n    "
                 "action = policy(percept)\n    state = act(action)")
        g = build_paragraph_graphs(art, _REGISTRY)
        self.assertNotIn("G8_policy_constraint", g.get("graphs", {}))
        self.assertIn("G8_policy_constraint",
                      [s["graph"] for s in g.get("skipped", [])])

    def test_guard_ident_skipped_no_ru_context(self) -> None:
        """R1-критический: 'action = guard(percept)' в коде БЕЗ русского
        контекста -> G8 SKIPPED (лат-сигнал guard не самоподтверждается
        через _RU_POLICY_MARKERS)."""
        art = _min_artifact(
            text="for step in steps:\n    percept = sense(state)\n    "
                 "action = guard(percept)\n    state = act(action)")
        g = build_paragraph_graphs(art, _REGISTRY)
        self.assertNotIn("G8_policy_constraint", g.get("graphs", {}))
        self.assertIn("G8_policy_constraint",
                      [s["graph"] for s in g.get("skipped", [])])

    def test_guard_built_with_ru_marker(self) -> None:
        """R1-критический: 'запрещено вызывать guard()' (русский маркер
        'запрещено') -> G8 BUILT."""
        art = _min_artifact(
            text="Запрещено вызывать guard() на недоверенном вводе "
                 "до проверки.",
            claims=[{"text": "Запрещено вызывать guard() на недоверенном вводе",
                     "start": 0, "end": 48, "qa_status": "GROUNDED"}])
        g = build_paragraph_graphs(art, _REGISTRY)
        g8 = g.get("graphs", {}).get("G8_policy_constraint")
        self.assertIsNotNone(g8)
        self.assertTrue(any(n["type"] == "GlobalPolicy" for n in g8["nodes"]))
        self.assertEqual(validate_against_registry(g, _REGISTRY), [])

    def test_no_signal_skipped(self) -> None:
        art = _min_artifact(text="Полученные значения сведены в таблицу.")
        g = build_paragraph_graphs(art, _REGISTRY)
        self.assertNotIn("G8_policy_constraint", g.get("graphs", {}))


class GraphBuildG9Tests(unittest.TestCase):
    def test_built_with_revisions(self) -> None:
        art = _min_artifact(
            text="Утверждение из источника.",
            claims=[{"text": "Утверждение из источника", "start": 0, "end": 26,
                     "qa_status": "GROUNDED"}],
            revisions=[
                {"id": "R-001", "date": "2026-09-01", "status": "superseded",
                 "added_claims": [0]},
                {"id": "R-002", "date": "2026-09-10", "status": "current",
                 "added_claims": [0]},  # тот же claim (R2)
            ])
        g = build_paragraph_graphs(art, _REGISTRY)
        g9 = g.get("graphs", {}).get("G9_revision_dependency")
        self.assertIsNotNone(g9)
        revs = [n for n in g9["nodes"] if n["type"] == "RevisionRef"]
        claims_g9 = [n for n in g9["nodes"] if n["type"] == "ClaimRef"]
        self.assertEqual(len(revs), 2)
        self.assertEqual(len(claims_g9), 1)  # R2: дедупликация
        gen = [e for e in g9["edges"] if e["relation"] == "GENERATED_FROM"]
        self.assertEqual(len(gen), 2)  # оба revision -> общая нода
        sup = [e for e in g9["edges"] if e["relation"] == "SUPERSEDES"]
        self.assertEqual(len(sup), 1)
        self.assertEqual(validate_against_registry(g, _REGISTRY), [])

    def test_no_revisions_skipped(self) -> None:
        art = _min_artifact(text="Утверждение.", claims=[{
            "text": "Утверждение", "start": 0, "end": 11,
            "qa_status": "GROUNDED"}])
        g = build_paragraph_graphs(art, _REGISTRY)
        self.assertNotIn("G9_revision_dependency", g.get("graphs", {}))


class LegacyArtifactTests(unittest.TestCase):
    def test_no_citations_fields_ok(self) -> None:
        """Legacy artifact без citations/artifact_refs/source_links не падает."""
        art = {
            "paragraph_id": "L0",
            "page": 1,
            "text": "Старое утверждение без ссылок.",
            "claims": [{"text": "Старое утверждение без ссылок", "start": 0,
                        "end": 28, "qa_status": "GROUNDED"}],
            "objects": [], "discourse": [], "philology": {},
            "digest": {}, "sentences": [],
            "links": {"claim_to_digest": [], "object_to_claim": []},
        }
        g = build_paragraph_graphs(art, _REGISTRY)
        self.assertEqual(g.get("errors", []), [])
        self.assertNotIn("G7_citation_provenance", g.get("graphs", {}))


if __name__ == "__main__":
    unittest.main()