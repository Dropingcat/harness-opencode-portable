#!/usr/bin/env python3
"""Регрессионные тесты генератора субагентов OpenCode (закрытие TD-A1/AG-A1).

Покрывают контракт «реестр -> .opencode/agent/*.md»:
  - артефакты сгенерированы и АКТУАЛЬНЫ (--check, детерминированность);
  - каждая запись реестра имеет файл агента + индекс покрывает реестр;
  - frontmatter артефакта round-trip-совместим со строгим YAML-парсером
    и согласован с источником agents/<name>.md (name/description/mode/steps);
  - model: из runtime/model_bindings.json проставлен в артефакте;
  - оркестраторы содержат GENERATED ROUTE HINTS из routes_authority.

Запуск:  python3 -m unittest tests.test_agent_gen -v   (из корня репозитория)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.registry import AgentRegistry, split_frontmatter  # noqa: E402
from scripts.agent_gen.compile_agents import (  # noqa: E402
    AGENT_DIR_REL,
    INDEX_NAME,
    compile_agents,
)

AGENT_DIR = ROOT / AGENT_DIR_REL


def _load_index() -> dict:
    return json.loads((AGENT_DIR / INDEX_NAME).read_text(encoding="utf-8"))


class TestGeneratedArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = AgentRegistry.load(ROOT)
        errors = cls.reg.validate()
        assert not errors, "registry must be valid for artifact tests"

    def test_check_mode_is_clean(self):
        """--check на реальном дереве обязан проходить (нет stale-артефактов)."""
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "agent_gen" / "compile_agents.py"), "--check"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, f"--check failed:\n{r.stdout}\n{r.stderr}")
        payload = json.loads(r.stdout)
        self.assertTrue(payload.get("ok"), r.stdout)

    def test_deterministic_rendering(self):
        """Двойная компиляция in-memory даёт идентичный content_hash."""
        h1 = compile_agents(ROOT, write=False)["index"]["content_hash"]
        h2 = compile_agents(ROOT, write=False)["index"]["content_hash"]
        self.assertEqual(h1, h2)
        idx = _load_index()
        self.assertEqual(idx["content_hash"], h1,
                         "on-disk index hash != freshly rendered hash (stale artifacts)")

    def test_every_registry_record_has_artifact(self):
        for name in sorted(self.reg.records):
            p = AGENT_DIR / f"{name}.md"
            self.assertTrue(p.is_file(), f"missing generated agent: {p.relative_to(ROOT)}")

    def test_index_covers_registry_exactly(self):
        idx = _load_index()
        self.assertEqual(sorted(idx["agents"]), sorted(self.reg.names()))
        modes = {"primary": [], "subagent": []}
        for rec in self.reg.records.values():
            if rec.mode in modes:
                modes[rec.mode].append(rec.name)
        self.assertEqual(sorted(idx["primary"]), sorted(modes["primary"]))
        self.assertEqual(sorted(idx["subagent"]), sorted(modes["subagent"]))

    def test_frontmatter_roundtrip_matches_source(self):
        """Строгий парсер читает артефакт; ключевые поля == источнику."""
        for name, src in sorted(self.reg.records.items()):
            fm, body = split_frontmatter((AGENT_DIR / f"{name}.md").read_text(encoding="utf-8"))
            self.assertEqual(fm.get("name"), src.name)
            self.assertEqual(str(fm.get("description", "")).strip(), src.description.strip())
            self.assertEqual(fm.get("mode"), src.mode)
            if src.steps is not None:
                self.assertEqual(int(fm.get("steps")), src.steps)
            self.assertTrue(body.strip(), f"{name}: empty generated prompt body")
            expected_model = src.bound_model or src.model
            if expected_model:
                self.assertEqual(fm.get("model"), expected_model,
                                 f"{name}: model binding not propagated to artifact")

    def test_route_hints_present_for_routed_orchestrators(self):
        authority = json.loads((ROOT / "config" / "routes_authority.json")
                               .read_text(encoding="utf-8"))
        routed = {r["agent"] for r in authority.get("routes", {}).values() if r.get("agent")}
        self.assertTrue(routed, "routes_authority has no route->agent links")
        pat = re.compile(r"GENERATED ROUTE HINTS")
        for name in sorted(routed):
            text = (AGENT_DIR / f"{name}.md").read_text(encoding="utf-8")
            self.assertRegex(text, pat, f"{name}: routed agent lacks GENERATED ROUTE HINTS footer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
