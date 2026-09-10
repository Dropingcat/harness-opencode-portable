import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, name: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


PREFLIGHT = load_module("scripts/router/capability_preflight.py", "capability_preflight_tests")
RESOLVER = load_module("scripts/router/resolve_bundle.py", "resolve_bundle_tests")


class CommandProbeTests(unittest.TestCase):
    def test_command_uses_configured_executable_when_path_has_no_python(self):
        spec = {
            "kind": "command",
            "executable_env": "TEST_WRITER_PYTHON",
            "executable_default": "definitely-not-on-path",
            "argv": ["-c", "import sys; raise SystemExit(0)"],
        }
        with tempfile.TemporaryDirectory() as empty_path, patch.dict(
            os.environ,
            {"TEST_WRITER_PYTHON": sys.executable, "PATH": empty_path},
            clear=False,
        ):
            result = PREFLIGHT._probe_one(spec)

        self.assertTrue(result["ok"], result)
        self.assertIn("env:TEST_WRITER_PYTHON", result["detail"])

    def test_missing_configured_executable_degrades_provider(self):
        provider = {
            "installed_probe": {"kind": "always"},
            "live_probe": {
                "kind": "command",
                "executable_env": "TEST_WRITER_PYTHON",
                "executable_default": "python",
                "argv": ["-c", "raise SystemExit(0)"],
            },
        }
        missing = str(ROOT / ".runs" / "missing-writer-python")
        with patch.dict(os.environ, {"TEST_WRITER_PYTHON": missing}, clear=False):
            result = PREFLIGHT.probe_provider(provider)

        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["available"])
        self.assertTrue(result["implemented"])


class WriterProviderRoutingTests(unittest.TestCase):
    def test_writer_core_only_claims_semantic_validation(self):
        authority = json.loads(
            (ROOT / "config/providers_authority.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            authority["providers"]["local.writer_core"]["provides"],
            ["writer.semantic_validate"],
        )

    def test_valid_writer_interpreter_routes_only_semantic_validation_locally(self):
        authority = json.loads(
            (ROOT / "config/providers_authority.json").read_text(encoding="utf-8")
        )
        live_probe = authority["providers"]["local.writer_core"]["live_probe"]
        candidates = [os.environ.get("WRITER_PYTHON"), shutil.which("python"), sys.executable]
        writer_python = None
        for candidate in dict.fromkeys(candidates):
            if not candidate:
                continue
            with patch.dict(os.environ, {"TEST_WRITER_PYTHON": candidate}, clear=False):
                if PREFLIGHT._probe_one(
                    {**live_probe, "executable_env": "TEST_WRITER_PYTHON"},
                    network=False,
                )["ok"]:
                    writer_python = candidate
                    break
        if writer_python is None:
            self.skipTest("no Writer Core-capable Python interpreter is available")
        with patch.dict(os.environ, {"WRITER_PYTHON": writer_python}, clear=False):
            preflight = PREFLIGHT.snapshot(network=False)

        self.assertEqual(
            preflight["capabilities"]["writer.semantic_validate"]["providers"][0],
            "local.writer_core",
        )
        self.assertEqual(
            preflight["capabilities"]["writer.draft"]["providers"][0],
            "agent.writer",
        )
        self.assertEqual(
            preflight["capabilities"]["writer.claims.read"]["providers"][0],
            "agent.writer",
        )

        with tempfile.TemporaryDirectory() as directory:
            preflight_path = Path(directory) / "preflight.json"
            preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
            semantic = RESOLVER.resolve_bundle(
                "validate semantics",
                route_id="writing-prose",
                stage="semantic-validation",
                preflight_path=str(preflight_path),
            )
            draft = RESOLVER.resolve_bundle(
                "draft prose",
                route_id="writing-prose",
                stage="draft",
                preflight_path=str(preflight_path),
            )
            claims = RESOLVER.resolve_bundle(
                "load claims",
                route_id="writing-prose",
                stage="claim-load",
                preflight_path=str(preflight_path),
            )

        self.assertEqual(
            semantic["providers"]["writer.semantic_validate"], "local.writer_core"
        )
        self.assertEqual(draft["providers"]["writer.draft"], "agent.writer")
        self.assertEqual(claims["providers"]["writer.claims.read"], "agent.writer")


if __name__ == "__main__":
    unittest.main()
