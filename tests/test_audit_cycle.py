# -*- coding: utf-8 -*-
"""Тесты: DamageBasket, ExternalAuditorV2, SleepPlannerAgent."""
import os, sys, io, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from damage_basket import DamageBasket, DamageEntry
from auditor_v2 import ExternalAuditorV2
from sleep_planner import SleepPlannerAgent


# --- DamageBasket ---
def test_basket_damage():
    with tempfile.TemporaryDirectory() as td:
        b = DamageBasket(td, threshold=100)
        b.drop(DamageEntry('R1', 'E', 'CRITICAL', 'm'))
        b.drop(DamageEntry('R2', 'E', 'WARNING', 'm'))
        b.drop(DamageEntry('R3', 'E', 'LOW', 'm'))
        assert b.total_damage() == 31  # 25+5+1
        assert b.should_trigger_sleep() is False


def test_basket_threshold():
    with tempfile.TemporaryDirectory() as td:
        b = DamageBasket(td, threshold=100)
        for _ in range(4):
            b.drop(DamageEntry('R', 'E', 'CRITICAL', 'm'))
        assert b.total_damage() == 100
        assert b.should_trigger_sleep() is True


def test_basket_cluster():
    with tempfile.TemporaryDirectory() as td:
        b = DamageBasket(td)
        b.drop(DamageEntry('RULE_A', 'E1', 'CRITICAL', 'x'))
        b.drop(DamageEntry('RULE_A', 'E1', 'WARNING', 'y'))
        b.drop(DamageEntry('RULE_B', 'E2', 'LOW', 'z'))
        cl = b.cluster_by_rule()
        assert len(cl['RULE_A']) == 2
        assert len(cl['RULE_B']) == 1


def test_basket_reset():
    with tempfile.TemporaryDirectory() as td:
        b = DamageBasket(td)
        b.drop(DamageEntry('R', 'E', 'CRITICAL', 'm'))
        b.reset()
        assert b.total_damage() == 0


# --- ExternalAuditorV2 ---
def test_auditor_dynamic_contract():
    with tempfile.TemporaryDirectory() as td:
        b = DamageBasket(td)
        aud = ExternalAuditorV2('aud', basket=b)
        # контракт под промпт оркестратора
        contract = aud.bind_contract('research', 'промпт оркестратора версия X')
        assert contract.prompt_hash  # хэш промпта
        assert len(contract.rules) >= 3
        # изоляция: аудитор не видит оркестратор
        assert all(k.startswith('auditor_') for k in aud.auditor_variables())


def test_auditor_drops_to_basket():
    with tempfile.TemporaryDirectory() as td:
        b = DamageBasket(td)
        aud = ExternalAuditorV2('aud', basket=b)
        # артефакт с нарушениями
        dropped = aud.observe_and_audit('XRD доказывает механизм, как известно')
        assert len(dropped) >= 2  # RULE_REL_04 (доказывает) + AP_T01 (как известно)
        assert b.total_damage() >= 26  # 25 + 1


def test_auditor_no_shared_state():
    """Аудитор не имеет доступа к оркестраторному state."""
    with tempfile.TemporaryDirectory() as td:
        b = DamageBasket(os.path.join(td, 'basket'))
        aud = ExternalAuditorV2('aud', basket=b, state_dir=os.path.join(td, 'aud'))
        # переменные только auditor_*
        vars_ = aud.auditor_variables()
        assert all(k.startswith('auditor_') for k in vars_)


# --- SleepPlannerAgent ---
def test_planner_plan():
    with tempfile.TemporaryDirectory() as td:
        b = DamageBasket(td, threshold=50)
        b.drop(DamageEntry('RULE_A', 'E1', 'CRITICAL', 'x'))
        b.drop(DamageEntry('RULE_A', 'E1', 'CRITICAL', 'y'))
        b.drop(DamageEntry('RULE_B', 'E2', 'CRITICAL', 'z'))
        planner = SleepPlannerAgent(b)
        plan = planner.run_plan('research')
        assert plan is not None
        assert 'fix/RULE_A' in plan.branches
        assert 'fix/RULE_B' in plan.branches
        prompt = plan.sleep_prompt()
        assert 'SLEEP-PLAN' in prompt
        assert 'RULE_A' in prompt


def test_planner_no_sleep():
    with tempfile.TemporaryDirectory() as td:
        b = DamageBasket(td, threshold=100)
        b.drop(DamageEntry('R', 'E', 'LOW', 'm'))  # 1 < 100
        planner = SleepPlannerAgent(b)
        assert planner.run_plan('research') is None


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