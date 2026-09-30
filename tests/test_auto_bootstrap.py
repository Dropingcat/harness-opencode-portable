# -*- coding: utf-8 -*-
"""Тесты AutoBootstrap: автозапуск, инжекция, автообработка контракта."""
import os, sys, io, tempfile, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from auto_bootstrap import AutoBootstrap


def test_dashboard_injection():
    with tempfile.TemporaryDirectory() as td:
        ab = AutoBootstrap('test', state_dir=td, auto_start_daemon=False)
        dash = ab.inject_dashboard()
        assert '[DASHBOARD' in dash
        assert 'HP=' in dash


def test_contract_autoprocess():
    with tempfile.TemporaryDirectory() as td:
        ab = AutoBootstrap('test', state_dir=td, auto_start_daemon=False)
        # создаём контракт сна (как от демона)
        contract = {
            'plan_id': 'plan-1',
            'orchestrator': 'test',
            'branches': ['fix/RULE_A', 'fix/RULE_B'],
            'clusters': {},
            'merged': False,
        }
        ab.contract_file.write_text(json.dumps(contract, ensure_ascii=False), encoding='utf-8')
        result = ab.process_sleep_contract()
        assert result is not None
        assert result['merged'] is True
        # повторный вызов — не обрабатывает снова
        result2 = ab.process_sleep_contract()
        assert result2 is None
        # meta sleep_state обновлён
        assert ab.meta.sleep_state.get('merged') is True


def test_contract_no_file():
    with tempfile.TemporaryDirectory() as td:
        ab = AutoBootstrap('test', state_dir=td, auto_start_daemon=False)
        assert ab.process_sleep_contract() is None


def test_contract_already_merged():
    with tempfile.TemporaryDirectory() as td:
        ab = AutoBootstrap('test', state_dir=td, auto_start_daemon=False)
        contract = {'plan_id': 'p2', 'branches': [], 'merged': True}
        ab.contract_file.write_text(json.dumps(contract), encoding='utf-8')
        assert ab.process_sleep_contract() is None


def test_bootstrap_full():
    with tempfile.TemporaryDirectory() as td:
        ab = AutoBootstrap('test', state_dir=td, auto_start_daemon=False)
        res = ab.bootstrap()
        assert 'dashboard' in res
        assert 'contract_processed' in res
        assert 'hp' in res


def test_ensure_daemon_noop():
    """Без автозапуска — демон не стартует."""
    with tempfile.TemporaryDirectory() as td:
        ab = AutoBootstrap('test', state_dir=td, auto_start_daemon=False)
        assert ab.ensure_daemon() is False


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            import traceback; traceback.print_exc()
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__} {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)