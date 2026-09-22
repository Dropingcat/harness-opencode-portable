#!/usr/bin/env python3
"""Тесты schemas.py: Pydantic-валидация состояния Writer Cell."""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from schemas import PHASES, FINAL_PHASES, validate_pydantic
from state_machine import EMPTY_STATE


def _mutate(state: dict, path: list, value) -> dict:
    s = copy.deepcopy(state)
    node = s
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return s


def test_empty_state_valid():
    assert validate_pydantic(EMPTY_STATE) == []


def test_phases_constants():
    assert len(PHASES) == 10
    assert PHASES == [
        "AWAITING_ANSWERS",
        "PLANNING",
        "WRITING",
        "WAVE_A",
        "REVISING",
        "WAVE_B",
        "CONSISTENCY",
        "REVERIFY",
        "REGRESSION",
        "DONE",
    ]
    assert FINAL_PHASES == {"DONE", "FINAL"}


def test_version_99_error():
    errors = validate_pydantic(_mutate(EMPTY_STATE, ["_meta", "version"], 99))
    assert errors, "expected an error for version=99"
    assert any("version" in e for e in errors)


def test_invalid_phase_error():
    errors = validate_pydantic(_mutate(EMPTY_STATE, ["cycle", "phase"], "INVALID_PHASE"))
    assert errors, "expected an error for INVALID_PHASE"
    assert any("phase" in e for e in errors)


def test_final_phase_accepted():
    errors = validate_pydantic(_mutate(EMPTY_STATE, ["cycle", "phase"], "FINAL"))
    assert errors == []


def test_negative_iteration_error():
    errors = validate_pydantic(_mutate(EMPTY_STATE, ["cycle", "iteration"], -1))
    assert errors, "expected an error for iteration=-1"
    assert any("iteration" in e for e in errors)


def test_negative_budget_error():
    errors = validate_pydantic(_mutate(EMPTY_STATE, ["budget", "spent_cost_rub"], -5.0))
    assert errors, "expected an error for spent_cost_rub=-5"
    assert any("spent_cost_rub" in e for e in errors)


def test_empty_discussion_id_not_pydantic_but_checked_by_state_machine():
    # Примечание: pydantic НЕ валидирует непустоту discussion_id по смыслу
    # (в EMPTY_STATE оно пустое и стейт должен проходить). Эта проверка
    # выполняется только в state_machine.validate().
    errors = validate_pydantic(_mutate(EMPTY_STATE, ["_meta", "discussion_id"], ""))
    assert errors == []
    from state_machine import validate as sm_validate

    assert any("discussion_id" in e for e in sm_validate(copy.deepcopy(EMPTY_STATE)))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
