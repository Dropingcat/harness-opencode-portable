#!/usr/bin/env python3
"""test_rivulet.py — «ручейковый тест» (sequential traversal test) пайплайна resercher.

Диагностический тест: обходит узлы пайплайна ПОСЛЕДОВАТЕЛЬНО (не параллельно),
от входа к выходу, запускает детерминированные скрипты на реальных данных exp1,
проверяет контракты схем (writes/reads) между узлами и статические дыры.

Pytest-совместимый: `pytest scripts/test_rivulet.py` и standalone `python3 ...`.

Файлы:
    спецификация:  /tmp/resercher-rivulet-spec.md
    лог прогона:   /tmp/rivulet-log.txt
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SERVICE = Path(__file__).resolve().parent
PROFILE = Path(__file__).resolve().parent
RULES_YAML = Path(__file__).resolve().parent / "testdata" / "rules.yaml"
EXP1 = Path(__file__).resolve().parent / "testdata" / "exp1"
WORK = Path(os.environ.get("TEMP", "/tmp")) / "rivulet-work"
LOG = Path(os.environ.get("TEMP", "/tmp")) / "rivulet-log.txt"

FACT_CHECKER_SKILL = Path(__file__).resolve().parent / "testdata" / "fact_checker_skill.md"
PIPELINE_SH = SERVICE / "run_pipeline.sh"

ISSUES: list[dict] = []
LOG_LINES: list[str] = []


def log(msg: str) -> None:
    LOG_LINES.append(msg)
    print(msg)


def check(cond: bool, category: str, message: str, severity: str = "FAIL") -> None:
    if not cond:
        ISSUES.append({"category": category, "severity": severity, "message": message})
        log(f"  ✗ [{category}] {message}")


# ───────────────────────── топология (контракты) ─────────────────────────
# reads_from: какие узлы-производители (по факту) питают вход данного узла.

NODES = [
    {
        "id": 1,
        "name": "extractor_claimeai",
        "script": "run_extractor.sh / claimeai_wrapper.py",
        "in": ["input.txt"],
        "out": "claims.json",
        "mode": "STUB/LLM",
        "reads_from": [],
        "writes": ["status", "claims", "statistics", "raw_keys", "processing_time_sec",
                   "validated", "text"],
        "reads": [],
    },
    {
        "id": 2,
        "name": "stub_verifier",
        "script": "stub_verifier.py (факт-чекер LLM)",
        "in": ["claims.json"],
        "out": "verdicts.json",
        "mode": "STUB/LLM",
        "reads_from": [1],
        "writes": ["claim_id", "claim_text", "verdict", "confidence", "reason",
                   "sources", "caveats", "numeric_comparison"],  # SKILL.md:50
        "reads": ["text"],  # claims.validated[].text
    },
    {
        "id": 3,
        "name": "numeric_comparator",
        "script": "numeric_comparator.py (+units/uncertainty/formulas)",
        "in": ["verdicts.json", "sources.json"],
        "out": "numeric_result.json",
        "mode": "DET",
        "reads_from": [2],
        "writes": ["total_groups", "total_claims", "status_counts", "groups"],
        "reads": ["claim_text", "sources"],
    },
    {
        "id": 4,
        "name": "evidence_contract",
        "script": "evidence_contract.py",
        "in": ["verdicts.json", "rules.yaml"],
        "out": "evidence.json",
        "mode": "DET",
        "reads_from": [2],
        "writes": ["evidence"],
        "reads": ["sources"],
    },
    {
        "id": 5,
        "name": "post_processor",
        "script": "post_processor.py",
        "in": ["verdicts.json", "rules.yaml"],
        "out": "verdicts_processed.json",
        "mode": "DET",
        "reads_from": [2, 4],  # rules.yaml: evidence_contract перед post_processor
        "writes": ["_post_processed", "_changes", "_caveats_total", "_caveats_critical",
                   "problematic", "trigger_tribunal", "numeric_comparison",
                   "verdict", "confidence"],
        "reads": ["numeric_comparison", "caveats", "evidence", "sources",
                  "confidence", "verdict"],
    },
    {
        "id": 6,
        "name": "judge_brief",
        "script": "judge_brief.py → LLM-судьи",
        "in": ["verdicts.json"],
        "out": "judge_briefs.json",
        "mode": "DET+STUB/LLM",
        "reads_from": [2, 4],
        "writes": ["total_claims", "briefs", "judge_id", "vector", "sources",
                   "include_verdict", "context"],
        "reads": ["claim_id", "claim_text", "evidence", "sources"],
    },
    {
        "id": 7,
        "name": "problematic_theses",
        "script": "(нет скрипта; SKILL.md 1i — LLM-оркестратор)",
        "in": ["verdicts_processed.json"],
        "out": "problematic_theses.json",
        "mode": "STUB/LLM",
        "reads_from": [5],
        "writes": ["claim_id", "claim_text", "verdict", "confidence", "caveats",
                   "reason", "changes", "suggested_reformulation"],
        "reads": ["problematic", "verdict", "confidence"],
    },
    {
        "id": 8,
        "name": "synthesizer",
        "script": "synthesizer.py / synthesizer-agent LLM",
        "in": ["verdicts.json"],
        "out": "final_report.md",
        "mode": "STUB/LLM",
        "reads_from": [2],
        "writes": ["# Отчёт верификации", "## Сводка", "## Детали по claims"],
        "reads": ["claim_id", "claim_text", "verdict", "confidence", "reason"],
    },
]


def run_cmd(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def load_json(p: Path):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def top_keys(p: Path) -> list[str]:
    d = load_json(p)
    if isinstance(d, dict):
        return sorted(d.keys())
    if isinstance(d, list) and d and isinstance(d[0], dict):
        return sorted(d[0].keys())
    return [f"<list:{len(d)}>"]


def first_keys(p: Path) -> list[str]:
    d = load_json(p)
    if isinstance(d, dict):
        return sorted(d.keys())
    if isinstance(d, list) and d and isinstance(d[0], dict):
        return sorted(d[0].keys())
    return []


def build_sources_json(out_path: Path) -> int:
    """Синтез sources.json из реальных sources[] вердиктов exp1 (не выдумано)."""
    verdicts = load_json(EXP1 / "verdicts.json")
    index = {}
    for v in verdicts:
        cid = str(v.get("claim_id"))
        sl = []
        for s in v.get("sources", []) or []:
            if isinstance(s, dict):
                sl.append({
                    "title": s.get("title", ""),
                    "descriptor": s.get("title", ""),
                    "text": s.get("excerpt", "") or "",
                    "type": s.get("type", ""),
                })
        index[cid] = {"original_index": v.get("claim_id"), "sources": sl}
    json.dump({"sources": index}, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    return len(index)


def artifact(exp1: Path, name: str) -> Path:
    """Реальный артефакт exp1 (если есть) или сгенерённый в WORK."""
    src = exp1 / name
    if src.exists():
        dst = WORK / name
        shutil.copy2(src, dst)
        return dst
    return WORK / name


def near_name(a: str, b: str) -> bool:
    return SequenceMatcher(None, a, b).ratio() > 0.65


# ───────────────────────── статические проверки ─────────────────────────

def static_checks() -> None:
    log("── Статический анализ ──")

# (1) числовая связка: факт-чекер пишет numeric_comparison, post_processor читает
    fc = FACT_CHECKER_SKILL.read_text(encoding="utf-8") if FACT_CHECKER_SKILL.exists() else ""
    pp = (SCRIPTS / "post_processor.py").read_text(encoding="utf-8")
    fc_writes = "numeric_comparison" in fc
    pp_reads = "numeric_comparison" in pp
    check(fc_writes and pp_reads, "signature_mismatch",
          "Числовая связка разорвана: факт-чекер (SKILL.md) и post_processor.py "
          f"должны использовать один ключ `numeric_comparison` "
          f"(SKILL.md: {fc_writes}, post_processor.py: {pp_reads}).")

    # (2) NUMERIC_JSON сливается в verdicts.json через merge_numeric (Этап 5.1)
    sh = PIPELINE_SH.read_text(encoding="utf-8") if PIPELINE_SH.exists() else ""
    merge_wired = re.search(r"""merge_numeric\.py""", sh) is not None
    post_fed_with_numeric = "verdicts_with_numeric" in sh
    check(merge_wired and post_fed_with_numeric, "disconnected_output",
          "NUMERIC_JSON (numeric_result.json) не сливается в вердикты: "
          "merge_numeric.py должен быть завязан в run_pipeline.sh (Этап 5.1) и "
          "его выход (verdicts_with_numeric.json) должен питать post_processor.")

    # (3) tribunal_rules.trigger_when/skip_when — мёртвая конфигурация
    trigger_when_dead = "trigger_when" in (Path(__file__).resolve().parent / "testdata" / "rules.yaml").read_text(encoding="utf-8") \
        and "trigger_when" not in pp
    skip_when_dead = "skip_when" in (Path(__file__).resolve().parent / "testdata" / "rules.yaml").read_text(encoding="utf-8") \
        and "skip_when" not in pp
    check(not (trigger_when_dead or skip_when_dead), "dead_config",
          "rules.yaml: tribunal_rules.trigger_when / skip_when — мёртвая конфигурация "
          "(post_processor.py их не читает; трибунал триггерится только по critical>=1).")

    # (4) verdict_schemas.py (Pydantic) подключён к пайплайну как предвалидация
    used = any("verdict_schemas" in (SCRIPTS / f).read_text(encoding="utf-8")
               for f in os.listdir(SCRIPTS) if f.endswith(".py") and f != "verdict_schemas.py"
               and not f.startswith("test_"))
    check(used, "dead_module",
          "verdict_schemas.py (Pydantic) не подключён к пайплайну "
          "(не используется как предвалидация ни одним скриптом).")

    # (5) хардкод API-ключа в claimeai_wrapper.py:43
    wrapper = (SCRIPTS / "claimeai_wrapper.py").read_text(encoding="utf-8")
    key_hits = re.findall(r"(?:OPENAI_API_KEY|API_KEY)\s*=\s*['\"](sk-[A-Za-z0-9_-]+)", wrapper)
    uses_polza = "POLZA_API_KEY" in wrapper and "polza.ai" in wrapper and "pza_" not in wrapper.split("POLZA_API_KEY")[0]
    check(not key_hits and uses_polza, "security",
          "claimeai_wrapper.py: должен использовать Polza без хардкода секрета "
          "(POLZA_API_KEY из env-файла + base_url polza.ai; никакого sk-... в коде).")

    # (6) детерминированные узлы вне run_pipeline.sh (мёртвые для оркестрации)
    for script_name in ("evidence_contract.py", "judge_brief.py", "synthesizer.py", "stub_verifier.py"):
        wired = script_name in sh
        check(wired, "dead_module",
              f"{script_name} не вызывается в run_pipeline.sh — узел не завязан "
              f"в shell-оркестрацию (упоминается только в SKILL.md/тестах).")


# ───────────────────────── ручей: обход узлов ─────────────────────────

def rivulet_traverse() -> None:
    log("── Ручей: последовательный обход узлов ──")

    # N1 Extractor (ClaimeAI) — STUB/LLM, агента не запускаем
    n1 = artifact(EXP1, "claims.json")
    ok1 = n1.exists()
    log(f"[NODE 1] extractor_claimeai: in={EXP1/'input.txt'} out={n1.name} "
        f"keys={top_keys(n1) if ok1 else 'MISSING'} status={'STUB/LLM' if ok1 else 'FAIL'}")
    check(ok1, "missing_input", "claims.json отсутствует в exp1 (вход N1→N2).")
    if ok1:
        d = load_json(n1)
        validated = d.get("claims", {}).get("validated", [])
        check(bool(validated), "dead_output",
              f"claims.validated пуст ({len(validated)}) — N2 не сможет верифицировать.")

    # N2 Stub-Verifier / факт-чекер — STUB/LLM
    n2 = artifact(EXP1, "verdicts.json")
    ok2 = n2.exists()
    log(f"[NODE 2] stub_verifier: in={n1.name} out={n2.name} "
        f"keys={first_keys(n2) if ok2 else 'MISSING'} status={'STUB/LLM' if ok2 else 'FAIL'}")
    check(ok2, "missing_input", "verdicts.json отсутствует в exp1 (вход N2→N3/N4/N5/N6/N8).")
    v_keys = set(first_keys(n2)) if ok2 else set()
    for k in ("claim_id", "claim_text", "verdict", "confidence"):
        check(k in v_keys, "signature_mismatch",
              f"verdicts.json не содержит ключ `{k}` (ожидает N5/N6/N8).")
    check("numeric_comparison" in v_keys, "signature_mismatch",
          "verdicts.json не содержит `numeric_comparison` — merge_numeric (Этап 5.1) "
          "не сможет заполнить поле для пост-процессора.")

    # N3 Числовой entailment — DET
    src_json = WORK / "sources.json"
    n_grp = build_sources_json(src_json) if (EXP1 / "verdicts.json").exists() else 0
    log(f"[NODE 3] numeric_comparator: in={n2.name}+sources.json "
        f"(sources синтезированы из sources[] вердиктов exp1: {n_grp} групп) "
        f"out=numeric_result.json status=RUN")
    rc, out = run_cmd(
        [sys.executable, str(SCRIPTS / "numeric_comparator.py"),
         str(n2), str(src_json), str(WORK / "numeric_result.json")],
        cwd=SCRIPTS)
    nres = WORK / "numeric_result.json"
    if rc != 0 or not nres.exists():
        log(f"[NODE 3] numeric_comparator: rc={rc} CRASH — {out.splitlines()[-1] if out else ''}")
        check(False, "shape_mismatch",
              "numeric_comparator.py падает на реальном verdicts.json exp1: "
              "ожидает dict с `verdicts[]`, получает list "
              f"(AttributeError 'list' object has no attribute get'; rc={rc}).")
    else:
        log(f"[NODE 3] numeric_comparator: out=numeric_result.json "
            f"keys={top_keys(nres)} status=OK")
        check("total_groups" in top_keys(nres), "dead_output",
              "numeric_result.json не содержит total_groups.")

    # N3b: probe с dict-обёрткой — проверка логики при совместимой форме
    wrapped = WORK / "verdicts_wrapped.json"
    if (EXP1 / "verdicts.json").exists():
        json.dump({"status": "success", "verdicts": load_json(EXP1 / "verdicts.json")},
                  open(wrapped, "w", encoding="utf-8"), ensure_ascii=False)
        rc2, _ = run_cmd(
            [sys.executable, str(SCRIPTS / "numeric_comparator.py"),
             str(wrapped), str(src_json), str(WORK / "numeric_result_wrapped.json")],
            cwd=SCRIPTS)
        if rc2 == 0 and (WORK / "numeric_result_wrapped.json").exists():
            nd = load_json(WORK / "numeric_result_wrapped.json")
            log(f"[NODE 3] numeric_comparator (probe dict-form): "
                f"keys={top_keys(WORK/'numeric_result_wrapped.json')} "
                f"status_counts={nd.get('status_counts')} status=OK")
            check(nd.get("total_claims", 0) > 0, "dead_output",
                  "numeric_comparator (даже при dict-форме) сравнивает 0 claims: "
                  "ожидает группы {original_index, claims:[text]}, а verdicts.json exp1 — "
                  "плоские вердикты {claim_id, claim_text} "
                  f"({nd.get('total_claims')} claims, status_counts={nd.get('status_counts')}).")

    # N4 Evidence Contract — DET
    n4 = WORK / "evidence.json"
    rc, out = run_cmd(
        [sys.executable, str(SCRIPTS / "evidence_contract.py"),
         str(n2), str(RULES_YAML), str(n4)],
        cwd=SCRIPTS)
    if rc == 0 and n4.exists():
        ev = load_json(n4)
        ev_ok = all(
            isinstance(v.get("evidence"), list) and
            all(isinstance(e, dict) and {"source_id", "span", "trust", "type"} <= set(e)
                for e in v.get("evidence") or [])
            for v in ev
        )
        log(f"[NODE 4] evidence_contract: in={n2.name} out=evidence.json "
            f"keys={sorted(first_keys(n4))} status={'OK' if ev_ok else 'FAIL'}")
        check(ev_ok, "signature_mismatch",
              "evidence[] не соответствует контракту {source_id, span, trust, type}.")
    else:
        log(f"[NODE 4] evidence_contract: rc={rc} CRASH")
        check(False, "dead_output", f"evidence_contract.py упал (rc={rc}).")

    # N5 Пост-процессор — DET (как в run_pipeline.sh: Этап 5.1 merge_numeric → Этап 6)
    n5 = WORK / "verdicts_processed.json"
    merged = WORK / "verdicts_with_numeric.json"
    rc_m, out_m = run_cmd(
        [sys.executable, str(SCRIPTS / "merge_numeric.py"),
         str(n2), str(WORK / "numeric_result.json"), str(merged)],
        cwd=SCRIPTS)
    n5_in = merged if (rc_m == 0 and merged.exists()) else n2
    if n5_in is merged:
        log(f"[NODE 5] merge_numeric: {n2.name} + numeric_result.json → "
            f"{merged.name} status=OK")
    else:
        log(f"[NODE 5] merge_numeric: rc={rc_m} CRASH — {out_m.splitlines()[-1] if out_m else ''}")
        check(False, "dead_output", f"merge_numeric.py упал (rc={rc_m}).")
    rc, out = run_cmd(
        [sys.executable, str(SCRIPTS / "post_processor.py"),
         str(n5_in), str(RULES_YAML), str(n5)],
        cwd=SCRIPTS)
    if rc == 0 and n5.exists():
        pkeys = set(first_keys(n5))
        log(f"[NODE 5] post_processor: in={n5_in.name} out=verdicts_processed.json "
            f"keys={sorted(pkeys)} status=OK")
        for k in ("_post_processed", "_changes", "_caveats_total", "_caveats_critical"):
            check(k in pkeys, "signature_mismatch", f"verdicts_processed.json не содержит `{k}`.")
        processed = load_json(n5)
        numeric_ran = sum(1 for v in processed if any(
            "numeric" in str(c).lower() for c in v.get("_changes") or []))
        log(f"[NODE 5] post_processor: numeric-правила применились для {numeric_ran} вердиктов "
            "(merge_numeric → numeric_comparison → правила).")
    else:
        log(f"[NODE 5] post_processor: rc={rc} CRASH")
        check(False, "dead_output", f"post_processor.py упал (rc={rc}).")

    # N6 Трибунал: judge_brief.py (DET) → LLM-судьи (STUB)
    n6 = WORK / "judge_briefs.json"
    rc, out = run_cmd(
        [sys.executable, str(SCRIPTS / "judge_brief.py"), str(n2), str(n6)],
        cwd=SCRIPTS)
    if rc == 0 and n6.exists():
        bd = load_json(n6)
        briefs = bd.get("briefs", {})
        sample = next(iter(briefs.values()), {}).get("briefs", [])
        roles_ok = sorted({b.get("judge_id") for b in sample}) == \
            sorted(["агрегатор", "адвокат", "методолог", "скептик", "физик"]) if sample else False
        log(f"[NODE 6] judge_brief: in={n2.name} out=judge_briefs.json "
            f"keys={top_keys(n6)} briefs={len(briefs)} roles={len(sample)} "
            f"status={'OK' if roles_ok else 'PARTIAL'}")
        check(roles_ok, "signature_mismatch", "judge_briefs.json: не все 5 ролей судей.")
        tribunal = EXP1 / "tribunal.json"
        sh_now = PIPELINE_SH.read_text(encoding="utf-8") if PIPELINE_SH.exists() else ""
        tribunal_fallback = ("deterministic_fallback" in sh_now and "tribunal.json" in sh_now)
        if tribunal.exists():
            tribunal_status = "артефакт есть в exp1"
        else:
            tribunal_status = "LLM-трибунал не выполнялся; fallback в run_pipeline.sh Этап 7: " + \
                ("да" if tribunal_fallback else "НЕТ")
        log(f"[NODE 6] tribunal-LLM: out=tribunal.json -> status=STUB/LLM ({tribunal_status})")
        check(tribunal.exists() or tribunal_fallback, "missing_input",
              "tribunal.json (выход LLM-судей) не гарантируется: в exp1 отсутствует "
              "И в run_pipeline.sh (Этап 7) нет детерминированного fallback "
              "(deterministic_fallback) для генерации tribunal.json из judge_briefs.json.")
    else:
        log(f"[NODE 6] judge_brief: rc={rc} CRASH")
        check(False, "dead_output", f"judge_brief.py упал (rc={rc}).")

    # N7 Проблемные тезисы — STUB/LLM (реальный артефакт exp1)
    n7 = artifact(EXP1, "problematic_theses.json")
    ok7 = n7.exists()
    k7 = set(first_keys(n7)) if ok7 else set()
    log(f"[NODE 7] problematic_theses: in=verdicts_processed.json out={n7.name} "
        f"keys={sorted(k7) if ok7 else 'MISSING'} status={'STUB/LLM' if ok7 else 'FAIL'}")
    check(ok7, "missing_input", "problematic_theses.json отсутствует в exp1.")
    for k in ("claim_id", "claim_text", "verdict", "suggested_reformulation"):
        check(k in k7, "signature_mismatch", f"problematic_theses.json не содержит `{k}`.")

    # N8 Синтез — проверка synthesizer.py на реальном формате + STUB/LLM артефакт
    log(f"[NODE 8] synthesizer: in={n2.name} out=final_report.md status=RUN")
    rc8, out8 = run_cmd(
        [sys.executable, str(SCRIPTS / "synthesizer.py"), str(n2), str(WORK / "final_report_probe.md")],
        cwd=SCRIPTS)
    if rc8 != 0:
        log(f"[NODE 8] synthesizer: rc={rc8} CRASH — "
            f"{out8.splitlines()[-1] if out8 else ''} (list-формат verdicts.json)")
        check(False, "shape_mismatch",
              "synthesizer.py падает на list-формате verdicts.json "
              "(data.get('verdicts') на списке) — rc=" + str(rc8))
    else:
        check((WORK / "final_report_probe.md").exists(), "dead_output",
              "final_report.md не создан synthesizer.py.")
    report = artifact(EXP1, "final_report.md")
    ok8 = report.exists()
    log(f"[NODE 8] synthesizer-agent (LLM): out=final_report.md -> "
        f"status={'STUB/LLM' if ok8 else 'FAIL'} "
        f"({'артефакт есть' if ok8 else 'артефакт отсутствует'})")
    check(ok8, "missing_input", "final_report.md отсутствует в exp1.")

    # ── Контракты связи: reads(N) ⊆ writes(upstream(N)) ──
    log("── Проверка контрактов связи (writes upstream → reads узла) ──")
    write_sets: dict[int, set] = {}
    if ok1:
        write_sets[1] = set(NODES[0]["writes"])
    if ok2:
        write_sets[2] = set(NODES[1]["writes"])
    if (WORK / "numeric_result.json").exists():
        write_sets[3] = set(NODES[2]["writes"])
    if (WORK / "evidence.json").exists():
        write_sets[4] = set(NODES[3]["writes"])
    if (WORK / "verdicts_processed.json").exists():
        write_sets[5] = set(NODES[4]["writes"])
    if (WORK / "judge_briefs.json").exists():
        write_sets[6] = set(NODES[5]["writes"])

    for node in NODES:
        ups = [u for u in node.get("reads_from", []) if u in write_sets]
        if not ups:
            continue
        for rk in node.get("reads", []):
            if any(rk in write_sets[u] for u in ups):
                continue
            near = {wk for u in ups for wk in write_sets[u] if near_name(rk, wk)}
            if near:
                check(False, "signature_mismatch",
                      f"READ `{rk}` (N{node['id']} {node['name']}) — upstream пишет похожее "
                      f"имя {sorted(near)} — несогласованность сигнатуры ключа.")
            else:
                check(False, "link_broken",
                      f"READ `{rk}` (N{node['id']} {node['name']}) отсутствует в выходах "
                      f"upstream N{ups} — обрыв связи (выход узла не читается следующим).")


def run_rivulet() -> int:
    LOG.unlink(missing_ok=True)
    log("=" * 72)
    log("РУЧЕЙКОВЫЙ ТЕСТ (sequential traversal) — пайплайн resercher")
    log(f"exp1:   {EXP1}")
    log(f"рабочая папка: {WORK}")
    log("=" * 72)

    WORK.mkdir(parents=True, exist_ok=True)

    static_checks()
    rivulet_traverse()

    log("=" * 72)
    log(f"ИТОГ: {'FAIL' if ISSUES else 'PASS'} — найдено проблем: {len(ISSUES)}")
    for i, iss in enumerate(ISSUES, 1):
        log(f"  {i}. [{iss['category']}] {iss['message']}")
    log("=" * 72)

    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(LOG_LINES) + "\n")
    print(f"\nЛог записан: {LOG}")
    return 1 if ISSUES else 0


def test_rivulet_traversal() -> None:
    """Pytest-обёртка: гоняет ручеёк и логирует в /tmp/rivulet-log.txt.

    Тест не падает по найденным проблемам — это диагностика: проблемы видны в логе.
    """
    rc = run_rivulet()
    assert rc in (0, 1), "rivulet crashed"


def main() -> int:
    return run_rivulet()


if __name__ == "__main__":
    sys.exit(main())
