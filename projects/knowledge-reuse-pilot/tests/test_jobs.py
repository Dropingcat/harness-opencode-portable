import tempfile
import threading
import unittest
from pathlib import Path

from knowledge_pilot.jobs import Jobs


class JobsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.jobs = Jobs(Path(self.temp.name))

    def test_same_work_is_single_flight_and_completed_result_is_reused(self):
        started, release = threading.Event(), threading.Event()
        calls = []

        def execute(payload, progress, cancelled):
            calls.append(payload)
            started.set()
            release.wait(3)
            return {"value": 42}

        first = self.jobs.submit("analysis", {"input": "a"}, "revision-1", execute)
        self.assertTrue(started.wait(3))
        second = self.jobs.submit("analysis", {"input": "a"}, "revision-1", execute)
        self.assertEqual(first["id"], second["id"])
        release.set()
        done = self.jobs.wait(first["id"], 5)
        self.assertEqual(done["status"], "completed")
        repeated = self.jobs.submit("analysis", {"input": "a"}, "revision-1", execute)
        self.assertEqual(repeated["id"], first["id"])
        self.assertEqual(len(calls), 1)

    def test_new_input_revision_runs_again_and_failure_is_not_completed(self):
        def execute(payload, progress, cancelled):
            raise RuntimeError("stage failed")

        first = self.jobs.submit("analysis", {}, "revision-1", execute)
        self.assertEqual(self.jobs.wait(first["id"], 5)["status"], "failed")
        second = self.jobs.submit("analysis", {}, "revision-2", execute)
        self.assertNotEqual(first["id"], second["id"])
        self.jobs.wait(second["id"], 5)

    def test_blocked_pipeline_is_not_labelled_completed(self):
        job = self.jobs.submit("network", {}, "v1", lambda *args: {"status": "blocked", "reason": "service absent"})
        self.assertEqual(self.jobs.wait(job["id"], 5)["status"], "blocked")

    def test_dead_owner_is_reported_interrupted_instead_of_running_forever(self):
        job = self.jobs.submit("analysis", {}, "v1", lambda *args: {"value": 1})
        self.jobs.wait(job["id"], 5)
        with self.jobs.db() as db:
            db.execute("UPDATE jobs SET status='running', owner=? WHERE id=?", (1073741824, job["id"]))
        self.assertEqual(self.jobs.get(job["id"])["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
