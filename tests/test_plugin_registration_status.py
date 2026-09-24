"""TD-D3 (issue #16): тесты гейта check_plugin_registration_status (PASS + мутации I1-I6)."""
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "tools"))
import check_plugin_registration_status as gate  # noqa: E402


def snapshot(dst: Path) -> Path:
    """Копия минимального дерева,_needed for gate evaluation."""
    dst.mkdir(parents=True, exist_ok=True)
    for rel in ("scripts/register_plugin.py",
                "config/opencode_plugin_config.json",
                ".opencode/opencode.json",
                "packages/opencode-harness-plugin/core/doctor.py",
                "docs/ARCHITECTURE_NOTES.md"):
        s = ROOT / rel
        d = dst / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, d)
    return dst


class GateTests(unittest.TestCase):
    def _mut(self, mutate):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = snapshot(Path(td))
            mutate(root)
            return gate.violations_for(root)

    def test_gate_passes_on_repo(self):
        self.assertEqual(gate.violations_for(ROOT), [])

    def test_I1_helper_unmarked(self):
        def m(r):
            p = r / "scripts/register_plugin.py"
            p.write_text(p.read_text(encoding="utf-8").replace("TEMPORARY", "temp"), encoding="utf-8")
        v = self._mut(m)
        self.assertTrue(any(x.startswith("I1") and "TEMPORARY" in x for x in v), v)

    def test_I2_status_removed(self):
        def m(r):
            p = r / "config/opencode_plugin_config.json"
            cfg = json.loads(p.read_text(encoding="utf-8"))
            del cfg["status"]
            p.write_text(json.dumps(cfg), encoding="utf-8")
        v = self._mut(m)
        self.assertTrue(any(x.startswith("I2") and "status" in x for x in v), v)

    def test_I2_mode_downgraded(self):
        def m(r):
            p = r / "config/opencode_plugin_config.json"
            cfg = json.loads(p.read_text(encoding="utf-8"))
            cfg["plugin"]["mode"] = "legacy_hostless"
            p.write_text(json.dumps(cfg), encoding="utf-8")
        v = self._mut(m)
        self.assertTrue(any(x.startswith("I2") and "mode" in x for x in v), v)

    def test_I3_canonical_entry_missing(self):
        def m(r):
            p = r / ".opencode/opencode.json"
            cfg = json.loads(p.read_text(encoding="utf-8-sig"))
            cfg["plugin"] = []
            p.write_text(json.dumps(cfg), encoding="utf-8")
        v = self._mut(m)
        self.assertTrue(any(x.startswith("I3") for x in v), v)

    def test_I4_runtime_consumer_appears(self):
        def m(r):
            (r / "scripts" / "rogue_reader.py").write_text(
                "import json\njson.load(open('config/opencode_plugin_config.json'))\n", encoding="utf-8")
        v = self._mut(m)
        self.assertTrue(any(x.startswith("I4") and "rogue_reader" in x for x in v), v)

    def test_I5_doctor_blinded(self):
        def m(r):
            p = r / "packages/opencode-harness-plugin/core/doctor.py"
            t = p.read_text(encoding="utf-8")
            t = t.replace(".opencode", "nowhere").replace("opencode-harness-plugin", "other-plugin")
            p.write_text(t, encoding="utf-8")
        v = self._mut(m)
        self.assertTrue(any(x.startswith("I5") for x in v), v)

    def test_I6_notes_missing_reference(self):
        def m(r):
            p = r / "docs/ARCHITECTURE_NOTES.md"
            p.write_text("# empty\n", encoding="utf-8")
        v = self._mut(m)
        self.assertTrue(any(x.startswith("I6") for x in v), v)


if __name__ == "__main__":
    unittest.main(verbosity=2)
