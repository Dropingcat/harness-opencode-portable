#!/usr/bin/env python3
"""Harness bridge peer (Core side) for harness-bridge-rpc/1.0.

Serves a line-delimited JSON-RPC over stdio to the OpenCode plugin (TS).
Full duplex: the peer can also issue reverse requests (reserved semantic.execute).

Protocol: harness-bridge-rpc/1.0
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict

PROTOCOL = "harness-bridge-rpc/1.0"
CONTRACT_SCHEMAS = [
    "host-context/1.0",
    "workspace-ref/1.0",
    "semantic-execution-request/1.0",
    "semantic-execution-result/1.0",
]

# Default reverse-call timeout when the request carries no usable timeout_ms.
_REVERSE_TIMEOUT_MS_DEFAULT = 15000
# Upper bound for a request's timeout_ms threaded into the reverse call.
_REVERSE_TIMEOUT_MS_CAP = 120000


def _request_timeout_ms(request: Any) -> int | None:
    """Request timeout_ms for the reverse call, capped, else None (default).

    Only a positive int (bool is not an int for this purpose) is honoured.
    ``None`` means "use the peer's default reverse timeout".
    """
    if isinstance(request, dict):
        value = request.get("timeout_ms")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return min(value, _REVERSE_TIMEOUT_MS_CAP)
    return None


def _harness_root() -> Path:
    env = __import__("os").environ.get("OPENCODE_HARNESS_ROOT")
    if env:
        return Path(env)
    # <root>/packages/opencode-harness-plugin/core/bridge_peer.py -> parents[3] == <root>
    return Path(__file__).resolve().parents[3]


class BridgeServer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self.reverse_request: Callable[[str, Dict[str, Any]], Any] | None = None
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.handlers["bridge.hello"] = self._hello
        self.handlers["bridge.health"] = self._health
        self.handlers["bridge.shutdown"] = lambda _: self._shutdown()
        self.handlers["bridge.reverse_echo_test"] = self._reverse_echo_test
        self.handlers["harness.status"] = self._status
        self.handlers["harness.run"] = self._run
        self.handlers["semantic.execute"] = self._semantic_execute

    def _semantic_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Forward a SemanticExecutionRequest/1.0 to the plugin via reverse RPC.

        The plugin owns model execution (child session); this peer only carries
        the request and returns whatever the plugin produced. No result is
        generated here.

        BRIDGE-03: the request's canonical ``timeout_ms`` (required field,
        default 180000) is threaded into the reverse call (capped at
        ``_REVERSE_TIMEOUT_MS_CAP``) so a healthy plugin that legitimately
        takes longer than the old hardcoded 15s is NOT failed as a fabricated
        host failure.
        """
        if not self.reverse_request:
            raise RuntimeError("reverse_request not configured")
        request = params.get("request")
        if request is None:
            raise ValueError("semantic.execute requires params.request")
        timeout_ms = _request_timeout_ms(request)
        raw = self._send_reverse("semantic.execute", {"request": request}, timeout_ms=timeout_ms)
        if isinstance(raw, dict) and "tool_result" in raw:
            return {"semantic_result": raw["tool_result"]}
        return {"semantic_result": raw}

    def _hello(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "schema": PROTOCOL,
            "plugin_semver": params.get("plugin_semver", "unknown"),
            "bridge_protocol_supported": [PROTOCOL],
            "core_api_supported": ["harness.status", "harness.run"],
            "contract_schemas": CONTRACT_SCHEMAS,
            "core_root": str(self.root),
        }

    def _health(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        ok = (self.root / "config").is_dir()
        return {
            "ok": ok,
            "core_root": str(self.root),
            "detail": "config-present" if ok else "config-missing",
        }

    def _status(self, _params: Dict[str, Any]) -> Dict[str, Any]:
        # Deterministic: report plugin/core state without semantic execution.
        runtime = self.root / "config" / "runtime_snapshot.json"
        capability = self.root / "config" / "capability_runtime_snapshot.json"
        return {
            "ok": True,
            "core_root": str(self.root),
            "runtime_policy_present": runtime.is_file(),
            "capability_policy_present": capability.is_file(),
            "protocol": PROTOCOL,
        }

    def _run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Deterministic Harness route/bundle path only. No semantic execution.
        try:
            return self._run_deterministic(params)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": {"code": "CORE_ERROR", "message": str(exc)}}

    def _run_deterministic(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import sys as _sys

        scripts_dir = str(self.root / "scripts")
        if scripts_dir not in _sys.path:
            _sys.path.insert(0, scripts_dir)

        task = params.get("task") or ""
        route = params.get("route")
        profile = params.get("profile")

        from router.resolve_route import resolve

        hints: Dict[str, Any] = {}
        if route:
            hints["route_id"] = route
        if profile:
            hints["preferred_profile"] = profile
        resolved = resolve(task, hints=hints)
        return {"ok": True, "result": resolved}

    def _reverse_echo_test(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.reverse_request:
            raise RuntimeError("reverse_request not configured")
        # Call plugin while a parent request is pending.
        echo = self.reverse_request("semantic.execute", {"value": params.get("value")})
        return {"reverse_result": echo}

    def _shutdown(self) -> Dict[str, Any]:
        self._shutdown_requested = True
        return {"ok": True, "message": "shutting down"}

    def _send_reverse(self, method: str, params: Dict[str, Any], timeout_ms: int | None = None) -> Any:
        """Issue a full-duplex request to the plugin and await its response.

        ``timeout_ms`` (when given) is the caller's per-call bound forwarded to
        ``_await_reverse``; ``None`` falls back to the default reverse timeout.
        """
        import uuid

        rid = str(uuid.uuid4())
        self._pending_reverse[rid] = {"resolved": False, "result": None, "error": None}
        self._write({"id": rid, "method": method, "params": params})
        return self._await_reverse(rid, timeout_ms or _REVERSE_TIMEOUT_MS_DEFAULT)

    def _await_reverse(self, rid: str, timeout_ms: int = _REVERSE_TIMEOUT_MS_DEFAULT) -> Any:
        import time

        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            entry = self._pending_reverse.get(rid)
            if entry and entry["resolved"]:
                if entry["error"]:
                    raise RuntimeError(entry["error"])
                return entry["result"]
            time.sleep(0.02)
        raise TimeoutError(f"reverse request timeout: {rid}")

    def _resolve_reverse(self, msg: Dict[str, Any]) -> bool:
        rid = msg.get("id")
        if rid is None or not isinstance(msg.get("ok"), bool):
            return False
        entry = self._pending_reverse.get(rid)
        if not entry:
            return False
        entry["resolved"] = True
        if msg.get("ok"):
            entry["result"] = msg.get("result")
        else:
            err = msg.get("error") or {}
            entry["error"] = f"{err.get('code', 'ERROR')}: {err.get('message', '')}"
        return True

    def _reader_thread(self) -> None:
        """Background stdin reader: resolves reverse responses and queues requests."""
        import queue

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if self._resolve_reverse(msg):
                continue
            self._inbox.put(msg)

    def serve(self) -> None:
        import queue
        import threading

        self._shutdown_requested = False
        self._pending_reverse: Dict[str, Dict[str, Any]] = {}
        self.reverse_request = self._send_reverse
        self._inbox: "queue.Queue[Dict[str, Any]]" = queue.Queue()

        t = threading.Thread(target=self._reader_thread, daemon=True)
        t.start()

        while True:
            try:
                msg = self._inbox.get(timeout=0.2)
            except queue.Empty:
                if getattr(self, "_shutdown_requested", False):
                    break
                continue
            rid = msg.get("id")
            method = msg.get("method")
            if rid is None or not method:
                continue
            handler = self.handlers.get(method)
            if handler is None:
                self._write({"id": rid, "ok": False, "error": {"code": "NO_METHOD", "message": method}})
                continue
            try:
                result = handler(msg.get("params") or {})
                self._write({"id": rid, "ok": True, "result": result})
            except Exception as exc:  # noqa: BLE001
                self._write({"id": rid, "ok": False, "error": {"code": "HANDLER_ERROR", "message": str(exc)}})
            if getattr(self, "_shutdown_requested", False):
                break

    def _write(self, obj: Dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def main() -> int:
    root = _harness_root()
    server = BridgeServer(root)
    server.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())