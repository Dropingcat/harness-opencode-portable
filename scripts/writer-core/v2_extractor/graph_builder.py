"""Graph builder: артефакты экстракции (объекты, claims, филология, хрия)
-> узлы и рёбра 12 графов (graph_registry.yaml v0.2).

Связывает извлечённые единицы в рёбра графов по правилам:
  - G3 discourse: Paragraph -> Transition -> Paragraph
  - G4 argument: Claim -> WARRANT/REBUTTAL/CONCLUSION (Toulmin из хрии)
  - G5 epistemic: ClaimRef <-> EvidenceRef (из claims, objects)
  - G6 artifact_symbol: Quote/Quantity -> Claim/HAS_UNIT (числа/химия -> контекст)
  - G10 vocabulary: Term/Abbr -> DEFINES
  - G11 forensics: стилистика/фигуры/хрия -> FeatureProfile (автор-паттерны)
  - G12 work_lineage: Work -> CITES (из списка литературы)

Вход: единый артефакт экстракции (dict) из extraction_engine + philological_layer.
Выход: nodes[] + edges[] (каноническая форма, пригодная для SQLite).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GNode:
    id: str
    type: str
    graph: str
    props: dict = field(default_factory=dict)


@dataclass
class GEdge:
    src: str
    dst: str
    relation: str
    graph: str
    props: dict = field(default_factory=dict)


# ------------------------- mapping helpers -------------------------

def _node_id(graph: str, kind: str, idx: int) -> str:
    return f"G{graph}_{kind}_{idx:04d}"


def build_graphs(extraction: dict, philology: dict, para_id: str = "PAR_000") -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []

    # ———— Относительные координаты (rel_pos) добавляются узлам по порядку в графе ————
    _counter = {}

    def _add_node(graph, ntype, props, span=None):
        """Добавить узел с rel_pos (порядок в графе) + abs_span (если есть)."""
        key = graph
        _counter[key] = _counter.get(key, 0) + 1
        node = {"id": _node_id(graph.split("_")[0][1:], ntype, _counter[key] - 1),
                "type": ntype, "graph": graph,
                "props": {**props, "rel_pos": _counter[key] - 1}}
        if span:
            node["abs_span"] = span
        nodes.append(node)
        return node["id"]

    # --- G5 epistemic: claims (из научной ветки, с координатами из QA) ---
    claims = extraction.get("claims", [])
    for ci, c in enumerate(claims):
        span = {"start": c.get("start"), "end": c.get("end"), "page": c.get("page"),
                "method": c.get("qa_method", "exact")}
        cid = _add_node("G5_epistemic_projection", "Claim",
                        {"text": c.get("text", "")[:80], "para": para_id,
                         "qa_status": c.get("qa_status", "PROPOSED"),
                         "role": c.get("role"), "kind": c.get("kind")},
                        span)
        # если claim содержит число -> Evidence/Quantity
        if re.search(r"\d+[,.]?\d*\s*[%°мкмм]|средняя скорость|составляла", c.get("text", "")):
            eid = _add_node("G5_epistemic_projection", "Evidence", {"claim": c.get("text", "")[:50]})
            edges.append({"src": cid, "dst": eid, "relation": "SUPPORTED_BY",
                          "graph": "G5_epistemic_projection"})

    # --- G6 artifact_symbol: числа/химия/годы -> Quantity/Formula ---
    objs = extraction.get("objects", [])
    num_idx = chem_idx = 0
    claim_text = " ".join(c.get("text", "") for c in claims)
    for o in objs:
        c = o.get("class", "")
        if c.startswith("B_number"):
            q_id = _add_node("G6_artifact_symbol", "Quantity",
                             {"raw": o["raw"], "unit": o.get("unit"), "lower": o.get("value_lower")},
                             {"start": o.get("start"), "end": o.get("end")})
            num_idx += 1
            # HAS_UNIT на Unit node
            if o.get("unit"):
                uid = _add_node("G6_artifact_symbol", "Unit", {"unit": o["unit"]})
                edges.append({"src": q_id, "dst": uid, "relation": "HAS_UNIT",
                              "graph": "G6_artifact_symbol", "props": {"unit": o["unit"]}})
        elif c.startswith("B_chemical") or c.startswith("B_steel"):
            f_id = _add_node("G6_artifact_symbol", "Formula", {"raw": o["raw"]},
                             {"start": o.get("start"), "end": o.get("end")})
            chem_idx += 1

    # --- G6: Quantity/Formula -> Claim (через наличие raw в тексте claim) ---
    for ci, c in enumerate(claims):
        ctext = c.get("text", "")
        for o in objs:
            raw = o.get("raw", "")
            if raw and raw.lower() in ctext.lower():
                src = _node_id(6, "QTY" if o["class"].startswith("B_number") else "FORM", 0)
                edges.append({"src": src, "dst": _node_id(5, "CLAIM", ci),
                              "relation": "USED_BY", "graph": "G6_artifact_symbol",
                              "props": {"evidence": raw}})

    # --- G10 vocabulary: термины/аббревиатуры -> DEFINES ---
    term_idx = 0
    for o in objs:
        if o.get("class", "").startswith("B_term"):
            _add_node("G10_vocabulary", "Term", {"term": o.get("term", "")})
            term_idx += 1
        if o.get("class", "").startswith("B_abbr_def"):
            tid = _add_node("G10_vocabulary", "Term",
                            {"abbr": o.get("abbr"), "expansion": o.get("expansion")})
            term_idx += 1
            # DEFINES: abbr -> expansion
            did = _add_node("G10_vocabulary", "Definition", {"text": o.get("expansion", "")[:50]})
            edges.append({"src": tid, "dst": did, "relation": "DEFINES",
                          "graph": "G10_vocabulary",
                          "props": {"expansion": o.get("expansion")}})

    # --- G3 discourse: связки + хрия-части ---
    for si, conn in enumerate(philology.get("connectors", [])):
        _add_node("G3_discourse", "Transition", {"связка": conn.get("связка", "")})
    # хрия (обратный композиционный скелет)
    for ci, part in enumerate(philology.get("chreia", [])):
        _add_node("G3_discourse", "DiscourseMove",
                  {"part": part.get("part"), "text": part.get("text", "")[:60]})

    # --- G4 argument: хрия -> аргументные роли (Toulmin) ---
    role_map = {"thesis": "CONCLUSION", "cause": "WARRANT", "contrary": "REBUTTAL",
                "evidence": "BACKING", "example": "PREMISE", "analogy": "PREMISE"}
    for ci, part in enumerate(philology.get("chreia", [])):
        role = role_map.get(part.get("part"))
        if role:
            _add_node("G4_argument", f"{role}Ref", {"role": role, "text": part.get("text", "")[:50]})
            # CONCLUDES: thesis -> conclusion
            if role == "CONCLUSION":
                edges.append({"src": _node_id(3, "MOVE", ci), "dst": _node_id(4, "ARG", ci),
                              "relation": "CONCLUDES", "graph": "G4_argument"})

    # --- G11 forensics: фигуры/морфология/акценты -> FeatureProfile ---
    fig_idx = 0
    for f in philology.get("figures", []):
        _add_node("G11_forensics_fingerprint", "FeatureProfile",
                  {"figure": f.get("type"), "text": f.get("text", "")[:50]})
        fig_idx += 1
    if philology.get("morphology"):
        morph = philology["morphology"]
        _add_node("G11_forensics_fingerprint", "AuthorProfile",
                  {"kantseliarit": morph.get("kantseliarit_ratio"),
                   "passive": morph.get("passive_participle_ratio"),
                   "participle": morph.get("participle_ratio")})

    # --- G12 work_lineage: ссылки на работы (из объектов-авторов/источников) ---
    ref_idx = 0
    text_blob = " ".join(o.get("raw", "") for o in objs) + " " + para_id
    ref_matches = re.findall(r"(\d{4})г?\.|([А-ЯЁ][а-яё]+ [А-ЯЁ]\.[А-ЯЁ]\.)", text_blob)
    for _ in ref_matches:
        _add_node("G12_work_lineage", "Work", {"ref": "source"})
        ref_idx += 1

    return {"nodes": nodes, "edges": edges, "paragraph": para_id}


# ------------------------- to sqlite -------------------------

def store_graphs(conn, graphs: dict, para_id: str) -> None:
    """Сохранить узлы/рёбра в SQLite (таблицы graph_nodes, graph_edges)."""
    conn.execute("""CREATE TABLE IF NOT EXISTS graph_nodes (
        id TEXT, type TEXT, graph TEXT, props TEXT, para TEXT, PRIMARY KEY(id, para))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS graph_edges (
        src TEXT, dst TEXT, relation TEXT, graph TEXT, props TEXT, para TEXT)""")
    for n in graphs["nodes"]:
        conn.execute("INSERT OR REPLACE INTO graph_nodes(id,type,graph,props,para) VALUES (?,?,?,?,?)",
                     (n["id"], n["type"], n["graph"], json.dumps(n.get("props", {}), ensure_ascii=False), para_id))
    for e in graphs["edges"]:
        conn.execute("INSERT OR REPLACE INTO graph_edges(src,dst,relation,graph,props,para) VALUES (?,?,?,?,?,?)",
                     (e["src"], e["dst"], e["relation"], e["graph"], json.dumps(e.get("props", {}), ensure_ascii=False), para_id))
    conn.commit()


def to_yaml(graphs: dict) -> str:
    import yaml
    return yaml.dump(graphs, allow_unicode=True, sort_keys=False, default_flow_style=False)