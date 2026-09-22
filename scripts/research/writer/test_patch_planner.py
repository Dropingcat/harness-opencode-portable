#!/usr/bin/env python3
"""Тесты patch_planner + contracts на реальных данных прогона 33."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sexpr import SExpr, format_sexpr, parse
from patch_planner import (
    plan_patches, plan_to_sexpr, plan_to_json,
    _is_problematic, _classify_issue, _extract_questions,
)
from contracts import (
    CONTRACTS, get_contract, contract_to_prompt,
    check_acceptance_criteria,
)

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {msg}")


def test_classify_issue():
    claim = {"numeric_comparison": {"status": "match"}}
    issues = _classify_issue(claim, "UNSUPPORTED", [])
    check("contradiction" in issues, "UNSUPPORTED → contradiction")

    claim2 = {"numeric_comparison": {"status": "mismatch"}}
    issues2 = _classify_issue(claim2, "SUPPORTED", [])
    check("numeric_mismatch" in issues2, "mismatch → numeric_mismatch")

    caveats = [{"severity": "warning", "text": "Метод не указан"}]
    issues3 = _classify_issue({}, "AMBIGUOUS", caveats)
    check("method_gap" in issues3, "caveat → method_gap")

    caveats2 = [{"severity": "info", "text": "Погрешность не указана ±"}]
    issues4 = _classify_issue({}, "SUPPORTED", caveats2)
    check("error_missing" in issues4, "caveat → error_missing")

    print("  test_classify_issue: OK")


def test_is_problematic():
    check(_is_problematic({"problematic": True}), "problematic flag")
    check(_is_problematic({"verdict": "UNSUPPORTED"}), "UNSUPPORTED")
    check(_is_problematic({"verdict": "CONTRADICTED"}), "CONTRADICTED")
    check(_is_problematic({"verdict": "AMBIGUOUS"}), "AMBIGUOUS")
    check(_is_problematic({"_caveats_critical": 1}), "critical caveats")
    check(_is_problematic({"numeric_comparison": {"status": "mismatch"}}), "numeric mismatch")
    check(not _is_problematic({"verdict": "SUPPORTED", "problematic": False}), "clean SUPPORTED")
    print("  test_is_problematic: OK")


def test_extract_questions():
    tribunal = {
        "groups": [
            {
                "original_index": 12,
                "questions_for_author": [
                    {"role": "физик", "text": "Каким методом?"},
                    {"role": "методолог", "text": "Какова погрешность?"},
                ],
            },
            {
                "original_index": 45,
                "questions_for_author": [
                    {"role": "скептик", "text": "Почему не альтернативный?"},
                ],
            },
        ]
    }
    qs = _extract_questions(tribunal)
    check(len(qs) == 3, "3 questions extracted")
    check(qs[0]["group_index"] == 12, "group 12")
    check(qs[0]["role"] == "физик", "role физик")
    check(qs[2]["group_index"] == 45, "group 45")
    print("  test_extract_questions: OK")


def test_plan_patches_real_data():
    path = "/home/orangepi/.hermes/profiles/resercher/workspace/exp1_20260805_192658/verdicts_processed.json"
    if not Path(path).exists():
        print("  test_plan_patches_real_data: SKIP (no data)")
        return

    with open(path) as f:
        verdicts = json.load(f)

    plan = plan_patches(verdicts)
    check(plan["total_groups"] == 20, "20 groups")
    check(plan["problematic_groups"] == 5, "5 problematic")
    check(plan["patch_count"] == 5, "5 patches")
    check(plan["cell_count"] == 5, "5 cells")

    sexpr = plan_to_sexpr(plan)
    check("patch-plan" in sexpr, "sexpr has patch-plan")
    check("(patches" in sexpr, "sexpr has patches")
    check("(cells" in sexpr, "sexpr has cells")

    js = plan_to_json(plan)
    check(js["patch_count"] == 5, "json patch_count")
    check(len(js["patches"]) == 5, "json patches list")

    print("  test_plan_patches_real_data: OK")


def test_plan_patches_with_answers():
    verdicts = [
        {
            "claim_id": 1,
            "claim_text": "K=1 в формуле Шеррера",
            "verdict": "AMBIGUOUS",
            "confidence": 0.65,
            "caveats": [{"severity": "warning", "text": "Не указан тип ширины пика"}],
            "problematic": True,
        },
        {
            "claim_id": 2,
            "claim_text": "Твёрдость HV 8240-9000",
            "verdict": "CONTRADICTED",
            "confidence": 0.20,
            "caveats": [{"severity": "critical", "text": "Физически невозможная твёрдость"}],
            "problematic": True,
        },
        {
            "claim_id": 3,
            "claim_text": "Фазовый состав ε→γ'",
            "verdict": "SUPPORTED",
            "confidence": 0.95,
            "caveats": [],
            "problematic": False,
        },
    ]

    tribunal = {
        "groups": [
            {
                "original_index": 1,
                "questions_for_author": [
                    {"role": "физик", "text": "Какой тип ширины пика?"},
                ],
            },
            {
                "original_index": 2,
                "questions_for_author": [
                    {"role": "физик", "text": "Это опечатка?"},
                ],
            },
        ]
    }

    answers = {
        "q_1_1": "FWHM, K=1 — опечатка, должно быть 0.9",
        "q_2_1": "Да, опечатка. Реальная твёрдость 824-900 HV",
    }

    plan = plan_patches(verdicts, tribunal, answers)
    check(plan["total_groups"] == 3, "3 groups")
    check(plan["problematic_groups"] == 2, "2 problematic")
    check(plan["patch_count"] == 2, "2 patches")
    check(plan["unanswered_questions"] == 0, "0 unanswered")

    sexpr = plan_to_sexpr(plan)
    check("p_1" in sexpr, "patch p_1")
    check("p_2" in sexpr, "patch p_2")
    check("p_3" not in sexpr, "no patch for SUPPORTED")

    print("  test_plan_patches_with_answers: OK")


def test_contracts():
    check(len(CONTRACTS) == 9, "9 contracts")

    for name in ["writer", "critic", "reviewer", "editor", "proofreader", "consistency", "reverify", "regression"]:
        c = get_contract(name)
        check(c.head == "contract", f"{name} is contract")
        check(c.get("input") is not None, f"{name} has input")
        check(c.get("output") is not None, f"{name} has output")
        check(c.get("criteria") is not None, f"{name} has criteria")

    prompt = contract_to_prompt("writer")
    check("HARD-критерии" in prompt, "prompt has HARD")
    check("S-expression" in prompt, "prompt has S-expression")

    result = parse("(result (only-own-claims) (numbers-from-answers) (no-content-deletion) (justification-required))")
    ok, issues = check_acceptance_criteria(result, "writer")
    check(ok or len(issues) <= 4, "acceptance check runs")
    check(isinstance(issues, list), "issues is list")

    result_bad = parse("(result (only-own-claims))")
    ok2, issues2 = check_acceptance_criteria(result_bad, "writer")
    check(not ok2 or len(issues2) > 0, "missing criteria detected")

    print("  test_contracts: OK")


def test_sexpr_contract_roundtrip():
    from sexpr import make_contract

    c = make_contract("test",
                      input={"claim": "K=1", "pattern": "xrd"},
                      output={"patch": "diff"},
                      criteria={"hard": [SExpr("only_own_claims")]})

    formatted = format_sexpr(c)
    parsed = parse(formatted)
    check(parsed.head == "contract", "roundtrip head")
    check(parsed["input"]["claim"] == "K=1", "roundtrip claim")
    hard = parsed["criteria"]["hard"]
    check(isinstance(hard, SExpr) or isinstance(hard, list), "roundtrip criteria exists")

    print("  test_sexpr_contract_roundtrip: OK")


def test_priority_ordering():
    verdicts = [
        {"claim_id": 1, "claim_text": "low", "verdict": "AMBIGUOUS", "caveats": [], "problematic": True},
        {"claim_id": 2, "claim_text": "high", "verdict": "CONTRADICTED", "caveats": [], "problematic": True},
        {"claim_id": 3, "claim_text": "mid", "verdict": "AMBIGUOUS",
         "caveats": [{"severity": "warning", "text": "Параметр не обоснован"}], "problematic": True},
    ]

    plan = plan_patches(verdicts)
    patches = plan["patches"]
    check(patches[0]["group"].args[0] == 2, "CONTRADICTED first (priority 0)")
    # priority 1 tie: sorted by group_index (1 < 3)
    check(patches[1]["group"].args[0] in (1, 3), "priority 1 group")
    check(patches[2]["group"].args[0] in (1, 3), "priority 1 group")

    print("  test_priority_ordering: OK")


if __name__ == "__main__":
    print("=== patch_planner + contracts tests ===\n")

    test_classify_issue()
    test_is_problematic()
    test_extract_questions()
    test_plan_patches_real_data()
    test_plan_patches_with_answers()
    test_contracts()
    test_sexpr_contract_roundtrip()
    test_priority_ordering()

    print(f"\n=== results: {passed} passed, {failed} failed ===")
    sys.exit(0 if failed == 0 else 1)
