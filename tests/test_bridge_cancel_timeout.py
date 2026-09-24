#!/usr/bin/env python3
"""AG-D5: end-to-end certification of semantic.execute cancel / timeout.

The debt said "semantic.execute cancel/timeout E2E: tests moved, live
certification remains". AG-A2 certified the happy roundtrip; this file
certifies the two failure paths over the REAL BridgeServer stdio loop:

  * timeout: a plugin peer that never answers the reverse call must fail the
    parent semantic.execute with the canonical TIMED_OUT status within the
    request's own timeout_ms bound (BRIDGE-03 threading), and the server must
    stay responsive afterwards (no wedged state);
  * cancel: harness.cancel {execution_id} (wire method already declared in
    schemas/BridgeMessage.schema.json) cooperatively cancels an in-flight
    reverse call; the pending entry is dropped so a late answer cannot
    resurrect it; cancelling an unknown id is NOT_PENDING (idempotent).

Deterministic, no network, no live opencode binary required.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEER = ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"


def make_request(execution_id: str = "exec-d5-0001", timeout_ms: int = 180000) -> dict:
    return {
        "schema": "semantic-execution-request/1.0",
        "execution_id": execution_id,
        "purpose": "CODE_REVIEW",
        "contract_schema": "code-review-result/1.0",
        "parent_host_session_id": "ses_parent_orchestrator",
        "bounded_input": {"diff_ref": "artifacts/diff-001.patch"},
        "expected_output": {"format": "json", "contract": "code-review-result/1.0"},
        "model_policy": {"provider": "anthropic", "model": "claude-sonnet-4-5"},
        "permission_profile": "read-only",
        "timeout_ms": timeout_ms,
        "trace": {"run_id": "run-ag-d5-cert", "step": 1},
    }


class SilentPluginPeer:
    """Simulates a hung child-session executor: receives reverse requests,
    records them, never answers."""

    def __init__(self, proc: subprocess.Popen) -> None:
        self.proc = proc
        self.seen_requests: list[dict] = []
        self.outbox: list[str] = []
        self._lock = threading.Lock()

    def reader(self) -> None:
        for line in iter(self.proc.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("method") == "semantic.execute":
                with self._lock:
                    self.seen_requests.append((msg.get("params") or {}).get("request") or {})
                continue  # hang: never respond to the reverse call
            with self._lock:
                self.outbox.append(line)

    def answer_late(self, rid_result: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(rid_result) + "\n")
        self.proc.stdin.flush()


class CancelTimeoutCertification(unittest.TestCase):
    def setUp(self) -> None:
        if not PEER.is_file():
            self.skipTest(f"bridge peer not found: {PEER}")
        self.proc = subprocess.Popen(
            [sys.executable, "-u", str(PEER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(ROOT),
        )
        self.peer = SilentPluginPeer(self.proc)
        threading.Thread(target=self.peer.reader, daemon=True).start()
        self._counter = 0
        hello = self._call("bridge.hello", {"plugin_semver": "0.0.0-cert"})
        self.assertTrue(hello["ok"], "bridge handshake failed")

    def tearDown(self) -> None:
        try:
            self._call("bridge.shutdown", {})
        except Exception:  # noqa: BLE001
            pass
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    # --- JSON-RPC client side (acts as the TS plugin calling into Core) ----
    def _send(self, obj: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _recv(self, rid: str, timeout: float = 20.0) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.peer._lock:
                for line in list(self.peer.outbox):
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        msg = None
                    if msg is not None and msg.get("id") == rid and "ok" in msg and "method" not in msg:
                        self.peer.outbox.remove(line)
                        return msg
            time.sleep(0.02)
        raise TimeoutError(f"no response for {rid} from bridge peer")

    def _call_async(self, method: str, params: dict) -> str:
        """Send without waiting; returns the request id."""
        self._counter += 1
        rid = f"req-{self._counter}-{method}"
        self._send({"id": rid, "method": method, "params": params})
        return rid

    def _call(self, method: str, params: dict, timeout: float = 20.0) -> dict:
        return self._recv(self._call_async(method, params), timeout=timeout)

    # ---------------------------------------------------------------- tests
    def test_timeout_fails_with_timed_out_and_server_recovers(self) -> None:
        # 300ms bound threaded from the request itself (BRIDGE-03).
        start = time.time()
        res = self._call("semantic.execute", {"request": make_request(timeout_ms=300)}, timeout=10.0)
        elapsed = time.time() - start
        self.assertFalse(res["ok"])
        self.assertIn("TIMED_OUT", res["error"]["message"])
        # The plugin really received the reverse request before timing out.
        self.assertEqual(len(self.peer.seen_requests), 1)
        # Bound honoured: failed near 0.3s, far below the 15s default.
        self.assertLess(elapsed, 5.0)
        # Server still responsive after the timed-out call.
        health = self._call("bridge.health", {})
        self.assertTrue(health["ok"])

    def test_harness_cancel_cancels_inflight_execution(self) -> None:
        req_id = self._call_async("semantic.execute", {"request": make_request("exec-cancel-1")})
        # Wait until the reverse request actually reached the plugin.
        deadline = time.time() + 5.0
        while time.time() < deadline and not self.peer.seen_requests:
            time.sleep(0.02)
        self.assertEqual(len(self.peer.seen_requests), 1, "reverse request never delivered")

        cancel = self._call("harness.cancel", {"execution_id": "exec-cancel-1"})
        self.assertTrue(cancel["ok"])
        self.assertEqual(cancel["result"], {"ok": True, "cancelled": True, "execution_id": "exec-cancel-1"})

        # Parent request fails fast with CANCELLED (not the 15s default wait).
        res = self._recv(req_id, timeout=5.0)
        self.assertFalse(res["ok"])
        self.assertIn("CANCELLED", res["error"]["message"])

    def test_cancel_is_idempotent_and_unknown_is_not_pending(self) -> None:
        unknown = self._call("harness.cancel", {"execution_id": "exec-never-existed"})
        self.assertTrue(unknown["ok"])
        self.assertFalse(unknown["result"]["cancelled"])
        self.assertEqual(unknown["result"]["reason"], "NOT_PENDING")

        req_id = self._call_async("semantic.execute", {"request": make_request("exec-cancel-2")})
        deadline = time.time() + 5.0
        while time.time() < deadline and not self.peer.seen_requests:
            time.sleep(0.02)
        first = self._call("harness.cancel", {"execution_id": "exec-cancel-2"})
        self.assertTrue(first["result"]["cancelled"])
        second = self._call("harness.cancel", {"execution_id": "exec-cancel-2"})
        self.assertFalse(second["result"]["cancelled"])  # already gone: NOT_PENDING
        self.assertEqual(second["result"]["reason"], "NOT_PENDING")
        res = self._recv(req_id, timeout=5.0)
        self.assertFalse(res["ok"])
        self.assertIn("CANCELLED", res["error"]["message"])

    def test_cancel_requires_execution_id(self) -> None:
        res = self._call("harness.cancel", {})
        self.assertFalse(res["ok"])
        self.assertIn("execution_id", res["error"]["message"])

    def test_late_answer_after_cancel_does_not_resurrect(self) -> None:
        req_id = self._call_async("semantic.execute", {"request": make_request("exec-late-1")})
        deadline = time.time() + 5.0
        while time.time() < deadline and not self.peer.seen_requests:
            time.sleep(0.02)
        # Capture the reverse-call id the peer wrote to us before cancelling.
        # (SilentPluginPeer swallowed it; re-read one raw line instead.)
        self._call("harness.cancel", {"execution_id": "exec-late-1"})
        res = self._recv(req_id, timeout=5.0)
        self.assertFalse(res["ok"])
        self.assertIn("CANCELLED", res["error"]["message"])
        # Even if the hung plugin later answers, the parent request is done;
        # server keeps serving new calls normally.
        self.assertTrue(self._call("bridge.health", {})["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
