"""Тесты Judge Brief (У1): judge_brief.py — информационная асимметрия судей трибунала."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from judge_brief import (
    JUDGE_ROLES,
    ROLE_LABEL_MAP,
    CONTEXT_MAX_LEN,
    _load_roles,
    build_all_briefs,
    build_judge_briefs,
    load_verdicts,
)

EXP1_PATH = str(Path(__file__).resolve().parent / "testdata" / "exp1_verdicts_processed.json")
SCRIPTS = Path(__file__).resolve().parent
PROFILE = Path(__file__).resolve().parent
EXP1 = Path(__file__).resolve().parent / "testdata" / "exp1"
RULES_YAML = Path(__file__).resolve().parent / "testdata" / "rules.yaml"
WORK = Path(os.environ.get("TEMP", "/tmp")) / "arch-test"
WORK.mkdir(parents=True, exist_ok=True)


def _run_cli(script, args):
    cmd = [sys.executable, str(SCRIPTS / script)] + [str(a) for a in args]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(cmd, cwd=str(SCRIPTS), capture_output=True, text=True, timeout=180, env=env)
    return proc.returncode, proc.stdout + proc.stderr


def _load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def golden_claim():
    return {
        "claim_id": 1,
        "claim_text": "Nitriding of steels is a process of surface hardening.",
        "verdict": "SUPPORTED",
        "confidence": 0.95,
        "sources": [
            {"title": "Steels Handbook", "type": "textbook", "trust": 0.9,
             "excerpt": "textbook excerpt"},
            {"title": "Wikipedia — Nitriding", "type": "encyclopedia", "trust": 0.6,
             "excerpt": "Nitriding is a heat treating process that diffuses nitrogen."},
            {"title": "Journal of Materials", "type": "journal_article", "trust": 0.8,
             "excerpt": "Gas nitriding is a surface hardening process."},
            {"title": "XRD Analysis of Nitriding", "type": "journal_article", "trust": 0.7,
             "excerpt": "in situ XRD of ε-Fe2-3N formation measured by the method of microscopy."},
        ],
        "caveats": [],
        "reason": "Confirmed.",
        "numeric_comparison": {},
    }


def briefs_by_role(briefs):
    return {b["judge_id"]: b for b in briefs}


def test_five_briefs_one_per_role():
    briefs = build_judge_briefs(golden_claim())
    assert len(briefs) == 5
    assert {b["judge_id"] for b in briefs} == set(JUDGE_ROLES)


def test_skeptic_no_verdict():
    briefs = build_judge_briefs(golden_claim())
    sk = briefs_by_role(briefs)["скептик"]
    assert sk["include_verdict"] is False
    assert sk["vector"] == "critical"


def test_others_include_verdict():
    briefs = build_judge_briefs(golden_claim())
    for judge in ("физик", "методолог", "адвокат", "агрегатор"):
        assert briefs_by_role(briefs)[judge]["include_verdict"] is True


def test_advocate_single_strongest():
    claim = golden_claim()
    briefs = build_judge_briefs(claim)
    adv = briefs_by_role(briefs)["адвокат"]
    assert len(adv["sources"]) == 1
    max_trust = max(s["trust"] for s in claim["sources"])
    assert adv["sources"][0]["trust"] == max_trust
    assert adv["vector"] == "defensive"


def test_aggregator_all_sources():
    briefs = build_judge_briefs(golden_claim())
    agg = briefs_by_role(briefs)["агрегатор"]
    assert len(agg["sources"]) == len(golden_claim()["sources"])
    assert agg["vector"] == ""


def test_physicist_filters_by_type():
    briefs = build_judge_briefs(golden_claim())
    ph = briefs_by_role(briefs)["физик"]
    assert {s["type"] for s in ph["sources"]} == {"textbook", "journal_article"}
    assert ph["vector"] == "physical"


def test_methodologist_markers():
    briefs = build_judge_briefs(golden_claim())
    met = briefs_by_role(briefs)["методолог"]
    assert len(met["sources"]) == 1
    assert "xrd" in met["sources"][0]["span"].lower()
    assert met["vector"] == "structural"


def test_methodologist_fallback_top3():
    claim = golden_claim()
    for s in claim["sources"]:
        s["excerpt"] = "plain excerpt without markers"
        s["title"] = "Plain Source"
    briefs = build_judge_briefs(claim)
    met = briefs_by_role(briefs)["методолог"]
    assert len(met["sources"]) == 3
    assert len(met["sources"]) > 0
    assert met["sources"] == sorted(met["sources"], key=lambda r: r["trust"], reverse=True)


def test_context_truncated_to_200():
    long_text = "Заявление: нитрирование — процесс упрочнения поверхности. " * 20
    claim = golden_claim()
    claim["claim_text"] = long_text
    for brief in build_judge_briefs(claim):
        assert brief["context"] == long_text[:CONTEXT_MAX_LEN]
        assert len(brief["context"]) <= CONTEXT_MAX_LEN


def test_evidence_precedence_over_sources():
    claim = golden_claim()
    claim["evidence"] = [
        {"source_id": "ev_primary", "span": "s1", "trust": 0.42, "type": "primary"},
        {"source_id": "ev_secondary", "span": "s2", "trust": 0.31, "type": "primary"},
    ]
    briefs = build_judge_briefs(claim)
    for brief in briefs:
        for source in brief["sources"]:
            assert set(source.keys()) == {"source_id", "span", "trust", "type"}
            assert source["source_id"].startswith("ev_")
    agg = briefs_by_role(briefs)["агрегатор"]
    assert len(agg["sources"]) == 2
    adv = briefs_by_role(briefs)["адвокат"]
    assert adv["sources"][0]["trust"] == 0.42


def test_all_briefs():
    verdicts = [
        golden_claim(),
        {
            "claim_id": 2,
            "claim_text": "Second claim",
            "sources": [
                {"title": "Handbook", "type": "textbook", "trust": 0.9, "excerpt": "e"},
                {"title": "Wikipedia", "type": "encyclopedia", "trust": 0.6, "excerpt": "e2"},
            ],
        },
    ]
    out = build_all_briefs(verdicts)
    assert set(out.keys()) == {1, 2}
    assert out[1]["claim_text"] == verdicts[0]["claim_text"]
    assert len(out[1]["briefs"]) == 5
    assert len(out[2]["briefs"]) == 5
    assert {b["judge_id"] for b in out[2]["briefs"]} == set(JUDGE_ROLES)


def test_exp1_real_data():
    verdicts = load_verdicts(EXP1_PATH)
    assert len(verdicts) == 20
    out = build_all_briefs(verdicts)
    assert len(out) == 20
    for claim_id, item in out.items():
        assert len(item["briefs"]) == 5
        assert {b["judge_id"] for b in item["briefs"]} == set(JUDGE_ROLES)
        skeptic = [b for b in item["briefs"] if b["judge_id"] == "скептик"][0]
        assert skeptic["include_verdict"] is False
        assert all(len(b["sources"]) >= 0 for b in item["briefs"])


def test_registry_roles_all_mapped():
    """Все роли expert_registry.yaml (вкл. aggregator) покрыты ROLE_LABEL_MAP."""
    registry_roles = {r["id"] for r in _load_roles()}
    assert "aggregator" in registry_roles, "aggregator отсутствует в expert_registry.yaml"
    unmapped = registry_roles - set(ROLE_LABEL_MAP)
    assert not unmapped, f"роли без label в ROLE_LABEL_MAP: {sorted(unmapped)}"
    assert set(ROLE_LABEL_MAP) >= registry_roles
    assert len(ROLE_LABEL_MAP) == len(set(ROLE_LABEL_MAP.values())), "дубликат label в маппинге"


def test_profile_role_brief_added():
    """Профильная роль узла (из patterns.json) получает свой бриф."""
    claim = golden_claim()
    briefs = build_judge_briefs(claim, node_roles=["metallurgist", "skeptic"])
    roles = {b["judge_id"] for b in briefs}
    assert "металлург" in roles
    met = [b for b in briefs if b["judge_id"] == "металлург"][0]
    assert met["vector"] == "metallurgist"
    assert met["include_verdict"] is True
    # базовые роли не дублируются
    assert sum(1 for b in briefs if b["judge_id"] == "скептик") == 1


def test_roles_patterns_subset_judge_briefs():
    """Контракт C3: roles(patterns[узел]) ⊆ roles(judge_briefs[claim]) для групп узла.

    Прогоняет pattern_generator → judge_brief на exp1 и проверяет, что каждый
    судья, назначенный паттерном узла, получил бриф (в англ. id через
    ROLE_LABEL_MAP).
    """
    d = WORK / "c3_contract"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EXP1 / "claims.json", WORK / "claims.json")

    claim_groups = WORK / "claim_groups.json"
    topics = d / "topics_tree.json"
    rc, out = _run_cli("topics_tree.py", [EXP1 / "input.txt", claim_groups, topics])
    assert rc == 0, f"topics_tree.py: {out[-300:]}"

    patterns = d / "patterns.json"
    rc, out = _run_cli("pattern_generator.py", [topics, claim_groups, patterns])
    assert rc == 0, f"pattern_generator.py: {out[-300:]}"

    evidence = d / "verdicts_with_evidence.json"
    rc, out = _run_cli("evidence_contract.py", [EXP1 / "verdicts.json", RULES_YAML, evidence])
    assert rc == 0, f"evidence_contract.py: {out[-300:]}"

    briefs_out = d / "judge_briefs.json"
    rc, out = _run_cli("judge_brief.py", [evidence, briefs_out, patterns, topics])
    assert rc == 0, f"judge_brief.py: {out[-300:]}"

    patterns_data = _load_json(patterns)
    topics_data = _load_json(topics)
    briefs_data = _load_json(briefs_out)["briefs"]
    label2id = {v: k for k, v in ROLE_LABEL_MAP.items()}

    def walk(node):
        nid = node.get("id")
        node_roles = {j["role"] for j in patterns_data.get("patterns", {}).get(nid, {}).get("judges", [])}
        for c in node.get("claims", []):
            cid = str(c)
            if cid not in briefs_data:
                continue
            claim_roles = {label2id.get(b["judge_id"], b["judge_id"]) for b in briefs_data[cid]["briefs"]}
            missing = node_roles - claim_roles
            assert not missing, f"узел {nid}, claim {cid}: роли без брифа {sorted(missing)}"
        for child in node.get("children", []):
            walk(child)

    walk(topics_data["topics_tree"])


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))