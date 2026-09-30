# -*- coding: utf-8 -*-
"""Тесты validation_engines (5 движков) — по сценарию из спецификации."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from validation_engines import (KnowledgeBase, ValidationPipeline, ValidationResult,
                                OntologyTypeChecker, RelationGraphValidator,
                                EpistemicModalityChecker, BoundaryConditionValidator,
                                CompletenessChecker)


def make_kb():
    kb = KnowledgeBase()
    # сущности
    kb.add_entity('OBS_XRD_FWHM', 'Observable')
    kb.add_entity('CLAIM_BULK_FERROMAGNETISM', 'Mechanism')
    kb.add_entity('CLAIM_MICROSTRAIN', 'PhysicalProperty')
    kb.add_entity('OBS_SQUID', 'CrossCheckEvidence')
    # слоты
    kb.set_allowed_slot_types('data', ['Observable', 'PhysicalProperty'])
    kb.set_allowed_slot_types('claim', ['Mechanism', 'PhysicalProperty'])
    # relations
    kb.forbid_relation('OBS_XRD_FWHM', 'proves', 'Mechanism')
    kb.allow_relation('OBS_XRD_FWHM', 'indicates', 'PhysicalProperty')
    # epistemic
    kb.set_evidence_type('OBS_XRD_FWHM', 'indirect')
    kb.set_evidence_type('OBS_SQUID', 'direct')
    kb.set_requires_cross_check('CLAIM_BULK_FERROMAGNETISM')
    # boundaries
    kb.add_model_boundary('MODEL_CURIE_WEISS', 'Temperature', '> Tc')
    return kb


def test_full_pipeline_ferro_case():
    """«Уширение пика доказывает ферромагнетизм» — 3 критических ошибки."""
    kb = make_kb()
    pipe = ValidationPipeline(kb)
    instance = {
        'template': 'T3',
        'slots': {
            'data': {'entity_id': 'OBS_XRD_FWHM'},
            'claim': {'entity_id': 'CLAIM_BULK_FERROMAGNETISM', 'modality': 'proves'},
            # warrant отсутствует
        },
        'conditions': {},
    }
    result = pipe.validate(instance)
    assert result.status == 'FAIL'
    assert result.has_critical
    rules = {e.rule_id for e in result.errors}
    # По спецификации: RULE_CMP_01 (warrant), RULE_REL_04 (forbidden proves), RULE_EPI_02 (indirect proves)
    assert 'RULE_CMP_01' in rules, rules
    assert 'RULE_REL_04' in rules, rules
    assert 'RULE_EPI_02' in rules, rules


def test_after_repair_pass():
    """После исправления (warrant + claim на microstrain + modality indicates) — PASS."""
    kb = make_kb()
    pipe = ValidationPipeline(kb)
    instance = {
        'template': 'T3',
        'slots': {
            'data': {'entity_id': 'OBS_XRD_FWHM'},
            'claim': {'entity_id': 'CLAIM_MICROSTRAIN', 'modality': 'indicates'},
            'warrant': {'entity_id': 'MODEL_WH'},
            'relation': {'value': 'indicates'},
        },
        'conditions': {},
    }
    result = pipe.validate(instance)
    assert result.status == 'PASS', [e.message for e in result.errors]


def test_ontology_type_error():
    kb = make_kb()
    ont = OntologyTypeChecker(kb)
    # data слот получает Mechanism — не разрешён
    inst = {'slots': {'data': {'entity_id': 'CLAIM_BULK_FERROMAGNETISM'}}}
    errors = ont.validate(inst)
    assert any(e.rule_id == 'RULE_ONT_01' for e in errors)


def test_boundary_condition():
    kb = make_kb()
    bnd = BoundaryConditionValidator(kb)
    inst = {'slots': {'warrant': {'entity_id': 'MODEL_CURIE_WEISS'}},
            'conditions': {'Temperature': 4, 'Tc': 90}}  # T=4 < Tc=90 -> нарушение
    errors = bnd.validate(inst)
    assert any(e.rule_id == 'RULE_BND_01' for e in errors)


def test_completeness():
    kb = make_kb()
    cmp = CompletenessChecker(kb, mandatory_slots=['data', 'claim', 'warrant'])
    errors = cmp.validate({'template': 'T3', 'slots': {'data': {'entity_id': 'X'}}})
    assert any(e.rule_id == 'RULE_CMP_01' for e in errors)
    assert len(errors) == 2  # claim и warrant отсутствуют


def test_observation_format():
    kb = make_kb()
    pipe = ValidationPipeline(kb)
    result = pipe.validate({'template': 'T3', 'slots': {}})
    obs = result.to_observation()
    assert 'VALIDATION FAILED' in obs
    assert 'RULE_CMP_01' in obs
    # PASS формат
    ok = pipe.validate({'template': 'T3', 'slots': {
        'data': {'entity_id': 'OBS_XRD_FWHM'},
        'claim': {'entity_id': 'CLAIM_MICROSTRAIN', 'modality': 'indicates'},
        'warrant': {'entity_id': 'MODEL_WH'},
        'relation': {'value': 'indicates'},
    }})
    assert ok.to_observation() == 'Observation: PASS. No validation errors.'


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