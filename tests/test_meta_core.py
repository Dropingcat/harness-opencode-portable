# -*- coding: utf-8 -*-
"""Тесты MetaCore: скилы <-> память <-> дашборд зациклены."""
import os, sys, io, tempfile, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from meta_core import MetaCore


def test_skill_upgrade_event():
    with tempfile.TemporaryDirectory() as td:
        mc = MetaCore('test', state_dir=td)
        # 5 использований → прокачка → событие
        ev = None
        for i in range(5):
            ev = mc.use_skill('xrd_skill', temporary_script=f'tmp{i}.py')
        assert ev is not None
        assert ev['level'] == 2
        assert 'xrd_skill' in ev['skill']


def test_dashboard_contains_skills():
    with tempfile.TemporaryDirectory() as td:
        mc = MetaCore('test', state_dir=td)
        for i in range(5):
            mc.use_skill('alpha')
        dash = mc.dashboard_text()
        assert '[SKILL-UPDATES]' in dash
        assert 'alpha' in dash
        assert 'level 2' in dash


def test_memory_lesson_written():
    """Прокачка вызывает memory_bridge (путь корректен, вызов не падает)."""
    with tempfile.TemporaryDirectory() as td:
        mc = MetaCore('test', state_dir=td)
        # путь bridge существует
        assert os.path.exists(mc.memory_bridge), 'memory_bridge должен существовать'
        for i in range(5):
            mc.use_skill('memory_skill')
        # _write_memory_lesson не бросил исключение (обработан)
        # не проверяем реальную запись (глобальный registry) — это интеграция


def test_cycle():
    with tempfile.TemporaryDirectory() as td:
        mc = MetaCore('test', state_dir=td)
        res = mc.cycle('задача')
        assert 'dashboard' in res
        assert 'hp' in res
        assert 'skill_events' in res


def test_skill_events_persist():
    with tempfile.TemporaryDirectory() as td:
        mc = MetaCore('test', state_dir=td)
        for i in range(5):
            mc.use_skill('persist_skill')
        mc2 = MetaCore('test', state_dir=td)
        assert len(mc2.skill_events) >= 1


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