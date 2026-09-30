# -*- coding: utf-8 -*-
"""Тесты ExternalAuditor + SleepController."""
import os, sys, io, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from external_auditor import ExternalAuditor, AuditFinding
from orchestrator_integration import OrchestratorIntegration
from sleep_controller import SleepController, SleepContract


def make_validator():
    """Валидатор: 3 критических находки."""
    def validate(artifact):
        return [
            AuditFinding('Completeness', 'RULE_CMP_01', 'CRITICAL', 'нет warrant'),
            AuditFinding('RelationGraph', 'RULE_REL_04', 'CRITICAL', 'XRD proves Mechanism'),
            AuditFinding('Epistemic', 'RULE_EPI_02', 'CRITICAL', 'indirect proves'),
        ]
    return validate


def test_auditor_independent():
    with tempfile.TemporaryDirectory() as td:
        aud = ExternalAuditor('aud', state_dir=td)
        findings = aud.observe('текст')
        assert len(findings) >= 1
        # независимые переменные
        assert 'auditor_id' in aud.auditor_variables
        assert 'auditor_observations' in aud.auditor_variables
        # промпт отдельный
        assert '[EXTERNAL-AUDITOR' in aud.auditor_prompt


def test_auditor_critical_damage():
    aud = ExternalAuditor('aud', validator_fn=make_validator())
    aud.observe('x')
    assert aud.critical_damage() <= -50.0
    assert aud.should_force_sleep(-50.0) is True


def test_sleep_order_contract():
    aud = ExternalAuditor('aud', validator_fn=make_validator())
    aud.observe('x')
    order = aud.order_sleep('research', 'критический демедж')
    assert 'contract' in order
    assert len(order['contract']['debts']) >= 3
    assert order['contract']['orchestrator'] == 'SLEEP'


def test_sleep_controller_force():
    with tempfile.TemporaryDirectory() as td:
        meta = OrchestratorIntegration('test', state_dir=td)
        aud = ExternalAuditor('aud', validator_fn=make_validator())
        ctrl = SleepController(meta, aud)
        # артефакт с критическими проблемами → принудительный сон
        contract = ctrl.check_and_force_sleep('текст с доказывает XRD', 'задача N')
        assert contract is not None
        assert contract.merged is True
        assert meta.sleep_state['merged'] is True
        assert len(meta.sleep_state['branches']) >= 3
        # HP восстановлен после успешного сна
        assert meta.health.health_points >= 60.0


def test_sleep_controller_no_force():
    with tempfile.TemporaryDirectory() as td:
        meta = OrchestratorIntegration('test', state_dir=td)
        aud = ExternalAuditor('aud', state_dir=td)  # изолированный state
        ctrl = SleepController(meta, aud)
        contract = ctrl.check_and_force_sleep('нормальный текст', 'задача')
        assert contract is None  # нет критического демеджа


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