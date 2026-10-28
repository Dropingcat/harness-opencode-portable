"""Independent A1 checks: synthetic paths only, no default runtime storage."""
import copy
import inspect
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/meta'))
import durable_json as durable
from trace_store import TraceEntry, TraceStore, TransitionRecord


class IndependentTraceTests(unittest.TestCase):
    def test_stale_writer_preserves_dangling_leaf_symlink(self):
        # The worker dangling-link case checks construction only, not a stale write.
        store = TraceStore(self.path)
        target = self.path.with_name('missing-target.json')
        try:
            self.path.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f'file symlink unavailable: {exc}')
        before = self.path.lstat()
        link_target = self.path.readlink()
        with self.assertRaisesRegex(ValueError, 'symlink'):
            store.append(TraceEntry('rejected', 'event', {}))
        after = self.path.lstat()
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(self.path.readlink(), link_target)
        self.assertEqual((after.st_ino, after.st_size, after.st_mtime_ns),
                         (before.st_ino, before.st_size, before.st_mtime_ns))
        self.assertFalse(target.exists())
        self.assertFalse(self.path.with_name('trace.json.lock').exists())
        self.assertEqual(store.entries, [])
        self.path.unlink()
        store.append(TraceEntry('accepted', 'event', {}))
        self.assertEqual(len(TraceStore(self.path).entries), 1)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=r'C:\Temp\opencode')
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'trace.json'

    def fixture(self):
        return {
            'entries': [{'entry_id': 'fixed-id', 'timestamp': '2001-02-03T04:05:06',
                         'source_branch': 'fixture', 'event_type': 'observed',
                         'payload': {'nested': ['λ', 17]},
                         'related_state_version': 'v0', 'related_branch_id': 'branch'}],
            'transitions': [{'from_version': 'v0', 'to_version': 'v1',
                             'delta': {'x': 19}, 'evidence': ['fixed-id'],
                             'metrics_before': {'score': 2}, 'metrics_after': {'score': 3},
                             'timestamp': '2001-02-03T04:06:07'}],
            'state_snapshots': {'v0': {'x': 2, 'timestamp': '2001-02-03T04:00:00'}}}

    def seed(self):
        data = self.fixture()
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return data

    def test_literal_legacy_fixture_survives_reload_and_new_commit(self):
        expected = self.seed()
        store = TraceStore(self.path)
        entry = store.entries[0]
        self.assertEqual((entry.entry_id, entry.timestamp, entry.payload),
                         ('fixed-id', '2001-02-03T04:05:06', {'nested': ['λ', 17]}))
        self.assertEqual(store.transitions[0].timestamp, '2001-02-03T04:06:07')
        self.assertEqual(store.get_snapshot('v0'), {'x': 2, 'timestamp': '2001-02-03T04:00:00'})
        store.append(TraceEntry('new', 'event', {}))
        disk = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(disk['entries'][0], expected['entries'][0])
        self.assertEqual(disk['transitions'], expected['transitions'])
        self.assertEqual(disk['state_snapshots'], expected['state_snapshots'])
        self.assertEqual(len(TraceStore(self.path).entries), 2)

    def test_mutator_exception_preserves_bytes_and_releases_lock(self):
        self.seed()
        before = self.path.read_bytes()
        def fail(data):
            data['entries'].clear()
            raise RuntimeError('mutator failure')
        with self.assertRaisesRegex(RuntimeError, 'mutator failure'):
            durable.update_json(self.path, TraceStore._default, TraceStore._validate, fail)
        self.assertEqual(self.path.read_bytes(), before)
        TraceStore(self.path).append(TraceEntry('after', 'event', {}))
        self.assertEqual(len(TraceStore(self.path).entries), 2)

    def test_write_and_flush_failures_preserve_disk_cache_and_release(self):
        self.seed()
        store = TraceStore(self.path)
        before = self.path.read_bytes()
        # Boundary injection, not a simulated OS/filesystem durability claim.
        for boundary in ('durable_json.os.fsync', 'durable_json.tempfile.NamedTemporaryFile'):
            with self.subTest(boundary=boundary):
                with patch(boundary, side_effect=OSError('injected write failure')):
                    with self.assertRaisesRegex(OSError, 'injected write failure'):
                        store.append(TraceEntry('fail', 'event', {}))
                self.assertEqual(self.path.read_bytes(), before)
                self.assertEqual([e.entry_id for e in store.entries], ['fixed-id'])
                self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
                with durable.bounded_lease(self.path.with_name('trace.json.lock'), timeout=0):
                    pass

    def test_wrong_nested_shapes_fail_on_read_and_stale_write(self):
        stale = TraceStore(self.path)
        cases = []
        for collection, field, value in (
                ('entries', 'payload', []), ('entries', 'entry_id', 7),
                ('entries', 'related_branch_id', {}),
                ('transitions', 'evidence', [7]), ('transitions', 'delta', []),
                ('transitions', 'timestamp', None)):
            data = self.fixture()
            data[collection][0][field] = value
            cases.append(data)
        data = self.fixture()
        data['state_snapshots']['v0'] = []
        cases.extend([data, {'schema_version': 99, **self.fixture()}, None])
        for data in cases:
            with self.subTest(data=data):
                raw = json.dumps(data).encode('utf-8')
                self.path.write_bytes(raw)
                with self.assertRaises(durable.StoreCorruption):
                    TraceStore(self.path)
                with self.assertRaises(durable.StoreCorruption):
                    stale.append(TraceEntry('stale', 'event', {}))
                self.assertEqual(self.path.read_bytes(), raw)

    def test_caller_transition_and_snapshot_not_aliased(self):
        store = TraceStore(self.path)
        delta, evidence = {'x': [1]}, ['proof']
        transition = TransitionRecord('v0', 'v1', delta, evidence)
        snapshot = {'x': [2]}
        original = copy.deepcopy(snapshot)
        class State:
            version_id = 'v1'
            def to_dict(self):
                return snapshot
        store.save_snapshot(State())
        store.record_transition(transition)
        self.assertEqual(snapshot, original)
        delta['x'].append(9)
        evidence.append('later')
        snapshot['x'].append(8)
        self.assertEqual(store.transitions[0].delta, {'x': [1]})
        self.assertEqual(store.transitions[0].evidence, ['proof'])
        self.assertEqual(store.get_snapshot('v1'), {'x': [2]})
        self.assertEqual(TraceStore(self.path).get_snapshot('v1'), {'x': [2]})

    def test_public_parameter_names_and_defaults(self):
        expected = {
            TraceStore: ['storage_path'], TraceEntry: ['source_branch', 'event_type', 'payload',
                'related_state_version', 'related_branch_id'],
            TransitionRecord: ['from_version', 'to_version', 'delta', 'evidence',
                               'metrics_before', 'metrics_after'],
            TraceStore.append: ['self', 'entry'],
            TraceStore.record_transition: ['self', 'tr'],
            TraceStore.save_snapshot: ['self', 'state'],
            TraceStore.reconstruct_state: ['self', 'initial_state', 'version_id']}
        for function, names in expected.items():
            with self.subTest(function=function.__name__):
                self.assertEqual(list(inspect.signature(function).parameters), names)
        self.assertIsNone(inspect.signature(TraceStore).parameters['storage_path'].default)
        for name in ('initial_state', 'version_id'):
            self.assertIsNone(inspect.signature(TraceStore.reconstruct_state).parameters[name].default)


if __name__ == '__main__':
    unittest.main(verbosity=2)
