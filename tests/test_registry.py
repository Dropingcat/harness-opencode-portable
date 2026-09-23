#!/usr/bin/env python3
"""Smoke-тесты Agent Registry (Фаза 0, закрытие TD-A1).

Запуск:  python3 -m unittest tests.test_registry -v
         (из корня репозитория)

Покрывает:
  - парсинг frontmatter + fallback для unquoted `: ` в description;
  - cross-validation: name==filename, overlay категорий, bucket из
    bucket_contracts, ссылки model_bindings;
  - детерминированность загрузки и to_dict;
  - CLI --validate на реальном дереве (регрессия: реестр обязан быть валиден).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.registry import (  # noqa: E402
    AgentRegistry,
    FrontmatterError,
    split_frontmatter,
    parse_agent_file,
)


class TestFrontmatter(unittest.TestCase):
    def test_basic_split(self):
        text = "---\nname: foo\ndescription: bar\nmode: subagent\nsteps: 10\n---\nBody here\n"
        fm, body = split_frontmatter(text)
        self.assertEqual(fm["name"], "foo")
        self.assertEqual(fm["mode"], "subagent")
        self.assertEqual(fm["steps"], 10)
        self.assertIn("Body here", body)

    def test_unquoted_colon_fallback(self):
        # описание с неэкранированным ": " — формальный YAML error,
        # но легально для OpenCode-парсера; fallback обязан спасти
        text = '---\nname: foo\ndescription: текст: с двоеточием внутри\nmode: primary\n---\nB\n'
        fm, _ = split_frontmatter(text)
        self.assertIn("текст: с двоеточием внутри", fm["description"])

    def test_no_frontmatter_raises(self):
        with self.assertRaises(FrontmatterError):
            split_frontmatter("# just markdown\n")

    def test_parse_keeps_body_and_extra_keys(self):
        text = "---\nname: foo\ndescription: d\nmode: all\nhidden: true\n---\nPROMPT\n"
        rec = parse_agent_file(Path("/tmp/nonexistent-foo.md")) if False else None
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "foo.md"
            p.write_text(text, encoding="utf-8")
            rec = parse_agent_file(p)
        self.assertEqual(rec.name, "foo")
        self.assertEqual(rec.mode, "all")
        self.assertEqual(rec.extra_fm.get("hidden"), True)
        self.assertEqual(rec.body, "PROMPT")


class TestRealRegistry(unittest.TestCase):
    """Регрессии на фактическом дереве harness."""

    @classmethod
    def setUpClass(cls):
        cls.reg = AgentRegistry.load(ROOT)

    def test_loads_all_agents(self):
        n_md = len(list((ROOT / "agents").glob("*.md")))
        self.assertEqual(len(self.reg.records), n_md)
        self.assertGreaterEqual(n_md, 15)

    def test_validate_clean(self):
        errors = self.reg.validate()
        self.assertEqual(errors, [], f"registry validation errors: {errors}")

    def test_name_matches_filename(self):
        for stem, rec in ((p.stem, r) for p, r in
                          ((r.source, r) for r in self.reg.records.values())):
            self.assertEqual(rec.name, stem)

    def test_modes_valid(self):
        for rec in self.reg.records.values():
            self.assertIn(rec.mode, {"primary", "subagent", "all"})

    def test_runner_wrappers_exist_for_factory_subagents(self):
        # конвенция code-orchestrator.md: у субагентов фабрик есть *-runner
        for base in ("coder-worker", "code-reviewer", "code-tester",
                     "claim-parser", "source-fetcher", "fact-checker",
                     "tribunal-judge", "synthesizer"):
            self.assertIn(f"{base}-runner", self.reg.records,
                          f"missing runner wrapper for {base}")
            self.assertEqual(self.reg.runner_of(base), f"{base}-runner")

    def test_categories_overlay_present(self):
        for rec in self.reg.records.values():
            self.assertTrue(rec.categories,
                            f"{rec.name}: empty categories overlay")
            self.assertIsNotNone(rec.default_bucket)
            self.assertIsNotNone(rec.capsule)

    def test_buckets_are_canonical(self):
        buckets = set(json.loads(
            (ROOT / "config" / "bucket_contracts.json")
            .read_text(encoding="utf-8"))["buckets"])
        for rec in self.reg.records.values():
            self.assertIn(rec.default_bucket, buckets)

    def test_deterministic_reload(self):
        reg2 = AgentRegistry.load(ROOT)
        a = [self.reg.records[n].to_dict() for n in self.reg.names()]
        b = [reg2.records[n].to_dict() for n in reg2.names()]
        self.assertEqual(a, b)

    def test_effective_model_binding_priority(self):
        rec = next(iter(self.reg.records.values()))
        fm_model, bound = rec.model, rec.bound_model
        expected = bound or fm_model
        self.assertEqual(rec.effective_model, expected)


class TestValidateNegative(unittest.TestCase):
    """Валидатор обязан ловить битые записи (на временном дереве, root-инъекция)."""

    def _mk_tree(self, td: str) -> Path:
        root = Path(td)
        (root / "agents").mkdir()
        (root / "config" / "agent_categories").mkdir(parents=True)
        (root / "runtime").mkdir()
        bc = {"version": 1, "buckets": {"code": {}, "research": {},
                                        "security": {}, "writing": {},
                                        "integration": {}}}
        (root / "config" / "bucket_contracts.json").write_text(
            json.dumps(bc), encoding="utf-8")
        return root

    def test_catches_bad_records(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._mk_tree(td)
            good = "---\nname: good\ndescription: ok\nmode: subagent\nsteps: 5\n---\nP\n"
            bad_name = "---\nname: WRONG\ndescription: ok\nmode: subagent\n---\nP\n"
            bad_mode = "---\nname: badmode\ndescription: ok\nmode: wizard\n---\nP\n"
            bad_bucket = "---\nname: badbucket\ndescription: ok\nmode: primary\n---\nP\n"
            (root / "agents" / "good.md").write_text(good, encoding="utf-8")
            (root / "agents" / "bad-name.md").write_text(bad_name, encoding="utf-8")
            (root / "agents" / "badmode.md").write_text(bad_mode, encoding="utf-8")
            (root / "agents" / "badbucket.md").write_text(bad_bucket, encoding="utf-8")
            (root / "config" / "agent_categories" / "good.json").write_text(
                json.dumps({"agent": "good", "categories": ["CAT_X"],
                            "default_bucket": "code", "capsule": "c"}),
                encoding="utf-8")
            (root / "config" / "agent_categories" / "WRONG.json").write_text(
                json.dumps({"agent": "WRONG", "categories": ["CAT_X"],
                            "default_bucket": "nope", "capsule": "c"}),
                encoding="utf-8")
            (root / "config" / "agent_categories" / "badmode.json").write_text(
                json.dumps({"agent": "badmode", "categories": ["CAT_X"],
                            "default_bucket": "code", "capsule": "c"}),
                encoding="utf-8")
            (root / "config" / "agent_categories" / "badbucket.json").write_text(
                json.dumps({"agent": "badbucket", "categories": ["CAT_X"],
                            "default_bucket": "not-a-bucket", "capsule": "c"}),
                encoding="utf-8")
            # model_bindings со ссылкой на несуществующего агента
            (root / "runtime" / "model_bindings.json").write_text(
                json.dumps({"schema": "harness-model-bindings/1.0",
                            "agents": {"ghost": {"model": "x/y"}}}),
                encoding="utf-8")
            reg = AgentRegistry.load(root)
            errors = "\n".join(reg.validate())
            self.assertIn("bad-name: name 'WRONG' != filename", errors)
            self.assertIn("badmode: mode 'wizard'", errors)
            self.assertIn("bad-name: missing config/agent_categories/bad-name.json", errors)
            # overlay ищется по имени файла (проверка name==filename
            # ловит несоответствие отдельно)
            self.assertIn("badbucket: default_bucket 'not-a-bucket'", errors)
            self.assertIn("model_bindings: unknown agent 'ghost'", errors)


class TestCli(unittest.TestCase):
    def test_validate_cli_exit0(self):
        r = subprocess.run([sys.executable, str(ROOT / "runtime" / "registry.py"),
                            "--validate"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("registry OK", r.stdout)

    def test_json_cli(self):
        r = subprocess.run([sys.executable, str(ROOT / "runtime" / "registry.py"),
                            "--json"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("code-orchestrator", data)
        self.assertEqual(data["code-orchestrator"]["mode"], "primary")


if __name__ == "__main__":
    unittest.main(verbosity=2)
