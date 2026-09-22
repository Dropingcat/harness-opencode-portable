"""Тесты для verdict_schemas.validate_verdicts."""

import json
from copy import deepcopy
from pathlib import Path

from verdict_schemas import VerdictModel, validate_verdicts

DATA_PATH = Path(__file__).resolve().parent / "testdata" / "exp1_verdicts_processed.json"


def _load_exp1() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _valid_item() -> dict:
    item = _load_exp1()[0]
    assert item["verdict"] in (
        "SUPPORTED",
        "CONTRADICTED",
        "UNSUPPORTED",
        "AMBIGUOUS",
        "OPEN",
    )
    assert item["sources"]
    return deepcopy(item)


def test_exp1_all_valid():
    assert validate_verdicts(_load_exp1()) == []


def test_valid_item_passes():
    assert validate_verdicts([_valid_item()]) == []


def test_confidence_out_of_range():
    item = _valid_item()
    item["confidence"] = 1.5
    assert len(validate_verdicts([item])) == 1


def test_negative_confidence():
    item = _valid_item()
    item["confidence"] = -0.1
    assert len(validate_verdicts([item])) == 1


def test_invalid_verdict():
    item = _valid_item()
    item["verdict"] = "INVALID"
    assert len(validate_verdicts([item])) == 1


def test_trust_out_of_range():
    item = _valid_item()
    item["sources"][0]["trust"] = 1.5
    assert len(validate_verdicts([item])) == 1


def test_model_roundtrip():
    item = _valid_item()
    model = VerdictModel.model_validate(item)
    dumped = model.model_dump(by_alias=True)
    assert dumped["_post_processed"] is item["_post_processed"]
    assert dumped["_changes"] == item["_changes"]
    assert dumped["_caveats_total"] == item["_caveats_total"]
    assert dumped["_caveats_critical"] == item["_caveats_critical"]
    assert model.claim_id == item["claim_id"]


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
