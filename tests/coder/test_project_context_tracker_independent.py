"""Independent stage-0 boundary probes; canonical data is read-only."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("independent_context", ROOT / "scripts/orchestration/project_context.py")
CTX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CTX)


class IndependentContextTests(unittest.TestCase):
    def test_source_and_failure_matrix(self):
        accepted = json.loads((ROOT / "config/development_tracker.json").read_text(encoding="utf-8-sig"))
        cases = [("structured_only", accepted, False), ("both", accepted, True),
                 ("legacy_only", None, True), ("neither", None, False),
                 ("malformed", "{bad", True), ("wrongshape", [], True),
                 ("duplicate_key", '{"counts":{},"counts":{}}', True)]
        duplicate = copy.deepcopy(accepted)
        duplicate["dev_items"].append(copy.deepcopy(duplicate["dev_items"][0]))
        drift = copy.deepcopy(accepted)
        drift["counts"]["dev_done"] += 1
        cases += [("duplicate_id", duplicate, True), ("count_drift", drift, True)]
        for name, data, legacy in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                if data is not None:
                    (root / "config/development_tracker.json").write_text(
                        data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
                if legacy:
                    (root / "IMPLEMENTATION_TRACKER.md").write_text("### Sentinel\n- [ ] LEGACY_SENTINEL\n", encoding="utf-8")
                evil = root / "scripts/tools/check_development_tracker.py"
                evil.parent.mkdir(parents=True)
                evil.write_text("raise AssertionError('DATA_ROOT_CODE_IMPORTED')", encoding="utf-8")
                def snapshot():
                    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in root.rglob("*") if p.is_file()}
                before = snapshot()
                result = CTX.tracker(root)
                self.assertEqual(before, snapshot())
                if name in ("structured_only", "both"):
                    self.assertEqual(result["validation"], "PASS")
                    self.assertNotIn("LEGACY_SENTINEL", json.dumps(result))
                    declared = {x["id"]: x for x in result["declared_items"]}
                    current = result["current_host_readiness"]
                    for ident in ("DEV-03", "DEV-04"):
                        self.assertEqual(declared[ident]["status"], "done")
                        self.assertIn("1.18", declared[ident]["completion_scope"])
                        self.assertIn(ident, current["pending_ids"])
                        self.assertIn(ident, [x["ws"] for x in result["open_items"]])
                    self.assertEqual(current["host_versions"], ["2.0.29"])
                elif name == "legacy_only":
                    self.assertEqual(result["source_format"], "legacy_markdown")
                    self.assertEqual(result["open_items"], [{"ws": "Sentinel", "item": "LEGACY_SENTINEL"}])
                elif name == "neither":
                    self.assertIn("error", result)
                    self.assertNotIn("open_items", result)
                else:
                    self.assertEqual(result["validation"], "FAIL")
                    self.assertNotIn("open_items", result)
                    self.assertNotIn("LEGACY_SENTINEL", json.dumps(result))

    def test_workspace_cli_canonical_readonly_utf8(self):
        canonical = Path("E:/opencode_harness_portable")
        paths = [canonical / name for name in (
            "config/development_tracker.json", "IMPLEMENTATION_TRACKER.md",
            "config/tech_debt.json", "config/memory_registry.json", ".runs/factory_state.json", ".kanban.db")]
        before = {str(p): p.read_bytes() for p in paths if p.is_file()}
        bootstrap = '''import os, runpy, sys
def audit(event, args):
    if event == "open":
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise AssertionError("file write attempted")
    if event in ("os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.chmod", "os.utime", "os.link", "os.symlink", "os.truncate"):
        raise AssertionError("filesystem mutation attempted")
    if event == "sqlite3.connect" and not os.path.isfile(args[0]):
        raise AssertionError("database creation attempted")
sys.addaudithook(audit)
runpy.run_path(sys.argv[1], run_name="__main__")
'''
        env = dict(os.environ, OPENCODE_HARNESS_ROOT=str(canonical), PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "-B", "-c", bootstrap,
                               str(ROOT / "scripts/orchestration/project_context.py")],
                              env=env, capture_output=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", errors="replace"))
        result = json.loads(proc.stdout.decode("utf-8", errors="strict"))
        self.assertEqual(Path(result["root"]), canonical)
        tracker = result["tracker"]
        self.assertEqual(tracker["validation"], "PASS")
        self.assertEqual(Path(tracker["source"]), canonical / "config/development_tracker.json")
        self.assertEqual(tracker["counts"]["dev_done"], 3)
        self.assertTrue({"DEV-03", "DEV-04"}.issubset(tracker["current_host_readiness"]["pending_ids"]))
        self.assertEqual(before, {str(p): p.read_bytes() for p in paths if p.is_file()})


if __name__ == "__main__":
    unittest.main()
