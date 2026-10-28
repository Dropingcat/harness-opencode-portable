"""Bounded alias rejection and pre-publication lease cleanup regressions."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts' / 'meta'))
from daemon_safety import FileLease
from durable_json import bounded_lease
from trace_store import TraceEntry, TraceStore


class TraceStoreReworkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=r'C:\Temp\opencode')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'trace.json'
        self.alias = self.path.with_name('alias.json')

    def symlink(self, target):
        try:
            self.alias.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f'file symlink unavailable: {exc}')

    def test_file_symlink_rejected_before_mutation_with_target_locked(self):
        store = TraceStore(self.path)
        store.append(TraceEntry('before', 'test', {}))
        stale_alias = TraceStore(self.alias)
        before = self.path.read_bytes()
        self.symlink(self.path)
        with bounded_lease(self.path.with_name(self.path.name + '.lock')):
            with self.assertRaisesRegex(ValueError, 'symlink'):
                TraceStore(self.alias)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                stale_alias.append(TraceEntry('rejected', 'test', {}))
        self.assertTrue(self.alias.is_symlink())
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.alias.read_bytes(), before)
        self.assertFalse(self.alias.with_name('alias.json.lock').exists())
        self.assertEqual(stale_alias.entries, [])
        store.append(TraceEntry('after', 'test', {}))
        self.assertEqual(len(TraceStore(self.path).entries), 2)

    def test_dangling_file_symlink_rejected_without_creating_target(self):
        self.symlink(self.path)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            TraceStore(self.alias)
        self.assertTrue(self.alias.is_symlink())
        self.assertFalse(self.path.exists())
        self.assertFalse(self.alias.with_name('alias.json.lock').exists())

    def test_hardlinks_rejected_on_both_names_before_mutation(self):
        store = TraceStore(self.path)
        store.append(TraceEntry('before', 'test', {}))
        stale_alias = TraceStore(self.alias)
        before = self.path.read_bytes()
        try:
            os.link(self.path, self.alias)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f'hardlinks unavailable: {exc}')
        self.assertGreater(self.path.stat().st_nlink, 1)
        with bounded_lease(self.path.with_name(self.path.name + '.lock')):
            for path, stale in ((self.path, store), (self.alias, stale_alias)):
                with self.subTest(path=path):
                    with self.assertRaisesRegex(ValueError, 'hardlink'):
                        TraceStore(path)
                    with self.assertRaisesRegex(ValueError, 'hardlink'):
                        stale.append(TraceEntry('rejected', 'test', {}))
        self.assertTrue(os.path.samefile(self.path, self.alias))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.alias.read_bytes(), before)
        self.assertFalse(self.alias.with_name('alias.json.lock').exists())
        self.alias.unlink()
        store.append(TraceEntry('after', 'test', {}))
        self.assertEqual(len(TraceStore(self.path).entries), 2)

    def test_non_oserror_acquisition_closes_open_handle_and_allows_retry(self):
        lease = FileLease(self.path.with_suffix('.lock'))
        real_open = Path.open
        opened = []

        def capture_open(path, *args, **kwargs):
            handle = real_open(path, *args, **kwargs)
            opened.append(handle)
            return handle

        boundary = 'msvcrt.locking' if os.name == 'nt' else 'fcntl.flock'
        with patch.object(Path, 'open', capture_open):
            with patch(boundary, side_effect=RuntimeError('injected acquisition')):
                with self.assertRaisesRegex(RuntimeError, 'injected acquisition'):
                    lease.acquire()
        try:
            self.assertEqual(len(opened), 1)
            self.assertTrue(opened[0].closed)
            self.assertIsNone(lease.handle)
            self.assertTrue(lease.acquire())
            contender = FileLease(lease.path)
            try:
                self.assertFalse(contender.acquire())
            finally:
                contender.close()
        finally:
            lease.close()
            for handle in opened:
                handle.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
