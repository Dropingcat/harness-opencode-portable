"""Review reproducers. No network, corpus mutations, or files outside pilot TEMP."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from knowledge_pilot.catalog import Catalog, digest_file
from knowledge_pilot.extract import Extraction, redact
from knowledge_pilot.jobs import Jobs
from knowledge_pilot.local_analysis import table_profile
from knowledge_pilot.projection import _write
from knowledge_pilot.service import Service


class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.corpus = self.base / "corpus"
        self.corpus.mkdir()
        self.home = self.base / "pilot"
        self.cat = Catalog(self.home, {"fixture": self.corpus})
        self.service = Service.__new__(Service)
        self.service.home, self.service.catalog = self.home, self.cat
        self.service.jobs = Jobs(self.home)

    def file(self, name, text):
        path = self.corpus / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_C1_structured_tokens_and_url_credentials_are_redacted(self):
        raw = '{"token":"private-value", "source_url":"https://user:private-password@example.com/p?token=private-query&x=ok"}'
        cleaned = redact(raw)
        for value in ("private-value", "private-password", "private-query"):
            self.assertNotIn(value, cleaned)
        self.assertIn("x=ok", cleaned)

    def test_C1_read_boundary_sanitizes_legacy_cached_text_before_slicing(self):
        source = self.file("legacy.json", '{"token":"private-value"}')
        self.cat.scan()
        with self.cat.db() as db:
            db.execute("UPDATE blobs SET text=?", ('{"token":"private-value"}',))
        self.assertNotIn("private-value", self.service.read(str(source))["text"])

    def test_I1_equal_and_reversed_clocks_cannot_resurrect_withdrawn_approval(self):
        source = self.file("source.md", "Evidence")
        report = self.file("report.md", "Analysis")
        self.cat.scan()
        with patch("knowledge_pilot.reuse.time.time", return_value=1000):
            self.cat.register(report, coverage=["analysis"], inputs=[source], status="accepted")
            self.cat.register(report, coverage=["analysis"], inputs=[source], status="rejected")
        self.assertNotEqual(self.cat.lookup("analysis")["action"], "REUSE")
        with patch("knowledge_pilot.reuse.time.time", return_value=500):
            self.cat.register(report, coverage=["analysis"], inputs=[source], status="superseded")
        self.assertEqual(self.cat.lookup("analysis")["excluded_reports"][0]["status"], "superseded")

    def chain(self):
        source = self.file("source.md", "Original evidence")
        a = self.file("a.md", "Intermediate analysis")
        b = self.file("b.md", "Final analysis")
        self.cat.scan()
        self.cat.register(a, coverage=["intermediate"], inputs=[source], status="accepted")
        self.cat.register(b, coverage=["final"], inputs=[a], status="accepted")
        return source, a, b

    def test_I2_changed_transitive_source_blocks_final_report_reuse(self):
        source, a, b = self.chain()
        source.write_text("Changed evidence", encoding="utf-8")
        self.assertEqual(self.cat.lookup("final")["action"], "REVALIDATE")

    def test_I2_upstream_withdrawal_blocks_final_report_reuse(self):
        source, a, b = self.chain()
        self.cat.register(a, coverage=["intermediate"], inputs=[source], status="rejected")
        self.assertEqual(self.cat.lookup("final")["action"], "REVALIDATE")

    def test_I2_dependency_cycle_is_not_accepted_as_self_support(self):
        a = self.file("a.md", "First report")
        b = self.file("b.md", "Second report")
        self.cat.scan()
        self.cat.register(a, coverage=["a"], inputs=[b], status="accepted")
        self.cat.register(b, coverage=["b"], inputs=[a], status="accepted")
        result = self.cat.lookup("a")
        self.assertEqual(result["action"], "REVALIDATE")
        self.assertTrue(any(x["reason"] == "dependency_cycle" for x in result["stale_reasons"]))

    def test_C1_lookup_sanitizes_full_legacy_text_before_fragment_selection(self):
        source = self.file("legacy.json", '{"token":"private-value", "claim":"needle evidence"}')
        self.cat.scan()
        with self.cat.db() as db:
            db.execute("UPDATE search SET text=?", ('{"token":"private-value", "claim":"needle evidence"}',))
        result = self.cat.lookup("needle")
        self.assertTrue(result["candidates"])
        self.assertNotIn("private-value", result["candidates"][0]["excerpt"])

    def test_I3_format_is_part_of_extraction_cache_identity(self):
        raw = "<script>private_script</script><p>Evidence</p>"
        text = self.file("a.txt", raw)
        html = self.file("b.html", raw)
        counts = {"extracted": 0, "unchanged": 0}
        self.cat._scan_file(text, "fixture", "test", counts)
        self.cat._scan_file(html, "fixture", "test", counts)
        self.assertNotIn("private_script", self.service.read(str(html))["text"])

    def test_I4_edit_during_extraction_cannot_poison_old_content_hash(self):
        source = self.file("source.txt", "alpha evidence")

        def editing_extract(path, *args):
            source.write_text("beta different evidence", encoding="utf-8")
            return Extraction(Path(path).read_text(encoding="utf-8"))

        with patch("knowledge_pilot.catalog.extract", side_effect=editing_extract):
            self.cat.scan()
        source.write_text("alpha evidence", encoding="utf-8")
        self.cat.scan()
        self.assertEqual(self.service.read(str(source))["text"], "alpha evidence")

    def test_stable_failed_input_is_not_reparsed_without_new_bytes_or_method(self):
        self.file("broken.pdf", "not a PDF")
        with patch("knowledge_pilot.catalog.extract", return_value=Extraction(status="failed", detail="malformed input")) as parser:
            first = self.cat.scan()
            second = self.cat.scan()
        self.assertEqual(parser.call_count, 1)
        self.assertEqual(first["failed"], 1)
        self.assertEqual(second["parsed"], 0)
        self.assertFalse(second["complete"])

    def test_I5_question_wording_does_not_duplicate_table_computation(self):
        source = self.file("table.csv", "x,y\n1,2\n3,4\n")
        self.cat.scan()
        first = self.service.start("table_profile", path=str(source), max_rows=10, question="first wording")
        self.assertEqual(self.service.jobs.wait(first["id"], 10)["status"], "completed")
        second = self.service.start("table_profile", path=str(source), max_rows=10, question="different wording")
        self.service.jobs.wait(second["id"], 10)
        self.assertEqual(first["id"], second["id"])

    def test_I6_replaying_profile_does_not_revoke_operator_acceptance(self):
        source = self.file("table.csv", "x,y\n1,2\n3,4\n")
        self.cat.scan()
        payload = {"path": str(source), "expected_sha256": digest_file(source), "question": "profile"}
        result = table_profile(source)
        artifact = self.service._store_profile(result, payload)
        self.cat.register(artifact["path"], coverage=["profile"], inputs=[source], status="accepted")
        self.service._store_profile(result, payload)
        self.assertEqual(self.cat.lookup("profile")["action"], "REUSE")

    def test_I7_provenance_change_invalidates_completed_graph_job(self):
        source = self.file("source.md", "Evidence")
        report = self.file("report.md", "Analysis")
        self.cat.scan()
        first = self.service.start("export_graph")
        self.assertEqual(self.service.jobs.wait(first["id"], 10)["status"], "completed")
        self.cat.register(report, coverage=["analysis"], inputs=[source], status="draft")
        second = self.service.start("export_graph")
        self.service.jobs.wait(second["id"], 10)
        self.assertNotEqual(first["id"], second["id"])

    def test_I7_missing_output_invalidates_completed_graph_job(self):
        self.file("source.md", "Evidence")
        self.cat.scan()
        first = self.service.start("export_graph")
        done = self.service.jobs.wait(first["id"], 10)
        Path(done["result"]["graph"]).unlink()
        second = self.service.start("export_graph")
        self.service.jobs.wait(second["id"], 10)
        self.assertNotEqual(first["id"], second["id"])

    def test_I8_cli_and_mcp_share_one_scanner_lease(self):
        self.file("a.md", "First evidence")
        self.file("b.md", "Second evidence")
        entered, release = threading.Event(), threading.Event()
        original = self.cat._scan_file
        calls = []

        def pause_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                entered.set()
                release.wait(10)
            return original(*args, **kwargs)

        first_result = []
        with patch.object(self.cat, "_scan_file", side_effect=pause_second):
            worker = threading.Thread(target=lambda: first_result.append(self.cat.scan()))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                second = Catalog(self.home, {"fixture": self.corpus}).scan()
                self.assertEqual(second.get("status"), "blocked")
            finally:
                release.set()
                worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(self.cat.lookup("evidence")["candidates"]), 2)

    def test_I9_cancel_cannot_resurrect_a_completed_job(self):
        jobs = self.service.jobs
        job = jobs.submit("fixture", {}, "v1", lambda *args: {"value": 1})
        jobs.wait(job["id"], 5)
        with jobs.db() as db:
            db.execute("UPDATE jobs SET status='running' WHERE id=?", (job["id"],))
        original_db = jobs.db
        fired = []

        @contextmanager
        def interleaved():
            with original_db() as connection:
                class Connection:
                    def execute(self, sql, params=()):
                        if "UPDATE jobs" in sql and "cancel_requested" in params and not fired:
                            fired.append(True)
                            connection.execute("UPDATE jobs SET status='completed' WHERE id=?", (job["id"],))
                        return connection.execute(sql, params)
                yield Connection()

        with patch.object(jobs, "db", interleaved):
            jobs.cancel(job["id"])
        self.assertEqual(jobs.get(job["id"])["status"], "completed")

    def test_I10_junction_is_rejected_before_output_is_written(self):
        outside = self.base / "outside"
        outside.mkdir()
        link = self.home / "escape"
        if os.name == "nt":
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
            self.assertEqual(made.returncode, 0)
        else:
            link.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            _write(link / "escaped.md", "must not be written")
        self.assertFalse((outside / "escaped.md").exists())

    def test_I11_trace_has_global_edge_and_byte_budgets(self):
        source = self.file("report.md", "Report")
        self.cat.scan()
        with self.cat.db() as db:
            for number in range(2000):
                db.execute("INSERT INTO edges VALUES (?,?,?,?,?,?)", (self.cat.ident(source), digest_file(source), f"target-{number}", "f" * 64, "links_to", "fixture"))
        result = self.cat.trace(str(source))
        self.assertLessEqual(len(result["edges"]), 128)
        self.assertLessEqual(len(json.dumps(result).encode("utf-8")), 20000)
        self.assertTrue(result["truncated"])

    def test_M1_dead_owner_is_not_returned_as_active_work(self):
        jobs = self.service.jobs
        job = jobs.submit("fixture", {"question": "q"}, "v1", lambda *args: {})
        jobs.wait(job["id"], 5)
        with jobs.db() as db:
            db.execute("UPDATE jobs SET status='running',owner=? WHERE id=?", (1073741824, job["id"]))
        self.assertEqual(jobs.active("q"), [])


if __name__ == "__main__":
    unittest.main()
