#!/usr/bin/env python3
"""pattern_generator.py — Волна 2, слой 0.6.

Генерирует паттерны судей из дерева направлений (topics_tree.json) и
групп claims (claim_groups.json).

Паттерн_узла = роль + аннотированный путь + специфика узла
(kw, evidence, questions) — короткие связные фразы, НЕ конкатенация.

Выбор судей: оверлеп keywords узла ↔ markers роли;
роль без >=1 маркера — не назначается (кроме skeptic/advocate: всем).

Usage: python3 pattern_generator.py <topics_tree.json> <claim_groups.json> <patterns.json>
"""
import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path


def _norm(s: str) -> str:
    return s.strip().lower()


def walk(node, out):
    out[node["id"]] = node
    for c in node.get("children", []):
        walk(c, out)


def label_ru(cid):
    """Аннотированный путь — короткие фразы по пути к корню."""
    return {
        "root": "диссертация",
        "processing": "обработка (термическая/химико-термическая/лазерная)",
        "laser": "лазерная обработка и оплавление",
        "nitriding": "азотирование (нитридные слои)",
        "alloys": "сплавы и стали",
        "08x18n10t": "сталь 08Х18Н10Т",
        "r18_steel": "быстрорежущая сталь Р18",
        "vks10_alloy": "ВКС-10 (литейный жаропрочный сплав)",
        "pure_iron": "чистое железо",
        "methods": "методы анализа (XRD, Ритвельд, регуляризация)",
        "xrd": "рентгенофазовый анализ (XRD)",
        "deconvolution": "деконволюция профилей",
        "rietveld": "метод Ритвельда (уточнение структуры)",
        "structure": "структура и фазовые превращения",
        "phase_transformations": "фазовые превращения при обработке",
        "nitride_phase": "нитридная фаза (концентрация, стехиометрия)",
        "carbide_phase": "карбидная фаза (состав, содержание)",
        "css": "компактное кристаллографическое описание",
        "lattice_param": "параметр кристаллической решётки",
        "general": "общие положения и методология диссертации",
    }.get(cid, cid)


def _questions_for(cid):
    q = {
        "nitriding": "Подтверждена ли связь режима азотирования с фазовым составом слоя?",
        "nitride_phase": "Корректны ли значения концентрации азота в нитридной фазе?",
        "carbide_phase": "Корректно ли определено содержание карбидной фазы?",
        "lattice_param": "Согласуется ли параметр решётки с данными справочников?",
        "rietveld": "Корректно ли выполнено уточнение Ритвельда (R-факторы, полнота)?",
        "deconvolution": "Обоснованно ли разделение перекрывающихся пиков?",
        "xrd": "Корректна ли интерпретация рентгенограмм (пики, фазы)?",
        "08x18n10t": "Корректны ли данные по стали 08Х18Н10Т?",
        "r18_steel": "Корректны ли данные по стали Р18?",
        "vks10_alloy": "Корректны ли данные по сплаву ВКС-10?",
    }
    return q.get(cid, "Каковы источники и полнота доказательств?")


def build_patterns(topics_tree, groups):
    """Возвращает (patterns, summary)."""
    from collections import Counter

    nodes = {}
    walk(topics_tree["topics_tree"], nodes)

    roles = _load_roles()
    marker2role = {}
    for r in roles:
        for m in r.get("markers", []):
            marker2role[_norm(m)] = r["id"]

    # фразы специфики: свежая подборка, не конкатенация
    spec_phrases = {
        "nitriding": "источники по азотированию и нитридным слоям",
        "nitride_phase": "фазовый состав и стехиометрия нитридов",
        "carbide_phase": "состав и дисперсность карбидов",
        "lattice_param": "значения параметров решётки и точность",
        "rietveld": "протокол уточнения структуры и критерии сходимости",
        "deconvolution": "процедура разделения пиков и погрешности",
        "xrd": "рентгенограммы, пики, идентификация фаз",
        "08x18n10t": "экспериментальные данные по 08Х18Н10Т",
        "r18_steel": "экспериментальные данные по Р18",
        "vks10_alloy": "экспериментальные данные по ВКС-10",
        "laser": "лазерное воздействие и оплавление поверхности",
        "css": "кристаллографическое описание и метрика решётки",
    }

    patterns = {}
    stats = Counter()
    per_role = Counter()

    # keywords предков для каждого узла (наследование ветки)
    inherited = {}
    for cid, node in nodes.items():
        kws = []
        cur = node
        seen = set()
        while cur is not None:
            for k in cur.get("keywords", []):
                if k not in seen:
                    seen.add(k)
                    kws.append(k)
            par = cur.get("parent")
            cur = nodes.get(par) if par else None
        inherited[cid] = kws

    for cid, node in sorted(nodes.items()):
        if cid == "root":
            continue
        node_kw = [k for k in node.get("keywords", [])]
        own_text = _norm(" ".join(node_kw))
        full_text = _norm(" ".join(inherited[cid]))

        # профильные роли: сначала по своим keywords, добираем по предкам
        assigned = []
        for r in roles:
            if r["id"] in ("skeptic", "advocate"):
                continue
            own_hits = [m for m in r.get("markers", []) if _norm(m) in own_text]
            if own_hits:
                assigned.append({"role": r["id"], "matched": own_hits})
                per_role[r["id"]] += 1
        if len(assigned) < 2:
            for r in roles:
                if r["id"] in ("skeptic", "advocate"):
                    continue
                if any(j["role"] == r["id"] for j in assigned):
                    continue
                inh_hits = [m for m in r.get("markers", []) if _norm(m) in full_text]
                if inh_hits:
                    assigned.append({"role": r["id"], "matched": inh_hits})
                    per_role[r["id"]] += 1
                if len(assigned) >= 2:
                    break

        # skeptical/advocate — пара для каждого узла
        assigned.append({"role": "skeptic", "matched": []})
        assigned.append({"role": "advocate", "matched": []})

        # фолбэк для general: методология диссертации = методолог + библиограф
        if cid == "general":
            wanted = ["methodologist", "bibliographer"]
            for w in wanted:
                if not any(j["role"] == w for j in assigned):
                    assigned.insert(0, {"role": w, "matched": []})

        path = _path_phrases(node, nodes, label_ru)
        patterns[cid] = {
            "id": cid,
            "label": label_ru(cid),
            "path": path,  # аннотированный путь фразами
            "keywords": node_kw,
            "judges": assigned,
            "focus_phrase": spec_phrases.get(cid, ""),
            "evidence_notes": f"групп привязано: {len(node.get('claims', []))}",
            "question": _questions_for(cid),
        }
        if len(node.get("claims", [])) >= 1:
            stats["nodes_with_claims"] += 1
        stats["nodes_total"] += 1

    return patterns, dict(stats), dict(per_role)


def _path_phrases(node, nodes, label_ru):
    """Аннотированный путь от корня к узлу — фразы, не конкатенация."""
    seq = []
    cur = node
    while cur is not None:
        seq.append(label_ru(cur["id"]))
        par = cur.get("parent")
        cur = nodes.get(par) if par else None
    seq.reverse()
    return seq


def _load_roles():
    import yaml

    p = Path(__file__).resolve().parent / "expert_registry.yaml"
    data = yaml.safe_load(open(p, encoding="utf-8"))
    return data["roles"]


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 pattern_generator.py <topics_tree.json> <claim_groups.json> <patterns.json>",
              file=sys.stderr)
        sys.exit(1)
    tt_path, groups_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    topics_tree = json.load(open(tt_path, encoding="utf-8"))
    groups = _load_groups(groups_path)
    patterns, stats, per_role = build_patterns(topics_tree, groups)

    out = {
        "method": "role_overlay",
        "patterns": patterns,
        "n_patterns": len(patterns),
        "stats": stats,
        "judges_per_role": per_role,
        "roles": list(_load_roles_dict().keys()),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    total_groups = sum(len(node.get("claims", [])) for node in
                       _all_nodes(topics_tree["topics_tree"]))
    print(f"✅ patterns: {len(patterns)} узлов, групп: {total_groups}")
    print(f"   узлы с claims: {stats['nodes_with_claims']}/{stats['nodes_total']}")
    print(f"   распределение ролей: {per_role}")


def _load_groups(groups_path):
    """Загрузка групп или генерация из claims.json (фолбэк, как в topics_tree)."""
    if Path(groups_path).is_file():
        data = json.load(open(groups_path, encoding="utf-8"))
        return data["groups"] if "groups" in data else data
    claims_path = str(groups_path).replace("claim_groups.json", "claims.json")
    data = json.load(open(claims_path, encoding="utf-8"))
    validated = data.get("claims", {}).get("validated", [])
    groups = {}
    for v in validated:
        gid = str(v.get("original_index"))
        g = groups.setdefault(gid, {"texts": [], "keywords": {"keywords": []}})
        if v.get("text") and v["text"] not in g["texts"]:
            g["texts"].append(v["text"])
    return groups


def _all_nodes(node):
    yield node
    for c in node.get("children", []):
        yield from _all_nodes(c)


def _load_roles_dict():
    return {r["id"]: r for r in _load_roles()}


if __name__ == "__main__":
    main()
