# -*- coding: utf-8 -*-
"""writer_core.dom_builder — связка writer_core с DOM-контрактом прослеживаемости.

DOM YAML (источник истины литературного объекта) по контракту
`${OPENCODE_HARNESS_ROOT}/shared/writer-traceability-contract.md`:

    product / structure(chapters->sections->paragraphs) / claims[] / graphs[] /
    uncertainty{} / sources[]

Модуль строит DOM из НАШЕГО слоя writer_core:
  - plan --topic (structure_plan.json) -> DOM structure (11 секций автореферата
    -> главы диссертации);
  - claims hybrid_extract -> DOM claims[] (id C-xxx, kind по числу/каузальности,
    verification по qa_status);
  - графы graph_builder_hybrid (G3-G15) -> DOM graphs[] (kind: support/derivation/
    conflict/citation_chain);
  - uncertainty-шкала ПО ПРОИСХОЖДЕНИЮ (raw_data/эксперимент -> high,
    published/автореферат -> low, direct_method -> low, indirect_method -> medium,
    modeling -> medium-high, hypothesis -> high).

Созданный DOM совместим с детерминированным цитатным гейтом
`${OPENCODE_HARNESS_ROOT}/scripts/writer/citation_trace.py` (проходит _check_dom:
product, structure.chapters, sources, claims непустые, id уникальны).

Только stdlib + PyYAML. Детерминированно, без LLM. Fail-closed: битый ввод ->
ValueError наружу (CLI превращает в JSON-ошибку + exit 2).
"""
from __future__ import annotations

import copy
import os
import re
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


# ---------------------------------------------------------------------------
# маппинг 11 секций автореферата -> главы диссертации (детерминированный)
# ---------------------------------------------------------------------------

_SECTION_TO_CHAPTER: dict[str, str] = {
    "TITLE": "Титул",
    "RELEVANCE": "Введение",
    "OBJECT_SUBJECT": "Введение",
    "TOPIC_STATE": "Введение",
    "GOAL": "Введение",
    "TASKS": "Введение",
    "NOVELTY": "Введение",
    "METHODS": "Методы",
    "RESULTS": "Результаты",
    "CONCLUSION": "Выводы",
    "LITERATURE": "Литература",
}

_CHAPTER_ORDER: list[str] = [
    "Титул", "Введение", "Методы", "Результаты", "Выводы", "Литература",
]

_SECTION_TITLES: dict[str, str] = {
    "TITLE": "Титул",
    "RELEVANCE": "Актуальность темы",
    "OBJECT_SUBJECT": "Объект и предмет исследования",
    "TOPIC_STATE": "Состояние исследований",
    "GOAL": "Цель работы",
    "TASKS": "Задачи исследования",
    "NOVELTY": "Научная новизна",
    "METHODS": "Методы исследования",
    "RESULTS": "Результаты",
    "CONCLUSION": "Выводы",
    "LITERATURE": "Список литературы",
}


# ---------------------------------------------------------------------------
# helpers YAML
# ---------------------------------------------------------------------------

def _require_yaml() -> None:
    if yaml is None:
        raise RuntimeError("PyYAML required (pip install PyYAML)")


def load_template(template_path: str) -> dict:
    """YAML DOM-шаблон -> dict (копия-источник для build_dom)."""
    _require_yaml()
    if not os.path.exists(template_path):
        raise ValueError(f"dom: шаблон не найден: {template_path}")
    with open(template_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"dom: шаблон {template_path} должен быть mapping")
    return data


def _write_yaml(path: str, dom: dict) -> None:
    _require_yaml()
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = dict(dom)
    payload.pop("_validation", None)  # служебное поле не попадает в артефакт
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)


# ---------------------------------------------------------------------------
# 1. plan (structure_plan.json) -> DOM structure
# ---------------------------------------------------------------------------

def plan_to_dom(plan: dict) -> dict:
    """structure_plan.json (наш plan --topic) -> DOM structure.

    11 секций автореферата -> главы диссертации:
      TITLE -> Титул;
      RELEVANCE/OBJECT_SUBJECT/TOPIC_STATE/GOAL/TASKS/NOVELTY -> Введение;
      METHODS -> Методы; RESULTS -> Результаты; CONCLUSION -> Выводы;
      LITERATURE -> Литература.
    Каждый слот секции (ClaimSlot/ArtifactSlot) -> paragraph с claim-ожиданием
    (expected/slot_id/kind) и пустым claims[] до верификации.
    """
    sections = plan.get("sections") or []
    slots = plan.get("slots") or []

    slots_by_section: dict[str, list[dict]] = {}
    for s in slots:
        if isinstance(s, dict) and s.get("section"):
            slots_by_section.setdefault(s["section"], []).append(s)

    # уникальные section_type в порядке плана
    seen: list[str] = []
    for sec in sections:
        st = sec.get("section_type") if isinstance(sec, dict) else None
        if st and st not in seen:
            seen.append(st)

    chapters: list[dict] = []
    ch_idx = 1
    for ch_title in _CHAPTER_ORDER:
        ch_sections = [st for st in seen if _SECTION_TO_CHAPTER.get(st) == ch_title]
        if not ch_sections:
            continue
        ch: dict = {"id": f"CH-{ch_idx:02d}", "title": ch_title, "sections": []}
        sec_idx = 1
        for st in ch_sections:
            sec: dict = {
                "id": f"SEC-{ch_idx:02d}-{sec_idx:02d}",
                "title": _SECTION_TITLES.get(st, st),
                "paragraphs": [],
            }
            for pi, slot in enumerate(slots_by_section.get(st, [])):
                sec["paragraphs"].append({
                    "id": f"PAR-{ch_idx:02d}-{sec_idx:02d}-{pi + 1:02d}",
                    "claims": [],
                    "text": "",
                    "expected": slot.get("expected"),
                    "slot_id": slot.get("id"),
                    "kind": slot.get("kind"),
                })
            ch["sections"].append(sec)
            sec_idx += 1
        chapters.append(ch)
        ch_idx += 1
    return {"chapters": chapters}


# ---------------------------------------------------------------------------
# 2. claims (hybrid_extract) -> DOM claims[]
# ---------------------------------------------------------------------------

_NUMERIC_RE = re.compile(
    r"\d+[,.]\d+\s*[%°]|\d+\s*(?:МПа|ГПа|мкм|мм|мг|[а-яёa-zA-Z]+/|м/с|кг/га|%|°C)"
)
_CAUSAL_RE = re.compile(
    r"(вызывает|приводит|обусловл|влияет|снижает|повышает|увеличивает|"
    r"уменьшает|способствует|определяет|оказывает|достигает|образует)",
    re.IGNORECASE,
)

_QA_TO_VERDICT = {"GROUNDED": "SUPPORTED", "PROPOSED": "OPEN", "UNGROUNDED": "UNSUPPORTED"}
_QA_TO_CONF = {"GROUNDED": 0.8, "PROPOSED": 0.5, "UNGROUNDED": 0.2}


def _claim_kind(text: str) -> str:
    """kind по наличию числа/каузальности: factual / derived / assumed."""
    t = text or ""
    if _NUMERIC_RE.search(t):
        return "factual"
    if _CAUSAL_RE.search(t):
        return "derived"
    return "assumed"


def _claim_text(c: dict) -> str:
    return re.sub(r"\s+", " ", str(
        c.get("text") or c.get("raw_span") or c.get("proposition") or ""
    )).strip()


def claims_to_dom(claims: list[dict]) -> list[dict]:
    """Наши claims (hybrid_extract: {text, qa_status, span}) -> DOM claims[].

    id: C-001..; kind: factual/derived/assumed (по числу/каузальности);
    evidence=[] (пусто до верификации); verification: verdict по qa_status
    (GROUNDED->SUPPORTED, PROPOSED->OPEN, UNGROUNDED->UNSUPPORTED), confidence
    дефолт 0.5.
    """
    out: list[dict] = []
    for i, c in enumerate(claims, start=1):
        text = _claim_text(c)
        qa = str(c.get("qa_status") or "PROPOSED")
        verdict = _QA_TO_VERDICT.get(qa, "OPEN")
        conf = _QA_TO_CONF.get(qa, 0.5)
        out.append({
            "id": f"C-{i:03d}",
            "text": text,
            "kind": _claim_kind(text),
            "evidence": [],
            "verification": {
                "verdict": verdict,
                "confidence": conf,
            },
        })
    return out


# ---------------------------------------------------------------------------
# 3. graphs (graph_builder_hybrid) -> DOM graphs[]
# ---------------------------------------------------------------------------

# (graph_key, relation) -> DOM kind
_GRAPH_KIND_MAP: dict[tuple[str, str], str] = {
    ("G4_argument", "CONCLUDES"): "derivation",
    ("G5_epistemic_projection", "DERIVED_FROM"): "derivation",
    ("G6_artifact_symbol", "DERIVED_FROM"): "derivation",
    ("G3_discourse", "LEADS_TO"): "derivation",
    ("G5_epistemic_projection", "SUPPORTS"): "support",
    ("G5_epistemic_projection", "PARTIALLY_SUPPORTS"): "support",
    ("G3_discourse", "MOTIVATES"): "support",
    ("G5_epistemic_projection", "CONTRADICTS"): "conflict",
    ("G14_cohesion_information_flow", "REFERS_TO"): "citation_chain",
    ("G14_cohesion_information_flow", "COREFERS_WITH"): "citation_chain",
}

_DOM_RELATION = {
    "derivation": "derived_from",
    "support": "supports",
    "conflict": "contradicts",
    "citation_chain": "depends_on",
}


def _iter_graph_edges(graphs: Any):
    """Нормализация входа -> (graph_key, edge) для всех графов.

    Принимает: одиночный вывод build_paragraph_graphs
    {"graphs": {"G4_argument": {nodes, edges}}}; CLI graphs.json
    {"graphs": {"para_id": {"graphs": {...}}}}; или голый dict графов.
    """
    if not isinstance(graphs, dict):
        return
    gs = graphs.get("graphs", graphs)
    if not isinstance(gs, dict):
        return
    for gk, gv in gs.items():
        if isinstance(gv, dict) and "edges" in gv:
            for e in gv.get("edges") or []:
                if isinstance(e, dict):
                    yield gk, e
        elif isinstance(gv, dict) and isinstance(gv.get("graphs"), dict):
            for gk2, gv2 in gv["graphs"].items():
                if isinstance(gv2, dict):
                    for e in gv2.get("edges") or []:
                        if isinstance(e, dict):
                            yield gk2, e


def graphs_to_dom(graphs: dict) -> list[dict]:
    """Наши графы (graph_builder_hybrid G3-G15) -> DOM graphs[].

    kind: support (G5 SUPPORTS/PARTIALLY_SUPPORTS), derivation (G4 CONCLUDES,
    G5/G6 DERIVED_FROM, G3 LEADS_TO), conflict (G5 CONTRADICTS),
    citation_chain (G14 REFERS_TO/COREFERS_WITH). edges: from/to/relation.
    """
    buckets: dict[str, list[dict]] = {}
    for gk, e in _iter_graph_edges(graphs):
        kind = _GRAPH_KIND_MAP.get((gk, e.get("relation")))
        if kind is None:
            continue
        buckets.setdefault(kind, []).append({
            "from": str(e.get("src") or ""),
            "to": str(e.get("dst") or ""),
            "relation": _DOM_RELATION.get(kind, "depends_on"),
        })

    out: list[dict] = []
    gi = 1
    for kind in ["support", "derivation", "conflict", "citation_chain"]:
        edges = buckets.get(kind, [])
        if not edges:
            continue
        out.append({"id": f"GRAPH-{gi:02d}", "kind": kind, "edges": edges})
        gi += 1
    return out


# ---------------------------------------------------------------------------
# 4. uncertainty-шкала ПО ПРОИСХОЖДЕНИЮ
# ---------------------------------------------------------------------------

_PROVENANCE_MAP: list[tuple[tuple[str, ...], str, str]] = [
    (("raw_data", "raw", "эксперимент", "experiment", "черновик первичных данных",
      "первичные данные", "draft", "черновик"), "high", "первичные данные"),
    (("published", "опубликовано", "автореферат", "защищённая диссертация",
      "диссертация", "статья", "publication", "thesis", "paper"), "low",
     "опубликовано/защищено"),
    (("direct_method", "direct", "прямой метод"), "low", "прямой метод"),
    (("indirect_method", "indirect", "косвенный метод"), "medium", "косвенный метод"),
    (("modeling", "model", "моделирование"), "medium-high", "моделирование"),
    (("hypothesis", "гипотеза"), "high", "гипотеза"),
]


def uncertainty_provenance(source_kind: str) -> dict:
    """Неопределённость ПО ПРОИСХОЖДЕНИЮ источника -> {level, note, provenance}.

    raw_data/эксперимент/черновик -> high (первичные данные);
    published/автореферат/защищённая диссертация/статья -> low;
    direct_method -> low; indirect_method -> medium; modeling -> medium-high;
    hypothesis -> high. Неизвестное происхождение -> medium.
    """
    sk = re.sub(r"\s+", " ", str(source_kind or "")).strip().lower()
    for keys, level, note in _PROVENANCE_MAP:
        if sk in keys:
            return {"level": level, "note": note, "provenance": str(source_kind)}
    return {"level": "medium", "note": "неизвестное происхождение",
            "provenance": str(source_kind)}


def _sources_and_uncertainty(source_kinds: list[str]) -> tuple[list[dict], dict]:
    """source_kinds -> (DOM sources[], uncertainty{} по происхождению).

    Каждый источник: id S-00N, ref по kind, kind primary/secondary;
    uncertainty[S-00N] = uncertainty_provenance(kind).
    """
    sources: list[dict] = []
    uncertainty: dict[str, dict] = {}
    for i, kind in enumerate(source_kinds, start=1):
        sid = f"S-{i:03d}"
        sources.append({
            "id": sid,
            "ref": f"источник: {kind}",
            "doi": None,
            "url": None,
            "kind": "primary",
            "accessed": "",
        })
        uncertainty[sid] = uncertainty_provenance(kind)
    return sources, uncertainty


# ---------------------------------------------------------------------------
# 5. build_dom — собрать DOM по контракту + сохранить YAML
# ---------------------------------------------------------------------------

def _next_free_id(existing: set[str], base: str) -> str:
    """Ближайший свободный id с префиксом base относительно множества existing.

    base='S-' -> S-001, S-002, ...; base='C-9001' -> C-9001, C-9002, ...
    (номер в base сохраняется, если он свободен). Гарантирует уникальность.
    """
    m = re.match(r"^(.*?)(\d+)$", base)
    if m:
        prefix, num = m.group(1), int(m.group(2))
    else:
        prefix, num = base, 1
    while f"{prefix}{num:03d}" in existing:
        num += 1
    return f"{prefix}{num:03d}"


def build_dom(template_path: str, plan: dict | None = None,
              claims: list[dict] | None = None,
              graphs: dict | None = None,
              source_kinds: list[str] | None = None,
              qwen_extra: dict | None = None,
              out_path: str | None = None) -> dict:
    """Собрать DOM YAML по контракту из нашего слоя и (опц.) сохранить.

    template_path  — DOM-шаблон (источник: product/каркас structure/claims/
                     graphs/uncertainty/sources);
    plan           — structure_plan.json (наш plan --topic) -> structure;
    claims         — claims hybrid_extract -> claims[];
    graphs         — графы graph_builder_hybrid -> graphs[];
    source_kinds   — происхождение источников -> sources[] + uncertainty{};
    qwen_extra     — результат qwen_to_dom (evidence-корпус литературы:
                     {sources, claims, graphs, uncertainty, errors}) — сливается
                     с существующими claims/sources/uncertainty;
    out_path       — если задан, сохранить DOM YAML (без служебного _validation).

    Возвращает собранный DOM (dict) с ключом _validation (errors/valid).
    """
    dom = copy.deepcopy(load_template(template_path))

    # product
    if plan is not None:
        topic = ((plan.get("meta") or {}).get("topic")
                 or (plan.get("source") or {}).get("topic") or "")
        dom.setdefault("product", {})["title"] = topic
        dom["product"]["id"] = "PROD-001"

    # structure
    if plan is not None:
        dom["structure"] = plan_to_dom(plan)

    # claims
    if claims:
        dom["claims"] = claims_to_dom(claims)

    # graphs
    if graphs:
        dom["graphs"] = graphs_to_dom(graphs)

    # sources + uncertainty (по происхождению)
    if source_kinds:
        srcs, unc = _sources_and_uncertainty(source_kinds)
        dom["sources"] = srcs
        dom["uncertainty"] = unc

    # Qwen evidence-корпус (литература): слить sources/claims/uncertainty
    if qwen_extra:
        # TD-087: dedup источников — qwen генерирует S-001.. с нуля и может
        # совпасть с S-xxx из plan/_sources_and_uncertainty/шаблона. Перенумеруем
        # коллизии монотонно (максимальный существующий номер + 1) и правим
        # evidence[].source_id у qwen-claims, ссылающихся на переименованный sid.
        dom.setdefault("sources", [])
        dom.setdefault("claims", [])
        existing_sids = {str(s.get("id")) for s in dom["sources"]
                         if isinstance(s, dict) and s.get("id")}
        sid_remap: dict[str, str] = {}
        qwen_sources: list[dict] = []
        for s in (qwen_extra.get("sources") or []):
            if not isinstance(s, dict):
                continue
            sid = str(s.get("id") or "")
            if sid and sid in existing_sids:
                new_sid = _next_free_id(existing_sids, sid)
                s = dict(s)
                s["id"] = new_sid
                sid_remap[sid] = new_sid
            if s.get("id"):
                existing_sids.add(str(s["id"]))
            qwen_sources.append(s)
        dom["sources"].extend(qwen_sources)

        # перенумерация claims: единый монотонный генератор ID (TD-088).
        # qwen_to_dom даёт локально монотонные C-001..; коллизии с шаблоном/plan
        # перенумеровываются продолжением после максимального существующего номера
        # -> итог строго монотонный (C-001..C-00N), без C-9XXX и без C-XXXb/c.
        existing_ids = {str(c.get("id")) for c in dom["claims"]
                        if isinstance(c, dict) and c.get("id")}
        max_cnum = 0
        for cid in existing_ids:
            m = re.match(r"^C-(\d+)$", cid)
            if m:
                max_cnum = max(max_cnum, int(m.group(1)))
        id_map: dict[str, str] = {}
        qwen_claims: list[dict] = []
        for c in (qwen_extra.get("claims") or []):
            cid = str(c.get("id") or "")
            if cid in existing_ids:
                max_cnum += 1
                new_id = _next_free_id(existing_ids, f"C-{max_cnum:03d}")
                id_map[cid] = new_id
            else:
                new_id = cid
            # TD-087: обновить ссылки evidence[].source_id на переименованные sids
            c = dict(c)
            c["id"] = new_id
            if sid_remap:
                ev = []
                for e in (c.get("evidence") or []):
                    if isinstance(e, dict):
                        e = dict(e)
                        src_id = str(e.get("source_id") or "")
                        if src_id in sid_remap:
                            e["source_id"] = sid_remap[src_id]
                    ev.append(e)
                c["evidence"] = ev
            qwen_claims.append(c)
            existing_ids.add(new_id)
        dom["claims"].extend(qwen_claims)
        dom.setdefault("graphs", []).extend(qwen_extra.get("graphs") or [])
        # uncertainty: применить полный маппинг id (старый -> новый) к копии —
        # маппинг может пересекаться (C-001->C-003 и C-003->C-005), поэтому
        # строим новый dict, а не мутируем исходный
        qunc = {}
        for old_id, val in (qwen_extra.get("uncertainty") or {}).items():
            qunc[id_map.get(old_id, old_id)] = val
        dom["uncertainty"] = {**(dom.get("uncertainty") or {}), **qunc}
        if qwen_extra.get("errors"):
            dom.setdefault("_qwen_errors", qwen_extra["errors"])

    errs = validate_dom(dom)
    dom["_validation"] = {"errors": errs, "valid": not errs}

    if out_path:
        _write_yaml(out_path, dom)
    return dom


# ---------------------------------------------------------------------------
# 6. validate_dom — самопроверка по контракту
# ---------------------------------------------------------------------------

def validate_dom(dom: dict) -> list[str]:
    """Самопроверка DOM по контракту (product, structure.chapters, id уникальны).

    Возвращает список ошибок ([] = валиден). Fail-closed: структурно битый
    DOM -> ошибки в списке, а не исключение.
    """
    errs: list[str] = []
    if not isinstance(dom, dict) or not dom.get("product"):
        errs.append("product missing")
    structure = dom.get("structure")
    if not isinstance(structure, dict) or not isinstance(structure.get("chapters"), list):
        errs.append("structure.chapters must be list")

    claims = dom.get("claims")
    if not isinstance(claims, list):
        errs.append("claims must be list")
    else:
        c_ids = [str(c.get("id")) for c in claims
                 if isinstance(c, dict) and c.get("id")]
        if len(c_ids) != len(set(c_ids)):
            errs.append("duplicate claim id")

    sources = dom.get("sources")
    if not isinstance(sources, list):
        errs.append("sources must be list")
    else:
        s_ids = [str(s.get("id")) for s in sources
                 if isinstance(s, dict) and s.get("id")]
        if len(s_ids) != len(set(s_ids)):
            errs.append("duplicate source id")

    graphs = dom.get("graphs")
    if graphs is not None and not isinstance(graphs, list):
        errs.append("graphs must be list")
    return errs


# ---------------------------------------------------------------------------
# 7. qwen_to_dom — evidence-мост из Qwen_yaml (карточки статей литературы)
# ---------------------------------------------------------------------------

_UNCERTAIN_MARKERS = ("по-видимому", "по всей видимости", "вероятно", "возможно",
                      "предположительно", "можно говорить", "по-видимому,")
_STRONG_MARKERS = ("установлен", "показано", "доказано", "наблюдается", "определён",
                   "получен", "выявлен")


def _qwen_claim_kind(text: str) -> str:
    low = text.lower()
    if any(m in low for m in _STRONG_MARKERS):
        return "factual"
    if any(m in low for m in _UNCERTAIN_MARKERS):
        return "assumed"
    return "derived"


def qwen_to_dom(yaml_paths: list[str]) -> dict:
    """Qwen_yaml карточки статей -> DOM-блоки {sources, claims, graphs, uncertainty}.

    Каждый файл (reference + conclusions + experiments) -> source S-xxx (DOI)
    + claims C-xxx (conclusions, kind по маркерам) + uncertainty.
    Нумерация ЛОКАЛЬНАЯ и независимая: sources S-001.. (si), claims C-001..
    (ci, монотонный, без chr-суффиксов). Глобальную перенумерацию при слиянии
    с plan/шаблоном выполняет build_dom (dedup S-xxx и C-xxx).
    Fail-closed: битый файл пропускается с errors.
    """
    _require_yaml()
    sources: list[dict] = []
    claims: list[dict] = []
    uncertainty: dict = {}
    graphs: list[dict] = []
    errors: list[str] = []
    # TD-088: независимые монотонные счётчики — si для sources, ci для claims.
    # Раньше один счётчик si использовался и для sources, и для claims, из-за чего
    # при нескольких conclusions появлялись C-001b/C-001c (chr-суффиксы). Теперь
    # каждый conclusion получает уникальный монотонный C-{ci:03d} без суффиксов.
    si = 0
    ci = 0

    for path in yaml_paths:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                card = yaml.safe_load(fh) or {}
        except Exception as e:
            errors.append(f"{os.path.basename(path)}: {type(e).__name__}: {e}")
            continue
        if not isinstance(card, dict):
            errors.append(f"{os.path.basename(path)}: not mapping")
            continue
        ref = card.get("reference") or {}
        sid = f"S-{si + 1:03d}"
        si += 1
        sources.append({
            "id": sid,
            "ref": (str(ref.get("title") or "") + ". "
                    + ", ".join(str(a) for a in (ref.get("authors") or [])) + " "
                    + str(ref.get("journal") or "") + ", " + str(ref.get("year") or "")),
            "doi": ref.get("doi"),
            "url": None,
            "kind": "primary" if ref.get("doi") else "secondary",
            "accessed": "2026-09-07",
        })
        # conclusions -> claims (уникальные монотонные id на каждый conclusion)
        for concl in card.get("conclusions") or []:
            if not isinstance(concl, str) or not concl.strip():
                continue
            ci += 1
            cid = f"C-{ci:03d}"
            claims.append({
                "id": cid,
                "text": concl.strip(),
                "kind": _qwen_claim_kind(concl),
                "evidence": [{"source_id": sid, "span": "conclusions"}],
                "verification": {"verdict": "OPEN", "confidence": 0.5},
            })
            uncertainty[cid] = {
                "level": "low" if _qwen_claim_kind(concl) == "factual" else
                         ("high" if _qwen_claim_kind(concl) == "assumed" else "medium"),
                "note": f"из Qwen_yaml карточки {os.path.basename(path)}",
            }
    return {"sources": sources, "claims": claims, "graphs": graphs,
            "uncertainty": uncertainty, "errors": errors}


# ---------------------------------------------------------------------------
# 8. qa_uncertainty — авторская маркировка неопределённости (Q&A автореферата)
# ---------------------------------------------------------------------------

def qa_uncertainty(qa_text: str, claims: list[dict]) -> dict:
    """Q&A автореферата (маркировка автора) -> override uncertainty для claims.

    Автор в Q&A явно разделяет: «однозначность обеспечивается» (низкая
    неопределённость, measured) vs «интерпретация»/«по-видимому» (высокая).
    Правило: если в Q&A есть оба паттерна — для каждого claim level выводится
    из его собственных маркеров, но ПОДТВЕРЖДАЕТСЯ наличием соответствующего
    паттерна в Q&A (автор использует тот же стиль маркировки). Если паттернов
    в Q&A нет — вернуть {} (нет базы для маркировки).
    """
    if not qa_text or not claims:
        return {}
    low = qa_text.lower()
    has_certain = any(m in low for m in ("однозначн", "жёсткими ограничениями",
                                         "обеспечивается", "не вызывает сомнений"))
    has_uncertain = any(m in low for m in ("интерпрет", "по-видимому",
                                           "предположительно", "можно говорить",
                                           "нельзя исключить"))
    if not (has_certain or has_uncertain):
        return {}
    out: dict = {}
    for c in claims:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "")
        txt = str(c.get("text") or "").lower()
        if not cid or not txt:
            continue
        if any(m in txt for m in _STRONG_MARKERS) and has_certain:
            out[cid] = {"level": "low", "note": "автор маркирует однозначность (Q&A паттерн)"}
        elif any(m in txt for m in _UNCERTAIN_MARKERS) and has_uncertain:
            out[cid] = {"level": "high", "note": "автор маркирует интерпретацию (Q&A паттерн)"}
        elif has_certain and has_uncertain:
            out[cid] = {"level": "medium", "note": "смешанная авторская маркировка (Q&A)"}
    return out


if __name__ == "__main__":
    print(__import__("json").dumps({
        "module": "writer_core.dom_builder",
        "functions": ["load_template", "plan_to_dom", "claims_to_dom",
                      "graphs_to_dom", "uncertainty_provenance", "build_dom",
                      "validate_dom", "qwen_to_dom", "qa_uncertainty"],
    }, ensure_ascii=False, indent=2))