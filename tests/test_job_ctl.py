#!/usr/bin/env python3
"""Smoke-тесты канонического Job/Attempt runtime `scripts/jobs/job_ctl.py` (TD-D7).

Проверяют полный жизненный цикл job: init -> attempt-start -> heartbeat ->
artifact -> stage -> gate -> child -> complete, а также reject-путь reconcile
и event-hash chain. Запуск:  python3 tests/test_job_ctl.py  (stdlib unittest, без зависимостей).

Host-ref mapping (документирование части TD-D7):
    OpenCode session id != Harness Job id. Сессия хоста коррелируется с Job
    только через metadata: `attempt.external_task_id` (уникален в пределах job)
    и артефакты. Сам Job ID создаётся оркестратором, а не хостом.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOB_CTL = ROOT / "scripts" / "jobs" / "job_ctl.py"


def run_ctl(state: Path, *args: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(JOB_CTL), "--state", str(state), *args],
        capture_output=True, text=True,
    )
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        out = {"raw": proc.stdout, "stderr": proc.stderr}
    return proc.returncode, out


class JobCtlSmokeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state = self.dir / "job_state.json"
        contract = self.dir / "contract.json"
        contract.write_text(json.dumps({"goal": "smoke", "acceptance": ["ok"]}), encoding="utf-8")
        rc, out = run_ctl(self.state, "init", "JOB-SMOKE-1",
                          "--contract", str(contract), "--stages", "plan,execute,review")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["ok"])
        self.assertEqual(out["job_id"], "JOB-SMOKE-1")
        self.assertIn("contract_hash", out)

    def tearDown(self):
        self.tmp.cleanup()

    # --- basics -------------------------------------------------------------
    def test_status_and_event_chain(self):
        rc, out = run_ctl(self.state, "status")
        self.assertEqual(rc, 0, out)
        job = out["job"]
        self.assertEqual(job["schema"], "research-job/1.1")
        self.assertEqual(job["status"], "RUNNING")
        self.assertEqual(set(job["stages"]), {"plan", "execute", "review"})
        # hash-chain integrity of events
        prev = None
        for e in job["events"]:
            self.assertEqual(e["prev_hash"], prev)
            recomputed = {k: v for k, v in e.items() if k != "hash"}
            import hashlib
            h = hashlib.sha256(json.dumps(recomputed, sort_keys=True,
                                          separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(e["hash"], h)
            prev = e["hash"]

    def test_unknown_stage_rejected(self):
        rc, out = run_ctl(self.state, "attempt-start", "--agent", "coder-worker", "--stage", "nope")
        self.assertNotEqual(rc, 0)
        self.assertFalse(out["ok"])
        self.assertIn("unknown stage", out["error"])

    # --- full happy path ----------------------------------------------------
    def test_full_lifecycle_complete(self):
        rc, out = run_ctl(self.state, "attempt-start", "--agent", "coder-worker",
                          "--stage", "execute", "--external-task-id", "ses_abc123")
        self.assertEqual(rc, 0, out)
        aid = out["attempt_id"]

        rc, out = run_ctl(self.state, "heartbeat", aid, "--stage", "execute", "--done", "3", "--total", "5")
        self.assertEqual(rc, 0, out)

        art = self.dir / "result.py"
        art.write_text("print('ok')\n", encoding="utf-8")
        rc, out = run_ctl(self.state, "artifact", "res_py", str(art), "--required")
        self.assertEqual(rc, 0, out)

        rc, out = run_ctl(self.state, "attempt-finish", aid, "COMPLETED", "--artifact", "res_py")
        self.assertEqual(rc, 0, out)

        for st in ("plan", "execute", "review"):
            rc, out = run_ctl(self.state, "stage", st, "COMPLETED")
            self.assertEqual(rc, 0, out)

        rc, out = run_ctl(self.state, "child-add", "CH-1", "--mode", "required",
                          "--external-task-id", "ses_child1")
        self.assertEqual(rc, 0, out)
        rc, out = run_ctl(self.state, "child-finish", "CH-1", "COMPLETED")
        self.assertEqual(rc, 0, out)

        rc, out = run_ctl(self.state, "gate", "quality", "PASS", "--required")
        self.assertEqual(rc, 0, out)

        rc, out = run_ctl(self.state, "reconcile")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["reconciliation"]["ok"], out["reconciliation"])

        rc, out = run_ctl(self.state, "complete")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out["status"], "COMPLETED")

        # artifact sha auto-computed
        _, st = run_ctl(self.state, "status")
        import hashlib
        self.assertEqual(st["job"]["artifacts"]["res_py"]["sha256"],
                         hashlib.sha256(art.read_bytes()).hexdigest())
        # external_task_id correlation documented as metadata (host session != job id)
        att = st["job"]["attempts"][0]
        self.assertEqual(att["external_task_id"], "ses_abc123")

    # --- failure paths ------------------------------------------------------
    def test_complete_rejected_when_incomplete(self):
        rc, out = run_ctl(self.state, "gate", "quality", "FAIL", "--required")
        self.assertEqual(rc, 0, out)
        rc, out = run_ctl(self.state, "complete")
        self.assertEqual(rc, 4)
        self.assertEqual(out["error"], "COMPLETION_REJECTED")
        self.assertIn("quality", out["reconciliation"]["failed_required_gates"])

    def test_duplicate_external_task_id_rejected(self):
        rc, out = run_ctl(self.state, "attempt-start", "--agent", "a", "--stage", "plan",
                          "--external-task-id", "dup")
        self.assertEqual(rc, 0, out)
        rc, out = run_ctl(self.state, "attempt-start", "--agent", "b", "--stage", "plan",
                          "--external-task-id", "dup")
        self.assertNotEqual(rc, 0)
        self.assertIn("already used", out["error"])

    def test_missing_state_file_error(self):
        rc, out = run_ctl(self.dir / "nonexistent.json", "status")
        self.assertNotEqual(rc, 0)
        self.assertFalse(out["ok"])

    def test_failed_attempt_sets_degraded(self):
        rc, out = run_ctl(self.state, "attempt-start", "--agent", "w", "--stage", "execute")
        aid = out["attempt_id"]
        rc, out = run_ctl(self.state, "attempt-finish", aid, "FAILED")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out["job_status"], "DEGRADED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
