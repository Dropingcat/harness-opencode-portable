# -*- coding: utf-8 -*-
"""Тесты OrchestratorIntegration."""
import os, sys, io, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from orchestrator_integration import OrchestratorIntegration


def test_pre_task_ok():
    with tempfile.TemporaryDirectory() as td:
        meta = OrchestratorIntegration('test', state_dir=td)
        ok, hint = meta.pre_task('задача')
        assert ok is True
        assert meta.cycle == 1


def test_post_task_damage_and_death():
    with tempfile.TemporaryDirectory() as td:
        meta = OrchestratorIntegration('test', state_dir=td, health_points=40, lives=2)
        ok, _ = meta.pre_task('x')
        # критический сигнал → damage → смерть
        status = meta.post_task('x', 'текст', metrics={'error_score': 0.5},
                                signals=[{'severity': 'CRITICAL', 'channel': 'phys',
                                          'message': 'bad'}])
        assert status in ('DEATH', 'OK')
        assert meta.deaths >= 1


def test_legacy_hint():
    with tempfile.TemporaryDirectory() as td:
        meta = OrchestratorIntegration('test', state_dir=td)
        # записываем провал
        meta.on_failure('ошибка X', task='сверхпроводимость')
        ok, hint = meta.pre_task('сверхпроводимость')
        # hint может быть пустым (embedding не настроен), но legacy не пуст
        assert len(meta.legacy.records) >= 1


def test_veto():
    with tempfile.TemporaryDirectory() as td:
        meta = OrchestratorIntegration('test', state_dir=td, health_points=10, lives=0)
        assert meta.veto() is True


def test_state_persist():
    with tempfile.TemporaryDirectory() as td:
        meta = OrchestratorIntegration('test', state_dir=td)
        meta.pre_task('a')
        meta.post_task('a', 'ok')
        # новый инстанс читает то же состояние
        meta2 = OrchestratorIntegration('test', state_dir=td)
        assert meta2.cycle >= 1


def test_status():
    with tempfile.TemporaryDirectory() as td:
        meta = OrchestratorIntegration('test', state_dir=td)
        s = meta.status()
        assert 'orchestrator' in s and 'health' in s and 'veto' in s


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
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__} {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)