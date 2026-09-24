#!/usr/bin/env python3
"""Harness native plugin doctor (канонический health-инструмент, TD-D2).

Единый plugin-aware doctor вместо двух расходящихся health-слоёв:
  - статические presence-проверки дерева поставки;
  - живые hostless-probes: bridge.hello / harness.status через stdio-запуск
    `core/bridge_peer.py` (реальный JSON-RPC handshake без хоста OpenCode);
  - protocol compatibility: BRIDGE_PROTOCOL в TS (`src/bridge/protocol.ts`) и
    PROTOCOL в Python (`core/bridge_peer.py`) должны совпадать;
  - host feature snapshot: регистрация native-плагина (project/global config),
    наличие dist-бандла, авто-discovery legacy/native;
  - semantic provider readiness: HARNESS_SEMANTIC_ENABLED + dist/index.js.

Выход != 0 при любом FAIL. Stdlib-only, без сети.
Запуск: python3 packages/opencode-harness-plugin/core/doctor.py [--report PATH]
Корень можно задать OPENCODE_HARNESS_ROOT (для тестов на временных деревьях).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROBE_TIMEOUT_S = 15


def harness_root() -> Path:
    env = os.environ.get("OPENCODE_HARNESS_ROOT")
    if env:
        return Path(env)
    # <root>/packages/opencode-harness-plugin/core/doctor.py -> parents[3] == <root>
    return Path(__file__).resolve().parents[3]


def _strip_jsonc_comments(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("//")]
    return "\n".join(lines)


def _load_json_config(path: Path) -> dict | None:
    try:
        data = json.loads(_strip_jsonc_comments(path.read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


# --- static presence checks -------------------------------------------------

def presence_checks(root: Path) -> list[dict]:
    spec = [
        ("config_dir", root / "config", "dir"),
        ("runtime_snapshot", root / "config" / "runtime_snapshot.json", "file"),
        ("capability_snapshot", root / "config" / "capability_runtime_snapshot.json", "file"),
        ("plugin_package", root / "packages" / "opencode-harness-plugin" / "package.json", "file"),
        ("bridge_peer", root / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py", "file"),
    ]
    out = []
    for name, p, kind in spec:
        ok = p.is_dir() if kind == "dir" else p.is_file()
        out.append({"check": name, "ok": ok, "detail": str(p) if ok else f"missing: {p}"})
    return out


# --- live bridge probes (hostless stdio) ------------------------------------

def _peer_request(root: Path, requests: list[dict], timeout_s: float = PROBE_TIMEOUT_S) -> dict[int, dict]:
    """Spawn bridge_peer.py and exchange line-delimited JSON-RPC over stdio."""
    peer = root / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
    proc = subprocess.Popen(
        [sys.executable, str(peer)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, cwd=str(root),
    )
    responses: dict[int, dict] = {}
    try:
        for req in requests:
            proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        wanted = {r["id"] for r in requests}
        deadline = time.time() + timeout_s
        while wanted and time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") in wanted:
                responses[msg["id"]] = msg
                wanted.discard(msg["id"])
    finally:
        try:
            proc.stdin.write(json.dumps({"id": 0, "method": "bridge.shutdown", "params": {}}) + "\n")
            proc.stdin.flush()
        except (OSError, ValueError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    return responses


def probe_bridge_handshake(root: Path) -> dict:
    from bridge_peer import PROTOCOL  # same-directory import
    try:
        res = _peer_request(root, [{"id": 1, "method": "bridge.hello",
                                    "params": {"plugin_semver": "doctor"}}])
    except Exception as exc:  # noqa: BLE001
        return {"check": "bridge.handshake", "ok": False, "detail": f"probe error: {exc}"}
    m = res.get(1)
    if not m or not m.get("ok"):
        return {"check": "bridge.handshake", "ok": False, "detail": f"no hello response: {m}"}
    result = m.get("result", {})
    ok = result.get("schema") == PROTOCOL and PROTOCOL in (result.get("bridge_protocol_supported") or [])
    return {"check": "bridge.handshake", "ok": ok,
            "detail": f"protocol={result.get('schema')}" if ok else f"unexpected: {result}"}


def probe_harness_status(root: Path) -> dict:
    try:
        res = _peer_request(root, [{"id": 1, "method": "harness.status", "params": {}}])
    except Exception as exc:  # noqa: BLE001
        return {"check": "core.health", "ok": False, "detail": f"probe error: {exc}"}
    m = res.get(1)
    if not m or not m.get("ok"):
        return {"check": "core.health", "ok": False, "detail": f"no status response: {m}"}
    result = m.get("result", {})
    ok = bool(result.get("ok")) and result.get("runtime_policy_present") and result.get("capability_policy_present")
    return {"check": "core.health", "ok": bool(ok),
            "detail": f"runtime/capability policy present via harness.status" if ok else f"incomplete: {result}"}


def probe_protocol_compat(root: Path) -> dict:
    ts = root / "packages" / "opencode-harness-plugin" / "src" / "bridge" / "protocol.ts"
    py = root / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
    try:
        from bridge_peer import PROTOCOL as PY_PROTOCOL
    except Exception as exc:  # noqa: BLE001
        return {"check": "protocol.compat", "ok": False, "detail": f"python side unavailable: {exc}"}
    if not ts.is_file():
        return {"check": "protocol.compat", "ok": False, "detail": f"missing {ts}"}
    import re
    mm = re.search(r'BRIDGE_PROTOCOL\s*=\s*"([^"]+)"', ts.read_text(encoding="utf-8"))
    if not mm:
        return {"check": "protocol.compat", "ok": False, "detail": "BRIDGE_PROTOCOL literal not found in TS"}
    ts_protocol = mm.group(1)
    ok = ts_protocol == PY_PROTOCOL
    return {"check": "protocol.compat", "ok": ok,
            "detail": f"ts={ts_protocol} py={PY_PROTOCOL}" if ok else f"MISMATCH ts={ts_protocol} py={PY_PROTOCOL}"}


# --- host feature snapshot / registration ------------------------------------

def _registered_plugins(cfg: dict) -> list[str]:
    plugins = cfg.get("plugin")
    return [p for p in plugins if isinstance(p, str)] if isinstance(plugins, list) else []


def host_feature_snapshot(root: Path) -> tuple[dict, bool, bool]:
    """Return (check, native_enabled, legacy_would_load)."""
    global_cfgs = [Path.home() / ".config" / "opencode" / "opencode.jsonc",
                   Path.home() / ".config" / "opencode" / "opencode.json"]
    legacy_in_global = False
    for gcfg in global_cfgs:
        if not gcfg.is_file():
            continue
        data = _load_json_config(gcfg)
        if data and any("tool-skill-contract-router" in p for p in _registered_plugins(data)):
            legacy_in_global = True

    native_enabled = False
    registration_source = None
    for pcfg in [root / ".opencode" / "opencode.json", root / "opencode.json", root / "opencode.jsonc"]:
        if not pcfg.is_file():
            continue
        data = _load_json_config(pcfg)
        if data and any("opencode-harness-plugin" in p for p in _registered_plugins(data)):
            native_enabled = True
            registration_source = str(pcfg)
            break
    native_auto = (root / ".opencode" / "plugins" / "opencode-harness-plugin.ts").is_file()
    legacy_auto = (root / ".opencode" / "plugins" / "tool-skill-contract-router.ts").is_file()
    legacy_would_load = legacy_in_global or legacy_auto
    dist_present = (root / "packages" / "opencode-harness-plugin" / "dist" / "index.js").is_file()
    ok = native_enabled or native_auto
    detail = ("registered" if native_enabled else "auto-discovered" if native_auto
              else "NOT registered (project config has no opencode-harness-plugin entry)")
    check = {"check": "plugin.registration", "ok": ok, "detail": detail,
             "registration_source": registration_source,
             "native_auto_discovered": native_auto,
             "legacy_would_load": legacy_would_load,
             "dist_bundle_present": dist_present}
    return check, native_enabled or native_auto, legacy_would_load


def semantic_provider_readiness(root: Path) -> dict:
    enabled = os.environ.get("HARNESS_SEMANTIC_ENABLED") == "1"
    dist = (root / "packages" / "opencode-harness-plugin" / "dist" / "index.js").is_file()
    peer = (root / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py").is_file()
    ready = enabled and dist and peer
    detail = (f"enabled={enabled} dist={dist} peer={peer}; "
              + ("READY" if ready else "DISABLED (default; P3 live certification pending — informational)"))
    # Informational: semantic не блокирует общий вердикт doctor (P3 не сертифицирован live).
    return {"check": "semantic.provider", "ok": ready, "blocking": False, "detail": detail}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    root = harness_root()
    core_dir = Path(__file__).resolve().parent
    if str(core_dir) not in sys.path:
        sys.path.insert(0, str(core_dir))

    checks = presence_checks(root)
    plugin_ok = all(c["ok"] for c in checks)
    if plugin_ok:
        checks.append(probe_bridge_handshake(root))
        checks.append(probe_harness_status(root))
        checks.append(probe_protocol_compat(root))
    else:
        for name in ("bridge.handshake", "core.health", "protocol.compat"):
            checks.append({"check": name, "ok": False, "blocking": True,
                           "detail": "skipped: static presence failed"})

    host_check, native_on, legacy_load = host_feature_snapshot(root)
    checks.append(host_check)
    sem_check = semantic_provider_readiness(root)
    checks.append(sem_check)

    conflict = legacy_load and native_on
    blocking_fail = [c for c in checks if not c["ok"] and c.get("blocking", True)]
    status = {
        "schema": "harness-opencode-plugin-doctor/1.1",
        "core_root": str(root),
        "checks": checks,
        "legacy_would_load": legacy_load,
        "native_active": native_on,
        "conflict": conflict,
        "conflict_detail": ("legacy + native both load; do not load simultaneously"
                            if conflict else "no simultaneous legacy/native loading"),
    }
    status["ok"] = not blocking_fail and not conflict

    text = json.dumps(status, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
