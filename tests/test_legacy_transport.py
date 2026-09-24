"""Тесты гейта check_legacy_transport.py (TD-D6/AG-D6, issue #18).

PASS на реальном репо + мутационные тесты каждого инварианта I1–I6.
Мутации применяются к копии дерева (только реестр и copy-модули), исходное
дерево не изменяется.
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "tools" / "check_legacy_transport.py"
REGISTRY = ROOT / "docs" / "LEGACY_TRANSPORT_REGISTRY.json"
TOKEN = "opencode_cli_legacy"


def run_gate() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATE)], capture_output=True, text=True)


def base_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


class TestGateOnRepo(unittest.TestCase):
    def test_pass(self):
        p = run_gate()
        self.assertEqual(p.returncode, 0, msg=p.stdout + p.stderr)
        self.assertIn("PASS", p.stdout)

    def test_registry_structure(self):
        data = base_registry()
        self.assertEqual(data["schema"], "legacy_transport_registry/1.0")
        self.assertEqual(data["canonical_transport_token"], TOKEN)
        ids = {m["id"] for m in data["modules"]}
        self.assertIn("mcp/coder_router_server.py", ids)
        self.assertIn("mcp/launchers/_runner.py", ids)
        self.assertIn("mcp/launchers/opencode_code_worker.py", ids)
        self.assertIn("mcp/launchers/opencode_tribunal_role.py", ids)

    def test_runner_emits_transport_in_meta_and_result(self):
        src = (ROOT / "mcp" / "launchers" / "_runner.py").read_text(encoding="utf-8")
        self.assertIn(f'TRANSPORT = "{TOKEN}"', src)
        self.assertIn('"transport": TRANSPORT,', src)
        # meta.json payload и result payload содержат transport
        self.assertGreaterEqual(src.count('"transport": TRANSPORT,'), 3)

    def test_coder_router_fail_closed_preserved(self):
        src = (ROOT / "mcp" / "coder_router_server.py").read_text(encoding="utf-8")
        self.assertIn("_TRANSPORT_LEGACY", src)
        self.assertIn("_transport_unavailable", src)


class MutationHarness(unittest.TestCase):
    """Каждая мутация ловится своим инвариантом (fail-closed)."""

    def _make_tree(self, tmp: Path, mutate=None) -> Path:
        """Копия минимального дерева: mcp/*, реестр, TECH_DEBT_AGENTS.md; затем мутация."""
        tree = tmp / "tree"
        (tree / "mcp" / "launchers").mkdir(parents=True)
        (tree / "docs").mkdir(parents=True)
        for f in sorted((ROOT / "mcp" / "launchers").glob("*.py")):
            shutil.copy(f, tree / "mcp" / "launchers" / f.name)
        shutil.copy(ROOT / "mcp" / "coder_router_server.py", tree / "mcp" / "coder_router_server.py")
        shutil.copy(ROOT / "TECH_DEBT_AGENTS.md", tree / "TECH_DEBT_AGENTS.md")
        data = base_registry()
        if mutate:
            mutate(data, tree)
        (tree / "docs" / "LEGACY_TRANSPORT_REGISTRY.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return tree

    def _run(self, tree: Path) -> subprocess.CompletedProcess:
        code = (
            "import importlib.util, sys\n"
            "from pathlib import Path\n"
            f"spec = importlib.util.spec_from_file_location('gate', {str(GATE)!r})\n"
            "g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)\n"
            f"g.ROOT = Path({str(tree)!r})\n"
            f"g.REGISTRY = g.ROOT / 'docs' / 'LEGACY_TRANSPORT_REGISTRY.json'\n"
            f"g.DEBT_LEDGER = g.ROOT / 'TECH_DEBT_AGENTS.md'\n"
            "sys.exit(g.main())\n"
        )
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    def _assert_fails_with(self, mutate, prefix: str):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tree = self._make_tree(Path(td), mutate)
            p = self._run(tree)
            self.assertNotEqual(p.returncode, 0, msg=f"мутация не поймана: {p.stdout}{p.stderr}")
            self.assertIn(prefix, p.stdout + p.stderr, msg=p.stdout + p.stderr)

    # --- I1 ---
    def test_I1_bad_schema(self):
        def m(data, tree):
            data["schema"] = "wrong/0.0"
        self._assert_fails_with(m, "I1:")

    def test_I1_duplicate_ids(self):
        def m(data, tree):
            data["modules"].append(json.loads(json.dumps(data["modules"][0])))
        self._assert_fails_with(m, "I1:")

    # --- I2 ---
    def test_I2_empty_rationale(self):
        def m(data, tree):
            data["modules"][0]["rationale"] = "  "
        self._assert_fails_with(m, "I2:")

    def test_I2_noncanonical_transport(self):
        def m(data, tree):
            data["modules"][1]["transport"] = "semantic_plugin"
        self._assert_fails_with(m, "I2:")

    # --- I3 ---
    def test_I3_missing_declaration_in_source(self):
        def m(data, tree):
            mod = data["modules"][2]  # opencode_code_worker
            rp = tree / mod["id"]
            src = rp.read_text(encoding="utf-8").replace(
                f'TRANSPORT_TAG = "{TOKEN}"', "TRANSPORT_TAG = \"other\"")
            rp.write_text(src, encoding="utf-8")
        self._assert_fails_with(m, "I3:")

    def test_I3_missing_module(self):
        def m(data, tree):
            rp = tree / data["modules"][2]["id"]
            rp.unlink()
        self._assert_fails_with(m, "I3:")

    # --- I4 ---
    def test_I4_unregistered_leakage(self):
        def m(data, tree):
            leak = tree / "mcp" / "launchers" / "opencode_new_leak.py"
            leak.write_text(
                "from _runner import run_with_contract\n"
                "async def call():\n"
                "    return await run_with_contract('leak', 'task', 'contract')\n",
                encoding="utf-8")
        self._assert_fails_with(m, "I4:")

    def test_I4_removed_declared_module_still_used(self):
        # Убрали запись из реестра — модуль с legacy-usage остался → I4 полнота.
        def m(data, tree):
            data["modules"] = [x for x in data["modules"]
                               if x["id"] != "mcp/launchers/opencode_service_task.py"]
        self._assert_fails_with(m, "I4:")

    # --- I5 ---
    def test_I5_bad_related_debt_id(self):
        def m(data, tree):
            data["modules"][0]["related_debt"] = ["NOT-A-DEBT-ID!!"]
        self._assert_fails_with(m, "I5:")

    def test_I5_unrelated_to_td_d6(self):
        def m(data, tree):
            data["modules"][0]["related_debt"] = ["TD-D1"]
        self._assert_fails_with(m, "I5:")

    # --- I6 ---
    def test_I6_ledger_not_closed(self):
        def m(data, tree):
            lp = tree / "TECH_DEBT_AGENTS.md"
            src = lp.read_text(encoding="utf-8").replace(
                "### TD-D6. **Writer/Coder «semantic launcher leakage» сохранена** (legacy CLI) — ЗАКРЫТО",
                "### TD-D6. **Writer/Coder «semantic launcher leakage» сохранена** (legacy CLI)")
            lp.write_text(src, encoding="utf-8")
        self._assert_fails_with(m, "I6:")


if __name__ == "__main__":
    unittest.main()
