#!/usr/bin/env python3
"""TD-D2: тесты канонического plugin-aware doctor и health_check-обёртки.

Покрывает:
  - живой bridge.hello / harness.status probe на реальном дереве;
  - protocol.compat (TS literal == Python PROTOCOL) и мутацию рассогласования;
  - fail-closed вердикт doctor на сломанном дереве (отсутствует snapshot);
  - делегирование health_check.py (идентичный JSON-вердикт, exit-контракт);
  - гейт check_health_canonical.py PASS на HEAD и FAIL на мутациях
    (legacy-логика в обёртке, потеря live-probe в doctor).

Запуск: python3 -m unittest tests.test_health_doctor -v  (из корня репо)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "packages" / "opencode-harness-plugin" / "core" / "doctor.py"
HEALTH = ROOT / "scripts" / "health_check.py"
GATE = ROOT / "scripts" / "tools" / "check_health_canonical.py"


def run_py(script: Path, root: Path, extra_env: dict | None = None):
    env = {"OPENCODE_HARNESS_ROOT": str(root), "PATH": "/usr/bin:/bin",
           "HOME": str(Path.home()), "SYSTEMROOT": str(Path("C:/windows"))}
    if extra_env:
        env.update(extra_env)
    return subprocess.run([sys.executable, str(script)], capture_output=True,
                          text=True, timeout=180, cwd=str(root), env=env)


def extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def minimal_tree(dst: Path) -> Path:
    """Копия минимально необходимых файлов реального дерева в tmp-корень."""
    rels = [
        "config/runtime_snapshot.json",
        "config/capability_runtime_snapshot.json",
        "packages/opencode-harness-plugin/package.json",
        "packages/opencode-harness-plugin/core/doctor.py",
        "packages/opencode-harness-plugin/core/bridge_peer.py",
        "packages/opencode-harness-plugin/src/bridge/protocol.ts",
        "scripts/router/resolve_route.py",
        "scripts/health_check.py",
        "scripts/tools/check_health_canonical.py",
    ]
    for r in rels:
        src = ROOT / r
        dstf = dst / r
        dstf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dstf)
    (dst / ".opencode").mkdir(exist_ok=True)
    proj = {
        "$schema": "https://opencode.ai/config.json",
        "plugin": [f"file://{(dst / 'packages/opencode-harness-plugin/dist/index.js').as_posix()}"],
    }
    (dst / ".opencode" / "opencode.json").write_text(json.dumps(proj), encoding="utf-8")
    return dst


class DoctorLiveProbesOnRealTree(unittest.TestCase):
    def test_doctor_passes_on_real_tree(self):
        r = run_py(DOCTOR, ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = extract_json(r.stdout)
        names = {c["check"]: c for c in d["checks"]}
        self.assertTrue(names["bridge.handshake"]["ok"])
        self.assertTrue(names["core.health"]["ok"])
        self.assertTrue(names["protocol.compat"]["ok"])
        self.assertTrue(d["ok"])
        self.assertFalse(d["conflict"])

    def test_protocol_compat_detects_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            tree = minimal_tree(Path(td))
            ts = tree / "packages/opencode-harness-plugin/src/bridge/protocol.ts"
            ts.write_text(ts.read_text(encoding="utf-8").replace(
                '"harness-bridge-rpc/1.0"', '"harness-bridge-rpc/9.9"'), encoding="utf-8")
            r = run_py(DOCTOR, tree)
            d = extract_json(r.stdout)
            names = {c["check"]: c for c in d["checks"]}
            self.assertIn("MISMATCH", names["protocol.compat"]["detail"])
            self.assertFalse(names["protocol.compat"]["ok"])
            self.assertEqual(r.returncode, 1, "протокольный дрейф должен валить doctor (fail-closed)")

    def test_broken_tree_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            tree = minimal_tree(Path(td))
            (tree / "config/runtime_snapshot.json").unlink()
            r = run_py(DOCTOR, tree)
            d = extract_json(r.stdout)
            names = {c["check"]: c for c in d["checks"]}
            self.assertFalse(names["runtime_snapshot"]["ok"])
            self.assertFalse(names["bridge.handshake"]["ok"])  # skipped->blocking fail
            self.assertEqual(r.returncode, 1)


class HealthCheckWrapper(unittest.TestCase):
    def test_wrapper_delegates_and_matches_verdict(self):
        rd = run_py(DOCTOR, ROOT)
        rh = run_py(HEALTH, ROOT)
        self.assertEqual(rd.returncode, rh.returncode)
        dd = extract_json(rd.stdout)
        dh = extract_json(rh.stdout)
        dd.pop("core_root"); dh.pop("core_root")
        self.assertEqual(dd, dh)
        self.assertIn("Overall: HEALTHY", rh.stdout)

    def test_wrapper_has_no_legacy_checks(self):
        src = HEALTH.read_text(encoding="utf-8")
        for legacy in ("sqlite3", "OPENCODE_SESSION_DB", "check_db_accessible"):
            self.assertNotIn(legacy, src)


class GateScript(unittest.TestCase):
    def test_gate_pass_on_head(self):
        r = run_py(GATE, ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout)

    def test_gate_fails_on_legacy_regression(self):
        with tempfile.TemporaryDirectory() as td:
            tree = minimal_tree(Path(td))
            hc = tree / "scripts/health_check.py"
            hc.write_text(hc.read_text(encoding="utf-8") +
                          "\n# regression\nimport sqlite3\nOPENCODE_SESSION_DB='x'\n", encoding="utf-8")
            r = run_py(tree / "scripts/tools/check_health_canonical.py", tree)
            self.assertEqual(r.returncode, 1)
            self.assertIn("I1", r.stdout)

    def test_gate_fails_when_live_probe_removed(self):
        with tempfile.TemporaryDirectory() as td:
            tree = minimal_tree(Path(td))
            dr = tree / "packages/opencode-harness-plugin/core/doctor.py"
            dr.write_text(dr.read_text(encoding="utf-8").replace("bridge.hello", "bridge.removed"),
                          encoding="utf-8")
            r = run_py(tree / "scripts/tools/check_health_canonical.py", tree)
            self.assertEqual(r.returncode, 1)
            self.assertIn("I2", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
