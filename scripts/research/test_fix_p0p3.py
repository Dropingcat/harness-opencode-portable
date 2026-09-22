"""test_fix_p0p3.py — регрессионные тесты правок P0–P3 пайплайна resercher.

Покрывает атомарные фиксы:
    P0 — факт-чекер: guard (валидация + LLM_PARSE_FAIL вместо critical-LLM-error).
    P1 — синтезатор: tribunal.json как источник истины (overlay на verdicts).
    P2 — extractor: санитизация JSON + retry + таймаут + детерминированный fallback.
    P3 — numeric_comparator: единый load_sources (dict-of-dict и dict-of-list).

Запуск:
    python3 -m pytest scripts/test_fix_p0p3.py -v
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
RULES_YAML = Path('testdata/rules.yaml')
WORK = Path(os.environ.get("TEMP", "/tmp")) / "fix-p0p3-test"
WORK.mkdir(parents=True, exist_ok=True)


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_json(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def run_cli(script, args, timeout=120):
    cmd = [sys.executable, str(SCRIPTS / script)] + [str(a) for a in args]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(cmd, cwd=str(SCRIPTS), capture_output=True, text=True, timeout=timeout, env=env, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


# ───────────────────────── P3: load_sources ─────────────────────────

def test_p3_load_sources_both_forms():
    """dict-of-dict и dict-of-list дают одинаковый список источников."""
    from numeric_comparator import load_sources, _lookup_sources

    src = {"title": "S3", "text": "x"}
    dict_of_dict = {"3": {"sources": [src]}}
    dict_of_list = {"3": [src]}

    idx_dd, lst_dd, warns_dd = load_sources({"sources": dict_of_dict})
    idx_dl, lst_dl, warns_dl = load_sources({"sources": dict_of_list})

    got_dd = _lookup_sources(idx_dd, lst_dd, "3", 3)
    got_dl = _lookup_sources(idx_dl, lst_dl, "3", 3)
    assert got_dd == got_dl == [src]


def test_p3_lookup_claim_id_and_str_int():
    """Поиск по claim_id (int) и по строковому ключу даёт источники."""
    from numeric_comparator import load_sources, _lookup_sources

    src = {"title": "S1"}
    idx, lst, _ = load_sources({"sources": {"5": [src]}})
    assert _lookup_sources(idx, lst, None, 5) == [src]
    assert _lookup_sources(idx, lst, "5", None) == [src]
    assert _lookup_sources(idx, lst, None, "5") == [src]


def test_p3_missing_key_returns_empty():
    """Нет ключа — пустой список (валидатор позже сообщит об этом)."""
    from numeric_comparator import load_sources, _lookup_sources

    idx, lst, _ = load_sources({"sources": {"5": [{"title": "S1"}]}})
    assert _lookup_sources(idx, lst, None, 999) == []


def test_p3_trace_ws_no_longer_blind():
    """На реальном sources.json (dict-of-list) числовой слой видит источники."""
    verdicts = WORK / "p3_verdicts.json"
    src = WORK / "p3_sources.json"
    write_json(verdicts, [{"claim_id": i, "claim_text": f"Тезис {i}", "verdict": "SUPPORTED",
                           "confidence": 0.9, "caveats": []} for i in range(3)])
    write_json(src, {"sources": {
        "0": [{"title": "S1", "text": "подтверждает"}],
        "1": [],
        "2": [{"title": "S2", "text": "подтверждает"}],
    }})
    rc, out, err = run_cli("numeric_comparator.py", [verdicts, src, WORK / "p3_out.json"])
    assert rc == 0, out + err
    res = load_json(WORK / "p3_out.json")
    by_id = {g["claim_id"]: g for g in res["groups"]}
    assert by_id[0]["n_sources"] == 1, "группа 0 должна видеть 1 источник"
    assert by_id[2]["n_sources"] == 1, "группа 2 должна видеть 1 источник"
    assert by_id[1]["n_sources"] == 0
    assert "n_sources=0" in err, "валидатор должен сообщить о группах с n_sources=0"


def test_p3_dict_of_dict_still_works():
    """Прежняя спецификационная форма {group_id: {sources: []}} не сломана."""
    verdicts = WORK / "p3_v2.json"
    src = WORK / "p3_s2.json"
    write_json(verdicts, [{"claim_id": 1, "claim_text": "Тезис 1", "verdict": "SUPPORTED",
                           "confidence": 0.9, "caveats": []}])
    write_json(src, {"sources": {"1": {"original_index": 1,
                                       "sources": [{"title": "S1", "text": "x"}]}}})
    rc, out, err = run_cli("numeric_comparator.py", [verdicts, src, WORK / "p3_out2.json"])
    assert rc == 0, out + err
    res = load_json(WORK / "p3_out2.json")
    assert res["groups"][0]["n_sources"] == 1


# ───────────────────────── P0: fact-checker guard ─────────────────────────

def _broken_verdict(claim_id=0):
    return {
        "claim_id": claim_id,
        "claim_text": "Тезис с битой выдачей LLM.",
        "verdict": "UNSUPPORTED",
        "confidence": 0.1,
        "sources": [],
        "caveats": [{"severity": "critical", "text": "LLM error: Expecting value: line 1 column 1 (char 0)"}],
        "reason": "LLM error: Expecting value: line 1 column 1 (char 0)",
    }


def test_p0_detect_llm_error():
    from factcheck_guard import validate_verdicts
    ok, problems = validate_verdicts([_broken_verdict()])
    assert ok is False
    assert any("LLM error" in p for p in problems)


def test_p0_mark_parse_fail_no_critical():
    """LLM_PARSE_FAIL: нет critical caveat, не валидируется как свидетельство."""
    from factcheck_guard import mark_parse_fail

    verdicts = [_broken_verdict(0), {"claim_id": 1, "claim_text": "OK", "verdict": "SUPPORTED",
                                     "confidence": 0.9, "sources": [], "caveats": []}]
    fixed, report = mark_parse_fail(verdicts)

    assert report["fixed"] == 1
    f0 = fixed[0]
    assert f0["llm_parse_fail"] is True
    assert f0["reason"].startswith("LLM_PARSE_FAIL")
    assert not any(c.get("severity") == "critical" for c in f0["caveats"]), \
        "LLM-сбой не должен оставаться critical caveat"
    assert f0["verdict"] == "UNSUPPORTED" and f0["confidence"] == 0.1

    import yaml
    from post_processor import post_process_verdict
    rules = yaml.safe_load(open(RULES_YAML, encoding="utf-8"))
    post_process_verdict(f0, rules)
    assert f0.get("trigger_tribunal") is not True, \
        "LLM_PARSE_FAIL не должен триггерить трибунал как критичное свидетельство"
    assert f0["_caveats_critical"] == 0


def test_p0_mark_parse_fail_keeps_clean():
    """Здоровые вердикты не меняются."""
    from factcheck_guard import mark_parse_fail
    v = {"claim_id": 1, "claim_text": "OK", "verdict": "SUPPORTED", "confidence": 0.9,
         "sources": [], "caveats": []}
    fixed, report = mark_parse_fail([v])
    assert fixed[0] == v
    assert report["fixed"] == 0


# ───────────────────────── P1: synthesizer + tribunal ─────────────────────────

def _processed_verdicts():
    return [
        {"claim_id": 0, "claim_text": "C0 текст", "verdict": "UNSUPPORTED",
         "confidence": 0.1, "reason": "LLM error...", "caveats": []},
        {"claim_id": 3, "claim_text": "C3 текст", "verdict": "UNSUPPORTED",
         "confidence": 0.1, "reason": "LLM error...", "caveats": []},
        {"claim_id": 4, "claim_text": "C4 текст", "verdict": "SUPPORTED",
         "confidence": 0.9, "reason": "источник S1", "caveats": []},
    ]


def _tribunal_groups():
    return {"groups": [
        {"original_index": 0, "claim_id": 0, "claim_text": "C0 текст",
         "tribunal_verdict": "SUPPORTED", "confidence": 0.95,
         "justification": "трибунал перевернул", "questions_for_author": []},
        {"original_index": 3, "claim_id": 3, "claim_text": "C3 текст",
         "tribunal_verdict": "SUPPORTED", "confidence": 0.8,
         "justification": "трибунал перевернул", "questions_for_author": []},
        {"original_index": 11, "claim_id": 11, "claim_text": "C11 текст",
         "tribunal_verdict": "UNSUPPORTED", "confidence": 0.9,
         "justification": "нет данных", "questions_for_author": []},
    ]}


def test_p1_overlay_tribunal():
    from synthesizer import overlay_tribunal
    verdicts = _processed_verdicts()
    final = overlay_tribunal(verdicts, _tribunal_groups()["groups"])
    by_id = {v["claim_id"]: v for v in final}
    assert by_id[0]["verdict"] == "SUPPORTED"
    assert by_id[0]["confidence"] == 0.95
    assert by_id[0]["reason"] == "трибунал перевернул"
    assert by_id[3]["verdict"] == "SUPPORTED"
    assert by_id[4]["verdict"] == "SUPPORTED"
    assert by_id[11]["verdict"] == "UNSUPPORTED"


def test_p1_report_uses_tribunal():
    """Отчёт не содержит вердикта, опровергнутого трибуналом."""
    verdicts = WORK / "p1_v.json"
    tribunal = WORK / "p1_t.json"
    report = WORK / "p1_report.md"
    write_json(verdicts, _processed_verdicts())
    write_json(tribunal, _tribunal_groups())
    rc, out, err = run_cli("synthesizer.py", [verdicts, tribunal, report])
    assert rc == 0, out + err
    text = report.read_text(encoding="utf-8")
    assert "SUPPORTED" in text
    # C0 и C3 в отчёте должны быть SUPPORTED (перекрыты трибуналом)
    assert "UNSUPPORTED (confidence: 0.1)" not in text, "отчёт повторяет битые вердикты"


def test_p1_optional_tribunal_backward_compat():
    """Без tribunal-аргумента синтезатор работает как раньше (обратная совместимость)."""
    verdicts = WORK / "p1_v2.json"
    report = WORK / "p1_report2.md"
    write_json(verdicts, _processed_verdicts())
    rc, out, err = run_cli("synthesizer.py", [verdicts, report])
    assert rc == 0, out + err
    assert report.exists()


# ───────────────────────── P2: extractor guard ─────────────────────────

def test_p2_sanitize_control_chars():
    """Raw control characters ломают json.loads — санитизация их убирает."""
    from extractor_guard import sanitize_llm_json
    bad = '{"processed_sentence": "ускорение\x01нитридов", "no_verifiable_claims": false, "remains_unchanged": false}'
    clean = sanitize_llm_json(bad)
    assert json.loads(clean)["processed_sentence"] == "ускорениенитридов"


def test_p2_unwrap_double_encoded():
    """LLM оборачивает JSON в JSON-строку/ключ — распаковка в валидный JSON."""
    from extractor_guard import sanitize_llm_json
    broken = '{\n  "{\n    "processed_sentence": "x",\n    "no_verifiable_claims": false,\n    "remains_unchanged": false\n  }'
    clean = sanitize_llm_json(broken)
    assert json.loads(clean)["processed_sentence"] == "x"


def test_p2_valid_json_unchanged():
    """Валидный JSON не должен быть искажён."""
    from extractor_guard import sanitize_llm_json
    good = '{"a": 1, "b": [1, 2]}'
    assert json.loads(sanitize_llm_json(good)) == {"a": 1, "b": [1, 2]}


def test_p2_markdown_fence_removed():
    from extractor_guard import sanitize_llm_json
    wrapped = '```json\n{"verdict": "SUPPORTED", "confidence": 0.9}\n```'
    assert json.loads(sanitize_llm_json(wrapped))["verdict"] == "SUPPORTED"


def test_p2_retry_success_after_failures():
    from extractor_guard import run_with_retry
    calls = {"n": 0}

    def flaky():
        async def _f():
            calls["n"] += 1
            if calls["n"] < 2:
                raise ValueError("LLM вернул битый JSON")
            return "ok"
        return _f()

    assert run_with_retry(flaky, max_retries=3, timeout=10) == "ok"
    assert calls["n"] == 2


def test_p2_retry_exhausted():
    from extractor_guard import RetryExhausted, run_with_retry

    def always_bad():
        async def _f():
            raise ValueError("битый")
        return _f()

    with pytest.raises(RetryExhausted):
        run_with_retry(always_bad, max_retries=3, timeout=10)


def test_p2_timeout_triggers_retry():
    from extractor_guard import run_with_retry
    calls = {"n": 0}

    def slow():
        import asyncio

        async def _f():
            calls["n"] += 1
            if calls["n"] == 1:
                await asyncio.sleep(0.5)
            return "fast"
        return _f()

    # таймаут 0.1с на 1-й попытке (медленный), 2-я — успешна
    assert run_with_retry(slow, max_retries=2, timeout=0.1) == "fast"
    assert calls["n"] == 2


def test_p2_deterministic_extract():
    from extractor_guard import deterministic_extract
    text = ("Первое предложение о диффузии азота в стали является утверждением. "
            "Второе предложение описывает механизм ускорения. Короткое!")
    out = deterministic_extract(text)
    assert out["status"] == "fallback_deterministic"
    validated = out["claims"]["validated"]
    assert len(validated) >= 1
    assert all({"text", "original_sentence", "original_index"} <= set(c) for c in validated)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))