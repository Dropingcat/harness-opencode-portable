# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "writer" / "cli.py"
OLD_DRAFT = ROOT / "scripts" / "writer" / "draft_loop.py"
OLD_TRACE = ROOT / "scripts" / "writer" / "citation_trace.py"
VERIFY = ROOT / "scripts" / "researcher" / "verify_claims.py"


def run_path(path: Path, *args: str):
    return subprocess.run([sys.executable, str(path), *args], cwd=ROOT,
                          capture_output=True, text=True)


def run_module(module: str, *args: str):
    return subprocess.run([sys.executable, "-m", module, *args], cwd=ROOT,
                          capture_output=True, text=True)


class WriterPhase5GateMoveTests(unittest.TestCase):
    def test_canonical_gate_modules_import(self):
        draft = importlib.import_module("scripts.writer.drafting.draft_loop")
        trace = importlib.import_module("scripts.writer.review.citation_trace")
        self.assertTrue(callable(draft.main))
        self.assertTrue(callable(trace.run))
        self.assertTrue(callable(trace.main))

    def test_legacy_gate_paths_are_thin_shims(self):
        draft = OLD_DRAFT.read_text(encoding="utf-8")
        trace = OLD_TRACE.read_text(encoding="utf-8")
        self.assertIn("Compatibility shim", draft)
        self.assertIn("scripts.writer.drafting", draft)
        self.assertIn("Compatibility shim", trace)
        self.assertIn("scripts.writer.review", trace)
        self.assertLess(len(draft.splitlines()), 40)
        self.assertLess(len(trace.splitlines()), 40)

    def test_draft_direct_path_and_canonical_module_argparse_parity(self):
        old = run_path(OLD_DRAFT)
        new = run_module("scripts.writer.drafting.draft_loop")
        self.assertEqual((new.returncode, new.stdout, new.stderr),
                         (old.returncode, old.stdout, old.stderr))

    def test_trace_direct_path_and_canonical_module_argparse_parity(self):
        old = run_path(OLD_TRACE)
        new = run_module("scripts.writer.review.citation_trace")
        self.assertEqual((new.returncode, new.stdout, new.stderr),
                         (old.returncode, old.stdout, old.stderr))

    def test_public_cli_dispatches_internal_gate_modules(self):
        text = CLI.read_text(encoding="utf-8")
        self.assertIn('"draft-loop": "scripts.writer.drafting.draft_loop"', text)
        self.assertIn('"citation-trace": "scripts.writer.review.citation_trace"', text)
        self.assertNotIn('"draft-loop": _HARNESS_ROOT', text)
        self.assertNotIn('"citation-trace": _HARNESS_ROOT', text)

    def test_research_verification_remains_external_shared_authority(self):
        text = CLI.read_text(encoding="utf-8")
        self.assertIn('"verify-claims": _HARNESS_ROOT / "scripts" / "researcher" / "verify_claims.py"', text)
        self.assertTrue(VERIFY.is_file())
        self.assertFalse((ROOT / "scripts" / "writer" / "verify_claims.py").exists())

    def test_core_review_uses_canonical_trace_module(self):
        review = (ROOT / "scripts" / "writer" / "core" / "review.py").read_text(encoding="utf-8")
        self.assertIn("from scripts.writer.review.citation_trace import run as _ct_run", review)
        self.assertNotIn("from scripts.writer.citation_trace import run as _ct_run", review)

    def test_internal_draft_gate_does_not_mutate_sys_path(self):
        text = (ROOT / "scripts" / "writer" / "drafting" / "draft_loop.py").read_text(encoding="utf-8")
        self.assertNotIn("sys.path.insert", text)
        self.assertIn("from scripts.writer.extractor import extract_all, build_graphs", text)

    def test_unknown_cli_command_remains_fail_closed(self):
        r = run_path(CLI, "not-a-writer-command")
        self.assertEqual(r.returncode, 2)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["fail_closed"])


if __name__ == "__main__":
    unittest.main()
