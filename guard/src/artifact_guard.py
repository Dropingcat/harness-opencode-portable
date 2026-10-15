"""Bounded file admission. Receipts are evidence, never authorization tokens."""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import queue
import sys
import threading

MAX_BYTES = 65536
CHUNK_CHARS = 4000
OVERLAP = 256
MAX_TIMEOUT = 180.0
MAX_COST_RUB = 5.0
OWN_ROOT = Path(__file__).resolve().parents[2]
CODE_PATHS = ('guard/src/artifact_guard.py', 'guard/src/session_guard.py',
              'guard/src/semantic_layer.py', 'scripts/tools/doc_guard.py')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _root(explicit=None):
    selected = explicit if explicit is not None else os.environ.get('OPENCODE_HARNESS_ROOT', OWN_ROOT)
    root = Path(selected).resolve()
    # A launcher must not import executable code from an environment-selected tree.
    if root != OWN_ROOT or not all((root / p).is_file() for p in CODE_PATHS):
        raise ValueError('root_invalid')
    return root


def _identity(root):
    policy = (root / 'config/guard_policy.json').read_bytes()
    parsed = json.loads(policy)
    if not isinstance(parsed, dict) or parsed.get('mode') != 'mandatory_fail_closed':
        raise ValueError('policy_invalid')
    return {'policy_path': 'config/guard_policy.json', 'policy_sha256': _hash(policy),
            'policy_version': parsed.get('version'),
            'code_sha256': {p: _hash((root / p).read_bytes()) for p in CODE_PATHS}}


def _config(root, explicit=None):
    selected = explicit if explicit is not None else os.environ.get('DOC_GUARD_CONFIG')
    if selected is None:
        # Both existing bundled defaults, in deterministic order; never example configs.
        defaults = [Path.home() / '.config/opencode/guard_config.json',
                    root / 'guard/src/guard_config.json']
        selected = next((p for p in defaults if p.is_file()), defaults[0])
    path = Path(selected).resolve()
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError('config_size')
    cfg = json.loads(raw.decode('utf-8'))
    if not isinstance(cfg, dict) or not isinstance(cfg.get('budget', {}), dict):
        raise ValueError('config_shape')
    bcfg = cfg.get('budget', {})
    maximum = bcfg.get('max_cost_rub', 5.0)
    if type(maximum) not in (int, float) or not math.isfinite(maximum) or not 0 <= maximum <= MAX_COST_RUB:
        raise ValueError('config_budget')
    for key in ('warn_threshold_rub', 'alarm_threshold_rub'):
        value = bcfg.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum):
            raise ValueError('config_budget')
    if not isinstance(cfg.get('providers', {}), dict):
        raise ValueError('config_providers')
    for name, provider in cfg.get('providers', {}).items():
        if name not in ('cloud', 'fallback', 'local') or not isinstance(provider, dict):
            raise ValueError('config_providers')
    return cfg, {'source': 'explicit' if explicit is not None else 'environment_or_existing_default',
                 'sha256': _hash(raw)}, path


def _load_stages():
    directory = str(OWN_ROOT / 'guard/src')
    if directory not in sys.path:
        sys.path.insert(0, directory)
    p0 = importlib.import_module('session_guard')
    p2 = importlib.import_module('semantic_layer')
    for module, name in ((p0, 'session_guard.py'), (p2, 'semantic_layer.py')):
        if Path(module.__file__).resolve() != OWN_ROOT / 'guard/src' / name:
            raise ImportError('stage_identity')
    return p0, p2


def _report():
    return {'ok': False, 'verdict': 'BLOCK', 'reason': 'not_scanned',
            'required_stages': ['P0', 'P2'], 'executed_stages': [],
            'artifact': {'sha256': None, 'bytes': None},
            'coverage': {'complete': False, 'ranges': [], 'unit': 'unicode_characters',
                         'chunk_chars': CHUNK_CHARS, 'overlap_chars': OVERLAP},
            'identity': None, 'config': None, 'receipt_authorizes': False}


def preflight(*, harness_root=None, config=None):
    report = _report()
    report.update(verdict='READINESS', readiness=False, interpreter=sys.executable,
                  python_version=sys.version.split()[0], provider_availability_verified=False)
    try:
        root = _root(harness_root)
        report['harness_root'] = str(root)
        report['identity'] = _identity(root)
        _, report['config'], _ = _config(root, config)
        report.update(readiness=True, reason='metadata_ready_not_admission')
    except Exception:
        report['reason'] = 'readiness_unavailable'
    return report


def _chunks(text):
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        yield start, end, text[start:end]
        if end == len(text):
            break
        start = end - OVERLAP


def _p2_run(text, cfg, factory=None):
    _, semantic = _load_stages()
    if semantic.P2_MAX_TEXT < CHUNK_CHARS:
        return {'reason': 'coverage_limit', 'ranges': []}
    bcfg = cfg.get('budget', {})
    budget = semantic.Budget(bcfg.get('max_cost_rub', 5.0),
                             bcfg.get('warn_threshold_rub'), bcfg.get('alarm_threshold_rub'))
    chain = (factory or semantic.ClassifierChain)(cfg, budget)
    ranges = []
    for start, end, chunk in _chunks(text):
        result = chain.run(chunk)
        if not isinstance(result, dict) or not all(k in result for k in
                ('verdict', 'votes', 'provider', 'cost', 'alarm_level', 'alarm_info')):
            return {'reason': 'p2_invalid_result', 'ranges': ranges}
        verdict = result['verdict']
        if verdict == 'YES':
            return {'reason': 'p2_injection', 'ranges': ranges}
        votes = result['votes']
        if (verdict != 'NO' or result['alarm_level'] is not None
                or not isinstance(result['provider'], str) or not result['provider']
                or result['provider'] == 'none' or not isinstance(votes, dict)
                or any(type(votes.get(k)) is not int or votes[k] < 0 for k in ('yes', 'no', 'timeout'))
                or votes['no'] < 2 or sum(votes[k] for k in ('yes', 'no', 'timeout')) != 3
                or type(result['cost']) not in (int, float) or not math.isfinite(result['cost'])
                or result['cost'] < 0 or budget.spent > budget.max):
            return {'reason': 'p2_unavailable_or_invalid', 'ranges': ranges}
        ranges.append([start, end])
    return {'reason': 'scanned', 'ranges': ranges}


def _process_worker(connection, text, cfg):
    try:
        # Never relay provider stderr, raw text, config or exception details.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = _p2_run(text, cfg)
        connection.send(result)
    except Exception:
        connection.send({'reason': 'p2_error', 'ranges': []})
    finally:
        connection.close()


def _bounded_p2(text, cfg, factory, timeout):
    if factory is not None:
        # Function-argument injection only; fixtures cannot be selected by CLI/env.
        output = queue.Queue(1)
        def run_fixture():
            try:
                output.put(_p2_run(text, cfg, factory))
            except Exception:
                output.put({'reason': 'p2_error', 'ranges': []})
        threading.Thread(target=run_fixture, daemon=True).start()
        try:
            return output.get(timeout=timeout)
        except queue.Empty:
            return {'reason': 'timeout', 'ranges': []}
    ctx = multiprocessing.get_context('spawn')
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_process_worker, args=(sender, text, cfg))
    try:
        process.start()
        sender.close()
        if not receiver.poll(timeout):
            return {'reason': 'timeout', 'ranges': []}
        result = receiver.recv()
        process.join(timeout=1)
        if process.exitcode != 0:
            return {'reason': 'p2_process_error', 'ranges': []}
        return result
    finally:
        if process.is_alive():
            process.terminate()
        if process.pid is not None:
            process.join(timeout=2)
        receiver.close()
        sender.close()


def scan_artifact(artifact, *, harness_root=None, config=None, timeout=MAX_TIMEOUT,
                  chain_factory=None):
    report = _report()
    report['evidence'] = ('testing_only_not_host_certification' if chain_factory is not None
                          else 'fresh_scan_not_native_enforcement')
    try:
        root = _root(harness_root)
        report['identity'] = _identity(root)
        path = Path(artifact)
        with path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        report['artifact'] = {'sha256': _hash(raw) if len(raw) <= MAX_BYTES else None,
                              'bytes': len(raw), 'bounded': len(raw) <= MAX_BYTES}
        if not raw or len(raw) > MAX_BYTES:
            report['reason'] = 'empty_or_size_limit'
            return report
        text = raw.decode('utf-8', errors='strict')
        p0, _ = _load_stages()
        report['executed_stages'].append('P0')
        normalized = p0._normalize(text)
        for signature in p0.STRONG_EN + p0.WEAK_RU:
            sig = p0._normalize(signature)
            if sig in normalized and p0._suspicion(text, 'untrusted', 'read', sig) == 'high':
                report['reason'] = 'p0_signature'
                return report
        cfg, report['config'], config_path = _config(root, config)
        if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT:
            raise ValueError('timeout_invalid')
        report['executed_stages'].append('P2')
        result = _bounded_p2(text, cfg, chain_factory, timeout)
        report['reason'] = result['reason']
        ranges = result['ranges']
        report['coverage']['ranges'] = ranges
        report['coverage']['characters'] = len(text)
        complete = (bool(ranges) and ranges[0][0] == 0 and ranges[-1][1] == len(text)
                    and all(0 <= a < b <= len(text) and b-a <= CHUNK_CHARS for a, b in ranges)
                    and all(a[1] >= b[0] for a, b in zip(ranges, ranges[1:])))
        report['coverage']['complete'] = complete
        with path.open('rb') as stream:
            current = stream.read(MAX_BYTES + 1)
        if current != raw:
            report['reason'] = 'artifact_changed'
        elif _identity(root) != report['identity']:
            report['reason'] = 'identity_changed'
        elif _hash(config_path.read_bytes()) != report['config']['sha256']:
            report['reason'] = 'config_changed'
        elif result['reason'] == 'scanned' and complete:
            report.update(ok=True, verdict='PASS')
        elif result['reason'] == 'scanned':
            report['reason'] = 'coverage_gap'
    except UnicodeError:
        report['reason'] = 'invalid_utf8'
    except ImportError:
        report['reason'] = 'stage_import_unavailable'
    except Exception:
        report['reason'] = 'input_root_policy_config_or_stage_unavailable'
    return report
