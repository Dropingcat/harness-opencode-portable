# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "writer" / "cli.py"
DRAFT = ROOT / "scripts" / "writer" / "draft_loop.py"
TRACE = ROOT / "scripts" / "writer" / "citation_trace.py"
VERIFY = ROOT / "scripts" / "researcher" / "verify_claims.py"


def run(path: Path, *args: str):
    return subprocess.run([sys.executable, str(path), *args], cwd=ROOT,
                          capture_output=True, text=True)


class WriterPublicCliTests(unittest.TestCase):
    def test_help(self):
        r = run(CLI, "--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("draft-loop", r.stdout)
        self.assertIn("citation-trace", r.stdout)
        self.assertIn("verify-claims", r.stdout)
        self.assertIn("plan", r.stdout)

    def test_unknown_command_is_fail_closed_json(self):
        r = run(CLI, "definitely-not-a-command")
        self.assertEqual(r.returncode, 2)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["fail_closed"])
        self.assertIn("unknown command", payload["error"])

    def test_core_invalid_input_is_fail_closed(self):
        new = run(CLI, "plan")
        self.assertEqual(2, new.returncode)
        payload = json.loads(new.stdout)
        self.assertTrue(payload["fail_closed"])

    def test_core_topic_plan_through_canonical_cli(self):
        with tempfile.TemporaryDirectory() as td:
            out = str(Path(td) / "new.json")
            new = run(CLI, "plan", "--topic", "тестовая тема", "--out", out)
            self.assertEqual(0, new.returncode, new.stderr + new.stdout)
            self.assertEqual("plan", json.loads(new.stdout)["command"])
            payload = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertIsInstance(payload, dict)

    def test_draft_loop_argparse_parity(self):
        old = run(DRAFT)
        new = run(CLI, "draft-loop")
        self.assertEqual(new.returncode, old.returncode)
        self.assertEqual(new.stdout, old.stdout)
        self.assertEqual(new.stderr, old.stderr)

    def test_citation_trace_argparse_parity(self):
        old = run(TRACE)
        new = run(CLI, "citation-trace")
        self.assertEqual(new.returncode, old.returncode)
        self.assertEqual(new.stdout, old.stdout)
        self.assertEqual(new.stderr, old.stderr)

    def test_verify_claims_argparse_parity(self):
        old = run(VERIFY)
        new = run(CLI, "verify-claims")
        self.assertEqual(new.returncode, old.returncode)
        self.assertEqual(new.stdout, old.stdout)
        self.assertEqual(new.stderr, old.stderr)

    def test_all_core_commands_are_declared_in_facade(self):
        text = CLI.read_text(encoding="utf-8")
        for cmd in ("plan", "draftcheck", "live-cycle", "extract", "graphs", "annotate",
                    "consolidate", "vectorsim", "dom", "review", "uncertainty", "register"):
            self.assertIn(f'"{cmd}"', text)


if __name__ == "__main__":
    unittest.main()
