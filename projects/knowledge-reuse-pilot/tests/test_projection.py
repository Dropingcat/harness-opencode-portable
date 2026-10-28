import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from knowledge_pilot.catalog import Catalog
from knowledge_pilot.projection import export_catalog, graph_query


class ProjectionTests(unittest.TestCase):
    def test_graph_and_wiki_are_idempotent_and_queryable_by_real_graphify(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus"
            corpus.mkdir()
            source = corpus / "source.md"
            report = corpus / "report.md"
            source.write_text("Primary measurement", encoding="utf-8")
            report.write_text("Analysis cites [source](source.md).", encoding="utf-8")
            catalog = Catalog(root / "pilot", {"test": corpus})
            catalog.scan()
            catalog.register(report, coverage=["analysis"], inputs=[source], status="accepted")
            first = export_catalog(catalog)
            path = Path(first["graph"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            second = export_catalog(catalog)
            self.assertEqual(second["changed_files"], 0)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(any(edge["relation"] == "derived_from" for edge in data["links"]))
            answer = graph_query(catalog, "source", budget=500)
            self.assertEqual(answer["engine"], "graphifyy-0.9.95")
            self.assertIn("source", answer["text"].lower())


if __name__ == "__main__":
    unittest.main()
