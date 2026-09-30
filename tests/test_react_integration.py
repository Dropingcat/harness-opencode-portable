# -*- coding: utf-8 -*-
"""Интеграция: ReactAuditorTools + ValidationPipeline (5 движков)."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from validation_engines import KnowledgeBase, ValidationPipeline
from react_auditor import ReactAuditorTools, AuditorInstance


def make_kb():
    kb = KnowledgeBase()
    kb.add_entity('OBS_XRD_FWHM', 'Observable')
    kb.add_entity('CLAIM_BULK_FERROMAGNETISM', 'Mechanism')
    kb.add_entity('CLAIM_MICROSTRAIN', 'PhysicalProperty')
    kb.set_allowed_slot_types('data', ['Observable', 'PhysicalProperty'])
    kb.set_allowed_slot_types('claim', ['Mechanism', 'PhysicalProperty'])
    kb.forbid_relation('OBS_XRD_FWHM', 'proves', 'Mechanism')
    kb.allow_relation('OBS_XRD_FWHM', 'indicates', 'PhysicalProperty')
    kb.set_evidence_type('OBS_XRD_FWHM', 'indirect')
    kb.set_requires_cross_check('CLAIM_BULK_FERROMAGNETISM')
    return kb


def test_react_with_full_pipeline():
    kb = make_kb()
    pipe = ValidationPipeline(kb)
    # валидатор для ReAct: оборачиваем pipeline
    def validator(inst):
        return pipe.validate_instance(inst)

    # начальное состояние: «уширение пика доказывает ферромагнетизм» (нет warrant)
    inst = AuditorInstance({
        'data': {'entity_id': 'OBS_XRD_FWHM'},
        'claim': {'entity_id': 'CLAIM_BULK_FERROMAGNETISM', 'modality': 'proves'},
    })
    tools = ReactAuditorTools(inst, validator, max_iterations=5)

    # Итерация 1: добавить warrant → всё ещё ошибки (claim неверен)
    obs1 = tools.add_slot('warrant', 'MODEL_WH')
    assert 'VALIDATION FAILED' in obs1
    # Итерация 2: изменить claim на microstrain + modality indicates + relation
    obs2 = tools.modify_slot('claim', 'CLAIM_MICROSTRAIN', 'indicates')
    assert 'VALIDATION FAILED' in obs2 or 'PASS' in obs2
    # добавить relation
    obs3 = tools.add_slot('relation', '', None)
    inst.slots['relation'] = {'value': 'indicates'}
    obs4 = tools.submit_final()
    assert 'SUCCESS' in obs4 or 'REJECTED' in obs4
    # история ReAct сохранена
    assert len(tools.replay_history()) >= 3


def test_react_ferro_case_errors():
    """ReAct с валидатором 5 движков: исходный сценарий даёт 3 ошибки."""
    kb = make_kb()
    pipe = ValidationPipeline(kb)
    inst = AuditorInstance({
        'data': {'entity_id': 'OBS_XRD_FWHM'},
        'claim': {'entity_id': 'CLAIM_BULK_FERROMAGNETISM', 'modality': 'proves'},
    })
    result = pipe.validate_instance(inst)
    assert result.has_critical
    rules = {e.rule_id for e in result.errors}
    assert 'RULE_CMP_01' in rules
    assert 'RULE_REL_04' in rules
    assert 'RULE_EPI_02' in rules


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