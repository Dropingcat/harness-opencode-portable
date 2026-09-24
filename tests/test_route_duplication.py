#!/usr/bin/env python3
"""TD-D10 / TD-003: тесты гейта дублирования route-данных.

Покрывает скрипт scripts/router/check_route_duplication.py:
  1. позитивный инвариант — на реальном дереве репозитория гейт PASS;
  2. компилируемость snapshot (--check compile_runtime.py) синхронна с гейтом;
  3. негативные мутации в изолированной копии дерева ловятся каждой проверкой:
       - дрейф compat-вью (правка priority в profile_routes.json)  -> I2/I4;
       - устаревший generated_from_policy_hash                     -> I2;
       - лишние/недостающие id в routes_authority vs snapshot       -> I1/I4;
       - hardcode несуществующего route-id в TS плагина            -> I3.

Stdlib unittest, без сети. Запуск: python3 -m unittest tests.test_route_duplication -v
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
sys.path.insert(0, str(ROOT))

from scripts.router.check_route_duplication import check  # noqa: E402

GATE = ROOT / "scripts" / "router" / "check_route_duplication.py"


def isolated_copy(dst: Path) -> None:
    """Копирует минимально необходимый срез дерева для запуска гейта."""
    shutil.copytree(ROOT / "config", dst / "config")
    shutil.copytree(ROOT / "scripts", dst / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "runtime", dst / "runtime",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "agents", dst / "agents")
    pkg_src = ROOT / "packages" / "opencode-harness-plugin" / "src"
    if pkg_src.is_dir():
        shutil.copytree(pkg_src, dst / "packages" / "opencode-harness-plugin" / "src")


class TestRouteDuplicationGate(unittest.TestCase):
    def test_real_tree_passes(self) -> None:
        errors = check(ROOT)
        self.assertEqual(errors, [], f"гейт на реальном дереве вернул нарушения: {errors}")

    def test_gate_cli_exit_zero(self) -> None:
        proc = subprocess.run([sys.executable, str(GATE)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS", proc.stdout)

    def test_compile_check_consistent(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "router" / "compile_runtime.py"), "--check"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_mutation_compat_drift_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / "repo"
            isolated_copy(dst)
            p = dst / "config" / "profile_routes.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            rid = sorted(data["routes"])[0]
            data["routes"][rid]["priority"] = 9999  # дрейф дубликата против snapshot
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            errors = check(dst)
            self.assertTrue(any(e.startswith(("I2", "I4")) for e in errors),
                            f"дрейф compat-вью не обнаружен: {errors}")

    def test_mutation_stale_policy_hash_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / "repo"
            isolated_copy(dst)
            p = dst / "config" / "skill_to_route_map.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            data["generated_from_policy_hash"] = "0" * 64  # имитация устаревшей вью
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            errors = check(dst)
            self.assertTrue(any(e.startswith("I2") and "generated_from_policy_hash" in e for e in errors),
                            f"устаревший policy_hash вью не обнаружен: {errors}")

    def test_mutation_extra_route_in_authority_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / "repo"
            isolated_copy(dst)
            p = dst / "config" / "routes_authority.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            src_rid = sorted(data["routes"])[0]
            data["routes"]["ghost-route"] = dict(data["routes"][src_rid])  # новый id без пересборки snapshot
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            errors = check(dst)
            self.assertTrue(any("ghost-route" in e or e.startswith("I1") for e in errors),
                            f"расхождение authority vs snapshot не обнаружено: {errors}")

    def test_mutation_ts_hardcode_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / "repo"
            isolated_copy(dst)
            ts = dst / "packages" / "opencode-harness-plugin" / "src" / "tools" / "ghost_route.ts"
            ts.write_text(
                'const target = { route: "route-that-does-not-exist" };\nexport default target;\n',
                encoding="utf-8")
            errors = check(dst)
            self.assertTrue(any(e.startswith("I3") and "route-that-does-not-exist" in e for e in errors),
                            f"hardcode route-id в TS не обнаружен: {errors}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
