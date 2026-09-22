#!/usr/bin/env python3
"""topics_tree.py — детерминированное дерево направлений (слой 0.5, Волна 1).

Строит ИЕРАРХИЮ тем документа из claim_groups.json (этап 1): родитель = общий
термин, дети = уточняющие. Без LLM: словарь синонимов + правила привязки.
Кэширует топологию по md5 входного текста — не перестраивать между прогонами.

Usage:
    python3 topics_tree.py <input.txt> <claim_groups.json> <topics_tree.json> [--no-cache]

Выход:
    {"topics_tree": {...}, "method": "deterministic", "n_groups": N,
     "groups_attached": N, "cached_topology": bool}
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import hashlib
import re
from pathlib import Path

# ── Словарь синонимов: концепт → маркеры (RU + EN) ────────────────────
# Доменно-специфично (естественные науки, материаловедение) — как в 36 §11.4.
# Маркеры приводятся к нижнему регистру и ищутся подстрокой (stem-иш).
CONCEPTS = [
    # (id, label, parent_id, [markers])
    ("alloys", "Материалы и сплавы", None, [
        "r18", "р18", "vks-10", "вкс-10", "08х18н10т", "сплав", "alloy",
        "стал", "steel", "мартенсит", "austenit", "аустенит", "железо", "iron",
        "fe-n", "nitrided steel",
    ]),
    ("r18_steel", "Инструментальная сталь Р18", "alloys", ["r18", "р18"]),
    ("vks10_alloy", "Мартенситно-стареющий сплав ВКС-10", "alloys",
     ["vks-10", "вкс-10"]),
    ("08x18n10t", "Аустенитная сталь 08Х18Н10Т", "alloys", ["08х18н10т"]),
    ("pure_iron", "Чистое железо (эталон)", "alloys",
     ["чистое железо", "pure iron", "reference material", "эталон"]),

    ("methods", "Методы исследования", None, [
        "x-ray", "рентген", "дифракц", "diffract", "рентгеноструктурн",
        "риа", "рифа", "xrd", "метод", "method", "методик",
    ]),
    ("xrd", "Рентгеноструктурный анализ", "methods", [
        "x-ray", "рентген", "дифракц", "diffract", "xrd", "брагг", "bragg",
        "рефлекс", "reflection", "профил", "profile", "line broadening",
    ]),
    ("rietveld", "Полнопрофильный анализ (Ритвельд)", "xrd",
     ["риетвельд", "rietveld", "полнопрофильн", "full-profile"]),
    ("deconvolution", "Обработка дифрактограмм (регуляризация)", "xrd", [
        "тихонов", "tikhonov", "фредгольм", "fredholm", "регуляризац",
        "regulariz", "разрешен", "resolution", "l-крив", "l-curve",
    ]),

    ("processing", "Химико-термическая обработка", None, [
        "азотирован", "nitriding", "nitrided", "термическ", "thermal",
        "обработк", "treatment", "химико-термич",
    ]),
    ("nitriding", "Азотирование", "processing", [
        "азотирован", "nitriding", "nitrided", "нитрид", "nitride",
    ]),
    ("laser", "Лазерная обработка", "processing", [
        "лазерн", "laser", "оплавлен", "melting", "облучен", "irradiat",
    ]),

    ("structure", "Структурные характеристики", None, [
        "микродеформац", "microdeformation", "параметр решетки",
        "lattice parameter", "фазов", "phase", "карбид", "carbide",
        "coherent scattering", "межплоскост", "interplanar", "кристаллит",
        "rystallite", "ocr", "множество", "объемн", "volume fraction",
    ]),
    ("phase_transformations", "Фазовые превращения", "structure",
     ["фазов", "phase transformation", "фазы", "phase"]),
    ("nitride_phase", "Нитридные фазы", "phase_transformations",
     ["нитрид", "nitride"]),
    ("carbide_phase", "Карбидные фазы", "phase_transformations",
     ["карбид", "carbide"]),
    ("lattice_param", "Параметр решётки и микродеформации", "structure",
     ["параметр решетки", "lattice parameter", "микродеформац",
      "microdeformation", "межплоскост", "interplanar", "microdistortion"]),
    ("css", "Области когерентного рассеяния", "structure",
     ["coherent scattering", "област"]),
    ("volume_fraction", "Объёмные доли фаз", "structure",
     ["volume fraction", "объемн дол", "объёмн дол"]),

    ("general", "Общие положения", None, [
        "диссертац", "dissertation", "автор", "author", "публикац",
        "publication", "апробац", "содержит", "consists", "введение",
        "заключени", "conclusion",
    ]),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _concept_index():
    index = {}
    for cid, label, parent, markers in CONCEPTS:
        index[cid] = {
            "id": cid, "label": label, "parent": parent, "markers": markers,
        }
    return index


def _concept_depth(index, cid):
    depth = 0
    cur = index[cid]
    while cur["parent"] is not None:
        depth += 1
        cur = index[cur["parent"]]
    return depth


def _match_group(concept_index, text_blob: str):
    """Возвращает список концептов, маркеры которых нашлись в text_blob."""
    text = _norm(text_blob)
    hits = []
    for cid, c in concept_index.items():
        if any(_norm(m) in text for m in c["markers"]):
            hits.append(cid)
    return hits


def _add_group_to_node(node, gid, group):
    claims = node.setdefault("claims", [])
    gid_s = str(gid)
    if gid_s not in claims:
        claims.append(gid_s)


def build_tree(concept_index, groups):
    """Строит дерево: корень → категории → подкатегории → группы."""
    tree = {
        "id": "root",
        "label": "Темы документа",
        "depth": 0,
        "parent": None,
        "keywords": [],
        "claims": [],
        "children": [],
    }
    nodes = {"root": tree}

    def _node(cid):
        if cid not in nodes:
            c = concept_index[cid]
            parent = c["parent"]
            pnode = nodes.get(parent) if parent else tree
            if parent and parent not in nodes:
                pnode = _node(parent)
            node = {
                "id": cid, "label": c["label"], "depth": (pnode["depth"] + 1),
                "parent": pnode["id"], "keywords": list(c["markers"]),
                "claims": [], "children": [],
            }
            pnode["children"].append(node)
            nodes[cid] = node
        return nodes[cid]

    attached = 0
    unattached = []
    for gid, group in groups.items():
        texts = group.get("texts", [])
        kw = group.get("keywords", {}).get("keywords", [])
        blob = " ".join(texts) + " " + " ".join(kw)
        hits = _match_group(concept_index, blob)
        if hits:
            # Наиболее специфичный узел = максимальная глубина в иерархии.
            # Листья (глубже) имеют приоритет над родителями.
            deepest = max(hits, key=lambda c: _concept_depth(concept_index, c))
            node = _node(deepest)
            _add_group_to_node(node, gid, group)
            attached += 1
        else:
            unattached.append(str(gid))

    # Группы без привязки → узел general (не теряем)
    for gid in unattached:
        node = _node("general")
        _add_group_to_node(node, gid, groups[gid])
        attached += 1

    return tree, attached, len(unattached)


def load_groups(groups_path):
    """Загружает claim_groups.json или генерирует из claims.json (детерм.).

    Формат claims.json: {claims:{validated:[{text, original_sentence, original_index}]}}
    Группировка по original_index — тот же ключ, что у claim_groups.json.
    """
    if Path(groups_path).is_file():
        # TD-115: битый/пустой claim_groups.json -> fallback на claims.json (не краш)
        try:
            data = json.load(open(groups_path, encoding="utf-8"))
            if isinstance(data, dict) and "groups" in data:
                return data["groups"]
            return data
        except (json.JSONDecodeError, ValueError):
            print(f"WARN: {groups_path} повреждён/пуст, fallback на claims.json", file=sys.stderr)
            # продолжить к фолбэку ниже
    # фолбэк: генерируем из claims.json (файл рядом с groups_path)
    claims_path = str(groups_path).replace("claim_groups.json", "claims.json")
    if not Path(claims_path).is_file():
        raise FileNotFoundError(
            f"Нет ни {groups_path}, ни {claims_path} — нельзя построить дерево"
        )
    data = json.load(open(claims_path, encoding="utf-8"))
    validated = data.get("claims", {}).get("validated", [])
    groups = {}
    for v in validated:
        gid = str(v.get("original_index"))
        g = groups.setdefault(gid, {"texts": [], "keywords": {"keywords": []}})
        if v.get("text") and v["text"] not in g["texts"]:
            g["texts"].append(v["text"])
    return groups


def _prune_empty(node):
    node["children"] = [c for c in node.get("children", []) if c.get("claims") or c.get("children")]
    for c in node["children"]:
        _prune_empty(c)
    return node


def cache_path_for(topics_path):
    return str(topics_path) + ".cached.json"


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 topics_tree.py <input.txt> <claim_groups.json> <topics_tree.json> [--no-cache]", file=sys.stderr)
        sys.exit(1)
    input_path, groups_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    use_cache = "--no-cache" not in sys.argv

    text = Path(input_path).read_text(encoding="utf-8", errors="ignore")
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

    cache_file = Path(out_path + ".cached.json")
    if use_cache and cache_file.is_file():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("input_hash") == text_hash:
                result = cached["result"]
                result["cached_topology"] = True
                json.dump(result, open(out_path, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=2)
                print(f"✅ topics_tree: кэш (md5 совпал), {result.get('n_groups')} групп, {result.get('groups_attached')} привязано")
                return
        except Exception:
            pass

    groups = load_groups(groups_path)

    concept_index = _concept_index()
    tree, attached, unattached = build_tree(concept_index, groups)
    tree = _prune_empty(tree)

    result = {
        "topics_tree": tree,
        "method": "deterministic_vocab",
        "n_groups": len(groups),
        "groups_attached": attached,
        "groups_unattached": unattached,
        "input_hash": text_hash,
        "cached_topology": False,
        "concepts_used": len(CONCEPTS),
    }

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(result, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if use_cache:
        json.dump({"input_hash": text_hash, "result": result},
                  open(cache_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"✅ topics_tree: {len(groups)} групп, привязано {attached}, без привязки {unattached}")
    print(f"   метод: deterministic_vocab, концептов: {len(CONCEPTS)}")


if __name__ == "__main__":
    main()
