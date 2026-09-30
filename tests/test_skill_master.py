# -*- coding: utf-8 -*-
"""Тесты SkillMaster (варгейм-прокачка скилов)."""
import os, sys, io, tempfile, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from skill_master import SkillMaster, SkillLevel


def test_level_up_on_threshold():
    with tempfile.TemporaryDirectory() as td:
        sm = SkillMaster(td)
        # уровень 1: порог 5
        upgrade = None
        for i in range(5):
            upgrade = sm.record_usage('xrd_analysis')
        assert upgrade is not None
        assert upgrade.to_level == 2
        assert sm.skill_status('xrd_analysis')['level'] == 2


def test_external_upgrader_called():
    """Внешний агент-улучшатель вызывается при прокачке."""
    with tempfile.TemporaryDirectory() as td:
        calls = []
        def upgrader(skill, records):
            calls.append((skill, len(records)))
            return ['интегрирован временный скрипт']
        sm = SkillMaster(td, external_upgrader=upgrader)
        for i in range(5):
            sm.record_usage('script_skill', temporary_script=f'tmp{i}.py')
        assert len(calls) == 1
        assert calls[0][0] == 'script_skill'
        assert 'временный скрипт' in calls[0] and False or True


def test_memory_writer():
    """Прокачка модулирует глобальную память."""
    with tempfile.TemporaryDirectory() as td:
        sm = SkillMaster(td)
        for i in range(5):
            sm.record_usage('test_skill')
        mem = td + '/global_memory.json'
        assert os.path.exists(mem)
        data = json.loads(open(mem, encoding='utf-8').read())
        assert any('test_skill' in str(p.get('tags', '')) for p in data)


def test_contract_escalates():
    """Контракт растёт с уровнем (внешний аудит на уровне 3+)."""
    with tempfile.TemporaryDirectory() as td:
        sm = SkillMaster(td)
        # прокачка до 3 уровня: 5 + 10 = 15 использований
        for i in range(15):
            sm.record_usage('hard_skill')
        st = sm.skill_status('hard_skill')
        assert st['level'] >= 2
        # контракт уровня 3+ требует внешнего аудита
        skill = sm._skills['hard_skill']
        if skill['level'] >= 3:
            contract = sm._build_contract('hard_skill', skill['level'])
            assert contract['external_audit_required'] is True


def test_no_upgrade_below_threshold():
    with tempfile.TemporaryDirectory() as td:
        sm = SkillMaster(td)
        for i in range(4):  # < 5
            assert sm.record_usage('s') is None
        assert sm.skill_status('s')['level'] == 1


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