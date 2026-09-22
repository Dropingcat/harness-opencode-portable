#!/usr/bin/env python3
"""judge_brief.py — детерминированная разбивка источников для судей трибунала (У1).

Разводит информационную позицию судей: каждый получает своё подмножество
источников и свой флаг наличия предварительного вердикта (include_verdict),
чтобы устранить корреляцию от общего бага данных. Без единого LLM-вызова.

Роли берутся из expert_registry.yaml (как pattern_generator.py): базовые роли
(физик/методолог/скептик/адвокат/агрегатор) — всегда; профильные роли,
назначенные узлу паттерном (patterns.json: metallurgist/chemist/…), — по факту
назначения. Маппинг англ. id ↔ рус. label — в одном месте (ROLE_LABEL_MAP).

Usage:
    python3 judge_brief.py <verdicts.json> <judge_briefs_out.json> \
        [patterns.json] [topics_tree.json]
"""
import json
import re
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path


ROLE_LABEL_MAP = {
    "physicist": "физик",
    "metallurgist": "металлург",
    "chemist": "химик",
    "mathematician": "математик",
    "methodologist": "методолог",
    "statistician": "статистик",
    "bibliographer": "библиограф",
    "skeptic": "скептик",
    "advocate": "адвокат",
    "aggregator": "агрегатор",
}

# Базовые роли: получают бриф всегда (их набор источников выводится по типу/
# маркерам источника). Профильные роли из patterns.json добавляются сверху.
BASE_ROLE_IDS = ("physicist", "methodologist", "skeptic", "advocate", "aggregator")
JUDGE_ROLES = [ROLE_LABEL_MAP[rid] for rid in BASE_ROLE_IDS]

PHYSICIST_TYPES = {"primary", "textbook", "review", "journal_article", "journal"}

METHOD_MARKERS = (
    "метод", "погрешн", "измерен", "выборк",
    "xrd", "рентген", "микротвёрд", "микротверд",
)

FALLBACK_TOP_N = 3
CONTEXT_MAX_LEN = 200
DEFAULT_TRUST = 0.5


def _slugify(title):
    """Стабильный source_id: lowercase, non-alnum → "_", коллапс, trim "_"."""
    if not title:
        return ""
    if not isinstance(title, str):
        title = str(title)
    return re.sub(r"[^a-zA-Z0-9]+", "_", title.lower()).strip("_")


def _normalize_source(source):
    """sources[] / evidence[] элемент → {source_id, span, trust, type}."""
    if not isinstance(source, dict):
        return None
    if "source_id" in source:
        return {
            "source_id": source.get("source_id", ""),
            "span": source.get("span", "") or "",
            "trust": source.get("trust", DEFAULT_TRUST),
            "type": source.get("type", ""),
        }
    excerpt = source.get("excerpt", "")
    if not isinstance(excerpt, str):
        excerpt = ""
    return {
        "source_id": _slugify(source.get("title", "")),
        "span": excerpt,
        "trust": source.get("trust", source.get("reliability", DEFAULT_TRUST)),
        "type": source.get("type", ""),
    }


def _load_sources(claim):
    """evidence[] если есть, иначе sources[]. Нормализует к 4-ключевым записям."""
    raw = claim.get("evidence") or claim.get("sources", [])
    records = []
    for item in raw:
        norm = _normalize_source(item)
        if norm:
            records.append(norm)
    return records


def _is_method_source(record):
    haystack = "{} {}".format(record.get("span", ""), record.get("source_id", "")).lower()
    return any(marker in haystack for marker in METHOD_MARKERS)


def _physicist_sources(records):
    return [r for r in records if r["type"] in PHYSICIST_TYPES]


def _methodologist_sources(records):
    return [r for r in records if _is_method_source(r)]


def _advocate_sources(records):
    if not records:
        return []
    return [max(records, key=lambda r: r["trust"])]


def _top_n(records, n=FALLBACK_TOP_N):
    return sorted(records, key=lambda r: r["trust"], reverse=True)[:n]


def _short_context(claim):
    claim_text = claim.get("claim_text", "")
    if not isinstance(claim_text, str):
        claim_text = ""
    return claim_text[:CONTEXT_MAX_LEN]


def _load_roles():
    import yaml

    p = Path(__file__).resolve().parent / "expert_registry.yaml"
    data = yaml.safe_load(open(p, encoding="utf-8"))
    return data["roles"]


def _load_roles_dict():
    return {r["id"]: r for r in _load_roles()}


def _role_sources(records, markers):
    """Источники, чей span/source_id задевает хотя бы один marker роли."""
    if not markers:
        return []
    hits = []
    for record in records:
        haystack = "{} {}".format(record.get("span", ""), record.get("source_id", "")).lower()
        if any(m.lower() in haystack for m in markers):
            hits.append(record)
    return hits


def _claim_to_nodes_map(topics_tree):
    """claim_id (original_index) → [node_id, ...] из topics_tree.json."""
    mapping = {}

    def walk(node):
        for c in node.get("claims", []):
            mapping.setdefault(str(c), []).append(node.get("id"))
        for child in node.get("children", []):
            walk(child)

    if isinstance(topics_tree, dict):
        walk(topics_tree.get("topics_tree", topics_tree))
    return mapping


def _node_roles(patterns, topics_tree, claim_id):
    """Англ. role id, назначенные узлам, к которым привязан claim (из patterns.json).

    Паттерн построен на общем наборе ролей: если claim привязан к нескольким
    узлам — берём объединение ролей их паттернов.
    """
    if not patterns:
        return []
    pattern_map = patterns.get("patterns", patterns) if isinstance(patterns, dict) else {}
    node_ids = _claim_to_nodes_map(topics_tree).get(str(claim_id), [])
    roles = []
    for nid in node_ids:
        pat = pattern_map.get(nid, {})
        for judge in pat.get("judges", []):
            role = judge.get("role")
            if role and role not in roles:
                roles.append(role)
    return roles


def build_judge_briefs(claim, node_roles=None):
    """Брифы судей с асимметрией информации.

    Базовые роли (физик/методолог/скептик/адвокат/агрегатор) — всегда.
    Если даны node_roles (англ. id ролей узла из patterns.json) — добавляются
    брифы для профильных ролей узла (металлург/химик/математик/статистик/
    библиограф), не входящих в базовый набор.

    Fallback: если у роли пустой набор источников → top-3 по trust из полного
    списка (кроме скептика, который всегда видит все источники сырыми).
    """
    full = _load_sources(claim)

    def resolve(role_sources):
        return role_sources if role_sources else _top_n(full)

    roles = [
        ("физик", "physical", resolve(_physicist_sources(full)), True),
        ("методолог", "structural", resolve(_methodologist_sources(full)), True),
        ("скептик", "critical", list(full), False),
        ("адвокат", "defensive", resolve(_advocate_sources(full)), True),
        ("агрегатор", "", list(full), True),
    ]

    if node_roles:
        roles_dict = _load_roles_dict()
        for rid in node_roles:
            if rid in BASE_ROLE_IDS:
                continue
            label = ROLE_LABEL_MAP.get(rid, rid)
            markers = roles_dict.get(rid, {}).get("markers", [])
            roles.append((label, rid, resolve(_role_sources(full, markers)), True))

    context = _short_context(claim)
    briefs = []
    for judge_id, vector, sources, include_verdict in roles:
        briefs.append({
            "judge_id": judge_id,
            "vector": vector,
            "sources": list(sources),
            "include_verdict": include_verdict,
            "context": context,
        })
    return briefs


def build_all_briefs(verdicts, patterns=None, topics_tree=None):
    """{claim_id: {claim_text, briefs: [...]}} для каждой записи.

    patterns/topics_tree (из pattern_generator.json / topics_tree.json) —
    опционально: по ним определяются профильные роли узла, назначенные
    паттерном, чтобы каждый назначенный судья получил бриф.
    """
    result = {}
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            continue
        claim_id = verdict.get("claim_id")
        node_roles = _node_roles(patterns, topics_tree, claim_id) if patterns else None
        result[claim_id] = {
            "claim_text": verdict.get("claim_text", ""),
            "briefs": build_judge_briefs(verdict, node_roles),
        }
    return result


def load_verdicts(verdicts_path):
    with open(verdicts_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("verdicts", [data])
    return []


def main():
    if len(sys.argv) not in (3, 4, 5):
        print("Usage: python3 judge_brief.py <verdicts.json> <judge_briefs_out.json>"
              " [patterns.json] [topics_tree.json]", file=sys.stderr)
        sys.exit(1)
    verdicts_path, output_path = sys.argv[1], sys.argv[2]
    patterns = None
    topics_tree = None
    if len(sys.argv) >= 4 and sys.argv[3]:
        patterns = json.load(open(sys.argv[3], encoding="utf-8"))
    if len(sys.argv) >= 5 and sys.argv[4]:
        topics_tree = json.load(open(sys.argv[4], encoding="utf-8"))
    verdicts = load_verdicts(verdicts_path)
    briefs = build_all_briefs(verdicts, patterns, topics_tree)
    out = {"total_claims": len(briefs), "briefs": briefs}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ Judge briefs: {len(briefs)} claims → {output_path}")


if __name__ == "__main__":
    main()