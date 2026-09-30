# -*- coding: utf-8 -*-
"""Тесты ReactAuditorTools (TD-163)."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from react_auditor import (ReactAuditorTools, AuditorInstance, AuditResult,
                           AuditError, ValidationStatus)


def make_validator(required_slot='warrant', claim_allowed=('PROP_MICROSTRAIN',)):
    """Валидатор: проверяет warrant + что claim разрешён."""
    def validate(inst):
        errors = []
        slots = inst.slots
        if required_slot not in slots:
            errors.append(AuditError('CRITICAL', 'Completeness', 'RULE_CMP_01',
                                     f"Missing slot '{required_slot}'"))
        claim = slots.get('claim', {}).get('entity_id')
        if claim and claim not in claim_allowed:
            errors.append(AuditError('CRITICAL', 'RelationGraph', 'RULE_REL_04',
                                     f"claim '{claim}' not allowed",
                                     f"allowed: {claim_allowed}"))
        if not errors:
            return AuditResult(ValidationStatus.PASS, [])
        return AuditResult(ValidationStatus.FAIL, errors)
    return validate


def test_react_loop_to_pass():
    inst = AuditorInstance({'claim': {'entity_id': 'CLAIM_BULK_FERRO'}})
    tools = ReactAuditorTools(inst, make_validator())
    # 1. add warrant -> still fail (claim wrong)
    obs1 = tools.add_slot('warrant', 'MODEL_WH')
    assert 'VALIDATION FAILED' in obs1
    # 2. modify claim -> PASS
    obs2 = tools.modify_slot('claim', 'PROP_MICROSTRAIN', 'indicates')
    assert 'PASS' in obs2
    # 3. submit -> SUCCESS
    obs3 = tools.submit_final()
    assert 'SUCCESS' in obs3
    # history: 3 шага
    assert len(tools.replay_history()) == 3


def test_react_max_iterations():
    def always_fail(inst):
        return AuditResult(ValidationStatus.FAIL,
                           [AuditError('CRITICAL', 'x', 'RULE_X', 'всегда')])
    inst = AuditorInstance({})
    tools = ReactAuditorTools(inst, always_fail, max_iterations=2)
    tools.add_slot('a', '1')
    tools.add_slot('b', '2')
    obs = tools.add_slot('c', '3')  # 3-я итерация > max=2
    assert 'MAX_ITERATIONS' in obs
    assert 'FAILED_REPAIR' in obs


def test_modify_nonexistent_slot():
    inst = AuditorInstance({})
    tools = ReactAuditorTools(inst, make_validator())
    obs = tools.modify_slot('ghost', 'X')
    assert 'does not exist' in obs


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