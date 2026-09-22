#!/usr/bin/env python3
"""test_merge_numeric.py — ручейковый тест Этапа 5.1 (merge_numeric) + канона numeric_comparison.

Глубокий ручеёк (последовательный обход сценариев) по проблемам 1+14+2:
  S1  claim_id match → вердикт получил numeric_comparison.status
  S2  claim_id не найден → вердикт не тронут
  S3  вручную проставленный numeric_comparison → merge не затирает неправильно
  S4  пустой numeric_result → ничего не вливается, не падает
  S5  grep number_comparison после фикса → нет в fact-checker/SKILL.md (канон)
  S6  полный прогон детерминированной цепочки exp1
      (numeric_comparator → merge_numeric → post_processor, mock LLM = реальные
      вердикты exp1) → числовые правила применяются к вердиктам с mismatch

Pytest-совместимый: `python3 -m pytest test_merge_numeric.py -q -s`
Standalone:         `python3 test_merge_numeric.py`
Лог прогона:        /tmp/merge-numeric-log.txt
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
PROFILE = Path(__file__).resolve().parent
RULES_YAML = Path(__file__).resolve().parent / "testdata" / "rules.yaml"
EXP1 = Path(__file__).resolve().parent / "testdata" / "exp1"
FACT_CHECKER_SKILL = Path(__file__).resolve().parent / "testdata" / "fact_checker_skill.md"
LOG_PATH = Path(os.environ.get("TEMP", "/tmp")) / "merge-numeric-log.txt"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import merge_numeric  # noqa: E402
import post_processor  # noqa: E402

LOG: list[str] = []
RESULTS: list[dict] = []


def log(msg: str) -> None:
    LOG.append(msg)
    print(msg)


def record(name: str, ok: bool, expected: str, actual: str, note: str = "") -> None:
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL",
                    "expected": expected, "actual": actual, "note": note})
    log(f"  [S{name}] {'PASS' if ok else 'FAIL'}")
    log(f"      ожидалось: {expected}")
    log(f"      получено:  {actual}")
    if note:
        log(f"      примечание: {note}")


def run_scenario(name: str, expected: str, fn, desc: str) -> bool:
    log(f"[S{name}] вход/действие: {desc}")
    note = ""
    try:
        result = fn()
        if len(result) == 3:
            ok, actual, note = result
        else:
            ok, actual = result
    except Exception as exc:  # noqa: BLE001
        ok, actual, note = False, f"CRASH {type(exc).__name__}: {exc}", ""
    record(name, ok, expected, actual, note)
    return ok


def run_main(verdicts, numeric, workdir=None):
    """Прогон merge_numeric.py как скрипт → (rc, output, result|None)."""
    workdir = workdir or Path(tempfile.mkdtemp(prefix="merge_numeric_"))
    vp, np_, op = workdir / "verdicts.json", workdir / "numeric_result.json", workdir / "out.json"
    vp.write_text(json.dumps(verdicts, ensure_ascii=False), encoding="utf-8")
    np_.write_text(json.dumps(numeric, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "merge_numeric.py"), str(vp), str(np_), str(op)],
        capture_output=True, text=True, timeout=120,
    )
    result = None
    if op.exists():
        try:
            result = json.loads(op.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result = None
    return proc.returncode, (proc.stdout + proc.stderr).strip(), result


def merge_in_memory(verdict, status, details="", n_sources=2):
    """Прямой вызов функции merge_numeric_into_verdict (без subprocess)."""
    v = dict(verdict)
    merge_numeric.merge_numeric_into_verdict(
        v, {"status": status, "details": details, "n_sources": n_sources})
    return v


# ───────────────────────── S1: claim_id match ─────────────────────────

def s1_merge_by_claim_id():
    verdicts = [{"claim_id": 7, "claim_text": "твёрдость 500 HV", "verdict": "SUPPORTED",
                 "confidence": 0.9}]
    numeric = {"total_groups": 1, "groups": [
        {"claim_id": 7, "original_index": 7, "group_status": "mismatch",
         "n_sources": 2, "n_claims_in_group": 1,
         "claims": [{"claim_id": 7, "status": "mismatch",
                     "explanation": "Best match across 2 sources: mismatch"}]}]}
    rc, out, result = run_main(verdicts, numeric)
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    nc = result[0].get("numeric_comparison")
    log(f"  -> выход: rc={rc} status={nc.get('status') if nc else None} "
        f"source={nc.get('source') if nc else None}")
    ok = nc and nc["status"] == "mismatch" and nc["source"] == "numeric_comparator"
    return ok, f"status={nc.get('status') if nc else None}, source={nc.get('source') if nc else None}"


def test_s1_claim_id_match():
    assert run_scenario("1", "rc=0, status=mismatch, source=numeric_comparator",
                        s1_merge_by_claim_id,
                        "вердикт claim_id=7 + numeric_result groups[].claim_id=7 → merge")


# ───────────────────────── S2: claim_id не найден ─────────────────────────

def s2_claim_id_not_found():
    verdicts = [{"claim_id": 99, "claim_text": "тезис без источников",
                 "verdict": "UNSUPPORTED", "confidence": 0.3}]
    numeric = {"groups": [{"claim_id": 7, "group_status": "mismatch", "n_sources": 2,
                           "claims": []}]}
    rc, out, result = run_main(verdicts, numeric)
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    untouched = result[0] == verdicts[0] and "numeric_comparison" not in result[0]
    log(f"  -> выход: rc={rc} numeric_comparison в вердикте: "
        f"{'numeric_comparison' in result[0]}")
    return untouched, f"numeric_comparison present: {'numeric_comparison' in result[0]}"


def test_s2_claim_id_not_found():
    assert run_scenario("2", "rc=0, вердикт без изменений (нет numeric_comparison)",
                        s2_claim_id_not_found,
                        "verdict claim_id=99, numeric_result содержит claim_id=7 → не найдено")


# ───────────────────────── S3: ручной numeric_comparison ─────────────────────────

def s3_manual_not_overwritten():
    manual = {"claim_id": 7, "claim_text": "500 HV", "verdict": "SUPPORTED",
              "confidence": 0.9,
              "numeric_comparison": {"status": "match", "details": "manual LLM details"}}
    # (а) детерминированный mismatch → приоритет детерминированному, детали LLM в llm_details
    a = merge_in_memory(manual, "mismatch", "det mismatch details")
    ok_a = (a["numeric_comparison"]["status"] == "mismatch"
            and a["numeric_comparison"]["llm_details"] == "manual LLM details"
            and a["numeric_comparison"]["details"] == "det mismatch details")
    # (б) детерминированный no_data → ручной status+details сохраняются
    b = merge_in_memory(manual, "no_data", "det no_data details")
    ok_b = (b["numeric_comparison"]["status"] == "match"
            and b["numeric_comparison"]["details"] == "manual LLM details")
    log(f"  -> выход: (а) status={a['numeric_comparison']['status']}, "
        f"llm_details={a['numeric_comparison'].get('llm_details')!r} | "
        f"(б) status={b['numeric_comparison']['status']}, "
        f"details={b['numeric_comparison']['details']!r}")
    ok = ok_a and ok_b
    note = ("(а) детерминированный mismatch перекрывает ручной match, "
            "но детали LLM сохранены в llm_details; "
            "(б) детерминированный no_data НЕ затирает ручной status/details")
    return ok, f"(а) ok={ok_a}, (б) ok={ok_b}", note


def test_s3_manual_not_overwritten():
    assert run_scenario("3", "ручной match+det mismatch → status=mismatch, llm_details сохранён; "
                             "ручной match+det no_data → ручной status сохранён",
                        s3_manual_not_overwritten,
                        "в verdict уже есть numeric_comparison (вручную) → merge не затирает")


# ───────────────────────── S4: пустой numeric_result ─────────────────────────

def s4_empty_numeric():
    verdicts = [{"claim_id": 7, "claim_text": "твёрдость 500 HV", "verdict": "SUPPORTED",
                 "confidence": 0.9}]
    rc, out, result = run_main(verdicts, {"total_groups": 0, "groups": []})
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    untouched = "numeric_comparison" not in result[0]
    log(f"  -> выход: rc={rc} numeric_comparison present: "
        f"{'numeric_comparison' in result[0]}")
    return rc == 0 and untouched, f"rc={rc}, numeric_comparison present: {'numeric_comparison' in result[0]}"


def test_s4_empty_numeric():
    assert run_scenario("4", "rc=0, ничего не влито, не падает",
                        s4_empty_numeric,
                        "пустой numeric_result (groups=[]) → merge ничего не делает")


# ───────────────────────── S5: канон numeric_comparison ─────────────────────────

def s5_canon_skill_md():
    skill_text = FACT_CHECKER_SKILL.read_text(encoding="utf-8")
    hits = [ln for ln in skill_text.splitlines() if "number_comparison" in ln]
    pp_text = (SCRIPTS / "post_processor.py").read_text(encoding="utf-8")
    has_backcompat = "number_comparison" in pp_text  # миграционная ветка
    log(f"  -> SKILL.md: number_comparison = {len(hits)} вхождений | "
        f"post_processor.py: backward-compat = {has_backcompat}")
    ok = not hits and has_backcompat
    note = "post_processor.py должен содержать number_comparison ТОЛЬКО как миграционную ветку"
    return ok, f"SKILL.md hits={len(hits)}, post_processor backcompat={has_backcompat}", note


def test_s5_canon_skill_md():
    assert run_scenario("5", "fact-checker/SKILL.md не содержит number_comparison; "
                             "post_processor.py держит миграцию",
                        s5_canon_skill_md,
                        "grep number_comparison после фикса — канон numeric_comparison")


# ───────────────────────── S6: полный прогон на exp1 ─────────────────────────

def _synth_sources(verdicts):
    index = {}
    for v in verdicts:
        sl = []
        for s in v.get("sources", []) or []:
            if isinstance(s, dict):
                sl.append({"title": s.get("title", ""), "descriptor": s.get("title", ""),
                           "text": s.get("excerpt", "") or "", "type": s.get("type", "")})
        index[str(v.get("claim_id"))] = {"original_index": v.get("claim_id"), "sources": sl}
    return {"sources": index}


def _run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def s6_full_chain_exp1():
    workdir = Path(tempfile.mkdtemp(prefix="merge_numeric_exp1_"))
    vp, sp, np_, vm, pp = (workdir / "verdicts.json", workdir / "sources.json",
                           workdir / "numeric_result.json", workdir / "verdicts_with_numeric.json",
                           workdir / "verdicts_processed.json")
    verdicts = json.loads((EXP1 / "verdicts.json").read_text(encoding="utf-8"))
    vp.write_text(json.dumps(verdicts, ensure_ascii=False), encoding="utf-8")
    sp.write_text(json.dumps(_synth_sources(verdicts), ensure_ascii=False), encoding="utf-8")

    # Этап 5: numeric_comparator (детерм.)
    rc5, out5 = _run([sys.executable, str(SCRIPTS / "numeric_comparator.py"),
                      str(vp), str(sp), str(np_)])
    if rc5 != 0 or not np_.exists():
        return False, f"этап 5 rc={rc5}: {out5[:200]}"
    nres = json.loads(np_.read_text(encoding="utf-8"))
    sc = nres["status_counts"]

    # Этап 5.1: merge_numeric (детерм.)
    rc51, out51 = _run([sys.executable, str(SCRIPTS / "merge_numeric.py"),
                        str(vp), str(np_), str(vm)])
    if rc51 != 0 or not vm.exists():
        return False, f"этап 5.1 rc={rc51}: {out51[:200]}"
    merged = json.loads(vm.read_text(encoding="utf-8"))
    merged_by_id = {v["claim_id"]: v for v in merged}

    # Этап 6: post_processor (детерм.)
    rc6, out6 = _run([sys.executable, str(SCRIPTS / "post_processor.py"),
                      str(vm), str(RULES_YAML), str(pp)])
    if rc6 != 0 or not pp.exists():
        return False, f"этап 6 rc={rc6}: {out6[:200]}"
    processed = json.loads(pp.read_text(encoding="utf-8"))
    proc_by_id = {v["claim_id"]: v for v in processed}

    # Проверки:
    # claim 7 — Fe2-3N теперь FORMULA (H2-фикс) → НЕ ложный mismatch → не демоушится
    #           в UNSUPPORTED; group-агрегация даёт no_data/no_numbers_in_claim.
    c7_nc = merged_by_id[7].get("numeric_comparison", {})
    c7 = proc_by_id[7]
    ok7 = (c7_nc.get("status") in ("no_data", "no_numbers_in_claim")
           and c7.get("verdict") == "SUPPORTED"
           and c7.get("confidence", 1.0) > 0.6
           and not any("numeric_mismatch_unsupported" in ch for ch in c7.get("_changes", [])))
    # claim 10 — детерминированный qualifier_mismatch перекрыл ручной partial_match
    c10_nc = merged_by_id[10].get("numeric_comparison", {})
    c10 = proc_by_id[10]
    ok10 = (c10_nc.get("status") == "qualifier_mismatch"
            and any("qualifier_mismatch_capped" in ch for ch in c10.get("_changes", [])))
    # claim 5 — детерминированный диапазон 10–50 ч → partial_match (перекрыл ручной)
    c5_nc = merged_by_id[5].get("numeric_comparison", {})
    ok5 = c5_nc.get("status") in ("match", "partial_match")
    n_merged = sum(1 for v in merged if isinstance(v.get("numeric_comparison"), dict))
    log(f"  -> этап5 status_counts={sc} | merge: {n_merged}/20 вердиктов с numeric_comparison | "
        f"claim7 status={c7_nc.get('status')} verdict={c7.get('verdict')} "
        f"conf={c7.get('confidence')} | claim10 status={c10_nc.get('status')} | "
        f"claim5 status={c5_nc.get('status')}")
    ok = ok7 and ok10 and ok5
    note = (f"ok7(mismatch→правило)={ok7}, ok10(qualifier→cap)={ok10}, "
            f"ok5(ручной сохранён)={ok5}; status_counts={sc}")
    return ok, (f"claim7: status={c7_nc.get('status')}, verdict={c7.get('verdict')}, "
                f"conf={c7.get('confidence')}; claim10: {c10_nc.get('status')}; "
                f"claim5: {c5_nc.get('status')}; merged={n_merged}/20"), note


def test_s6_full_chain_exp1():
    assert run_scenario("6", "claim7 Fe2-3N → no_numbers_in_claim (не ложный mismatch), "
                             "SUPPORTED сохраняется; claim10 qualifier → cap; "
                             "claim5 диапазон 10-50ч → partial_match",
                        s6_full_chain_exp1,
                        "цепочка exp1 (mock LLM = реальные вердикты): "
                        "numeric_comparator → merge_numeric → post_processor")


# ───────────────────────── сводка PASS/FAIL ─────────────────────────

def _print_summary() -> None:
    log("=" * 72)
    log("СВОДКА РУЧЕЙКОВОГО ПРОГОНА merge_numeric (S1-S6)")
    log("=" * 72)
    for r in RESULTS:
        log(f"  S{r['name']}: {r['status']} — {r['actual']}")
    total, passed = len(RESULTS), sum(1 for r in RESULTS if r["status"] == "PASS")
    log("-" * 72)
    log(f"ИТОГО: {passed}/{total} PASS, {total - passed} FAIL")
    for r in RESULTS:
        if r["status"] == "FAIL":
            log(f"  FAIL S{r['name']}: ожидалось={r['expected']} получено={r['actual']}")
    log("=" * 72)
    LOG_PATH.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    print(f"\nЛог прогона: {LOG_PATH}")


@pytest.fixture(scope="session", autouse=True)
def _merge_summary():
    yield
    _print_summary()


def main() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    _print_summary()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())