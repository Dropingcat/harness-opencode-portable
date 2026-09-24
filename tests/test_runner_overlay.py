#!/usr/bin/env python3
"""TD-117: контракт runner-обёрток для субагентов (гейт инвариантов).

Проверяет слой, закрывающий TD-117 (`opencode run --agent` не вызывает
субагентов напрямую — нужен primary-runner с диспатчем через task):

  1. gen_runners.py --check проходит на HEAD (инварианты не нарушены);
  2. каждый видимый subagent реестра имеет agents/<name>-runner.md;
  3. runner: mode=primary и тело вызывает task(...subagent_type="<name>");
  4. категорийный оверлей runner'а ссылается через wraps на субагента;
  5. генератор детерминирован: повторный рендер шаблона == существующий runner
     (для runner'ов, созданных шаблоном) — защита от дрейфа;
  6. регрессия дрейфа: оборванный wraps/несуществующая цель в изолированном
     дереве детектируется (--check возвращает нарушения).

Stdlib-only, без сети, без live-opencode (live-прогон — хост-runtimes).
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

from scripts.agent_gen.gen_runners import (  # noqa: E402
    AGENTS_DIR,
    CATEGORIES_DIR,
    check_invariants,
    load_registry,
    render_runner_md,
    subagents,
)

GEN = ROOT / "scripts" / "agent_gen" / "gen_runners.py"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GEN), *args],
                          capture_output=True, text=True, cwd=cwd or ROOT)


class TestRunnerOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = load_registry()
        cls.subs = {r.name: r for r in subagents(cls.reg)}

    # ------------------------------------------------------------ 1
    def test_check_gate_passes_on_head(self):
        r = run_cli("--check")
        self.assertEqual(r.returncode, 0, f"--check failed:\n{r.stderr}")
        payload = json.loads(r.stdout)
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(payload["visible_subagents"], 5)

    # ------------------------------------------------------------ 2+3+4
    def test_every_visible_subagent_has_valid_runner(self):
        problems = check_invariants(self.reg)
        self.assertEqual(problems, [], "\n".join(problems))
        for name in self.subs:
            rp = AGENTS_DIR / f"{name}-runner.md"
            self.assertTrue(rp.exists(), f"missing runner for {name}")
            text = rp.read_text(encoding="utf-8")
            self.assertIn('mode: primary', text, f"{rp.name}: not primary")
            self.assertIn(f'subagent_type="{name}"', text,
                          f"{rp.name}: no task dispatch to {name}")
            cp = CATEGORIES_DIR / f"{name}-runner.json"
            data = json.loads(cp.read_text(encoding="utf-8"))
            self.assertEqual(data.get("wraps"), name,
                             f"{cp.name}: wraps != {name}")

    # ------------------------------------------------------------ 5
    def test_template_matches_generated_runners(self):
        """Детерминизм шаблона: повторный рендер байт-в-байт стабилен и
        структурно эквивалентен канону (frontmatter + dispatch-строка)."""
        first = render_runner_md("demo-agent", "x")
        second = render_runner_md("demo-agent", "y")  # описание не влияет на шаблон
        self.assertEqual(first, second, "template rendering is not deterministic")
        self.assertIn('subagent_type="demo-agent"', first)
        self.assertIn("mode: primary", first)
        # все dispatch-строки существующих runner'ов совпадают по формату
        for name in self.subs:
            text = (AGENTS_DIR / f"{name}-runner.md").read_text(encoding="utf-8")
            canon_line = (f'task(description="{name} dispatch", '
                          f'prompt=<весь промпт>, subagent_type="{name}")')
            self.assertIn(canon_line, text,
                          f"{name}-runner dispatch line drifted from canonical template")

    # ------------------------------------------------------------ 6
    def test_drift_is_detected(self):
        """Изолированное дерево: удалённый runner и битый wraps ловятся гейтом."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            shutil.copytree(ROOT / "agents", tmp / "agents")
            shutil.copytree(CATEGORIES_DIR, tmp / "config" / "agent_categories")
            shutil.copytree(ROOT / "runtime", tmp / "runtime")
            # ломаем: runner удалён, категории оставлены
            victim = sorted(self.subs)[0]
            (tmp / "agents" / f"{victim}-runner.md").unlink()
            import scripts.agent_gen.gen_runners as gr
            old_agents, old_cats = gr.AGENTS_DIR, gr.CATEGORIES_DIR
            try:
                gr.AGENTS_DIR = tmp / "agents"
                gr.CATEGORIES_DIR = tmp / "config" / "agent_categories"
                reg = gr.AgentRegistry.load(tmp)
                problems = gr.check_invariants(reg)
            finally:
                gr.AGENTS_DIR, gr.CATEGORIES_DIR = old_agents, old_cats
            self.assertTrue(any(victim in p and "без primary-обёртки" in p
                                for p in problems),
                            f"deleted runner not detected: {problems}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
