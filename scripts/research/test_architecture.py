#!/usr/bin/env python3
"""test_architecture.py — глубокое архитектурное тестирование пайплайна resercher.

Покрывает 5 направлений (consistency / dependencies / encapsulation /
failure handling / negative). Запускает детерминированные скрипты на реальных
данных exp1 + микро-фикстуры. НЕ чинит найденное — только фиксирует.

Запуск:
    python3 -m pytest scripts/test_architecture.py -v
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SERVICE = Path(__file__).resolve().parent
WRITER = Path(__file__).resolve().parent / "writer"
PROFILE = Path(__file__).resolve().parent
RULES_YAML = Path(__file__).resolve().parent / "testdata" / "rules.yaml"
CONFIG_YAML = Path(__file__).resolve().parent / "config.yaml"
EXP1 = Path(__file__).resolve().parent / "testdata" / "exp1"
WORK = Path(os.environ.get("TEMP", "/tmp")) / "arch-test"
WORK.mkdir(parents=True, exist_ok=True)

EXP1_VERDICTS = EXP1 / "verdicts.json"
EXP1_CLAIMS = EXP1 / "claims.json"
EXP1_INPUT = EXP1 / "input.txt"


# ───────────────────────── helpers ─────────────────────────

def run_cli(script, args, cwd=SCRIPTS, timeout=120):
    script_path = Path(script) if Path(script).is_absolute() else SCRIPTS / script
    cmd = [sys.executable, str(script_path)] + [str(a) for a in args]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env, encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_json(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def build_sources_from_exp1(out: Path) -> dict:
    """Синтез sources.json из реальных sources[] вердиктов exp1."""
    verdicts = load_json(EXP1_VERDICTS)
    index = {}
    for v in verdicts:
        cid = str(v.get("claim_id"))
        sl = []
        for s in v.get("sources", []) or []:
            if isinstance(s, dict):
                sl.append({
                    "title": s.get("title", ""),
                    "descriptor": s.get("title", ""),
                    "text": s.get("excerpt", "") or s.get("title", ""),
                    "type": s.get("type", ""),
                })
        index[cid] = {"original_index": v.get("claim_id"), "sources": sl}
    write_json(out, {"sources": index})
    return index


def build_topics_tree(out: Path):
    """topics_tree.json из exp1 (через fallback на claims.json)."""
    shutil.copy2(EXP1_CLAIMS, WORK / "claims.json")
    rc, _ = run_cli("topics_tree.py", [EXP1_INPUT, WORK / "claim_groups.json", out])
    return rc, out


def run_det_chain() -> dict:
    """Прогон детерминированной цепочки на exp1; возвращает карту артефактов."""
    d = WORK / "chain"
    d.mkdir(parents=True, exist_ok=True)
    src_json = d / "sources.json"
    build_sources_from_exp1(src_json)

    verdicts = d / "verdicts.json"
    shutil.copy2(EXP1_VERDICTS, verdicts)

    evidence = d / "verdicts_with_evidence.json"
    rc1, _ = run_cli("evidence_contract.py", [verdicts, RULES_YAML, evidence])

    nc = d / "numeric_result.json"
    rc2, _ = run_cli("numeric_comparator.py", [verdicts, src_json, nc])

    merged = d / "verdicts_with_numeric.json"
    rc3, _ = run_cli("merge_numeric.py", [evidence, nc, merged])

    processed = d / "verdicts_processed.json"
    rc4, _ = run_cli("post_processor.py", [merged, RULES_YAML, processed])

    tt = d / "topics_tree.json"
    rc5, _ = build_topics_tree(tt)

    escalated = d / "escalated.json"
    rc6, _ = run_cli("escalation.py", [processed, tt, RULES_YAML, escalated])

    justified = d / "justification.json"
    rc7, _ = run_cli("justification_check.py", [escalated, RULES_YAML, justified, "--report", d / "alarms.json"])

    briefs = d / "judge_briefs.json"
    rc8, _ = run_cli("judge_brief.py", [evidence, briefs])

    return {
        "evidence": (rc1, evidence), "numeric": (rc2, nc), "merged": (rc3, merged),
        "processed": (rc4, processed), "topics": (rc5, tt),
        "escalated": (rc6, escalated), "justified": (rc7, justified),
        "briefs": (rc8, briefs),
    }


SH = (SERVICE / "run_pipeline.sh").read_text(encoding="utf-8")


def load_rules():
    import yaml
    with open(RULES_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def all_scripts():
    return sorted(p.name for p in SCRIPTS.glob("*.py") if not p.name.startswith("test_"))


# ═══════════════════════ 1. CONSISTENCY ═══════════════════════

def test_c1_canonical_numeric_key():
    """number_comparison остался только в миграционном коде post_processor."""
    hits = []
    for f in all_scripts():
        src = (SCRIPTS / f).read_text(encoding="utf-8")
        for m in re.finditer(r"number_comparison", src):
            if f == "post_processor.py":
                continue
            hits.append(f"{f}:{src.count('number_comparison')}")
    assert not hits, f"неканонический ключ number_comparison в: {hits}"


def test_c2_chain_schema_reads_writes():
    """Сквозная цепочка: каждый блок читает ключи, написанные предыдущим."""
    artifacts = run_det_chain()

    # evidence: sources[] -> evidence[] {source_id, span, trust, type}
    rc, ev_path = artifacts["evidence"]
    assert rc == 0 and ev_path.exists()
    ev = load_json(ev_path)
    for v in ev:
        for e in v.get("evidence", []):
            assert {"source_id", "span", "trust", "type"} <= set(e), \
                f"evidence ключи: {sorted(e)}"

    # post_processor: читает numeric_comparison и пишет _post_processed
    rc, pp_path = artifacts["processed"]
    if rc == 0 and pp_path.exists():
        for v in load_json(pp_path):
            assert v.get("_post_processed") is True
            assert "_changes" in v

    # judge_brief читает evidence (созданный evidence_contract)
    rc, jb_path = artifacts["briefs"]
    assert rc == 0 and jb_path.exists()
    briefs = load_json(jb_path).get("briefs", {})
    sample = next(iter(briefs.values()), {}).get("briefs", [])
    roles = sorted({b.get("judge_id") for b in sample})
    assert roles == sorted(["физик", "методолог", "скептик", "адвокат", "агрегатор"]), roles


def test_c3_rules_yaml_all_keys_used():
    """Каждый ключ rules.yaml реально читается кодом (или явно мёртвый)."""
    rules = load_rules()
    pp = (SCRIPTS / "post_processor.py").read_text(encoding="utf-8")
    esc = (SCRIPTS / "escalation.py").read_text(encoding="utf-8")

    dead = []

    if '"supported"' not in pp and "thresholds" in rules:
        dead.append("thresholds.supported (в rules, не читается post_processor)")
    if '"ambiguous"' not in pp:
        dead.append("thresholds.ambiguous (в rules, не читается post_processor)")
    if rules.get("problematic_rules", {}).get("caveats_gte_2") is not None \
            and "caveats_gte_2" not in pp:
        dead.append("problematic_rules.caveats_gte_2 (в rules, не применяется кодом)")
    if "enabled" in rules.get("escalation_rules", {}) and "enabled" not in esc:
        dead.append("escalation_rules.enabled (в rules, не читается escalation.py)")
    cut_off = rules.get("escalation_rules", {}).get("cut_off", {})
    if cut_off.get("status") is not None and "cut_off" in esc \
            and "status" not in esc:
        dead.append("escalation_rules.cut_off.status (хардкод OPEN)")

    assert not dead, "мёртвая конфигурация: " + "; ".join(dead)


def test_c4_config_matches_code():
    """config.yaml (провайдер/модель/база) согласован с кодом LLM-скриптов."""
    cfg = Path(CONFIG_YAML).read_text(encoding="utf-8")
    # провайдер по config.yaml
    base = re.search(r"base_url:\s*(\S+)", cfg)
    assert base, "config.yaml: нет base_url"
    cfg_base = base.group(1).strip()
    for script in ("synthesizer.py", "stub_verifier.py"):
        src = (SCRIPTS / script).read_text(encoding="utf-8")
        hits = re.findall(r'base_url\s*=\s*"([^"]+)"', src)
        if hits:
            assert cfg_base in hits or any("aitunnel" in h for h in hits) == (
                "aitunnel" in cfg_base), \
                f"{script}: base_url {hits} не согласован с config.yaml {cfg_base}"


def test_c5_id_space_group_coverage():
    """Вердикты (claim_id) находят свой узел в дереве (original_index)."""
    artifacts = run_det_chain()
    rc, tt_path = artifacts["topics"]
    assert rc == 0 and tt_path.exists()
    tt = load_json(tt_path)
    verdicts = load_json(EXP1_VERDICTS)

    node_claims = set()

    def walk(n):
        node_claims.update(str(c) for c in n.get("claims", []))
        for c in n.get("children", []):
            walk(c)
    walk(tt["topics_tree"])

    matched = sum(1 for v in verdicts if str(v.get("claim_id")) in node_claims)
    assert matched == len(verdicts), \
        f"claim_id ↔ original_index расходятся: совпало {matched}/{len(verdicts)}"


def test_c6_pipeline_artifact_flow_static():
    """run_pipeline.sh: выход каждого этапа читается последующим."""
    step_inputs = {
        "topics_tree": "claim_groups.json",
        "pattern_generator": "topics_tree.json,claim_groups.json",
        "evidence_contract": "verdicts.json",
        "merge_numeric": "verdicts_with_evidence.json,numeric_result.json",
        "post_processor": "verdicts_with_numeric.json",
        "escalation": "verdicts_processed.json,topics_tree.json",
        "justification_check": "escalated.json",
        "judge_brief": "verdicts_with_evidence.json",
    }
    missing = []
    for script, inputs in step_inputs.items():
        for i in inputs.split(","):
            i = i.strip()
            producer = {v: k for k, v in {
                "claims.json": "extractor",
                "claim_groups.json": "extractor",
                "verdicts.json": "fact-checker",
                "verdicts_with_evidence.json": "evidence_contract",
                "numeric_result.json": "numeric_comparator",
                "verdicts_with_numeric.json": "merge_numeric",
                "verdicts_processed.json": "post_processor",
                "escalated.json": "escalation",
                "topics_tree.json": "topics_tree",
            }.items()}
            if script not in SH:
                missing.append(f"{script} не в run_pipeline.sh")
            if producer.get(i) and producer[i] not in SH:
                missing.append(f"{i} (продюсер {producer[i]}) не создаётся")
    assert not missing, "; ".join(missing)


# ═══════════════════════ 2. DEPENDENCIES ═══════════════════════

def test_d1_claim_groups_robustness():
    """Пустой/битый claim_groups.json не роняет topics_tree (fallback на claims.json)."""
    bad = WORK / "claim_groups_bad.json"
    bad.write_text("")
    rc, out = run_cli("topics_tree.py", [EXP1_INPUT, bad, WORK / "tt_bad.json"])
    assert rc == 0, f"пустой claim_groups.json → крах: {out[-300:]}"


def test_d2_topics_cache_md5():
    """Кэш topics_tree не выдаётся за свежий при другом md5 входа."""
    tt = WORK / "tt_cache.json"
    tt2 = WORK / "tt_cache2.json"
    for p in (tt, tt2, Path(str(tt) + ".cached.json"), Path(str(tt2) + ".cached.json")):
        p.unlink(missing_ok=True)
    rc1, _ = build_topics_tree(tt)
    result1 = load_json(tt)
    # меняем вход (другой текст) -> кэш не должен совпасть
    other_input = WORK / "input_other.txt"
    other_input.write_text("Совершенно другой текст о диффузии и нитридах.", encoding="utf-8")
    shutil.copy2(EXP1_CLAIMS, WORK / "claims.json")
    rc2, _ = run_cli("topics_tree.py", [other_input, WORK / "claim_groups.json", tt2])
    result2 = load_json(tt2)
    assert rc1 == 0 and rc2 == 0
    assert result2.get("cached_topology") is False, "кэш сработал на другой вход"


def test_d3_dead_code():
    """Нет неиспользуемых функций/импортов в детерминированных блоках."""
    esc = (SCRIPTS / "escalation.py").read_text(encoding="utf-8")
    # find_group_node и converges определены, но в main() не вызываются
    dead = []
    if "def find_group_node" in esc and "find_group_node(" not in esc.replace("def find_group_node(", ""):
        dead.append("escalation.find_group_node() не используется")
    if "def converges" in esc and "converges(" not in esc.replace("def converges(", ""):
        dead.append("escalation.converges() не используется")
    assert not dead, "; ".join(dead)


def test_d4_writer_paths_exist():
    """Все вызываемые run_pipeline.sh файлы существуют."""
    for name in ("patch_planner.py", "consistency_check.py", "reverify.py", "regression_suite.py"):
        assert (WRITER / name).exists(), f"writer/{name} отсутствует"
    assert (PROFILE / "context_vectors.yaml").exists(), "context_vectors.yaml отсутствует"
    assert (PROFILE / "skills" / "tribunal-judge" / "SKILL.md").exists(), "tribunal-judge SKILL.md отсутствует"


def test_d5_llm_stages_no_overwrite():
    """Каждый LLM-этап пишет свой уникальный артефакт (нет гонок)."""
    out_files = {
        "context-digestor": "compressed_contexts.json",
        "literature-searcher": "sources.json",
        "fact-checker": "verdicts.json",
        "tribunal-judge": "tribunal.json",
        "synthesizer-agent": "final_report.md",
    }
    seen = []
    for skill, f in out_files.items():
        if f in seen:
            raise AssertionError(f"дубль выхода {f} у {skill}")
        seen.append(f)


# ═══════════════════════ 3. ENCAPSULATION ═══════════════════════

def test_e1_verification_writer_boundary():
    """writer-домен не импортирует verification-домен и наоборот (по ast)."""
    verif_imports = set()
    for f in all_scripts():
        tree = ast.parse((SCRIPTS / f).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                verif_imports.add(n.module or "")
            elif isinstance(n, ast.Import):
                for a in n.names:
                    verif_imports.add(a.name.split(".")[0])
    verif_imports = {i for i in verif_imports if i}
    verif_domain_files = {f[:-3] for f in all_scripts()}

    for f in ("patch_planner.py", "consistency_check.py", "reverify.py", "regression_suite.py"):
        src = (WRITER / f).read_text(encoding="utf-8")
        for m in re.findall(r"^\s*(?:from|import)\s+([\w_.]+)", src, re.M):
            mod = m.split(".")[0]
            if mod in verif_domain_files:
                raise AssertionError(f"writer/{f} импортирует verification-модуль {mod}")


def test_e2_cli_standalone_no_traceback():
    """CLI без аргументов: usage/код ошибки, без traceback."""
    for script in all_scripts():
        if script in ("verdict_schemas.py", "claimeai_wrapper.py"):
            continue  # claimeai_wrapper требует langchain (вне venv) — pre-existing
        src = (SCRIPTS / script).read_text(encoding="utf-8")
        if "__main__" not in src:
            continue  # чистая библиотека (не CLI)
        rc, out = run_cli(script, [])
        assert "Traceback" not in out, f"{script} без аргументов даёт traceback"
        assert rc != 0, f"{script} без аргументов вернул 0"


def test_e3_internal_fields_not_broken():
    """Служебные _-поля одного блока не ломают другой."""
    artifacts = run_det_chain()
    rc, jb_path = artifacts["briefs"]
    assert rc == 0
    rc, pp_path = artifacts["processed"]
    assert rc == 0
    # judge_brief на пост-обработанных (с _-полями) не падает
    rc2, _ = run_cli("judge_brief.py", [pp_path, WORK / "jb_from_processed.json"])
    assert rc2 == 0, "judge_brief не переваривает _-поля post_processor"


# ═══════════════════════ 4. FAILURE HANDLING ═══════════════════════

def test_f1_broken_json_nonzero():
    """Битый JSON → ненулевой код, ошибка в stderr."""
    bad = WORK / "broken.json"
    bad.write_text("{ not json", encoding="utf-8")
    for script in ("synthesizer.py", "numeric_comparator.py", "evidence_contract.py",
                   "post_processor.py", "merge_numeric.py", "escalation.py",
                   "justification_check.py", "judge_brief.py"):
        if script == "numeric_comparator.py":
            args = [bad, WORK / "sources.json", WORK / "out.json"]
        elif script in ("evidence_contract.py", "post_processor.py"):
            args = [bad, RULES_YAML, WORK / "out.json"]
        elif script == "merge_numeric.py":
            args = [bad, WORK / "out.json", WORK / "out2.json"]
        elif script == "escalation.py":
            args = [bad, WORK / "tt.json", RULES_YAML, WORK / "out.json"]
        elif script == "justification_check.py":
            args = [bad, RULES_YAML, WORK / "out.json"]
        elif script == "judge_brief.py":
            args = [bad, WORK / "out.json"]
        else:
            args = [bad, WORK / "out.md"]
        rc, out = run_cli(script, args)
        assert rc != 0, f"{script} на битом JSON вернул rc=0"


def test_f2_missing_file_nonzero():
    """Отсутствующий файл → ненулевой код."""
    missing = WORK / "no_such.json"
    rc, _ = run_cli("synthesizer.py", [missing, WORK / "out.md"])
    assert rc != 0
    rc, _ = run_cli("numeric_comparator.py", [missing, WORK / "sources.json", WORK / "o.json"])
    assert rc != 0
    rc, _ = run_cli("evidence_contract.py", [missing, RULES_YAML, WORK / "o.json"])
    assert rc != 0
    rc, _ = run_cli("post_processor.py", [missing, RULES_YAML, WORK / "o.json"])
    assert rc != 0


def test_f3_empty_list_ok():
    """Пустой список → корректный пустой выход."""
    empty = WORK / "empty.json"
    write_json(empty, [])
    for script, args in (
        ("synthesizer.py", [empty, WORK / "r.md"]),
        ("numeric_comparator.py", [empty, empty, WORK / "o.json"]),
        ("evidence_contract.py", [empty, RULES_YAML, WORK / "o.json"]),
        ("post_processor.py", [empty, RULES_YAML, WORK / "o.json"]),
        ("merge_numeric.py", [empty, empty, WORK / "o.json"]),
        ("justification_check.py", [empty, RULES_YAML, WORK / "o.json"]),
        ("judge_brief.py", [empty, WORK / "o.json"]),
    ):
        rc, out = run_cli(script, args)
        assert rc == 0, f"{script} на пустом списке: rc={rc} {out[-200:]}"


def test_f4_weird_types_no_crash():
    """str confidence / str claim_id / caveats не-list не роняют post_processor."""
    bad = WORK / "strconf.json"
    write_json(bad, [{
        "claim_id": 1, "claim_text": "x", "verdict": "SUPPORTED",
        "confidence": "0.95", "sources": [{"title": "t", "type": "blog", "trust": 0.3}],
        "caveats": [{"severity": "critical", "text": "c"}],
    }])
    rc, out = run_cli("post_processor.py", [bad, RULES_YAML, WORK / "strconf_out.json"])
    assert rc == 0, f"post_processor падает на str confidence: {out[-300:]}"


def test_f5_missing_original_index_no_crash():
    """Плоские вердикты без original_index (формат exp1) не роняют escalation."""
    artifacts = run_det_chain()
    rc, pp_path = artifacts["processed"]
    assert rc == 0
    tt = WORK / "chain" / "topics_tree.json"
    rc, out = run_cli("escalation.py", [pp_path, tt, RULES_YAML, WORK / "esc_flat.json"])
    assert rc == 0, f"escalation падает без original_index: {out[-400:]}"


def test_f6_llm_unavailable_graceful():
    """synthesizer.py без ключа API → fallback-секция, не падение."""
    rc, out = run_cli("synthesizer.py", [EXP1_VERDICTS, WORK / "rep_nokey.md"])
    assert rc == 0
    rep = (WORK / "rep_nokey.md").read_text(encoding="utf-8")
    assert "LLM недоступен" in rep, "нет fallback-строки при недоступном LLM"


def test_f7_writer_cli_creates_artifact():
    """Writer-блок: вызов как в run_pipeline.sh создаёт артефакт."""
    d = WORK / "writer"
    d.mkdir(parents=True, exist_ok=True)
    verdicts = d / "verdicts.json"
    shutil.copy2(EXP1_VERDICTS, verdicts)
    tribunal = d / "tribunal.json"
    write_json(tribunal, {"groups": [{
        "original_index": 1, "claim_id": 1,
        "claim_text": "Nitriding of steels is a process of surface hardening.",
        "tribunal_verdict": "OPEN", "confidence": 0.5,
        "justification": "fallback", "questions_for_author": [],
    }]})

    plan = d / "patch_plan.sexpr"
    # именно так вызывает run_pipeline.sh (3 позиционных аргумента)
    rc, out = run_cli(WRITER / "patch_planner.py", [verdicts, tribunal, plan], cwd=WRITER)
    assert plan.exists(), f"patch_plan.sexpr не создан (rc={rc}): {out[-200:]}"

    # consistency_check / reverify / regression_suite: без CLI — демо вместо файла
    rc_c, _ = run_cli(WRITER / "consistency_check.py", [plan, d / "consistency_report.json"], cwd=WRITER)
    rc_r, _ = run_cli(WRITER / "reverify.py", [verdicts, plan, d / "reverify_result.json"], cwd=WRITER)
    rc_g, _ = run_cli(WRITER / "regression_suite.py", [d / "reverify_result.json", d / "regression_result.json"], cwd=WRITER)
    assert rc_c == 0 and rc_r == 0 and rc_g == 0
    assert (d / "consistency_report.json").exists(), "consistency_report.json не создан"
    assert (d / "reverify_result.json").exists(), "reverify_result.json не создан"
    assert (d / "regression_result.json").exists(), "regression_result.json не создан"


# ═══════════════════════ 5. NEGATIVE ═══════════════════════

def test_n1_chemical_formula_not_numeric():
    """Химическая формула Fe2-3N не должна трактоваться как диапазон 2-3."""
    from numeric_comparator import extract_numbers
    nums = extract_numbers("Образование ε-фазы (Fe2-3N) происходит на поверхности")
    ranges = [n for n in nums if n["type"] == "range"]
    assert ranges == [], f"Fe2-3N распознан как диапазон: {ranges}"


def test_n2_same_unit_convert():
    """0.6 мм vs 0.6 mm (одна и та же единица) → match, не dimension_mismatch."""
    from numeric_comparator import compare_claim_sources
    res = compare_claim_sources(
        {"claim_id": 1, "claim_text": "Глубина слоя 0.6 мм"},
        [{"title": "s", "text": "Глубина слоя 0.6 mm"}])
    assert res["status"] != "dimension_mismatch", \
        f"мм/mm (одинаковые единицы) → {res['status']}"


def test_n3_no_number_claim_not_demoted():
    """Definition-claim без чисел не должен получать no_data → cap 0.7 → AMBIGUOUS."""
    import yaml
    from merge_numeric import merge_numeric_into_verdict
    from post_processor import post_process_verdict

    with open(RULES_YAML, encoding="utf-8") as f:
        rules = yaml.safe_load(f)

    verdict = {"claim_id": 1, "claim_text": "Nitriding of steels is a process of surface hardening.",
               "verdict": "SUPPORTED", "confidence": 0.95, "sources": [], "caveats": []}
    numeric_entry = {"status": "no_data", "details": "no numbers in claim", "n_sources": 0}
    merge_numeric_into_verdict(verdict, numeric_entry)
    post_process_verdict(verdict, rules)
    assert verdict["verdict"] == "SUPPORTED", \
        f"claim без чисел понижен: {verdict.get('_changes')}"


def test_n4_scale_0_1_1000():
    """0/1/1000 claims не роняют numeric_comparator и post_processor."""
    from numeric_comparator import _normalize_groups
    import yaml
    from post_processor import post_process_verdict
    with open(RULES_YAML, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    for n in (0, 1, 1000):
        verdicts = [{"claim_id": i, "claim_text": f"Твёрдость {i} HV", "verdict": "SUPPORTED",
                     "confidence": 0.9, "sources": [], "caveats": []} for i in range(n)]
        groups = _normalize_groups(verdicts)
        assert len(groups) == n
        for v in verdicts[:50]:
            post_process_verdict(dict(v), rules)  # не падает


def test_n5_trust_bounds():
    """trust из правил/мапы в [0,1]; не наследует >1 от источника."""
    ev_path = WORK / "trust5_ev.json"
    write_json(WORK / "trust5.json", [{
        "claim_id": 1, "claim_text": "x",
        "sources": [{"title": "t", "type": "unknown_type", "trust": 5.0}],
    }])
    rc, _ = run_cli("evidence_contract.py", [WORK / "trust5.json", RULES_YAML, ev_path])
    assert rc == 0
    trust = load_json(ev_path)[0]["evidence"][0]["trust"]
    assert 0.0 <= trust <= 1.0, f"trust вне [0,1]: {trust}"


def test_n6_no_tribunal_for_confident_clean():
    """SUPPORTED confidence 0.9 без caveats не триггерит tribunal (skip_when)."""
    import yaml
    from post_processor import post_process_verdict
    with open(RULES_YAML, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    v = {"claim_id": 1, "claim_text": "x", "verdict": "SUPPORTED", "confidence": 0.9,
         "sources": [], "caveats": []}
    post_process_verdict(v, rules)
    assert not v.get("trigger_tribunal"), "чистый уверенный вердикт триггерит трибунал"


def test_n7_missing_justification_to_open():
    """Вердикт без justification/reason/evidence → OPEN."""
    import yaml
    from justification_check import check_verdicts
    with open(RULES_YAML, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    verdicts = [{"claim_id": 1, "claim_text": "x", "verdict": "SUPPORTED", "confidence": 0.9}]
    summary = check_verdicts(verdicts, rules)
    assert verdicts[0]["verdict"] == "OPEN", "без обоснования не стал OPEN"


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-v", "-x"]))
