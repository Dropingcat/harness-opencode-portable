# -*- coding: utf-8 -*-
"""Тесты MergeProtocol (V2)."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from state import StateManager, StateVariable, StabilityLevel, SystemState
from merge_protocol import (MergeProtocol, MergeRequest, ThreeWayMergeContext,
                            MergeConflict, MergeConflictType)


def make_state(**vars_):
    sm = StateManager()
    for k, v in vars_.items():
        sm.set_variable(k, v, StabilityLevel.POLICY)
    return sm.current


def test_merge_no_conflict():
    base = make_state(a=1, b=2)
    ours = make_state(a=1, b=2)   # same as base
    ours.variables['b'].update(20)  # ours изменил b
    theirs = make_state(a=1, b=2)
    theirs.variables['a'].update(10)  # theirs изменил a (не конфликт)
    ctx = ThreeWayMergeContext(base, ours, theirs, {'a': 10})
    req = MergeRequest('branch1', ctx)
    mp = MergeProtocol()
    result = mp.execute_merge(req)
    assert result.success, result.failure_reason
    assert result.new_main_state.variables['a'].value == 10  # из theirs
    assert result.new_main_state.variables['b'].value == 20  # из ours


def test_merge_conflict_auto():
    base = make_state(a=1, b=2)
    ours = make_state(a=1, b=2)
    ours.variables['a'].update(None)  # ours поставил None
    theirs = make_state(a=1, b=2)
    theirs.variables['a'].update(5)   # theirs поставил 5
    ctx = ThreeWayMergeContext(base, ours, theirs, {'a': 5})
    req = MergeRequest('branch1', ctx)
    mp = MergeProtocol()
    result = mp.execute_merge(req)
    assert result.success
    # auto-resolve: None + 5 -> 5 (their)
    assert result.new_main_state.variables['a'].value == 5


def test_merge_regression_fail():
    base = make_state(a=1)
    ours = make_state(a=1)
    theirs = make_state(a=1)
    theirs.variables['a'].update(2)
    ctx = ThreeWayMergeContext(base, ours, theirs, {'a': 2})
    req = MergeRequest('branch1', ctx)
    # regression всегда падает
    mp = MergeProtocol(regression_suite=lambda s: (False, ['test_fail']))
    result = mp.execute_merge(req)
    assert result.success is False
    assert result.rollback_performed is True
    assert req.decision == 'REJECT'


def test_merge_invariant_violation():
    base = make_state(a=1)
    ours = make_state(a=1)
    theirs = make_state(a=1)
    theirs.variables['a'].update(2)
    ctx = ThreeWayMergeContext(base, ours, theirs, {'a': 2})
    req = MergeRequest('branch1', ctx)
    mp = MergeProtocol(invariant_checker=lambda s: False)  # инвариант нарушен
    result = mp.execute_merge(req)
    assert result.success is False
    assert req.decision == 'REJECT'


def test_cherry_pick():
    branch = make_state(a=1, b=2, c=3)
    main = make_state(a=1, b=2)
    mp = MergeProtocol()
    result = mp.cherry_pick(branch, 'c', main)
    assert 'c' in result.variables


def test_rebase():
    branch = make_state(a=1)
    new_base = make_state(x=99)
    mp = MergeProtocol()
    rebased = mp.rebase(branch, new_base)
    assert rebased.parent_version_id == new_base.version_id


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