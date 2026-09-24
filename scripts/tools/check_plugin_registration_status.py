#!/usr/bin/env python3
"""TD-D3 (issue #16): гейт статуса регистрации плагина (transitional helper vs canonical path).

Инварианты:
  I1. `scripts/register_plugin.py` содержит явную маркировку transitional-статуса
      ("TEMPORARY") и указание канонического пути (.opencode/opencode.json);
  I2. `config/opencode_plugin_config.json`: version>=3, status=="TRANSITIONAL_DECLARATION",
      непустой note, canonical_path==".opencode/opencode.json", plugin.mode=="native";
  I3. Канонический путь существует: `.opencode/opencode.json` — валидный JSON, поле
      `plugin` — список строк, хотя бы одна запись содержит "opencode-harness-plugin"
      и оканчивается на "dist/index.js";
  I4. Ни один исполняемый модуль (.py/.ts/.js/.mjs/.cjs/.sh; исключения: гейты/тесты check_*/test_*
      и register_plugin.py, которые только документируют запрет) не читает
      `opencode_plugin_config.json` как runtime-источник истины (конфиг — декларация статуса);
  I5. Канонический doctor проверяет регистрацию по project config: содержит
      ".opencode/opencode.json" и "opencode-harness-plugin";
  I6. Документация статуса на месте: docs/ARCHITECTURE_NOTES.md упоминает TD-D3,
      register_plugin.py и TRANSITIONAL/TEMPORARY-роль.

Fail-closed: любая ошибка -> список нарушений и exit code 1.
Stdlib-only, без сети. Запуск: python3 scripts/tools/check_plugin_registration_status.py [--root PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXEC_SUFFIXES = {".py", ".ts", ".js", ".mjs", ".cjs", ".sh"}
SKIP_DIR_PARTS = {"node_modules", ".git", "__pycache__", ".venv", "dist"}
# Тесты и гейты ссылаются на имя конфига намеренно (мутации/проверки) — не runtime-потребители.
SKIP_NAME_PREFIXES = ("test_", "check_")


def violations_for(root: Path) -> list[str]:
    v: list[str] = []

    helper = root / "scripts" / "register_plugin.py"
    cfg_p = root / "config" / "opencode_plugin_config.json"
    canon_p = root / ".opencode" / "opencode.json"
    doctor = root / "packages" / "opencode-harness-plugin" / "core" / "doctor.py"
    notes = root / "docs" / "ARCHITECTURE_NOTES.md"
    gate = Path(__file__).resolve()

    for p in (helper, cfg_p, canon_p, doctor, notes):
        if not p.is_file():
            v.append(f"missing file: {p}")
    if v:
        return v

    # I1: helper carries transitional marking + canonical path pointer
    hs = helper.read_text(encoding="utf-8")
    if "TEMPORARY" not in hs:
        v.append("I1: register_plugin.py не помечен как TEMPORARY transitional helper")
    if ".opencode/opencode.json" not in hs:
        v.append("I1: register_plugin.py не указывает канонический путь .opencode/opencode.json")

    # I2: config declares transitional status
    try:
        cfg = json.loads(cfg_p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        v.append(f"I2: opencode_plugin_config.json невалиден: {e}")
        cfg = {}
    if isinstance(cfg.get("version"), int) and cfg["version"] < 3:
        v.append(f"I2: config version {cfg['version']} < 3 (нет TD-D3 статуса)")
    if cfg.get("status") != "TRANSITIONAL_DECLARATION":
        v.append(f"I2: status должен быть 'TRANSITIONAL_DECLARATION', найдено {cfg.get('status')!r}")
    if not str(cfg.get("note", "")).strip():
        v.append("I2: отсутствует непустой note с пояснением роли конфига")
    if cfg.get("canonical_path") != ".opencode/opencode.json":
        v.append(f"I2: canonical_path != '.opencode/opencode.json' (найдено {cfg.get('canonical_path')!r})")
    mode = (cfg.get("plugin") or {}).get("mode")
    if mode != "native":
        v.append(f"I2: plugin.mode должен быть 'native', найдено {mode!r}")

    # I3: canonical registration exists and points at harness plugin dist entry
    try:
        canon = json.loads(canon_p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        v.append(f"I3: .opencode/opencode.json невалиден: {e}")
        canon = {}
    plugins = canon.get("plugin")
    if not isinstance(plugins, list) or not any(
        isinstance(p, str) and "opencode-harness-plugin" in p and p.replace("\\", "/").endswith("dist/index.js")
        for p in plugins
    ):
        v.append("I3: в .opencode/opencode.json нет file:// записи harness-plugin на dist/index.js")

    # I4: no runtime consumers of the declaration config
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in EXEC_SUFFIXES:
            continue
        parts = set(p.parts)
        if (parts & SKIP_DIR_PARTS or p.name.startswith(SKIP_NAME_PREFIXES)
                or p.resolve() == gate or p.resolve() == helper.resolve()):
            continue  # сам helper документирует запрет — не является потребителем
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "opencode_plugin_config" in text:
            v.append(f"I4: runtime-потребитель декларации: {p.relative_to(root)} читает opencode_plugin_config")

    # I5: canonical doctor verifies registration via project config
    ds = doctor.read_text(encoding="utf-8")
    if ".opencode" not in ds or "opencode-harness-plugin" not in ds:
        v.append("I5: doctor.py не проверяет регистрацию плагина по project config")

    # I6: architecture notes document the status
    ns = notes.read_text(encoding="utf-8")
    for needle in ("TD-D3", "register_plugin.py", "TRANSITIONAL"):
        if needle not in ns:
            v.append(f"I6: docs/ARCHITECTURE_NOTES.md не упоминает '{needle}'")

    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = ap.parse_args()
    v = violations_for(Path(args.root))
    if v:
        print("PLUGIN_REGISTRATION_STATUS_GATE: FAIL")
        for x in v:
            print(f"  - {x}")
        return 1
    print("PLUGIN_REGISTRATION_STATUS_GATE: PASS (I1-I6)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
