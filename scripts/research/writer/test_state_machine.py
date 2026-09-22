#!/usr/bin/env python3
"""Тесты state_machine.py: все переходы, чекпоинты, восстановление, граничные случаи."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_machine import (
    PHASES,
    FINAL_PHASES,
    TRANSITIONS,
    create_state,
    load_state,
    save_state,
    advance_phase,
    start_new_iteration,
    finalize,
    add_question,
    record_answer,
    pending_questions,
    answered_questions,
    add_patch,
    update_patch_status,
    record_verdict_flow,
    record_regression,
    add_budget,
    budget_exceeded,
    iterations_exhausted,
    add_text_version,
    resume,
    validate,
    is_phase_completed,
    recover,
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


def test_create_state():
    state = create_state("test-disc", "test.pdf", "test.txt")
    check(state["_meta"]["discussion_id"] == "test-disc", "discussion_id")
    check(state["_meta"]["document"] == "test.pdf", "document")
    check(state["cycle"]["phase"] == "AWAITING_ANSWERS", "initial phase")
    check(state["cycle"]["iteration"] == 0, "initial iteration")
    check(state["budget"]["max_cost_rub"] == 20.0, "default max_cost")
    check(len(state["checkpoints"]) == 1, "initial checkpoint")
    check(state["checkpoints"][0]["phase"] == "AWAITING_ANSWERS", "checkpoint phase")
    print("  test_create_state: OK")


def test_phase_transitions():
    state = create_state("test", "test.pdf", "test.txt")
    path = os.path.join(tempfile.gettempdir(), "writer_state_test_transitions.json")

    for i, phase in enumerate(PHASES):
        check(state["cycle"]["phase"] == phase, f"phase {i}: {phase}")
        if phase == "DONE":
            break
        next_phase = advance_phase(state, path)
        check(next_phase == TRANSITIONS[phase], f"transition {phase} -> {next_phase}")

    check(state["cycle"]["phase"] == "DONE", "final phase DONE")
    check(len(state["checkpoints"]) == len(PHASES), f"checkpoints count {len(PHASES)}")

    try:
        advance_phase(state, path)
        check(False, "should raise on DONE")
    except ValueError:
        check(True, "raises on DONE")

    os.unlink(path)
    print("  test_phase_transitions: OK")


def test_save_load():
    state = create_state("test-load", "doc.pdf", "orig.txt")
    add_question(state, 1, "физик", "Вопрос?")
    record_answer(state, "q_1_1", "Ответ")
    add_patch(state, "p_1", 1, ["методическая"])
    add_budget(state, 1000, 0.05)

    path = os.path.join(tempfile.gettempdir(), "writer_state_test_load.json")
    save_state(state, path)

    loaded = load_state(path)
    check(loaded["_meta"]["discussion_id"] == "test-load", "load discussion_id")
    check(loaded["cycle"]["phase"] == "AWAITING_ANSWERS", "load phase")
    check(len(loaded["questions"]) == 1, "load questions")
    check(loaded["questions"]["q_1_1"]["answer"] == "Ответ", "load answer")
    check(len(loaded["patches"]) == 1, "load patches")
    check(loaded["budget"]["spent_tokens"] == 1000, "load budget")

    os.unlink(path)
    print("  test_save_load: OK")


def test_questions():
    state = create_state("test-q", "doc.pdf", "orig.txt")

    q1 = add_question(state, 12, "физик", "Вопрос 1")
    q2 = add_question(state, 12, "методолог", "Вопрос 2", n=2)
    q3 = add_question(state, 45, "скептик", "Вопрос 3")

    check(q1 == "q_12_1", "q1 id")
    check(q2 == "q_12_2", "q2 id")
    check(q3 == "q_45_1", "q3 id")

    check(len(pending_questions(state)) == 3, "all pending")
    check(len(answered_questions(state)) == 0, "none answered")

    check(record_answer(state, "q_12_1", "Ответ 1"), "answer q1")
    check(not record_answer(state, "q_nonexistent", "x"), "answer nonexistent")

    check(len(pending_questions(state)) == 2, "2 pending after 1 answer")
    check(len(answered_questions(state)) == 1, "1 answered")

    check(state["questions"]["q_12_1"]["answer"] == "Ответ 1", "answer stored")
    check(state["questions"]["q_12_1"]["answered_at"] is not None, "answered_at set")

    print("  test_questions: OK")


def test_patches():
    state = create_state("test-p", "doc.pdf", "orig.txt")

    add_patch(state, "p_1", 1, ["методическая неполнота"])
    add_patch(state, "p_2", 2, ["числовой mismatch", "погрешности"])

    check(len(state["patches"]) == 2, "2 patches")
    check(state["patches"]["p_1"]["status"] == "created", "initial status")
    check(state["patches"]["p_1"]["iteration"] == 0, "patch iteration")

    check(update_patch_status(state, "p_1", "accepted", justification="ok"), "update p_1")
    check(state["patches"]["p_1"]["status"] == "accepted", "status updated")
    check(state["patches"]["p_1"]["justification"] == "ok", "justification stored")

    check(not update_patch_status(state, "p_nonexistent", "accepted"), "update nonexistent")

    update_patch_status(state, "p_2", "open_honest", open_honest_reason="нет данных")
    check(state["patches"]["p_2"]["status"] == "open_honest", "open_honest status")
    check(state["patches"]["p_2"]["open_honest_reason"] == "нет данных", "open_honest reason")

    print("  test_patches: OK")


def test_verdict_flow():
    state = create_state("test-v", "doc.pdf", "orig.txt")

    record_verdict_flow(state, 12, "AMBIGUOUS")
    record_verdict_flow(state, 12, "SUPPORTED")
    record_verdict_flow(state, 45, "CONTRADICTED")

    check(len(state["verdicts_flow"]["12"]) == 2, "group 12: 2 verdicts")
    check(state["verdicts_flow"]["12"][0]["verdict"] == "AMBIGUOUS", "first verdict")
    check(state["verdicts_flow"]["12"][1]["verdict"] == "SUPPORTED", "second verdict")
    check(len(state["verdicts_flow"]["45"]) == 1, "group 45: 1 verdict")

    print("  test_verdict_flow: OK")


def test_regression():
    state = create_state("test-r", "doc.pdf", "orig.txt")

    record_regression(state, 0.12, 0.85, ["accept"], 0, 8, 4)
    key = "iteration_0"
    check(key in state["regression"], "regression key")
    r = state["regression"][key]
    check(r["ks_p_value"] == 0.12, "ks")
    check(r["semantic_agreement"] == 0.85, "semantic")
    check(r["conformal_set"] == ["accept"], "conformal")
    check(r["regress_count"] == 0, "regress")
    check(r["improve_count"] == 8, "improve")
    check(r["residual_count"] == 4, "residual")

    print("  test_regression: OK")


def test_budget():
    state = create_state("test-b", "doc.pdf", "orig.txt", max_cost_rub=5.0)

    add_budget(state, 10000, 0.5)
    add_budget(state, 20000, 1.0)

    check(state["budget"]["spent_tokens"] == 30000, "total tokens")
    check(state["budget"]["spent_cost_rub"] == 1.5, "total cost")
    check(not budget_exceeded(state), "not exceeded")

    add_budget(state, 100000, 4.0)
    check(state["budget"]["spent_cost_rub"] == 5.5, "total cost after")
    check(budget_exceeded(state), "exceeded")

    check(state["budget"]["per_iteration"]["0"]["tokens"] == 130000, "per-iter tokens")
    check(state["budget"]["per_iteration"]["0"]["cost_rub"] == 5.5, "per-iter cost")

    print("  test_budget: OK")


def test_iterations():
    state = create_state("test-i", "doc.pdf", "orig.txt", max_iterations=2)

    check(not iterations_exhausted(state), "not exhausted at 0")
    start_new_iteration(state, os.path.join(tempfile.gettempdir(), "writer_state_test_iter.json"))
    check(state["cycle"]["iteration"] == 1, "iteration 1")
    check(not iterations_exhausted(state), "not exhausted at 1")
    start_new_iteration(state, os.path.join(tempfile.gettempdir(), "writer_state_test_iter.json"))
    check(state["cycle"]["iteration"] == 2, "iteration 2")
    check(iterations_exhausted(state), "exhausted at 2")

    os.unlink(os.path.join(tempfile.gettempdir(), "writer_state_test_iter.json"))
    print("  test_iterations: OK")


def test_text_versions():
    state = create_state("test-tv", "doc.pdf", "orig.txt")

    add_text_version(state, "v1", "patched_v1.txt", "sha256:abc")
    add_text_version(state, "v2", "patched_v2.txt", "sha256:def")

    check(len(state["text_versions"]["history"]) == 2, "2 versions")
    check(state["text_versions"]["current"] == "patched_v2.txt", "current version")
    check(state["text_versions"]["history"][0]["version"] == "v1", "v1")
    check(state["text_versions"]["history"][1]["hash"] == "sha256:def", "v2 hash")

    print("  test_text_versions: OK")


def test_resume():
    state = create_state("test-resume", "doc.pdf", "orig.txt")
    add_question(state, 1, "физик", "Вопрос?")
    record_answer(state, "q_1_1", "Ответ")
    add_patch(state, "p_1", 1, ["методическая"])
    update_patch_status(state, "p_1", "accepted")
    add_budget(state, 5000, 0.25)

    info = resume(state)
    check(info["discussion_id"] == "test-resume", "resume discussion_id")
    check(info["phase"] == "AWAITING_ANSWERS", "resume phase")
    check(info["iteration"] == 0, "resume iteration")
    check(len(info["pending_questions"]) == 0, "resume no pending")
    check(len(info["answered_questions"]) == 1, "resume 1 answered")
    check(info["budget_spent_rub"] == 0.25, "resume budget")
    check(info["patches_count"] == 1, "resume patches")
    check(info["patches_by_status"] == {"accepted": 1}, "resume statuses")
    check(info["last_checkpoint"]["phase"] == "AWAITING_ANSWERS", "resume checkpoint")

    print("  test_resume: OK")


def test_validate():
    state = create_state("test-valid", "doc.pdf", "orig.txt")
    errs = validate(state)
    check(len(errs) == 0, "valid state")

    bad = create_state("", "", "")
    bad["_meta"]["version"] = 99
    bad["cycle"]["phase"] = "INVALID_PHASE"
    bad["cycle"]["iteration"] = -1
    bad["budget"]["spent_cost_rub"] = -5.0
    bad["questions"]["bad_id"] = {"group_index": 1, "role": "x", "text": "?"}
    bad["patches"]["p"] = {}
    errs = validate(bad)
    check(len(errs) >= 5, f"invalid state has errors: {len(errs)}")

    print("  test_validate: OK")


def test_recover():
    state = create_state("test-rec", "doc.pdf", "orig.txt")
    path = os.path.join(tempfile.gettempdir(), "writer_state_test_recover.json")
    save_state(state, path)

    rec = recover(state)
    check(rec["phase"] == "AWAITING_ANSWERS", "recover phase")
    check(rec["phase_completed"], "phase completed (checkpoint exists)")

    advance_phase(state, path)
    rec2 = recover(state)
    check(rec2["phase"] == "PLANNING", "recover after advance")
    check(rec2["phase_completed"], "new phase completed")

    os.unlink(path)
    print("  test_recover: OK")


def test_finalize():
    state = create_state("test-fin", "doc.pdf", "orig.txt")
    path = os.path.join(tempfile.gettempdir(), "writer_state_test_finalize.json")

    finalize(state, path, "all_criteria_met")
    check(state["cycle"]["phase"] == "FINAL", "final phase")
    check(state["cycle"]["stop_reason"] == "all_criteria_met", "stop reason")
    check(state["checkpoints"][-1]["phase"] == "FINAL", "final checkpoint")

    os.unlink(path)
    print("  test_finalize: OK")


def test_atomic_write():
    state = create_state("test-atomic", "doc.pdf", "orig.txt")
    path = os.path.join(tempfile.gettempdir(), "writer_state_test_atomic.json")

    result = save_state(state, path)
    check("ok: wrote" in result, "save returns ok")
    check(os.path.exists(path), "file exists")
    size1 = os.path.getsize(path)

    add_question(state, 1, "физик", "Вопрос")
    save_state(state, path)
    size2 = os.path.getsize(path)
    check(size2 > size1, "file grew after update")

    os.unlink(path)
    print("  test_atomic_write: OK")


if __name__ == "__main__":
    print("=== state_machine tests ===\n")

    test_create_state()
    test_phase_transitions()
    test_save_load()
    test_questions()
    test_patches()
    test_verdict_flow()
    test_regression()
    test_budget()
    test_iterations()
    test_text_versions()
    test_resume()
    test_validate()
    test_recover()
    test_finalize()
    test_atomic_write()

    print(f"\n=== results: {passed} passed, {failed} failed ===")
    sys.exit(0 if failed == 0 else 1)
