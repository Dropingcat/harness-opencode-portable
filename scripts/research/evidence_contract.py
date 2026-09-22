#!/usr/bin/env python3
"""evidence_contract.py — нормализация sources → evidence[] (Evidence Contract, У2).

Каждый источник из claim["sources"] превращается в evidence-запись
{source_id, span, trust, type}, чтобы provenance проверялся механически:
source_id — стабильный slug от title, span — фрагмент excerpt (≤ 500 симв.),
trust — доверие из rules.yaml → TYPE_TO_TRUST_MAP → trust в источнике → 0.5.

Usage:
    python3 evidence_contract.py <verdicts.json> <rules.yaml> <evidence_out.json>
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import re
import yaml
from pathlib import Path


TYPE_TO_TRUST_MAP = {
    "primary": 0.9,
    "textbook": 0.9,
    "review": 0.75,
    "educational": 0.7,
    "wikipedia": 0.6,
    "encyclopedia": 0.6,
    "researchgate": 0.6,
    "blog": 0.3,
    "local_md": 0.75,
    "journal_article": 0.75,
}

SPAN_MAX_LEN = 500
DEFAULT_TRUST = 0.5


def _slugify(title):
    """Стабильный source_id: lowercase, non-alnum → "_", коллапс, trim "_"."""
    if not title:
        return ""
    if not isinstance(title, str):
        title = str(title)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.lower()).strip("_")
    return slug


def _numeric_source_trust(source_trust_rules):
    """Оставляет только числовые type → trust из rules.yaml (отбрасывает action-ы)."""
    if not source_trust_rules:
        return {}
    return {k: v for k, v in source_trust_rules.items() if isinstance(v, (int, float))}


def load_rules(rules_path):
    with open(rules_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_verdicts(verdicts_path):
    with open(verdicts_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("verdicts", [data])


def build_evidence(claim, source_trust_rules=None):
    """Возвращает {"claim_id", "evidence": [{source_id, span, trust, type}], "status": "ok"}."""
    source_trust_rules = _numeric_source_trust(source_trust_rules)
    sources = claim.get("sources", [])
    evidence = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        src_type = source.get("type", "")
        trust = source_trust_rules.get(src_type)
        if trust is None:
            trust = TYPE_TO_TRUST_MAP.get(src_type)
        if trust is None:
            trust = source.get("trust", source.get("reliability", DEFAULT_TRUST))
        if not isinstance(trust, (int, float)):
            trust = DEFAULT_TRUST
        trust = max(0.0, min(1.0, float(trust)))
        excerpt = source.get("excerpt", "")
        if not isinstance(excerpt, str):
            excerpt = ""
        evidence.append({
            "source_id": _slugify(source.get("title", "")),
            "span": excerpt[:SPAN_MAX_LEN],
            "trust": trust,
            "type": src_type,
            **{k: v for k, v in (
                ("found_via", source.get("found_via")),
                ("origin", source.get("origin")),
                ("doi", source.get("doi")),
                ("url", source.get("url")),
                ("year", source.get("year")),
            ) if v not in (None, "")},
        })
    return {
        "claim_id": claim.get("claim_id"),
        "evidence": evidence,
        "status": "ok",
    }


def build_all_evidence(verdicts, source_trust_rules=None):
    """Добавляет поле evidence к каждой записи verdict."""
    result = []
    for verdict in verdicts:
        ev = build_evidence(verdict, source_trust_rules)
        verdict["evidence"] = ev["evidence"]
        result.append(verdict)
    return result


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 evidence_contract.py <verdicts.json> <rules.yaml> <evidence_out.json>",
              file=sys.stderr)
        sys.exit(1)
    verdicts_path, rules_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]
    verdicts = load_verdicts(verdicts_path)
    rules = load_rules(rules_path)
    source_trust_rules = _numeric_source_trust(rules.get("source_trust", {}))
    out = build_all_evidence(verdicts, source_trust_rules)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with_evidence = sum(1 for v in out if v.get("evidence"))
    print(f"✅ Evidence contract: {len(out)} verdicts, {with_evidence} with evidence → {output_path}")


if __name__ == "__main__":
    main()
