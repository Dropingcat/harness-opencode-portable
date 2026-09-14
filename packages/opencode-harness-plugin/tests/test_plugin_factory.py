"""
Fake-host plugin factory E2E: simulate PluginInput and call the plugin factory,
verifying the tool map (harness_status / harness_run) exists and executes through
the real Python bridge peer.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def harness_root() -> Path:
    env = os.environ.get("OPENCODE_HARNESS_ROOT")
    if env:
        return Path(env)
    return ROOT.parents[0]


def test_plugin_factory_returns_tools() -> None:
    """The factory module (compiled JS) must export a Plugin function returning a tool map."""
    pkg = ROOT / "dist" / "index.js"
    assert pkg.is_file(), f"dist/index.js missing; run npx tsc first ({pkg})"
    code = pkg.read_text(encoding="utf-8")
    assert "export default" in code or "export {" in code
    assert "harness_status" in code
    assert "harness_run" in code


def test_bridge_peer_hello_and_status() -> None:
    """Drive the Python bridge peer directly with NDJSON lines on stdin."""
    root = harness_root()
    peer = ROOT / "core" / "bridge_peer.py"
    env = dict(os.environ)
    env["OPENCODE_HARNESS_ROOT"] = str(root)
    proc = subprocess.Popen(
        [sys.executable, str(peer)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert proc.stdin and proc.stdout

    def call(method: str, params: dict) -> dict:
        req = json.dumps({"id": "t1", "method": method, "params": params})
        proc.stdin.write(req + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        return json.loads(line)

    try:
        hello = call("bridge.hello", {"plugin_semver": "0.1.0"})
        assert hello["ok"] is True
        assert hello["result"]["schema"] == "harness-bridge-rpc/1.0"
        assert "harness.status" in hello["result"]["core_api_supported"]

        status = call("harness.status", {})
        assert status["ok"] is True
        assert status["result"]["runtime_policy_present"] is True

        run = call("harness.run", {"task": "проверить литературу по теме статьи"})
        assert run["ok"] is True
        result = run["result"]["result"]
        assert isinstance(result, dict)
        assert "route_id" in result or "bucket" in result
    finally:
        proc.stdin.write(json.dumps({"id": "bye", "method": "bridge.shutdown", "params": {}}) + "\n")
        proc.stdin.flush()
        proc.stdin.close()
        proc.wait(timeout=10)


def test_doctor_report() -> None:
    """Doctor must produce a machine-readable report."""
    root = harness_root()
    doctor = ROOT / "core" / "doctor.py"
    env = dict(os.environ)
    env["OPENCODE_HARNESS_ROOT"] = str(root)
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "doctor.json"
        proc = subprocess.run(
            [sys.executable, str(doctor), "--report", str(report)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        assert report.is_file()
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["schema"] == "harness-opencode-plugin-doctor/1.0"
        assert data["checks"]


def test_installer_report(tmp_path: Path) -> None:
    """Installer must copy the entry to the project plugin dir and write a report."""
    root = harness_root()
    installer = ROOT / "core" / "install_plugin.py"
    env = dict(os.environ)
    env["OPENCODE_HARNESS_ROOT"] = str(root)
    report = tmp_path / "install.json"
    proc = subprocess.run(
        [sys.executable, str(installer), "--target", "project", "--report", str(report)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["schema"] == "harness-opencode-plugin-install/1.0"
    installed = Path(data["installed"])
    assert installed.is_file()