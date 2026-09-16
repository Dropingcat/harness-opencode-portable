# -*- coding: utf-8 -*-
"""M_GRAPH_BRIDGE: единый граф-билдер для writer-core v0.3.

Из ГИБРИДНОГО артефакта параграфа (v2 claims/objects/discourse/philology
+ v0.3 LinguisticDigest + links) строит узлы и рёбра графов реестра v0.3
(graph_registry.yaml), честно — только из тех данных, что есть в артефакте.

Строятся на уровне параграфа (7 графов):
  G3_discourse            — discourse-роли v2 (result/method/conclusion/...) +
                            connectors (Transition) + digest.discourse_role
  G4_argument             — хрия (Toulmin): thesis→ConclusionRef, cause→WarrantRef,
                            contrary→RebuttalRef, evidence→BackingRef,
                            example→PremiseRef + ArgumentInstance
  G5_epistemic_projection — claims→ClaimRef, объекты→EvidenceRef,
                            SUPPORTS по links.object_to_claim, ScopeRef по digest
  G6_artifact_symbol      — числа→Quantity→HAS_UNIT→Unit, химия/стали→Formula,
                            термины/аббревиатуры→Term/DEFINES
  G13_linguistic_structure— DocumentSpan→Sentence→Clause→Token (HEAD_OF)
  G14_cohesion_information_flow — links.claim_to_digest (Theme/Rheme,
                            THEME_TO_RHEME) + повторяющиеся объекты между claims
                            (Mention/EntityRef, REFERS_TO/COREFERS_WITH/
                            LEXICALLY_CONTINUES/LexicalChain)
  G15_pragmatic_rhetorical— digest.discourse_role + хрия (CommunicativeAct/
                            DiscourseRelation/RhetoricalMove/Presupposition)

Skipped на уровне параграфа (причины в "skipped"): G1, G2, G7, G8, G9, G10,
G11, G12, G16. G10_vocabulary отсутствует в реестре v0.3 (есть G10_execution).

Принцип grounded: связи строятся ТОЛЬКО по links артефакта либо по явным
span-совпадениям (вхождение raw объекта в span claim / позиции в тексте).
Каждый узел/ребро валидируется против node_types/edge_types реестра
(нарушение → ValueError).

Выход build_paragraph_graphs:
  {"graphs": {graph_id: {"nodes": [...], "edges": [...]}, ...},
   "skipped": [{"graph": ..., "reason": ...}, ...]}

Узел:   {"id": "<graph>__<type>__<para>__<idx>", "type", "graph", "props"}
Ребро:  {"src", "dst", "relation", "graph", "props"}
props  — JSON-серизуемые атрибуты, включая span-координаты (start/end) и para.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any

_DEFAULT_REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph_registry.yaml")

# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

def load_graph_registry(path: str | None = None) -> dict[str, dict]:
    """Загрузить graph_registry.yaml v0.3 -> {graph_id: {topology,
    node_types: set, edge_types: set}}."""
    p = path or os.environ.get("WRITER_GRAPH_REGISTRY") or _DEFAULT_REGISTRY
    if not os.path.exists(p):
        raise FileNotFoundError(f"graph registry not found: {p}")
    import yaml
    with open(p, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    out: dict[str, dict] = {}
    for g in data.get("graphs", []):
        gid = g.get("id")
        if not gid:
            continue
        out[gid] = {
            "topology": g.get("topology", "directed_graph"),
            "node_types": set(g.get("node_types", [])),
            "edge_types": set(g.get("edge_types", [])),
        }
    return out


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).lower().strip()


def _find_span(needle: str, text: str) -> list[int] | None:
    """Позиция needle в text -> [start, end] | None.

    Word-boundary поиск (\\b): не матчит подстроку внутри слова
    ('чем' в 'причем', 'огранич' в 'пограничная'). Координаты — в исходном
    тексте (не в нормализованном). Case-insensitive для маркеров/строк.
    """
    if not needle or not text:
        return None
    needle = str(needle).strip()
    if not needle:
        return None
    m = re.search(r"\b" + re.escape(needle) + r"\b", str(text), re.IGNORECASE)
    if not m:
        return None
    return [m.start(), m.end()]


def _find_word(needle: str, text: str) -> list[int] | None:
    """Word-boundary, CASE-SENSITIVE поиск needle в text -> [start, end] | None."""
    if not needle or not text:
        return None
    needle = str(needle).strip()
    if not needle:
        return None
    m = re.search(r"\b" + re.escape(needle) + r"\b", str(text))
    if not m:
        return None
    return [m.start(), m.end()]


def _link_claims(c2d: list) -> list[int]:
    """Извлечь индексы claims из links.claim_to_digest.

    Поддерживает оба формата: [3, ...] и [{"claim":3,"sentence":2,"overlap":0.9}, ...]
    (а также legacy-ключ "claim_idx").
    """
    out: list[int] = []
    for x in c2d:
        if isinstance(x, dict):
            c = x.get("claim")
            if c is None:
                c = x.get("claim_idx")
            if isinstance(c, int) and c >= 0:
                out.append(c)
        elif isinstance(x, int) and x >= 0:
            out.append(x)
    return out


def _object_in_claim(o: dict, c: dict, text: str) -> bool:
    """Grounded-проверка связи объект->claim.

    Два условия (оба, если данные есть):
      1) span объекта содержится в span claim (c.start <= o.start and o.end <= c.end);
      2) raw объекта (case-sensitive, word-boundary) реально присутствует в тексте.
    Без выполнения — связь считается выдуманной и пропускается.
    """
    os_, oe = o.get("start"), o.get("end")
    cs_, ce = c.get("start"), c.get("end")
    if isinstance(os_, int) and isinstance(oe, int) \
            and isinstance(cs_, int) and isinstance(ce, int):
        if not (cs_ <= os_ and oe <= ce):
            return False
    raw = o.get("raw", "") or o.get("term", "") or o.get("value", "") \
        or o.get("abbr", "") or ""
    if not raw:
        return False
    return _find_word(raw, text) is not None


def _object_to_claim_grounded(objects: list[dict], claims: list[dict],
                              o2c: list, text: str) -> list[tuple[int, int]]:
    """Нормализованные (oi, ci) из links.object_to_claim (если есть) либо
    grounded-fallback по явному совпадению raw в тексте claim.

    Поддерживает ключи "object"/"object_idx" и "claim"/"claim_idx".
    """
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for l in o2c:
        oi = l.get("object") if isinstance(l, dict) else None
        ci = l.get("claim") if isinstance(l, dict) else None
        if oi is None:
            oi = l.get("object_idx") if isinstance(l, dict) else None
        if ci is None:
            ci = l.get("claim_idx") if isinstance(l, dict) else None
        if not isinstance(oi, int) or not isinstance(ci, int) \
                or oi < 0 or ci < 0 or oi >= len(objects) or ci >= len(claims):
            continue
        key = (oi, ci)
        if key in seen:
            continue
        seen.add(key)
        out.append((oi, ci))
    if out:
        return out  # links есть — используем их (grounded-проверка на уровне вызова)
    # grounded fallback: raw объекта, case-sensitive, в тексте claim
    for oi, o in enumerate(objects):
        if not (o.get("raw") or o.get("term") or o.get("value") or o.get("abbr")):
            continue
        for ci, c in enumerate(claims):
            if _object_in_claim(o, c, text):
                out.append((oi, ci))
    return out


def _sanitize_para(para_id: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(para_id or "PAR"))


class _GraphAcc:
    """Аккумулятор узлов/рёбер одного графа с валидацией по реестру."""

    def __init__(self, graph_id: str, registry: dict):
        self.graph_id = graph_id
        self._nt = registry[graph_id]["node_types"]
        self._et = registry[graph_id]["edge_types"]
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self._counters: dict[str, int] = {}
        self._para_safe: str = "PAR"

    def set_para(self, para_id: Any) -> None:
        self._para_safe = _sanitize_para(para_id)

    def add_node(self, ntype: str, props: dict, para: Any) -> str:
        if ntype not in self._nt:
            raise ValueError(
                f"[{self.graph_id}] node type {ntype!r} not in registry "
                f"node_types {sorted(self._nt)}")
        idx = self._counters.get(ntype, 0)
        self._counters[ntype] = idx + 1
        nid = f"{self.graph_id}__{ntype}__{_sanitize_para(para)}__{idx:03d}"
        props = {**props, "para": str(para or "")}
        self.nodes.append({"id": nid, "type": ntype, "graph": self.graph_id,
                           "props": props})
        return nid

    def add_edge(self, src: str, dst: str, relation: str, props: dict | None = None,
                 para: Any = None) -> None:
        if relation not in self._et:
            raise ValueError(
                f"[{self.graph_id}] edge type {relation!r} not in registry "
                f"edge_types {sorted(self._et)}")
        eprops = dict(props or {})
        if para is not None:
            eprops["para"] = str(para)
        self.edges.append({"src": src, "dst": dst, "relation": relation,
                           "graph": self.graph_id, "props": eprops})

    def result(self) -> dict:
        return {"nodes": self.nodes, "edges": self.edges}


def _span_props(start: Any, end: Any, page: Any = None) -> dict:
    p: dict = {}
    if start is not None:
        p["start"] = start
    if end is not None:
        p["end"] = end
    if page is not None:
        p["page"] = page
    return p


# --------------------------------------------------------------------------
# graph builders (каждый возвращает _GraphAcc или None, если данных нет)
# --------------------------------------------------------------------------

def _build_g13(art: dict, reg: dict) -> _GraphAcc | None:
    """G13: DocumentSpan -> Sentence -> Clause -> Token (HEAD_OF)."""
    sentences = art.get("sentences") or []
    if not sentences:
        return None
    acc = _GraphAcc("G13_linguistic_structure", reg)
    para_id = art.get("paragraph_id", "")
    acc.set_para(para_id)
    page = art.get("page")

    text = art.get("text") or ""
    tlen = len(text)
    doc_span = {"start": 0, "end": tlen} if text else {}
    doc_id = acc.add_node("DocumentSpan", {"text": text[:200], **doc_span}, para_id)

    punct = {",", ";", ":", "—", "–", "(", ")", "«", "»", "…"}
    for si, s in enumerate(sentences):
        stext = s.get("text", "")
        s_start, s_end = s.get("start"), s.get("end")
        sspan = _span_props(s_start, s_end, page)
        sent_id = acc.add_node("Sentence",
                               {"text": stext[:200], "index": si, **sspan}, para_id)
        acc.add_edge(doc_id, sent_id, "HEAD_OF", para=para_id)

        toks = s.get("tokens") or []
        if not toks:  # fallback: токенизация по пробелам с координатами
            off = s_start if isinstance(s_start, int) else 0
            pos = 0
            for w in re.finditer(r"\S+", stext):
                toks.append({"text": w.group(0), "start": off + w.start(),
                             "end": off + w.end(), "pos": pos})
                pos += 1
        # валидация span токенов: 0<=start<end<=len(text); дедупликация (start,end)
        seen_tok: set[tuple[int, int]] = set()
        valid: list[dict] = []
        for t in toks:
            st, en = t.get("start"), t.get("end")
            if not isinstance(st, int) or not isinstance(en, int):
                continue
            if not (0 <= st < en <= tlen):
                continue
            key = (st, en)
            if key in seen_tok:
                continue
            seen_tok.add(key)
            valid.append(t)
        if not valid:
            continue
        # разбиение на клаузы по пунктуационным границам
        clauses: list[list[dict]] = []
        cur: list[dict] = []
        for t in valid:
            cur.append(t)
            if t.get("text") in punct:
                clauses.append(cur)
                cur = []
        if cur:
            clauses.append(cur)
        seen_clause: set[tuple[int, int]] = set()
        for ci, ctoks in enumerate(clauses):
            if not ctoks:
                continue
            c0, c1 = ctoks[0], ctoks[-1]
            ckey = (c0.get("start"), c1.get("end"))
            if ckey in seen_clause:
                continue
            seen_clause.add(ckey)
            # текст клаузы: срез по валидному span, иначе fallback из текстов токенов
            ctext = ""
            rel0 = c0.get("start") - (s_start if isinstance(s_start, int) else 0)
            rel1 = c1.get("end") - (s_start if isinstance(s_start, int) else 0)
            if stext and isinstance(rel0, int) and isinstance(rel1, int) \
                    and 0 <= rel0 < rel1 <= len(stext):
                ctext = stext[rel0:rel1]
            if not ctext or not ctext.strip():
                ctext = " ".join(t.get("text", "") for t in ctoks).strip()
            if not ctext:
                continue  # не создаём пустые Clause-узлы
            clause_id = acc.add_node(
                "Clause", {"text": ctext[:200], "index": ci,
                           "start": c0.get("start"), "end": c1.get("end"),
                           **({"page": page} if page is not None else {})}, para_id)
            acc.add_edge(sent_id, clause_id, "HEAD_OF", para=para_id)
            for t in ctoks:
                tok_id = acc.add_node(
                    "Token", {"text": t.get("text", ""), "pos": t.get("pos"),
                              "start": t.get("start"), "end": t.get("end")}, para_id)
                acc.add_edge(clause_id, tok_id, "HEAD_OF", para=para_id)
    return acc


def _build_g14(art: dict, reg: dict) -> _GraphAcc | None:
    """G14: Theme/Rheme (claim_to_digest) + Mention/EntityRef (object_to_claim),
    COREFERS_WITH/LEXICALLY_CONTINUES для объектов в >=2 claims.

    Grounded: Mention/EntityRef эмитятся ТОЛЬКО если span объекта содержится
    в span claim и raw объекта (case-sensitive, word-boundary) есть в тексте.
    Theme==Rheme (самоссылочные) не порождают ребро THEME_TO_RHEME.
    """
    claims = art.get("claims") or []
    objects = art.get("objects") or []
    links = art.get("links") or {}
    if not claims and not objects:
        return None
    acc = _GraphAcc("G14_cohesion_information_flow", reg)
    para_id = art.get("paragraph_id", "")
    acc.set_para(para_id)
    page = art.get("page")
    text = art.get("text") or ""

    # Theme/Rheme: digest.main_statement — тема, связанные claims — ремы
    digest = art.get("digest") or {}
    ms = digest.get("main_statement") or {}
    c2d = _link_claims(links.get("claim_to_digest") or [])
    if ms.get("text"):
        ms_norm = _norm(ms["text"])
        theme_id = acc.add_node("Theme", {"text": ms["text"][:200]}, para_id)
        for ci in c2d:
            if ci >= len(claims):
                continue
            c = claims[ci]
            if _norm(c.get("text", "")) == ms_norm:
                # тема == рема: не выдаём самоссылку за information-flow
                continue
            rheme_id = acc.add_node(
                "Rheme", {"text": c.get("text", "")[:200], "claim": ci,
                          **_span_props(c.get("start"), c.get("end"), page)}, para_id)
            acc.add_edge(theme_id, rheme_id, "THEME_TO_RHEME", para=para_id)

    # Mentions/Entities: только grounded (span-контейнмент + case-sensitive raw)
    o2c = _object_to_claim_grounded(objects, claims,
                                    links.get("object_to_claim") or [], text)
    entity_by_obj: dict[int, str] = {}
    mention_by_obj: dict[int, list[str]] = {}
    for oi, ci in o2c:
        o = objects[oi]
        c = claims[ci]
        if not _object_in_claim(o, c, text):
            continue  # объект не лежит в span claim — не создаём Mention
        if oi not in entity_by_obj:
            raw = o.get("raw", "")
            eid = acc.add_node(
                "EntityRef", {"raw": raw, "class": o.get("class", ""),
                              **_span_props(o.get("start"), o.get("end"), page)},
                para_id)
            entity_by_obj[oi] = eid
            mention_by_obj[oi] = []
        mid = acc.add_node(
            "Mention", {"text": o.get("raw", ""), "claim": ci, "object": oi,
                        **_span_props(o.get("start"), o.get("end"), page)}, para_id)
        acc.add_edge(mid, entity_by_obj[oi], "REFERS_TO", para=para_id)
        mention_by_obj[oi].append(mid)

    # повторяющиеся объекты: LexicalChain + COREFERS_WITH + LEXICALLY_CONTINUES
    for oi, mids in mention_by_obj.items():
        if len(mids) < 2:
            continue
        o = objects[oi]
        chain_id = acc.add_node(
            "LexicalChain", {"entity": o.get("raw", ""), "occurrences": len(mids)},
            para_id)
        for mid in mids:
            acc.add_edge(mid, chain_id, "LEXICALLY_CONTINUES", para=para_id)
        for a, b in zip(mids, mids[1:]):
            acc.add_edge(a, b, "COREFERS_WITH", para=para_id)
    return acc


def _act_for_claim(c: dict) -> str:
    low = _norm(c.get("text", ""))
    if c.get("hedged"):
        return "hedged_assert"
    if re.search(r"известно|установлено|показано|показали|доказано", low):
        return "assert_report"
    if re.search(r"снижает|повышает|приводит|увеличивает|уменьшает|вызывает", low):
        return "assert_effect"
    return "assert"


def _build_g15(art: dict, reg: dict) -> _GraphAcc | None:
    """G15: CommunicativeAct (claims) + RhetoricalMove (chreia) +
    DiscourseRelation (digest.discourse_role) + Presupposition (ambiguities)."""
    claims = art.get("claims") or []
    phil = art.get("philology") or {}
    chreia = phil.get("chreia") or []
    digest = art.get("digest") or {}
    if not claims and not chreia and not digest.get("discourse_role"):
        return None
    acc = _GraphAcc("G15_pragmatic_rhetorical", reg)
    para_id = art.get("paragraph_id", "")
    acc.set_para(para_id)
    page = art.get("page")
    text = art.get("text") or ""

    # RhetoricalMove из хрии
    move_ids: list[str] = []
    for part in chreia:
        ptext = part.get("text", "")
        sp = _find_span(ptext, text)
        mid = acc.add_node(
            "RhetoricalMove", {"part": part.get("part", ""), "text": ptext[:200],
                               **(_span_props(*sp, page) if sp else {})}, para_id)
        move_ids.append(mid)

    # CommunicativeAct из claims
    act_ids: list[str] = []
    for ci, c in enumerate(claims):
        aid = acc.add_node(
            "CommunicativeAct", {"act": _act_for_claim(c), "claim": ci,
                                 "text": c.get("text", "")[:200],
                                 **_span_props(c.get("start"), c.get("end"), page)},
            para_id)
        act_ids.append(aid)

    # Связи между хрия-ходами по семантике частей (grounded: части определены)
    anchor = None
    thesis_idx = next((i for i, p in enumerate(chreia) if p.get("part") == "thesis"), None)
    anchor = move_ids[thesis_idx] if thesis_idx is not None else (move_ids[0] if move_ids else None)
    rel_by_part = {"cause": "ELABORATES", "analogy": "ELABORATES",
                   "example": "ELABORATES", "preface": "ELABORATES",
                   "evidence": "INTERPRETS", "contrary": "CONTRASTS",
                   "conclusion": "REFORMULATES"}
    if anchor is not None:
        for i, part in enumerate(chreia):
            rel = rel_by_part.get(part.get("part"))
            if rel and i != thesis_idx:
                acc.add_edge(move_ids[i], anchor, rel, para=para_id)

    # CommunicativeAct реализует ход при span-перекрытии (grounded)
    if act_ids and move_ids:
        for i, part in enumerate(chreia):
            ptext = _norm(part.get("text", ""))
            for ci, c in enumerate(claims):
                cspan = (c.get("start"), c.get("end"))
                pspan = _find_span(part.get("text", ""), text)
                if not pspan:
                    continue
                if pspan and cspan[0] is not None and cspan[1] is not None:
                    ov = not (cspan[1] <= pspan[0] or pspan[1] <= cspan[0])
                    if ov:
                        acc.add_edge(act_ids[ci], move_ids[i], "ELABORATES",
                                     para=para_id)

    # Presupposition из digest ambiguities (PRESUPPOSITION_CANDIDATE)
    for iss in digest.get("ambiguities") or []:
        if iss.get("type") != "PRESUPPOSITION_CANDIDATE":
            continue
        phrases = (iss.get("details") or {}).get("phrases") or []
        pid_ = acc.add_node("Presupposition",
                            {"phrases": phrases, "issue": iss.get("type")}, para_id)
        if act_ids:
            acc.add_edge(act_ids[0], pid_, "PRESUPPOSES", para=para_id)

    # DiscourseRelation из digest.discourse_role (role -> лицензируемое ребро)
    role = digest.get("discourse_role")
    if role:
        rid = acc.add_node("DiscourseRelation", {"role": role,
                                                 "source": "digest.discourse_role"},
                           para_id)
        role_edge = {"contrast": ("contrary", "CONTRASTS"),
                     "reformulation": ("conclusion", "REFORMULATES"),
                     "inference": ("conclusion", "ELABORATES"),
                     "connective": ("thesis", "ELABORATES")}.get(role)
        if role_edge and move_ids and anchor is not None:
            want_part, rel = role_edge
            for i, p in enumerate(chreia):
                if p.get("part") == want_part:
                    acc.add_edge(move_ids[i], rid, rel, para=para_id)
                    break
    return acc


def _build_g3(art: dict, reg: dict) -> _GraphAcc | None:
    """G3: ParagraphIntent/TopicFocus (digest) + DiscourseMove (v2 discourse)
    + Transition (connectors); PREPARES/LEADS_TO/CONTRASTS/SUMMARIZES/
    QUALIFIES_MOVE по позициям."""
    discourse = art.get("discourse") or []
    phil = art.get("philology") or {}
    connectors = phil.get("connectors") or []
    digest = art.get("digest") or {}
    if not discourse and not connectors and not digest:
        return None
    acc = _GraphAcc("G3_discourse", reg)
    para_id = art.get("paragraph_id", "")
    acc.set_para(para_id)
    page = art.get("page")
    text = art.get("text") or ""

    intent = digest.get("discourse_role") or "expository"
    intent_id = acc.add_node("ParagraphIntent", {"intent": intent,
                                                 "source": "digest"}, para_id)
    ms = digest.get("main_statement") or {}
    focus_id = acc.add_node("TopicFocus", {"text": ms.get("text", "")[:200]}, para_id)

    # DiscourseMove из v2 discourse-ролей (с позицией маркера)
    moves: list[tuple[int, str]] = []  # (position, move_id)
    for d in discourse:
        role = d.get("role")
        marker = d.get("marker") or ""
        sp = _find_span(marker, text) if marker else None
        pos = sp[0] if sp else None
        mid = acc.add_node(
            "DiscourseMove", {"role": role, "marker": marker,
                              **(_span_props(*sp, page) if sp else {})}, para_id)
        moves.append((pos if pos is not None else 10**9, mid))
    moves.sort(key=lambda x: x[0])

    # Transition из connectors
    trans: list[tuple[int, str, str]] = []  # (position, id, связка)
    for conn in connectors:
        mk = conn.get("связка", "")
        sp = _find_span(mk, text) if mk else None
        pos = sp[0] if sp else None
        tid = acc.add_node(
            "Transition", {"marker": mk, **_span_props(*(sp or [None, None]), page)},
            para_id)
        trans.append((pos if pos is not None else 10**9, tid, mk))

    if moves:
        acc.add_edge(intent_id, moves[0][1], "MOTIVATES", para=para_id)
        acc.add_edge(moves[0][1], focus_id, "ELABORATES", para=para_id)
        # последовательные ходы: PREPARES; conclusion -> SUMMARIZES;
        # limitation -> QUALIFIES_MOVE
        for (p1, m1), (p2, m2) in zip(moves, moves[1:]):
            acc.add_edge(m1, m2, "PREPARES", para=para_id)
            role2 = _role_of(acc, m2)
            if role2 == "conclusion":
                acc.add_edge(m2, m1, "SUMMARIZES", para=para_id)
            elif role2 == "limitation":
                acc.add_edge(m2, m1, "QUALIFIES_MOVE", para=para_id)
        # transition LEADS_TO ближайший следующий ход; контрастивные ->
        # CONTRASTS между соседними ходами
        for (tp, tid, mk) in trans:
            nxt = next((m for pp, m in moves if pp > tp), None)
            if nxt:
                acc.add_edge(tid, nxt, "LEADS_TO", para=para_id)
        contrastive = ("однако", "но", "в отличие", "напротив", "вместе с тем")
        if any(any(cx in _norm(mk) for cx in contrastive) for _, _, mk in trans):
            for (p1, m1), (p2, m2) in zip(moves, moves[1:]):
                acc.add_edge(m1, m2, "CONTRASTS", para=para_id)
    return acc


def _role_of(acc: _GraphAcc, node_id: str) -> str:
    for n in acc.nodes:
        if n["id"] == node_id:
            return n["props"].get("role", "")
    return ""


_ROLE_MAP = {"thesis": "ConclusionRef", "cause": "WarrantRef",
             "contrary": "RebuttalRef", "evidence": "BackingRef",
             "example": "PremiseRef"}
_USE_EDGE = {"PremiseRef": "USES_AS_PREMISE", "WarrantRef": "USES_AS_WARRANT",
             "BackingRef": "USES_AS_BACKING", "RebuttalRef": "USES_AS_REBUTTAL"}


def _build_g4(art: dict, reg: dict) -> _GraphAcc | None:
    """G4: Toulmin-роли из хрии (role_map) + ArgumentInstance + QualifierRef."""
    phil = art.get("philology") or {}
    chreia = phil.get("chreia") or []
    claims = art.get("claims") or []
    mapped = [p for p in chreia if p.get("part") in _ROLE_MAP]
    if not mapped:
        return None
    acc = _GraphAcc("G4_argument", reg)
    para_id = art.get("paragraph_id", "")
    acc.set_para(para_id)
    page = art.get("page")
    text = art.get("text") or ""
    digest = art.get("digest") or {}

    ms = digest.get("main_statement") or {}
    arg_id = acc.add_node("ArgumentInstance",
                          {"text": ms.get("text", "")[:200], "role": "Toulmin"},
                          para_id)

    conclusion_id = None
    for part in mapped:
        ntype = _ROLE_MAP[part["part"]]
        ptext = part.get("text", "")
        sp = _find_span(ptext, text)
        ref_id = acc.add_node(
            ntype, {"role": part["part"], "text": ptext[:200],
                    **(_span_props(*sp, page) if sp else {})}, para_id)
        if ntype == "ConclusionRef":
            conclusion_id = ref_id
            acc.add_edge(arg_id, ref_id, "CONCLUDES", para=para_id)
        else:
            acc.add_edge(arg_id, ref_id, _USE_EDGE[ntype], para=para_id)

    # QualifierRef: хеджирование в claims / слабая модальность digest
    hedged = False
    qual_text = ""
    for c in claims:
        low = _norm(c.get("text", ""))
        m = re.search(r"возможно|вероятно|по-видимому|может|предположительно", low)
        if m:
            hedged, qual_text = True, m.group(0)
            break
    if not hedged and digest.get("modality") in {"possibility", "weak_inference",
                                                 "assertive_compat"}:
        hedged, qual_text = True, digest["modality"]
    if hedged:
        qid = acc.add_node("QualifierRef", {"qualifier": qual_text}, para_id)
        acc.add_edge(qid, arg_id, "QUALIFIES_ARGUMENT", para=para_id)
    return acc


def _build_g5(art: dict, reg: dict) -> _GraphAcc | None:
    """G5: ClaimRef + EvidenceRef (объекты со связью object_to_claim),
    SUPPORTS; ScopeRef (digest.scope) с APPLIES_WITHIN."""
    claims = art.get("claims") or []
    objects = art.get("objects") or []
    links = art.get("links") or {}
    if not claims:
        return None
    acc = _GraphAcc("G5_epistemic_projection", reg)
    para_id = art.get("paragraph_id", "")
    acc.set_para(para_id)
    page = art.get("page")
    text = art.get("text") or ""

    claim_ids: list[str] = []
    for ci, c in enumerate(claims):
        cid = acc.add_node(
            "ClaimRef", {"text": c.get("text", "")[:200], "role": c.get("role"),
                         "kind": c.get("kind") or c.get("claim_kind"),
                         "qa_status": c.get("qa_status", "GROUNDED"),
                         "strength": c.get("strength"),
                         **_span_props(c.get("start"), c.get("end"), page)}, para_id)
        claim_ids.append(cid)

    o2c = _object_to_claim_grounded(objects, claims,
                                    links.get("object_to_claim") or [], text)
    evid_by_obj: dict[int, str] = {}
    for oi, ci in o2c:
        if not _object_in_claim(objects[oi], claims[ci], text):
            continue
        o = objects[oi]
        if oi not in evid_by_obj:
            eid = acc.add_node(
                "EvidenceRef", {"raw": o.get("raw", ""), "class": o.get("class", ""),
                                **_span_props(o.get("start"), o.get("end"), page)},
                para_id)
            evid_by_obj[oi] = eid
        acc.add_edge(evid_by_obj[oi], claim_ids[ci], "SUPPORTS", para=para_id)

    # ScopeRef из digest.scope; APPLIES_WITHIN для claims, связанных с digest
    scope = art.get("digest", {}).get("scope") or {}
    c2d = _link_claims(links.get("claim_to_digest") or [])
    if scope and c2d:
        sid = acc.add_node("ScopeRef", {"scope": scope, "restricted": scope.get(
            "restricted", False)}, para_id)
        for ci in c2d:
            if ci < len(claim_ids):
                acc.add_edge(claim_ids[ci], sid, "APPLIES_WITHIN", para=para_id)
    return acc


def _build_g6(art: dict, reg: dict) -> _GraphAcc | None:
    """G6: Quantity->HAS_UNIT->Unit, химия/стали->Formula, Term/DEFINES."""
    objects = art.get("objects") or []
    relevant = [o for o in objects if str(o.get("class", "")).startswith(
        ("B_number", "B_chemical", "B_steel", "B_term", "B_abbr_def"))]
    if not relevant:
        return None
    acc = _GraphAcc("G6_artifact_symbol", reg)
    para_id = art.get("paragraph_id", "")
    acc.set_para(para_id)
    page = art.get("page")

    for o in relevant:
        cls = o.get("class", "")
        sp = _span_props(o.get("start"), o.get("end"), page)
        if cls == "B_number":
            qid = acc.add_node(
                "Quantity", {"raw": o.get("raw", ""),
                             "value_lower": o.get("value_lower"),
                             "value_upper": o.get("value_upper"),
                             "unit": o.get("unit"), **sp}, para_id)
            if o.get("unit"):
                uid = acc.add_node("Unit", {"unit": o["unit"]}, para_id)
                acc.add_edge(qid, uid, "HAS_UNIT",
                             {"unit": o["unit"]}, para_id)
        elif cls in ("B_chemical", "B_steel"):
            acc.add_node("Formula", {"raw": o.get("raw", ""), "class": cls, **sp},
                         para_id)
        elif cls == "B_term":
            acc.add_node("Term", {"term": o.get("term", o.get("raw", "")), **sp},
                         para_id)
        elif cls == "B_abbr_def":
            tid = acc.add_node("Term", {"abbr": o.get("abbr", ""),
                                        "expansion": o.get("expansion", ""), **sp},
                               para_id)
            did = acc.add_node("Definition", {"text": o.get("expansion", "")[:200]},
                               para_id)
            acc.add_edge(tid, did, "DEFINES",
                         {"abbr": o.get("abbr", "")}, para_id)
    return acc


# --------------------------------------------------------------------------
# сборка
# --------------------------------------------------------------------------

_BUILDERS = {
    "G3_discourse": _build_g3,
    "G4_argument": _build_g4,
    "G5_epistemic_projection": _build_g5,
    "G6_artifact_symbol": _build_g6,
    "G13_linguistic_structure": _build_g13,
    "G14_cohesion_information_flow": _build_g14,
    "G15_pragmatic_rhetorical": _build_g15,
}

# Графы реестра, не строящиеся из параграфного артефакта (причины).
_SKIPPED_REASONS = {
    "G1_document_structure": "doc-level: paragraph artifact не содержит дерева документа",
    "G2_writing_decomposition": "planning-level: нет WritingObjective/Goal в артефакте параграфа",
    "G7_citation_provenance": "нет citation-маркеров (CitationMarker/ArtifactRef) в гибридном артефакте",
    "G8_policy_constraint": "static policy registry: нет политик в артефакте параграфа",
    "G9_revision_dependency": "нет revision/review данных на уровне параграфа",
    "G10_execution": "event log: нет Run/Operation данных в артефакте",
    "G10_vocabulary": "отсутствует в реестре v0.3 (реестр определяет G10_execution); Term/Definition строятся в G6_artifact_symbol",
    "G11_forensics_fingerprint": "корпус/автор-уровень: нет AuthorProfile/verdict в артефакте параграфа",
    "G12_work_lineage": "генеалогия работ: нет Work/Edition/перевод-связей в артефакте",
    "G16_linguistic_memory": "session/corpus learning: нет данных в артефакте параграфа",
}


def validate_against_registry(graphs_dict: dict, registry: dict) -> list[dict]:
    """Проверка всех узлов/рёбер против реестра. Возвращает список нарушений."""
    violations: list[dict] = []
    for gid, g in (graphs_dict.get("graphs") or {}).items():
        reg = registry.get(gid)
        if reg is None:
            violations.append({"graph": gid, "kind": "graph", "value": gid,
                               "error": "graph not in registry"})
            continue
        for n in g.get("nodes", []):
            if n["type"] not in reg["node_types"]:
                violations.append({"graph": gid, "kind": "node",
                                   "value": n["type"]})
        for e in g.get("edges", []):
            if e["relation"] not in reg["edge_types"]:
                violations.append({"graph": gid, "kind": "edge",
                                   "value": e["relation"]})
    return violations


def build_paragraph_graphs(artifact: dict,
                           registry: dict | None = None) -> dict:
    """Построить графы реестра v0.3 из гибридного артефакта параграфа.

    Возвращает {"graphs": {gid: {"nodes", "edges"}}, "skipped": [...]}.
    Кидает ValueError, если какой-то узел/ребро не соответствует реестру.
    """
    reg = registry if registry is not None else load_graph_registry()
    para_id = artifact.get("paragraph_id", "")
    graphs: dict[str, dict] = {}
    built = 0
    for gid, builder in _BUILDERS.items():
        if gid not in reg:
            continue  # нет в реестре — не строим
        acc = builder(artifact, reg)
        if acc is None:
            continue
        res = acc.result()
        if not res["nodes"]:
            continue
        graphs[gid] = res
        built += 1

    violations = validate_against_registry({"graphs": graphs}, reg)
    if violations:
        raise ValueError("graph types not in registry v0.3: "
                         + json.dumps(violations, ensure_ascii=False))

    # skipped = все графы реестра, которые не построены на уровне параграфа
    skipped = [{"graph": gid, "reason": reason, "in_registry": gid in reg}
               for gid, reason in _SKIPPED_REASONS.items()
               if gid not in graphs]
    skipped.sort(key=lambda s: s["graph"])
    return {"graphs": graphs, "skipped": skipped, "paragraph_id": para_id,
            "built": built}


def graph_stats(graphs_dict: dict) -> dict:
    """По каждому графу: число узлов/рёбер (для отчёта)."""
    out: dict[str, dict] = {}
    for gid, g in (graphs_dict.get("graphs") or {}).items():
        out[gid] = {"nodes": len(g.get("nodes", [])),
                    "edges": len(g.get("edges", []))}
    return out


# --------------------------------------------------------------------------
# sqlite
# --------------------------------------------------------------------------

def to_sqlite(graphs_dict: dict, conn: sqlite3.Connection) -> None:
    """Сохранить узлы/рёбра в SQLite (таблицы graph_nodes, graph_edges).

    Поля: id/type/graph/props/para (para берётся из props каждого узла/ребра).
    """
    conn.execute(
        """CREATE TABLE IF NOT EXISTS graph_nodes (
               id TEXT, type TEXT, graph TEXT, props TEXT, para TEXT,
               PRIMARY KEY(id, para))""")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS graph_edges (
               src TEXT, dst TEXT, relation TEXT, graph TEXT, props TEXT, para TEXT,
               PRIMARY KEY(src, dst, relation, graph, para))""")
    para = str(graphs_dict.get("paragraph_id", ""))
    # идемпотентность: перед записью стираем данные этого параграфа,
    # чтобы повторный прогон не удваивал узлы/рёбра
    conn.execute("DELETE FROM graph_edges WHERE para = ?", (para,))
    conn.execute("DELETE FROM graph_nodes WHERE para = ?", (para,))
    for gid, g in (graphs_dict.get("graphs") or {}).items():
        for n in g.get("nodes", []):
            npara = n.get("props", {}).get("para") or para
            conn.execute(
                "INSERT OR REPLACE INTO graph_nodes(id,type,graph,props,para) "
                "VALUES (?,?,?,?,?)",
                (n["id"], n["type"], gid,
                 json.dumps(n.get("props", {}), ensure_ascii=False), npara))
        for e in g.get("edges", []):
            epara = e.get("props", {}).get("para") or para
            conn.execute(
                "INSERT OR REPLACE INTO graph_edges(src,dst,relation,graph,props,para) "
                "VALUES (?,?,?,?,?,?)",
                (e["src"], e["dst"], e["relation"], gid,
                 json.dumps(e.get("props", {}), ensure_ascii=False), epara))
    conn.commit()


if __name__ == "__main__":
    import sys as _sys
    _path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests", "fixtures", "sample_artifact.json")
    if len(_sys.argv) > 1:
        _path = _sys.argv[1]
    _art = json.load(open(_path, encoding="utf-8"))
    _g = build_paragraph_graphs(_art)
    print("built:", _g["built"], "graphs:", {k: len(v["nodes"]) for k, v in _g["graphs"].items()})
    print("skipped:", [s["graph"] for s in _g["skipped"]])
