"""Synthetic, explicit-path TraceStore regressions; no production runtime."""
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/meta'))
from trace_store import TraceEntry, TraceStore, TransitionRecord


def append_child(path, ready, start, label):
    store = TraceStore(path)
    ready.put(label)
    if not start.wait(5):
        raise TimeoutError('test barrier')
    for index in range(4):
        store.append(TraceEntry(label, 'synthetic', {'index': index}))
    store.record_transition(TransitionRecord(label, label + '-next', {'x': label}))
    store.save_snapshot(SimpleNamespace(version_id=label, to_dict=lambda: {'label': label}))


def hold_child(path, ready):
    from durable_json import bounded_lease
    with bounded_lease(path):
        ready.set()
        time.sleep(10)


class TraceDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=r'C:\Temp\opencode')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'trace.json'

    def test_transition_round_trip(self):
        store = TraceStore(self.path)
        entry = TraceEntry('synthetic', 'test', {'nested': ['é', 1]}, 'v0', 'b')
        transition = TransitionRecord('v0', 'v1', {'a': 1}, ['e'], {'m': 0}, {'m': 1})
        snapshot = {'version_id': 'v0', 'timestamp': 'fixed', 'nested': {'a': []}}
        store.append(entry)
        store.save_snapshot(SimpleNamespace(version_id='v0', to_dict=lambda: snapshot))
        store.record_transition(transition)
        before = self.path.read_bytes()
        loaded = TraceStore(self.path)
        self.assertEqual([e.to_dict() for e in loaded.entries], [e.to_dict() for e in store.entries])
        self.assertEqual([t.to_dict() for t in loaded.transitions], [transition.to_dict()])
        self.assertEqual(loaded.get_snapshot('v0'), snapshot)
        self.assertEqual(self.path.read_bytes(), before)

    def test_two_stale_instances_preserve_records(self):
        first, second = TraceStore(self.path), TraceStore(self.path)
        a, b = TraceEntry('a', 'test', {}), TraceEntry('b', 'test', {})
        first.append(a)
        second.append(b)
        self.assertEqual([e.entry_id for e in TraceStore(self.path).entries], [a.entry_id, b.entry_id])

    def test_missing_store_and_legacy_bytes(self):
        self.assertEqual(TraceStore(self.path).entries, [])
        self.assertFalse(self.path.exists())
        data = {'entries': [], 'transitions': [], 'state_snapshots': {'v': {'x': 1}}}
        self.path.write_text(json.dumps(data), encoding='utf-8')
        before = self.path.read_bytes()
        self.assertEqual(TraceStore(self.path).get_snapshot('v'), {'x': 1})
        self.assertEqual(self.path.read_bytes(), before)

    def test_corruption_never_overwritten_even_by_stale_writer(self):
        from durable_json import StoreCorruption
        store = TraceStore(self.path)
        for raw in (b'{bad', b'[]', b'{}', b'\xff',
                    b'{"entries":{},"transitions":[],"state_snapshots":{}}',
                    b'{"entries":[],"transitions":[],"state_snapshots":{"v":NaN}}'):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaises(StoreCorruption):
                    TraceStore(self.path)
                with self.assertRaises(StoreCorruption):
                    store.append(TraceEntry('test', 'test', {}))
                self.assertEqual(self.path.read_bytes(), raw)

    def test_failed_replace_keeps_bytes_cache_and_releases_lock(self):
        store = TraceStore(self.path)
        store.append(TraceEntry('before', 'test', {}))
        before = self.path.read_bytes()
        with patch('durable_json.os.replace', side_effect=OSError('injected before replace')):
            with self.assertRaises(OSError):
                store.record_transition(TransitionRecord('a', 'b', {}))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(store.entries), 1)
        self.assertEqual(store.transitions, [])
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        store.append(TraceEntry('after', 'test', {}))
        self.assertEqual(len(TraceStore(self.path).entries), 2)

    def test_invalid_write_does_not_commit_or_mutate_caller(self):
        store = TraceStore(self.path)
        entry = TraceEntry('valid', 'test', {'nested': []})
        original = entry.to_dict()
        store.append(entry)
        self.assertEqual(entry.to_dict(), original)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.append(TraceEntry('bad', 'test', {'number': float('nan')}))
        self.assertEqual(self.path.read_bytes(), before)
        entry.payload['nested'].append(1)
        self.assertEqual(store.entries[0].payload, {'nested': []})

    def test_stale_instances_preserve_transitions_and_snapshots(self):
        first, second = TraceStore(self.path), TraceStore(self.path)
        for store, label in ((first, 'a'), (second, 'b')):
            store.record_transition(TransitionRecord(label, label + '1', {}))
            store.save_snapshot(SimpleNamespace(version_id=label, to_dict=lambda: {'x': label}))
        loaded = TraceStore(self.path)
        self.assertEqual(len(loaded.transitions), 2)
        self.assertEqual(set(loaded.state_snapshots), {'a', 'b'})
        self.assertEqual(len(loaded.entries), 2)

    def test_bounded_timeout_and_exception_cleanup(self):
        from durable_json import bounded_lease
        lock = self.path.with_suffix('.lock')
        with bounded_lease(lock) as lease:
            handle = lease.handle
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                with bounded_lease(lock, timeout=0.05):
                    self.fail('second lock acquired')
            self.assertLess(time.monotonic() - started, 1)
        self.assertTrue(handle.closed)
        self.assertTrue(lock.exists())
        with self.assertRaisesRegex(RuntimeError, 'body'):
            with bounded_lease(lock) as lease:
                handle = lease.handle
                raise RuntimeError('body')
        self.assertTrue(handle.closed)
        with bounded_lease(lock, timeout=0.1):
            pass

    def test_close_exception_still_closes_handle(self):
        from durable_json import bounded_lease
        with self.assertRaisesRegex(OSError, 'unlock'):
            with bounded_lease(self.path.with_suffix('.lock')) as lease:
                handle = lease.handle
                lease.close = lambda: (_ for _ in ()).throw(OSError('unlock'))
        self.assertTrue(handle.closed)
        self.assertIsNone(lease.handle)
        with bounded_lease(self.path.with_suffix('.lock'), timeout=0.1):
            pass

    def test_invalid_timeouts(self):
        from durable_json import bounded_lease
        for timeout in (-1, float('inf'), float('nan')):
            with self.assertRaises(ValueError):
                with bounded_lease(self.path, timeout=timeout):
                    pass

    def test_two_spawned_stale_writers(self):
        ctx = multiprocessing.get_context('spawn')
        ready, start = ctx.Queue(), ctx.Event()
        children = [ctx.Process(target=append_child, args=(str(self.path), ready, start, label))
                    for label in ('a', 'b')]
        try:
            for child in children:
                child.start()
            self.assertEqual({ready.get(timeout=5), ready.get(timeout=5)}, {'a', 'b'})
            start.set()
            for child in children:
                child.join(8)
                self.assertEqual(child.exitcode, 0)
        finally:
            start.set()
            for child in children:
                if child.pid is not None:
                    if child.is_alive():
                        child.terminate()
                    child.join(3)
                    child.close()
            ready.close()
            ready.join_thread()
        store = TraceStore(self.path)
        self.assertEqual(len(store.entries), 10)
        self.assertEqual(len({e.entry_id for e in store.entries}), 10)
        self.assertEqual(len(store.transitions), 2)
        self.assertEqual(set(store.state_snapshots), {'a', 'b'})

    def test_owner_exit_releases_kernel_lock(self):
        from durable_json import bounded_lease
        ctx = multiprocessing.get_context('spawn')
        ready = ctx.Event()
        lock = self.path.with_suffix('.lock')
        child = ctx.Process(target=hold_child, args=(str(lock), ready))
        try:
            child.start()
            self.assertTrue(ready.wait(5))
            with self.assertRaises(TimeoutError):
                with bounded_lease(lock, timeout=0.05):
                    self.fail('owner was not locked')
        finally:
            if child.pid is not None:
                if child.is_alive():
                    child.terminate()
                child.join(3)
                child.close()
        with bounded_lease(lock, timeout=0.5):
            pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
