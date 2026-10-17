"""Offline Windows Desktop CLI discovery contract for coder_router.

No subprocess or model call is made: these tests only validate command construction.
"""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ROUTER_PATH = ROOT / "mcp" / "coder_router_server.py"


def load_router():
    spec = importlib.util.spec_from_file_location("router_desktop_discovery", ROUTER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DesktopCliDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.router = load_router()

    def test_explicit_environment_has_priority(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "approved-opencode-cli.exe"
            binary.write_bytes(b"")
            result = self.router._resolve_opencode_bin(
                environment={"CODER_ROUTER_OPENCODE": str(binary)},
                which=lambda _: "should-not-run",
            )
        self.assertEqual(str(binary), result)

    def test_path_cli_precedes_desktop_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "opencode-cli.exe"
            binary.write_bytes(b"")
            result = self.router._resolve_opencode_bin(
                environment={},
                which=lambda name: str(binary) if name == "opencode-cli" else None,
            )
        self.assertEqual(str(binary), result)

    def test_stale_path_candidate_does_not_mask_desktop_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "ai.opencode.desktop" / "cli" / "2.0.29-x64"
            desktop = root / "opencode-cli.exe"
            root.mkdir(parents=True)
            desktop.write_bytes(b"")
            result = self.router._resolve_opencode_bin(
                environment={"APPDATA": temporary},
                which=lambda _: str(Path(temporary) / "missing-opencode.exe"),
            )
        self.assertEqual(str(desktop), result)

    def test_stale_environment_override_does_not_mask_desktop_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "ai.opencode.desktop" / "cli" / "2.0.29-x64"
            desktop = root / "opencode-cli.exe"
            root.mkdir(parents=True)
            desktop.write_bytes(b"")
            result = self.router._resolve_opencode_bin(
                environment={
                    "APPDATA": temporary,
                    "OPENCODE_BIN": str(Path(temporary) / "stale-opencode.exe"),
                },
                which=lambda _: None,
            )
        self.assertEqual(str(desktop), result)

    def test_stale_primary_override_allows_valid_secondary_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            valid = Path(temporary) / "valid-opencode-cli.exe"
            valid.write_bytes(b"")
            result = self.router._resolve_opencode_bin(
                environment={
                    "CODER_ROUTER_OPENCODE": str(Path(temporary) / "stale.exe"),
                    "OPENCODE_BIN": str(valid),
                },
                which=lambda _: None,
            )
        self.assertEqual(str(valid), result)

    def test_newest_desktop_cli_is_selected_when_path_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "ai.opencode.desktop" / "cli"
            old = root / "2.0.9-x64" / "opencode-cli.exe"
            latest = root / "2.0.29-x64" / "opencode-cli.exe"
            old.parent.mkdir(parents=True)
            latest.parent.mkdir(parents=True)
            old.write_bytes(b"")
            latest.write_bytes(b"")
            result = self.router._resolve_opencode_bin(
                environment={"APPDATA": temporary}, which=lambda _: None
            )
        self.assertEqual(str(latest), result)

    def test_v2_command_has_explicit_model_and_no_retired_flags(self):
        command = self.router._cli_command("opencode-cli.exe", "openai/gpt-5.6-terra", "synthetic")
        self.assertEqual(
            ["opencode-cli.exe", "run", "--model", "openai/gpt-5.6-terra", "synthetic"],
            command,
        )
        self.assertNotIn("--pure", command)
        self.assertNotIn("--dir", command)


if __name__ == "__main__":
    unittest.main(verbosity=2)
