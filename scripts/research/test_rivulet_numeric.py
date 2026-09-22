#!/usr/bin/env python3
"""test_rivulet_numeric.py — глубокий ручейковый тест numeric_comparator.

Диагностический «ручеёк» (sequential traversal) по 4 уровням:
  L1 — форматы входа (shape)
  L2 — источники (sources)
  L3 — числовые сценарии (качество entailment)
  L4 — интеграция

Каждый сценарий логирует: вход → что сделано → выход → статус (PASS/FAIL).
В конце — сводка PASS/FAIL по уровням.

Pytest-совместимый: `python3 -m pytest test_rivulet_numeric.py -q -s`
Standalone: `python3 test_rivulet_numeric.py`
Лог прогона: /tmp/rivulet-numeric-log.txt
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
EXP1 = Path(__file__).resolve().parent / "testdata" / "exp1"
REAL_VERDICTS = EXP1 / "verdicts_processed.json"

LOG_PATH = Path("/tmp/rivulet-numeric-log.txt")

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from numeric_comparator import (  # noqa: E402
    _extract_sources_index,
    _lookup_sources,
    _normalize_groups,
    compare_claim_sources,
)

LEVELS = {
    "L1": "Уровень 1 — Форматы входа (shape)",
    "L2": "Уровень 2 — Источники (sources)",
    "L3": "Уровень 3 — Числовые сценарии (entailment)",
    "L4": "Уровень 4 — Интеграция",
}

LOG: list[str] = []
RESULTS: list[dict] = []


def log(msg: str) -> None:
    LOG.append(msg)
    print(msg)


def record(level: str, name: str, ok: bool, expected: str, actual: str, note: str = "") -> None:
    RESULTS.append({
        "level": level,
        "name": name,
        "status": "PASS" if ok else "FAIL",
        "expected": expected,
        "actual": actual,
        "note": note,
    })
    log(f"  [{level}·{name}] {'PASS' if ok else 'FAIL'}")
    log(f"      ожидалось: {expected}")
    log(f"      получено:  {actual}")
    if note:
        log(f"      примечание: {note}")


def run_scenario(level: str, name: str, expected: str, fn, desc: str) -> bool:
    """Логирует вход→действие, запускает fn() → (ok, actual[, note]), пишет статус."""
    log(f"[{level}·{name}] вход/действие: {desc}")
    note = ""
    try:
        result = fn()
        if len(result) == 3:
            ok, actual, note = result
        else:
            ok, actual = result
    except Exception as exc:  # noqa: BLE001 — любое падение сценария = FAIL
        ok, actual, note = False, f"CRASH {type(exc).__name__}: {exc}", ""
    record(level, name, ok, expected, actual, note)
    return ok


def run_main(verdicts, sources, workdir=None):
    """Прогон numeric_comparator.py как скрипт → (rc, stdout+stderr, result|None)."""
    workdir = workdir or Path(tempfile.mkdtemp(prefix="rivulet_numeric_"))
    vp, sp, op = workdir / "verdicts.json", workdir / "sources.json", workdir / "numeric_result.json"
    vp.write_text(json.dumps(verdicts, ensure_ascii=False), encoding="utf-8")
    sp.write_text(json.dumps(sources, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "numeric_comparator.py"), str(vp), str(sp), str(op)],
        capture_output=True, text=True, timeout=120, env=env, encoding="utf-8", errors="replace",
    )
    result = None
    if op.exists():
        try:
            result = json.loads(op.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result = None
    return proc.returncode, (proc.stdout + proc.stderr).strip(), result


def synth_sources_from_verdicts(verdicts):
    """Синтезирует sources.json {sources: {claim_id: {sources: []}}} из sources[] вердиктов."""
    index = {}
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        sl = []
        for s in v.get("sources", []) or []:
            if isinstance(s, dict):
                sl.append({
                    "title": s.get("title", ""),
                    "descriptor": s.get("title", ""),
                    "text": s.get("excerpt", "") or s.get("text", "") or "",
                    "type": s.get("type", ""),
                })
        cid = v.get("claim_id")
        if cid is not None:
            index[str(cid)] = {"original_index": v.get("original_index"), "sources": sl}
    return {"sources": index}


# ───────────────────────── Уровень 1 — форматы входа ─────────────────────────

def l1_flat_real():
    verdicts = json.loads(REAL_VERDICTS.read_text(encoding="utf-8"))
    groups = _normalize_groups(verdicts)
    log(f"  -> _normalize_groups: {len(groups)} групп, у всех claim_id: "
        f"{all(g.get('claim_id') is not None for g in groups)}")
    rc, out, result = run_main(verdicts, synth_sources_from_verdicts(verdicts))
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    ok = (result["total_claims"] == 20 and bool(result["status_counts"])
          and all(g.get("claim_id") is not None for g in result["groups"]))
    log(f"  -> выход: rc={rc} total_claims={result['total_claims']} "
        f"total_groups={result['total_groups']} status_counts={result['status_counts']}")
    return ok, (f"rc={rc}, total_claims={result['total_claims']}, "
                f"status_counts={result['status_counts']}")


def l1_dict_verdicts():
    verdicts = json.loads(REAL_VERDICTS.read_text(encoding="utf-8"))
    wrapped = {"status": "success", "verdicts": verdicts}
    rc, out, result = run_main(wrapped, synth_sources_from_verdicts(verdicts))
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    log(f"  -> выход: rc={rc} total_claims={result['total_claims']} "
        f"status_counts={result['status_counts']}")
    return result["total_claims"] == 20, f"total_claims={result['total_claims']}"


def l1_dict_groups():
    groups = [
        {"original_index": 5, "claims": ["твердость 500 HV"]},
        {"original_index": 7, "claims": ["размер 77 мм"]},
    ]
    sources = {"sources": {"5": {"sources": [{"text": "твердость 500 HV"}]}}}
    rc, out, result = run_main({"groups": groups}, sources)
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    gstatus = [(g["original_index"], g["group_status"]) for g in result["groups"]]
    log(f"  -> выход: rc={rc} total_claims={result['total_claims']} groups={gstatus}")
    ok = result["total_claims"] == 2 and result["groups"][0]["group_status"] == "match"
    return ok, f"total_claims={result['total_claims']}, groups={gstatus}"


def l1_dict_single():
    rc, out, result = run_main({"claim_id": 9, "claim_text": "0.3-0.6 мм"}, {})
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    g = result["groups"][0]
    log(f"  -> выход: rc={rc} total_claims={result['total_claims']} "
        f"group_claim_id={g.get('claim_id')} group_status={g['group_status']}")
    return result["total_claims"] == 1 and g.get("claim_id") == 9, \
        f"total_claims={result['total_claims']}, group_claim_id={g.get('claim_id')}"


def l1_empty_list():
    rc, out, result = run_main([], {})
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    log(f"  -> выход: rc={rc} total_claims={result['total_claims']} "
        f"status_counts={result['status_counts']}")
    return result["total_claims"] == 0 and result["status_counts"] == {}, \
        f"total_claims={result['total_claims']}, status_counts={result['status_counts']}"


def l1_none_and_broken():
    td = Path(tempfile.mkdtemp(prefix="rivulet_none_"))
    vp, sp, op = td / "verdicts.json", td / "sources.json", td / "out.json"
    sp.write_text("{}", encoding="utf-8")
    vp.write_text("null", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p1 = subprocess.run(
        [sys.executable, str(SCRIPTS / "numeric_comparator.py"), str(vp), str(sp), str(op)],
        capture_output=True, text=True, timeout=60, env=env, encoding="utf-8", errors="replace")
    rc_none = p1.returncode
    vp.write_text("{ this is not json", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p2 = subprocess.run(
        [sys.executable, str(SCRIPTS / "numeric_comparator.py"), str(vp), str(sp), str(op)],
        capture_output=True, text=True, timeout=60, env=env, encoding="utf-8", errors="replace")
    err2 = (p2.stdout + p2.stderr).strip()
    log(f"  -> None (файл 'null'): rc={rc_none} | битый JSON: rc={p2.returncode} "
        f"err={err2[:120]!r}")
    ok = rc_none == 0 and p2.returncode == 2 and "AttributeError" not in err2 and "ОШИБКА" in err2
    return ok, (f"None rc={rc_none}, broken rc={p2.returncode}, "
                f"AttributeError={'AttributeError' in err2}, ОШИБКА={'ОШИБКА' in err2}")


def test_l1_flat_list_20_real():
    assert run_scenario("L1", "1", "rc=0, total_claims=20, status_counts непустой, "
                                   "claim_id у каждой группы", l1_flat_real,
                        "список 20 плоских вердиктов (verdicts_processed.json exp1) → "
                        "_normalize_groups + main()")


def test_l1_dict_verdicts():
    assert run_scenario("L1", "2", "rc=0, total_claims=20", l1_dict_verdicts,
                        "dict {verdicts: [...]} (обёртка exp1) → main()")


def test_l1_dict_groups():
    assert run_scenario("L1", "3", "rc=0, total_claims=2, группа с source → match",
                        l1_dict_groups, "dict {groups: [...]} с original_index → main()")


def test_l1_dict_single_verdict():
    assert run_scenario("L1", "4", "rc=0, total_claims=1, claim_id=9",
                        l1_dict_single, "dict БЕЗ verdicts/groups (одиночный вердикт) → main()")


def test_l1_empty_list():
    assert run_scenario("L1", "5", "rc=0, total_claims=0, status_counts={}",
                        l1_empty_list, "пустой list [] → main()")


def test_l1_none_broken_json():
    assert run_scenario("L1", "6", "None → rc=0; битый JSON → rc=2, понятная ОШИБКА, "
                                   "НЕ AttributeError", l1_none_and_broken,
                        "файл вердиктов = null / битый JSON → main()")


# ───────────────────────── Уровень 2 — источники (sources) ─────────────────────────

def l2_sources_dict():
    verdicts = [{"claim_id": 7, "claim_text": "твердость 500 HV"}]
    sources = {"sources": {"7": {"sources": [{"title": "s", "text": "твердость 500 HV"}]}}}
    rc, out, result = run_main(verdicts, sources)
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    g = result["groups"][0]
    log(f"  -> выход: rc={rc} n_sources={g['n_sources']} group_status={g['group_status']}")
    return g["n_sources"] == 1 and g["group_status"] == "match", \
        f"n_sources={g['n_sources']}, group_status={g['group_status']}"


def l2_sources_list():
    verdicts = [{"original_index": 7, "claim_id": 7, "claim_text": "твердость 500 HV"}]
    sources = [{"original_index": 7, "sources": [{"title": "s", "text": "твердость 500 HV"}]}]
    rc, out, result = run_main(verdicts, sources)
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    g = result["groups"][0]
    log(f"  -> выход: rc={rc} n_sources={g['n_sources']} group_status={g['group_status']}")
    return g["n_sources"] == 1 and g["group_status"] == "match", \
        f"n_sources={g['n_sources']}, group_status={g['group_status']}"


def l2_by_claim_id():
    verdicts = [{"claim_id": 7, "claim_text": "твердость 500 HV"}]
    sources = {"sources": {"7": {"sources": [{"title": "s", "text": "твердость 500 HV"}]}}}
    idx_dict, idx_list = _extract_sources_index(sources)
    found = _lookup_sources(idx_dict, idx_list, None, 7)
    rc, out, result = run_main(verdicts, sources)
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    g = result["groups"][0]
    log(f"  -> выход: _lookup_sources(claim_id=7)={len(found)} найдено, rc={rc} "
        f"n_sources={g['n_sources']} group_status={g['group_status']}")
    return len(found) == 1 and g["n_sources"] == 1 and g["group_status"] == "match", \
        f"lookup={len(found)}, n_sources={g['n_sources']}, group_status={g['group_status']}"


def l2_empty_sources():
    verdicts = [{"claim_id": 7, "claim_text": "твердость 500 HV"}]
    rc, out, result = run_main(verdicts, {"sources": {}})
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    g = result["groups"][0]
    log(f"  -> выход: rc={rc} n_sources={g['n_sources']} group_status={g['group_status']}")
    return g["n_sources"] == 0 and g["group_status"] == "no_data", \
        f"n_sources={g['n_sources']}, group_status={g['group_status']}"


def l2_verdict_without_sources():
    verdicts = [{"claim_id": 7, "claim_text": "твердость 500 HV"}]
    res = compare_claim_sources(verdicts[0], [])
    rc, out, result = run_main(verdicts, {})
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    g = result["groups"][0]
    log(f"  -> выход: compare_claim_sources.status={res['status']!r}, rc={rc} "
        f"group_status={g['group_status']}")
    return res["status"] == "no_data" and g["group_status"] == "no_data", \
        f"compare={res['status']!r}, group_status={g['group_status']}"


def test_l2_sources_dict_form():
    assert run_scenario("L2", "1", "n_sources=1, group_status=match", l2_sources_dict,
                        "sources dict {group_id: {sources:[]}} → main()")


def test_l2_sources_list_form():
    assert run_scenario("L2", "2", "n_sources=1, group_status=match", l2_sources_list,
                        "sources list [{original_index, sources:[]}] → main()")


def test_l2_sources_by_claim_id():
    assert run_scenario("L2", "3", "источник найден по claim_id, group_status=match",
                        l2_by_claim_id, "плоский вердикт без original_index → fallback по claim_id")


def test_l2_empty_sources():
    assert run_scenario("L2", "4", "n_sources=0, group_status=no_data, не падает",
                        l2_empty_sources, "пустые sources → main()")


def test_l2_verdict_without_sources():
    assert run_scenario("L2", "5", "status=no_data, не падает", l2_verdict_without_sources,
                        "вердикт без sources[] → compare_claim_sources + main()")


# ──────────────────────── Уровень 3 — числовые сценарии ────────────────────────

def l3_convertible_units():
    hv = compare_claim_sources(
        {"claim_id": 1, "claim_text": "твердость 500 HV"},
        [{"title": "s", "numbers": [{"type": "single", "value": 4.9, "unit": "GPa", "raw": "4.9 GPa"}]}])
    nm = compare_claim_sources(
        {"claim_id": 2, "claim_text": "размер частиц 500 nm"},
        [{"title": "s", "text": "размер частиц 0.5 µm"}])
    log(f"  -> выход: HV→GPa → {hv['status']!r} | nm→µm (текст) → {nm['status']!r}")
    ok = all(s in ("match", "partial_match") and s != "dimension_mismatch"
             for s in (hv["status"], nm["status"]))
    return ok, f"HV→GPa={hv['status']!r}, nm→µm={nm['status']!r}"


def l3_uncertainty():
    a = compare_claim_sources(
        {"claim_id": 3, "claim_text": "значение 77 ± 3 мм"},
        [{"title": "s", "text": "значение 78 ± 5 мм"}])
    b = compare_claim_sources(
        {"claim_id": 3, "claim_text": "значение 77 ± 3 мм"},
        [{"title": "s", "text": "диапазон 70-80 мм"}])
    log(f"  -> выход: 77±3 vs 78±5 → {a['status']!r} | 77±3 vs 70-80 → {b['status']!r}")
    return a["status"] == "match" and b["status"] == "match", \
        f"78±5→{a['status']!r}, 70-80→{b['status']!r}"


def l3_formula_conflict():
    res = compare_claim_sources(
        {"claim_id": 4, "claim_text": "D = λ/(βcosθ), K=1 по Шерреру"},
        [{"title": "s", "text": "по Шерреру K = 0.9"}])
    log(f"  -> выход: status={res['status']!r} formula={res['formula']}")
    ok = res["status"] == "mismatch" and res["formula"] \
        and res["formula"]["constant_check"] == "formula_conflict"
    return ok, f"status={res['status']!r}, constant_check=" \
        f"{res['formula']['constant_check'] if res['formula'] else None}"


def l3_dimension_mismatch():
    res = compare_claim_sources(
        {"claim_id": 5, "claim_text": "размер 77 мм"},
        [{"title": "s", "text": "температура 77 °C"}])
    log(f"  -> выход: status={res['status']!r} "
        f"comparisons={[c['status'] for c in res['results'][0]['comparisons']]}")
    # Слой 3: разноразмерная пара → not_comparable, НЕ dimension-вердикт
    return res["status"] == "not_comparable", f"status={res['status']!r}"


def l3_bare_numbers():
    eq = compare_claim_sources(
        {"claim_id": 6, "claim_text": "температура 540"},
        [{"title": "s", "text": "температура 540"}])
    skip = compare_claim_sources(
        {"claim_id": 6, "claim_text": "температура 540"},
        [{"title": "s", "text": "температура 541"}])
    log(f"  -> выход: голое=голое (540 vs 540) → {eq['status']!r} | "
        f"голое vs 541 → {skip['status']!r}")
    return eq["status"] == "match" and skip["status"] == "not_comparable", \
        f"equal→{eq['status']!r}, diff→{skip['status']!r}"


def l3_contradictory():
    within = compare_claim_sources(
        {"claim_id": 7, "claim_text": "твердость 500 HV"},
        [{"title": "s", "text": "500 HV, 501 HV, 200 HV"}])
    across = compare_claim_sources(
        {"claim_id": 7, "claim_text": "твердость 500 HV"},
        [{"title": "m1", "text": "твердость 500 HV"},
         {"title": "m2", "numbers": [{"type": "single", "value": 4.9, "unit": "GPa", "raw": "4.9 GPa"}]},
         {"title": "mis", "text": "твердость 200 HV"}])
    log(f"  -> выход: внутри источника (500 vs 500/501/200) → {within['status']!r} | "
        f"3 источника (2 match + 1 mismatch) → {across['status']!r}")
    # Слой 3: парное выравнивание best-match — claim 500 HV спаривается с ближайшим
    # source-числом 500 HV → match, а не ложный mismatch по шумовым парам.
    ok = within["status"] == "match"
    note = (f"парное выравнивание: внутри источника 500 HV спаривается с 500 HV → "
            f"match ({within['status']!r}); "
            f"агрегация ПО ИСТОЧНИКАМ — best-case ({across['status']!r})")
    return ok, f"внутри={within['status']!r}, по-источникам={across['status']!r}", note


def test_l3_convertible_units():
    assert run_scenario("L3", "1", "HV→GPa и nm→µm → match/partial, НЕ dimension_mismatch",
                        l3_convertible_units, "claim с числом + source с конвертируемой единицей")


def test_l3_uncertainty():
    assert run_scenario("L3", "2", "77±3 → match (через uncertainty)", l3_uncertainty,
                        "claim 77±3 vs source 78±5 / 70-80")


def test_l3_formula_constant_conflict():
    assert run_scenario("L3", "3", "Шеррер, K=1 → mismatch (formula_conflict)",
                        l3_formula_conflict, "claim с формулой (Шеррер) + конфликт константы")


def test_l3_dimension_mismatch():
    assert run_scenario("L3", "4", "77 мм vs 77 °C → not_comparable (не dimension_mismatch)",
                        l3_dimension_mismatch, "claim число + НЕконвертируемая единица источника")


def test_l3_bare_numbers():
    assert run_scenario("L3", "5", "голое=голое → match; голое≠голое → not_comparable",
                        l3_bare_numbers, "голое число без единицы — по точному равенству")


def test_l3_contradictory_sources():
    assert run_scenario("L3", "6", "противоречивые источники → парное выравнивание best-match",
                        l3_contradictory, "противоречивые источники (500 vs 500/501/200)")


# ───────────────────────── Уровень 4 — интеграция ─────────────────────────

def l4_claim_id_in_output():
    verdicts = json.loads(REAL_VERDICTS.read_text(encoding="utf-8"))
    rc, out, result = run_main(verdicts, synth_sources_from_verdicts(verdicts))
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    missing_g = [g["claim_id"] for g in result["groups"] if g.get("claim_id") is None]
    missing_c = [c.get("claim_id") for g in result["groups"] for c in g["claims"]
                 if c.get("claim_id") is None]
    g0 = result["groups"][0]
    log(f"  -> выход: groups={len(result['groups'])}, group[0].claim_id={g0.get('claim_id')}, "
        f"групп без claim_id: {len(missing_g)}, claims без claim_id: {len(missing_c)}")
    return not missing_g and not missing_c and g0.get("claim_id") is not None, \
        f"groups={len(result['groups'])}, missing_g={len(missing_g)}, missing_c={len(missing_c)}"


def l4_real_exp1():
    verdicts = json.loads(REAL_VERDICTS.read_text(encoding="utf-8"))
    rc, out, result = run_main(verdicts, synth_sources_from_verdicts(verdicts))
    if rc != 0:
        return False, f"rc={rc}: {out[:200]}"
    sc = result["status_counts"]
    log(f"  -> выход: rc={rc} total_claims={result['total_claims']} status_counts={sc}")
    return rc == 0 and result["total_claims"] == 20 and bool(sc), \
        f"total_claims={result['total_claims']}, status_counts={sc}"


def test_l4_claim_id_in_output():
    assert run_scenario("L4", "1", "каждая группа и claim содержит claim_id (для будущего merge)",
                        l4_claim_id_in_output, "выход main() на реальном exp1")


def test_l4_real_exp1():
    assert run_scenario("L4", "2", "rc=0, total_claims=20, status_counts показан",
                        l4_real_exp1, "прогон на реальном verdicts_processed.json (exp1)")


# ───────────────────────── сводка PASS/FAIL ─────────────────────────

def _print_summary() -> None:
    log("=" * 72)
    log("СВОДКА РУЧЕЙКОВОГО ПРОГОНА numeric_comparator (PASS/FAIL по уровням)")
    log("=" * 72)
    for lvl, title in LEVELS.items():
        items = [r for r in RESULTS if r["level"] == lvl]
        if not items:
            continue
        passed = sum(1 for r in items if r["status"] == "PASS")
        log(f"{title}: {passed}/{len(items)} PASS")
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    log("-" * 72)
    log(f"ИТОГО: {passed}/{total} PASS, {total - passed} FAIL")
    for r in RESULTS:
        if r["status"] == "FAIL":
            log(f"  FAIL {r['level']}·{r['name']}: ожидалось={r['expected']} "
                f"получено={r['actual']}")
    log("=" * 72)
    LOG_PATH.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    print(f"\nЛог прогона: {LOG_PATH}")


@pytest.fixture(scope="session", autouse=True)
def _rivulet_summary():
    yield
    _print_summary()


def main() -> int:
    failures = 0
    test_funcs = [(k, v) for k, v in sorted(globals().items())
                  if k.startswith("test_") and callable(v)]
    for name, fn in test_funcs:
        try:
            fn()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    _print_summary()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
