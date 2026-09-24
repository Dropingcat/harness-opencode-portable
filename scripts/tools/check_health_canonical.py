#!/usr/bin/env python3
"""TD-D2: гейт единства health-инструментов (health_check vs canonical doctor).

Инварианты:
  I1. `scripts/health_check.py` — тонкая обёртка: делегирует doctor.py, НЕ
      содержит собственной legacy-логики проверок (sqlite/DB accessible,
      собственные check_-функции, вызов start_mcp_servers/guard_runner);
  I2. Канонический `doctor.py` содержит живые probes: bridge.hello,
      harness.status и protocol-compat (TS literal vs Python PROTOCOL);
  I3. Протокольный слой согласован: литерал BRIDGE_PROTOCOL в TS ==
      PROTOCOL в bridge_peer.py (то же, что проверяет живой probe);
  I4. Оба входа дают идентичный JSON-вердикт на одном и том же дереве
      (запуск doctor напрямую и через health_check wrapper; сравнение по
      нормализованному содержимому отчёта) и оба exit==0 на HEAD-дереве.

Fail-closed: любая ошибка -> список нарушений и exit code 1.
Stdlib-only, без сети. Запуск: python3 scripts/tools/check_health_canonical.py [--root PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def violations_for(root: Path) -> list[str]:
    v: list[str] = []
    hc_path = root / "scripts" / "health_check.py"
    doctor_path = root / "packages" / "opencode-harness-plugin" / "core" / "doctor.py"
    peer_path = root / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
    ts_path = root / "packages" / "opencode-harness-plugin" / "src" / "bridge" / "protocol.ts"

    for p in (hc_path, doctor_path, peer_path, ts_path):
        if not p.is_file():
            v.append(f"missing file: {p}")
    if v:
        return v

    hc = hc_path.read_text(encoding="utf-8")
    dr = doctor_path.read_text(encoding="utf-8")

    # I1: wrapper purity
    if "doctor.py" not in hc or "subprocess" not in hc:
        v.append("I1: health_check.py не делегирует doctor.py (нет ссылки/субпроцесса)")
    for legacy in ("import sqlite3", "OPENCODE_SESSION_DB", "check_db_accessible",
                   "check_guard_running", "check_mcp_definitions", "start_mcp_servers"):
        if legacy in hc:
            v.append(f"I1: health_check.py содержит legacy-логику: '{legacy}'")

    # I2: live probes in canonical doctor
    for needle in ("bridge.hello", "harness.status", "protocol.compat", "bridge_peer.py"):
        if needle not in dr:
            v.append(f"I2: doctor.py не содержит живой probe/слой: '{needle}'")

    # I3: protocol literal parity (static mirror of the runtime probe)
    py_mm = re.search(r'^PROTOCOL\s*=\s*"([^"]+)"', peer_path.read_text(encoding="utf-8"), re.M)
    ts_mm = re.search(r'BRIDGE_PROTOCOL\s*=\s*"([^"]+)"', ts_path.read_text(encoding="utf-8"))
    if not py_mm:
        v.append("I3: PROTOCOL literal не найден в bridge_peer.py")
    if not ts_mm:
        v.append("I3: BRIDGE_PROTOCOL literal не найден в src/bridge/protocol.ts")
    if py_mm and ts_mm and py_mm.group(1) != ts_mm.group(1):
        v.append(f"I3: протокол рассогласован: ts={ts_mm.group(1)!r} py={py_mm.group(1)!r}")

    # I4: identical verdict through both entrypoints
    env_root = str(root)
    def _popen(cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                              cwd=env_root, env={"OPENCODE_HARNESS_ROOT": env_root,
                                                 "PATH": "/usr/bin:/bin",
                                                 "HOME": str(Path.home())})

    def run(cmd: list[str]) -> tuple[int, dict | None]:
        r = _popen(cmd)
        try:
            return r.returncode, json.loads(r.stdout)
        except json.JSONDecodeError:
            return r.returncode, None

    def run_raw(cmd: list[str]) -> tuple[int, str | None]:
        r = _popen(cmd)
        return r.returncode, r.stdout

    rc_d, out_d = run([sys.executable, str(doctor_path)])
    # health_check печатает JSON doctor-отчёта + строку "Overall:" — выделяем JSON.
    rc_h, raw_h = run_raw([sys.executable, str(hc_path)])
    out_h = None
    if raw_h:
        start = raw_h.find("{")
        end = raw_h.rfind("}")
        if start != -1 and end > start:
            try:
                out_h = json.loads(raw_h[start:end + 1])
            except json.JSONDecodeError:
                out_h = None
    if rc_d != 0 or out_d is None:
        v.append(f"I4: canonical doctor завершился с rc={rc_d} (ожидался 0 на HEAD-дереве)")
    if out_h is None:
        v.append("I4: health_check не вернул корректный JSON doctor-отчёта")
    elif rc_h != 0:
        v.append(f"I4: health_check завершился с rc={rc_h} (ожидался 0)")
    elif out_d is not None:
        a = {k: val for k, val in (out_d or {}).items() if k != "core_root"}
        b = {k: val for k, val in out_h.items() if k != "core_root"}
        if a != b:
            v.append("I4: расхождение doctor-отчётов между прявым запуском и health_check-обёрткой")
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = ap.parse_args()
    v = violations_for(Path(args.root).resolve())
    if v:
        print("TD-D2 GATE: FAIL")
        for x in v:
            print(f"  - {x}")
        return 1
    print("TD-D2 GATE: PASS (health_check -> canonical plugin-aware doctor, единый вердикт, protocol parity)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
