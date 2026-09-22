"""Unified extraction pipeline (det + LLM + QC → graphs artifacts).

Собирает:
  1. Детерминированный слой (C1-C7, филология) — быстрая база.
  2. LLM-обогащение (gemma): claims/scope/objects.
  3. QC (claim_qa): grounding каждого извлечённого элемента + типизация.
  4. graph_builder: очищенные артефакты → 12 графов.

Принцип: LLM ПРЕДЛАГАЕТ, код ПРИНИМАЕТ/ОТКЛОНЯЕТ (span grounding).
Только GROUNDED элементы идут в графы.
"""

from __future__ import annotations

import json
import re
from typing import Any

from claim_qa import span_locate, classify_claim
from extraction_engine import extract_all as det_extract
from philologcal_layer import analyze as phil_analyze
from graph_builder import build_graphs
from llm_extractor import extract_claims_llm, extract_scope_llm, extract_objects_llm
from llm_philology import enrich_language
from linguo_harness import harness_analyze, to_dict as harness_to_dict
from context_analyzer import get_context, is_rhetorical_repetition, evidence_is_supported, connector_clean


def _is_table_like(text: str) -> bool:
    """Детектор таблиц: много чисел + хим.обозначений + колонок.

    Таблицы — не проза: LLM-claims из них ложные. Но числа/химия ценные.
    """
    import re
    nums = len(re.findall(r"\d+[.,]?\d*", text))
    chem = len(re.findall(r"\b\d{1,3}[А-ЯЁA-Z]{1,3}\d*", text))
    # много подряд значений (7+ чисел на абзац и редкие слова)
    words = len(re.findall(r"[а-яёa-zA-Z]+", text))
    return nums >= 15 and words > 5 and (nums / max(1, words)) > 0.5


def _overlaps(a1, a2, b1, b2) -> bool:
    """Перекрытие двух span; None-safe (None = unknown -> не обрабатывать)."""
    if a1 is None or a2 is None or b1 is None or b2 is None:
        return False
    return not (a2 <= b1 or b2 <= a1)


def _same_semantic(x_text: str, y_text: str) -> bool:
    """Семантический дубль: один текст является подстрокой другого (нормализованно).
    Fallback для случая, когда span недоступен (det-сущность без координат)."""
    if not x_text or not y_text:
        return False
    a = re.sub(r"\s+", " ", x_text.lower()).strip().rstrip(".,)(")[:50]
    b = re.sub(r"\s+", " ", y_text.lower()).strip().rstrip(".,)(")[:50]
    return a in b or b in a


def unified_extract(text: str, para_id: str = "PAR", page: int | None = None,
                    use_llm: bool = True) -> dict:
    """Полный конвейер: детерминированный + LLM + QC → графы."""
    # 1) детерминированный слой
    det = det_extract(text, para_id, page=page)
    phil = phil_analyze(text)

    # 1.5) LLM-лингвослой (фигуры/хрия/акценты) — с детерм. харнессом как контекстом
    lang_llm = {}
    harness = harness_analyze(text)  # падежи/ЧР/связки — код
    if use_llm:
        try:
            lang_llm = enrich_language(text, harness_context=harness_to_dict(harness))
        except Exception:
            lang_llm = {"error": "lang_llm_failed"}

    claims_ok = []
    objects_ok = []
    is_table = _is_table_like(text)

    # 2) LLM claims (если включен) — но НЕ для таблиц (ложные claims)
    if use_llm and not is_table:
        try:
            llm_claims = extract_claims_llm(text)
            for c in llm_claims:
                if "error" in c:
                    continue
                # QC: span grounding
                loc = span_locate(c.get("text", ""), text)
                if loc["method"] == "none":
                    continue  # отбросить галлюцинацию/пересказ
                cls = classify_claim(c.get("text", ""), c.get("claim_kind", "OBSERVATIONAL"))
                claims_ok.append({
                    "text": c.get("text", ""),
                    "claim_kind": c.get("claim_kind", cls["kind"]),
                    "role": c.get("role", cls["role"]),
                    "strength": c.get("strength", "medium"),
                    "start": loc["start"], "end": loc["end"], "page": page,
                    "qa_status": "GROUNDED", "qa_method": loc["method"],
                })
        except Exception:
            pass

    # 3) LLM объекты (дополнительно к детерминированным) + QC
    llm_obj_ids = set()
    if use_llm and not is_table:
        try:
            for o in extract_objects_llm(text):
                loc = span_locate(o.get("raw", ""), text)
                if loc["method"] == "none":
                    continue
                key = o.get("raw", "").lower().strip()
                if key in llm_obj_ids:
                    continue
                llm_obj_ids.add(key)
                objects_ok.append({
                    "class": "B_llm_" + (o.get("type", "object")),
                    "raw": o.get("raw", ""),
                    "start": loc["start"], "end": loc["end"],
                })
        except Exception:
            pass

    # 4) QC для детерминированных объектов (проверка, что они в тексте)
    for o in det.objects:
        raw = o.get("raw", "")
        if not raw:
            continue
        key = raw.lower().strip()
        if key in llm_obj_ids:
            continue
        loc = span_locate(raw, text)
        if loc["method"] != "none":
            o["start"] = loc["start"] or o.get("start")
            o["end"] = loc["end"] or o.get("end")
            objects_ok.append(o)

    # 5) дет-claims (эвристика) — тоже через QC (только grounded) + DEDUP с LLM
    llm_spans = [(c.get("start"), c.get("end")) for c in claims_ok if c.get("start") is not None]
    for c in det.claims:
        loc = span_locate(c.get("text", ""), text)
        if loc["method"] == "none":
            continue
        # skip если пересекается с LLM-claim (LLM точнее)
        if any(_overlaps(loc["start"], loc["end"], s, e) for s, e in llm_spans):
            continue
        cls = classify_claim(c.get("text", ""))
        claims_ok.append({
            "text": c.get("text", ""), "claim_kind": cls["kind"], "role": cls["role"],
            "start": c.get("start") or loc["start"], "end": c.get("end") or loc["end"],
            "page": page, "qa_status": "GROUNDED", "qa_method": loc["method"],
        })

    # 6) scope (LLM) — с координатами; для таблиц scope не нужен
    scope_ok = []
    if use_llm and not is_table:
        try:
            for s in extract_scope_llm(text):
                loc = span_locate(s.get("span") or s.get("value", ""), text)
                if loc["method"] == "none":
                    continue
                scope_ok.append({**s, "start": loc["start"], "end": loc["end"]})
        except Exception:
            pass

    # Синтез лингвослоя: детерминированный + LLM (LLM дополняет; dedup по span-перекрытию)
    # сначала локализуем детерминированные сущности (span) для dedup
    for f in phil.figures:
        fs = span_locate(f.get("text", ""), text)
        f["start"] = fs.get("start"); f["end"] = fs.get("end")
    for c in phil.chreia:
        cs = span_locate(c.get("text", ""), text)
        c["start"] = cs.get("start"); c["end"] = cs.get("end")
    for e in phil.emphasis:
        es = span_locate(e.get("text", ""), text)
        e["start"] = es.get("start"); e["end"] = es.get("end")
    all_figures = list(phil.figures)
    all_chreia = [{"part": p.get("part"), "text": p.get("text", "")} for p in phil.chreia]
    all_connectors = [{"связка": c.get("связка", "")} for c in phil.connectors]
    all_emphasis = list(phil.emphasis)

    # ———— КОНТЕКСТНЫЙ ФИЛЬТР (как researcher EvidenceSpan: окрестности, не отруб) ————
    # repetition: только риторический повтор этого слова (не термин)
    filtered_figures = []
    for f in all_figures:
        if f.get("type") == "repetition":
            w = (f.get("words") or [""])[0]
            widx = text.lower().find(w.lower())
            ctx = get_context(text, max(0, widx), max(0, widx + len(w)))
            if is_rhetorical_repetition(w, ctx.sentence, ctx):
                filtered_figures.append(f)
        else:
            filtered_figures.append(f)
    all_figures = filtered_figures
    # evidence-хрия: только если источник близко (не просто число)
    filtered_chreia = []
    for c in all_chreia:
        if c.get("part") == "evidence":
            frag = c.get("text", "")
            idx = text.find(frag)
            ctx = get_context(text, max(0, idx), max(0, idx + len(frag)))
            has_num = bool(re.search(r"\d+[.,]?\d*\s*[%°]|МПа|мкм|мм\b", frag))
            if evidence_is_supported(ctx, has_num):
                filtered_chreia.append(c)
        else:
            filtered_chreia.append(c)
    all_chreia = filtered_chreia
    # connectors: только целые слова (не substring внутри «карбидов»)
    filtered_conn = []
    for c in all_connectors:
        mk = c.get("связка", "")
        idx = text.lower().find(mk.lower())
        ctx = get_context(text, max(0, idx), max(0, idx + len(mk)))
        if connector_clean(ctx, mk):
            filtered_conn.append(c)
    all_connectors = filtered_conn
    if lang_llm and "error" not in lang_llm:
        for f in lang_llm.get("figures", []):
            fspan = span_locate(f.get("text", ""), text)
            dup = any(
                _overlaps(fspan.get("start"), fspan.get("end"), s.get("start"), s.get("end"))
                or _same_semantic(f.get("text", ""), s.get("text", ""))
                for s in all_figures if s.get("type") == f.get("type"))
            if not dup:
                all_figures.append({"type": f.get("type", "figure"),
                                    "text": f.get("text", ""), "qa": "llm",
                                    "start": fspan.get("start"), "end": fspan.get("end")})
        for c in lang_llm.get("chreia_parts", []):
            cspan = span_locate(c.get("text", ""), text)
            dup = any(
                _overlaps(cspan.get("start"), cspan.get("end"), s.get("start"), s.get("end"))
                or _same_semantic(c.get("text", ""), s.get("text", ""))
                for s in all_chreia if s.get("part") == c.get("part"))
            if not dup:
                all_chreia.append({"part": c.get("part"), "text": c.get("text", ""), "qa": "llm",
                                   "start": cspan.get("start"), "end": cspan.get("end")})
        for c in lang_llm.get("connectors", []):
            mk = c.get("marker") or c.get("text", "")
            if not any(x.get("связка", "").lower() == mk.lower() for x in all_connectors):
                all_connectors.append({"связка": mk})
        for e in lang_llm.get("emphasis", []):
            espan = span_locate(e.get("text", ""), text)
            dup = any(
                _overlaps(espan.get("start"), espan.get("end"), x.get("start"), x.get("end"))
                or _same_semantic(e.get("text", ""), x.get("text", ""))
                for x in all_emphasis if x.get("type") == e.get("type"))
            if not dup:
                all_emphasis.append({"type": e.get("type", "emphasis"), "text": e.get("text", ""),
                                     "start": espan.get("start"), "end": espan.get("end")})

    # 7) графы из очищенных артефактов
    graphs = build_graphs(
        {"claims": claims_ok, "objects": objects_ok},
        {"connectors": all_connectors, "chreia": all_chreia,
         "figures": all_figures, "morphology": phil.morphology},
        para_id,
    )

    return {
        "paragraph_id": para_id,
        "claims": claims_ok,
        "objects": objects_ok,
        "scope": scope_ok,
        "philology": {"figures": all_figures, "chreia": all_chreia,
                      "connectors": all_connectors, "morphology": phil.morphology,
                      "emphasis": all_emphasis, "lang_llm_error": lang_llm.get("error") if isinstance(lang_llm, dict) else None,
                      "harness": harness_to_dict(harness)},
        "graphs": graphs,
        "tail": det.tail,
    }


def to_yaml(result: dict) -> str:
    import yaml
    # уберём большие поля для компактности
    out = {**result, "graphs": {"nodes": result["graphs"]["nodes"],
                                "edges": result["graphs"]["edges"]}}
    return yaml.dump(out, allow_unicode=True, sort_keys=False, default_flow_style=False)