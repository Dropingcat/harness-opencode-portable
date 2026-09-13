from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from mcp.launchers.opencode_tribunal_role import _provider_payload
except ModuleNotFoundError:
    _provider_payload = None


class OpenCodeTribunalLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        if _provider_payload is None:
            self.skipTest("MCP server runtime is not installed in the Researcher test environment")

    def test_launcher_returns_typed_provider_payload_from_results_file(self) -> None:
        expected = {"schema": "tribunal-question-draft/1.0", "question": "What distinguishes the alternatives?"}
        with tempfile.TemporaryDirectory() as raw:
            run_dir = Path(raw)
            (run_dir / "results.json").write_text(json.dumps(expected), encoding="utf-8")

            actual = _provider_payload({"ok": True, "run_dir": str(run_dir), "stdout": "runner log"})

        self.assertEqual(actual, expected)

    def test_launcher_rejects_missing_provider_json(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            actual = _provider_payload({"ok": True, "run_dir": raw, "stdout": "not json"})

        self.assertFalse(actual["ok"])
        self.assertIn("no valid Tribunal JSON", actual["error"])


if __name__ == "__main__":
    unittest.main()
