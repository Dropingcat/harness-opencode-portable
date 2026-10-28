from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from knowledge_pilot.lease import FileLease, LeaseBusy
from knowledge_pilot.network import Network


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def test_M2_stale_search_lock_does_not_permanently_block_startup(self):
        network = Network(self.home, {"search_url": "http://127.0.0.1:8888", "search_backend": "existing-mini-searxng", "harness_root": str(self.home)})
        (self.home / "state/search-start.lock").write_text("legacy lock", encoding="utf-8")
        with patch.object(network, "search_health", side_effect=[{"available": False}, {"available": True}]), patch("knowledge_pilot.network.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="ready", stderr="")) as launched:
            result = network.ensure_search()
        self.assertTrue(result["available"])
        self.assertEqual(launched.call_count, 1)

    def test_one_owner_and_crash_recovery(self):
        path = self.home / "state/fixture.lease"
        with FileLease(path, self.home):
            with self.assertRaises(LeaseBusy):
                with FileLease(path, self.home):
                    pass
        code = "from knowledge_pilot.lease import FileLease; import os,sys; lock=FileLease(sys.argv[1],sys.argv[2]);lock.__enter__();os._exit(0)"
        result = subprocess.run([sys.executable, "-B", "-c", code, str(path), str(self.home)], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        with FileLease(path, self.home):
            pass


if __name__ == "__main__":
    unittest.main()
