#!/usr/bin/env python3
"""pytest для контракт-валидатора P1 (TD-FACTORY-2/3/4/5/6).

Кейсы из контракта:
1. auditor без audit_mode → fail (error содержит "auditor.audit_mode")
2. reviewer без verified_by_commands → fail
3. written_by != agent_type → fail (role substitution)
4. planner валидный → valid (0 ошибок)
5. planner c input_level="L9" → fail
6. deployer DEPLOYED без commits → fail
7. deployer BLOCKED без commits → valid
"""

import pytest

import importlib.util
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("contract_validator_p1_mod", _HERE / "contract_validator.py")
assert _spec and _spec.loader
_cv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cv)

validate = _cv.validate
validate_auditor = _cv.validate_auditor
validate_reviewer = _cv.validate_reviewer
validate_planner = _cv.validate_planner
validate_deployer = _cv.validate_deployer
VALIDATORS = _cv.VALIDATORS
SCHEMAS = _cv.SCHEMAS


def _auditor_data(audit_mode="A"):
    return {
        "verdict": "APPROVE",
        "justification": "Проверка контрактов фабрики выполнена, все звенья честные. " * 2,
        "process_analysis": {
            "contracts_respected": True,
            "iteration_count": 3,
            "iteration_limit": 5,
            "role_violation": False,
        },
        "audit_mode": audit_mode,
        "written_by": "auditor",
        "verified_by_commands": ["python -m pytest -q", "python contract_validator.py auditor out.json"],
    }


def _reviewer_data():
    return {
        "module": "mod_a",
        "verdict": "APPROVE",
        "comments": [{
            "file": "a.py",
            "line": 10,
            "problem": "потенциальная гонка",
            "suggestion": "добавить lock",
            "falsification": "нет фактов подмены",
        }],
        "written_by": "reviewer",
        "verified_by_commands": ["pytest scripts/verify/test_xval_check.py -q"],
    }


# ---------------------------------------------------------------- 1. audit_mode

def test_auditor_without_audit_mode_fails():
    data = _auditor_data()
    del data["audit_mode"]
    errors = validate("auditor", data)
    assert errors, "expected validation errors for missing audit_mode"
    assert any("auditor.audit_mode" in e for e in errors)


def test_auditor_with_wrong_audit_mode_fails():
    data = _auditor_data(audit_mode="C")
    errors = validate("auditor", data)
    assert errors
    assert any("auditor.audit_mode" in e and "P3" in e for e in errors)


def test_auditor_valid_with_audit_mode():
    errors = validate("auditor", _auditor_data())
    assert errors == []


# ---------------------------------------------------------------- 2. verified_by_commands

def test_reviewer_without_verified_by_commands_fails():
    data = _reviewer_data()
    del data["verified_by_commands"]
    errors = validate("reviewer", data)
    assert errors, "expected validation errors for missing verified_by_commands"
    assert any("verified_by_commands" in e for e in errors)


def test_reviewer_with_empty_verified_by_commands_fails():
    data = _reviewer_data()
    data["verified_by_commands"] = []
    errors = validate("reviewer", data)
    assert errors
    assert any("verified_by_commands" in e for e in errors)


def test_reviewer_with_blank_command_string_fails():
    data = _reviewer_data()
    data["verified_by_commands"] = ["   "]
    errors = validate("reviewer", data)
    assert errors
    assert any("verified_by_commands[0]" in e for e in errors)


def test_reviewer_valid_with_verified_by_commands():
    errors = validate("reviewer", _reviewer_data())
    assert errors == []


def test_auditor_verified_by_commands_enforced():
    data = _auditor_data()
    del data["verified_by_commands"]
    errors = validate("auditor", data)
    assert any("verified_by_commands" in e for e in errors)


# ---------------------------------------------------------------- 3. written_by

def test_written_by_mismatch_fails():
    data = _reviewer_data()
    data["written_by"] = "worker"  # подмена звена
    errors = validate("reviewer", data)
    assert errors
    assert any("role substitution" in e and "worker" in e and "reviewer" in e for e in errors)


def test_written_by_required_in_all_schemas():
    # written_by должен быть в required у всех схем (защита подмены звена)
    for agent_type, schema in SCHEMAS.items():
        assert "written_by" in schema["required"], f"{agent_type}: written_by not required"


# ---------------------------------------------------------------- 4/5. planner

def _planner_data(input_level="L1", pipeline="P3"):
    return {
        "role": "planner",
        "project_id": "gost13132-gum-anova",
        "level": "L1",
        "input_level": input_level,
        "pipeline": pipeline,
        "sections": {
            "section_1_input_level_and_pipeline": {"level": "L1", "input_level": input_level, "pipeline": pipeline},
            "section_2_input_audit": {"inputs_audited": True},
            "section_3_stages": {"stages": ["data", "model", "verify"]},
            "section_4_resources": {"resources": ["venv", "xlsx"]},
            "section_5_recommendation": {"recommendation": "continue"},
        },
        "written_by": "planner",
    }


def test_planner_valid():
    errors = validate("planner", _planner_data())
    assert errors == []


def test_planner_invalid_input_level():
    data = _planner_data(input_level="L9")
    errors = validate("planner", data)
    assert errors
    assert any('input_level' in e and 'L9' in e for e in errors)


def test_planner_invalid_pipeline():
    data = _planner_data(pipeline="P9")
    errors = validate("planner", data)
    assert errors
    assert any('pipeline' in e for e in errors)


def test_planner_missing_sections():
    data = _planner_data()
    del data["sections"]
    errors = validate("planner", data)
    assert errors
    assert any('sections' in e for e in errors)


def test_validate_planner_direct_function():
    assert validate_planner(_planner_data()) == []
    assert validate_planner({})


# ---------------------------------------------------------------- 6/7. deployer

def _deployer_data(verdict="DEPLOYED", commits=None, files=None):
    d = {
        "role": "deployer",
        "project_id": "gost13132-gum-anova",
        "verdict": verdict,
        "written_by": "deployer",
    }
    if commits is not None:
        d["commits"] = commits
    if files is not None:
        d["files"] = files
    return d


def test_deployer_deployed_without_commits_fails():
    data = _deployer_data(verdict="DEPLOYED", commits=[], files=["a.xlsx"])
    errors = validate("deployer", data)
    assert errors
    assert any('commits' in e for e in errors)


def test_deployer_deployed_missing_files_fails():
    data = _deployer_data(verdict="DEPLOYED", commits=["abc123"])
    errors = validate("deployer", data)
    assert errors
    assert any('files' in e for e in errors)


def test_deployer_blocked_without_commits_valid():
    data = _deployer_data(verdict="BLOCKED")
    errors = validate("deployer", data)
    assert errors == []


def test_deployer_deployed_with_commits_and_files_valid():
    data = _deployer_data(verdict="DEPLOYED", commits=["abc123", "def456"], files=["a.xlsx", "b.xlsx"])
    errors = validate("deployer", data)
    assert errors == []


def test_deployer_invalid_verdict_fails():
    data = _deployer_data(verdict="REJECTED")
    errors = validate("deployer", data)
    assert errors
    assert any('verdict' in e for e in errors)


def test_validate_deployer_direct_function():
    assert validate_deployer(_deployer_data(verdict="BLOCKED")) == []
    assert validate_deployer({})


# ---------------------------------------------------------------- регрессия существующего

def test_validators_registry_grows():
    assert "planner" in VALIDATORS
    assert "deployer" in VALIDATORS
    assert "planner" in SCHEMAS
    assert "deployer" in SCHEMAS
    # существующие не удалены
    for at in ["worker", "reviewer", "tester", "auditor", "experimenter"]:
        assert at in VALIDATORS
        assert at in SCHEMAS


def test_worker_still_valid_with_written_by():
    data = {
        "module": "mod",
        "code": "print('hi')",
        "description": "тестовый модуль",
        "written_by": "worker",
    }
    assert validate("worker", data) == []
    assert validate_auditor  # import работает


def test_unknown_agent_type_fails():
    errors = validate("nobody", {"written_by": "nobody"})
    assert errors == ["unknown agent_type: nobody"]