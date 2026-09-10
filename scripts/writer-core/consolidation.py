# -*- coding: utf-8 -*-
"""M_CONSOLIDATE — консолидация графов знаний по версиям автореферата (v1–v12).

Назначение: собрать гибридные графы (graph_builder_hybrid) всех версий
документа в единый отчёт эволюции — динамические метрики для будущего
написания/рецензирования: как менялся объём утверждений (claims), grounded,
объектов, узлов/рёбер графов, структура секций, каузальная аргументация,
scope-неоднозначности, gaps и попарная косинусная схожесть версий.

Конвейер одной версии (collect_version):
  1) hybrid_extract_document(path, max_paragraphs=100) — гибридные артефакты
     параграфов (v2 claims/objects/discourse + v0.3 digest + links);
  2) структура: build_document_tree + build_writing_plan + fill_slots из
     structure_annotator — это ТОТ ЖЕ конвейер, что annotate_document, но без
     повторной экстракции (annotate_document(path) внутри сам вызывает
     hybrid_extract_document — двойная экстракция удвоила бы время; структура
     идентична, т.к. annotate_document является ровно этой композицией);
  3) по каждому параграфу build_paragraph_graphs -> graph_stats_total
     (7 графов параграфного уровня) + средний вектор версии через
     graph_vector.vectorize (dim = len(vector_schema()) = 89).

Fail-closed: .doc (legacy binary, python-docx не читает) и непрочитанные
документы пропускаются, ошибки фиксируются в модульном реестре CORPUS_ERRORS
(collect_corpus) / в поле "errors" версии. Один упавший параграф или версия
не роняют весь прогон.

Выход (write_report):
  hybrid/consolidation/evolution_report.json — машиночитаемый
  hybrid/consolidation/evolution_summary.md  — человекочитаемый
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

_WC_ROOT = os.environ.get("WRITER_CORE_ROOT") or os.path.dirname(os.path.abspath(__file__))
_HARNESS_ROOT = os.path.dirname(os.path.dirname(_WC_ROOT))
for _p in (_WC_ROOT, os.path.join(_WC_ROOT, "v2_extractor")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hybrid_extract import hybrid_extract_document  # noqa: E402
from structure_annotator import (build_document_tree,  # noqa: E402
                                 build_writing_plan, fill_slots)
from graph_builder_hybrid import build_paragraph_graphs, graph_stats  # noqa: E402
from graph_vector import vectorize, vector_schema, cosine_similarity  # noqa: E402

# ---------------------------------------------------------------------------
# пути артефактов
# ---------------------------------------------------------------------------

CONSOLIDATION_DIR = os.path.join(os.environ.get("WRITER_RUNS_DIR", os.path.join(_WC_ROOT, "runs")), "consolidation")
EVOLUTION_REPORT_JSON = os.path.join(CONSOLIDATION_DIR, "evolution_report.json")
EVOLUTION_SUMMARY_MD = os.path.join(CONSOLIDATION_DIR, "evolution_summary.md")

# Модульный реестр ошибок корпуса (заполняется collect_corpus):
# .doc / отсутствующие файлы / упавшие версии — {"version", "path", "error"}.
CORPUS_ERRORS: list[dict] = []

# Суффиксы «канонической» версии (основная цепочка v1..v12).
_CANONICAL_SUFFIXES = ("актуальная", "редакция")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _derive_version(path: str) -> str:
    """Версия из имени файла: 'Автореферат_v8_АКТУАЛЬНАЯ.docx' -> 'v8'."""
    stem = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r"v(\d+)(?:_(\d+))?", stem, re.IGNORECASE)
    if not m:
        return stem
    out = f"v{m.group(1)}"
    if m.group(2):
        out += f"_{m.group(2)}"
    return out


def _full_label(path: str) -> str:
    """Полная метка версии с суффиксом: '..._v6_АКТУАЛЬНАЯ.docx' -> 'v6_актуальная'."""
    stem = os.path.splitext(os.path.basename(path))[0]
    m = re.match(r"^Автореферат_(v\d+.*)$", stem, re.IGNORECASE)
    return m.group(1).lower() if m else _derive_version(path)


def _classify_version_path(path: str) -> tuple[str, str | None]:
    """Классифицировать .docx: ("main"|"extra"|"skip", label|None).

    main  — vN без суффикса или с каноническим суффиксом (актуальная/редакция);
    extra — суб-версии (v2_0, v6_бэкап, ...) — без полного разбора;
    skip  — не похоже на версию Автореферата.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    m = re.match(r"^Автореферат_(v\d+(?:_\d+)?)(.*)$", stem, re.IGNORECASE)
    if not m:
        return "skip", None
    vnum = m.group(1).lower()
    suffix = m.group(2).lower().lstrip("_")
    if not suffix or suffix.startswith(_CANONICAL_SUFFIXES):
        return "main", vnum
    return "extra", f"{vnum}_{suffix}"


def _main_priority(path: str) -> int:
    """Приоритет каноничности версии: vN (3) > vN_актуальная (2) > vN_редакция (1)."""
    core = os.path.splitext(os.path.basename(path))[0].lower()
    mm = re.match(r"^автореферат_v\d+(?:_(\d+))?(?:_(.+))?$", core)
    suffix = (mm.group(2) or "") if mm else ""
    if not suffix:
        return 3
    if suffix.startswith("актуальная"):
        return 2
    if suffix.startswith("редакция"):
        return 1
    return 0


def _version_sort_key(v: dict) -> tuple:
    """Ключ сортировки версий: (major, minor, суффикс) — v1 < v2 < v2_0 < v6 < v12."""
    name = str((v or {}).get("version") or "").lower()
    m = re.search(r"v(\d+)(?:_(\d+))?", name)
    if not m:
        return (10 ** 9, 0, name)
    major = int(m.group(1))
    minor = int(m.group(2)) if m.group(2) else -1
    return (major, minor, name[m.end():])


def _zero_vector() -> list[float]:
    return [0.0] * len(vector_schema())


def _i(v: dict, dotted_path: str, default: int = 0) -> int:
    """Безопасное int-значение по точечному пути ('digest.causal_count')."""
    cur: Any = v
    for part in dotted_path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part, default)
    if isinstance(cur, (int, float)) and not isinstance(cur, bool):
        return int(cur)
    return default


def _cos(v_a: list[float] | None, v_b: list[float] | None) -> float | None:
    if not v_a or not v_b or len(v_a) != len(v_b) or not any(v_a) or not any(v_b):
        return None
    try:
        return round(cosine_similarity(v_a, v_b), 4)
    except Exception:  # pragma: no cover - защита от битых векторов
        return None


# ---------------------------------------------------------------------------
# 1. collect_version — одна версия -> агрегаты
# ---------------------------------------------------------------------------

def collect_version(path: str, max_paragraphs: int = 100) -> dict:
    """Одна версия -> агрегаты для эволюционного отчёта.

    Возвращает (JSON-серизуемый dict):
      version, path, status ("OK"|"PARTIAL"|"ERROR"),
      paragraphs, chars, claims_total, grounded_total, objects_total,
      numbers_total, ambiguities_total,
      graph_stats_total: {gid: {nodes, edges}} — сумма по параграфам,
      nodes_total, edges_total,
      sections: [типы секций в порядке документа],
      section_count, sections_unique,
      gaps: n, gap_expected: [expected незакрытых слотов],
      digest: {modality_dist, causal_count, scope_expansion},
      vector: средний параграф-вектор версии (dim 89),
      errors: [ошибки документа/параграфов].

    Fail-closed: .doc и непрочитанные документы -> status="ERROR" с ошибкой,
    исключения на любом этапе не роняют функцию.
    """
    out: dict = {
        "version": _derive_version(path),
        "path": os.path.normpath(path),
        "status": "OK",
        "paragraphs": 0,
        "chars": 0,
        "claims_total": 0,
        "grounded_total": 0,
        "objects_total": 0,
        "numbers_total": 0,
        "ambiguities_total": 0,
        "graph_stats_total": {},
        "nodes_total": 0,
        "edges_total": 0,
        "sections": [],
        "section_count": 0,
        "sections_unique": [],
        "gaps": 0,
        "gap_expected": [],
        "digest": {"modality_dist": {}, "causal_count": 0, "scope_expansion": 0},
        "vector": _zero_vector(),
        "errors": [],
    }

    ext = os.path.splitext(path)[1].lower()
    if ext == ".doc":
        out["status"] = "ERROR"
        out["errors"].append({
            "stage": "extract", "path": path,
            "error": "python-docx не читает .doc (legacy binary) — пропущено"})
        return out

    # ---- экстракция (один проход; структура строится из того же артефакта) ----
    doc = hybrid_extract_document(path, max_paragraphs=max_paragraphs)
    out["errors"].extend((doc.get("meta") or {}).get("errors", []))
    paras = doc.get("paragraphs") or []
    out["paragraphs"] = (doc.get("meta") or {}).get("count", len(paras))
    out["chars"] = (doc.get("meta") or {}).get("chars", 0)

    # ---- структура: тот же конвейер, что annotate_document (без повторной
    # экстракции: annotate_document(path) внутри сам вызывает
    # hybrid_extract_document — здесь мы используем уже извлечённый doc). ----
    try:
        tree = build_document_tree(doc)
    except Exception as e:
        out["status"] = "ERROR"
        out["errors"].append({"stage": "tree", "path": path,
                              "error": f"{type(e).__name__}: {e}"})
        return out
    try:
        build_writing_plan(tree)
    except Exception as e:
        out["errors"].append({"stage": "plan", "path": path,
                              "error": f"{type(e).__name__}: {e}"})
    try:
        filled = fill_slots(tree, doc)
    except Exception as e:
        out["errors"].append({"stage": "slots", "path": path,
                              "error": f"{type(e).__name__}: {e}"})
        filled = {"gaps": []}
    out["sections"] = [str(s.get("section_type") or "UNKNOWN")
                       for s in tree.get("sections", [])]
    seen: list[str] = []
    for t in out["sections"]:
        if t not in seen:
            seen.append(t)
    out["sections_unique"] = seen
    out["section_count"] = len(out["sections"])
    out["gaps"] = len(filled.get("gaps") or [])
    out["gap_expected"] = [
        str(g.get("expected") or g.get("slot_id") or "?")
        for g in (filled.get("gaps") or [])]

    if not paras:
        out["status"] = "ERROR"
        if not out["errors"]:
            out["errors"].append({"stage": "extract", "path": path,
                                  "error": "документ не прочитан: 0 параграфов"})
        return out

    # ---- графы + агрегаты + вектор по каждому параграфу ----
    vecs: list[list[float]] = []
    for art in paras:
        try:
            g = build_paragraph_graphs(art)
            graphs = (g or {}).get("graphs") or {}
            art["graphs"] = graphs
            for gid, st in graph_stats(g).items():
                gs = out["graph_stats_total"].setdefault(
                    gid, {"nodes": 0, "edges": 0})
                gs["nodes"] += int(st.get("nodes", 0))
                gs["edges"] += int(st.get("edges", 0))
        except Exception as e:
            art["graphs"] = {}
            out["errors"].append({
                "stage": "graphs",
                "paragraph_id": art.get("paragraph_id"),
                "error": f"{type(e).__name__}: {e}"})
        # агрегация claims/objects/digest — даже если графы параграфа не собрались
        claims = art.get("claims") or []
        objects = art.get("objects") or []
        digest = art.get("digest") or {}
        out["claims_total"] += len(claims)
        out["grounded_total"] += sum(
            1 for c in claims if isinstance(c, dict)
            and c.get("qa_status") == "GROUNDED")
        out["objects_total"] += len(objects)
        out["numbers_total"] += sum(
            1 for o in objects if isinstance(o, dict)
            and str(o.get("class", "")).startswith("B_number"))
        amb = digest.get("ambiguities") or []
        out["ambiguities_total"] += len(amb)
        out["digest"]["scope_expansion"] += sum(
            1 for iss in amb if isinstance(iss, dict)
            and iss.get("type") == "SCOPE_EXPANSION")
        mod = str(digest.get("modality") or "").strip().lower() or "none"
        out["digest"]["modality_dist"][mod] = \
            out["digest"]["modality_dist"].get(mod, 0) + 1
        cf = str(digest.get("causal_force") or "").strip().lower()
        if cf and cf != "none":
            out["digest"]["causal_count"] += 1
        try:
            vecs.append(vectorize(art))
        except Exception as e:
            out["errors"].append({
                "stage": "vector",
                "paragraph_id": art.get("paragraph_id"),
                "error": f"{type(e).__name__}: {e}"})

    for st in out["graph_stats_total"].values():
        out["nodes_total"] += st["nodes"]
        out["edges_total"] += st["edges"]

    if vecs:
        n = len(vecs)
        dim = len(vecs[0])
        out["vector"] = [
            round(sum(v[i] for v in vecs) / n, 6) for i in range(dim)]

    if out["errors"]:
        out["status"] = "PARTIAL"  # разобрано, но с ошибками — версия учитывается
    return out


# ---------------------------------------------------------------------------
# 2. collect_corpus — все версии, fail-closed
# ---------------------------------------------------------------------------

def collect_corpus(version_files: list[dict], max_paragraphs: int = 100) -> list[dict]:
    """Все версии из version_files=[{"version","path"}, ...] -> list[dict].

    Fail-closed: .doc / отсутствующие файлы / упавшие версии пропускаются,
    ошибка фиксируется в модульном CORPUS_ERRORS. Порядок результата —
    порядок входа (для попарных дельт compute_evolution сортирует сам).
    """
    global CORPUS_ERRORS
    CORPUS_ERRORS = []
    versions: list[dict] = []
    for vf in version_files:
        if not isinstance(vf, dict):
            CORPUS_ERRORS.append({"version": "", "path": "",
                                  "error": f"запись не dict: {vf!r}"})
            continue
        version = str(vf.get("version") or "")
        path = str(vf.get("path") or "")
        if not path:
            CORPUS_ERRORS.append({"version": version, "path": "",
                                  "error": "путь не задан"})
            continue
        if not os.path.exists(path):
            CORPUS_ERRORS.append({"version": version, "path": path,
                                  "error": "файл не найден"})
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext == ".doc":
            CORPUS_ERRORS.append({
                "version": version, "path": path,
                "error": "python-docx не читает .doc (legacy binary) — пропущено"})
            continue
        try:
            v = collect_version(path, max_paragraphs=max_paragraphs)
        except Exception as e:  # pragma: no cover - последний рубеж fail-closed
            CORPUS_ERRORS.append({"version": version, "path": path,
                                  "error": f"{type(e).__name__}: {e}"})
            continue
        v["version"] = version or v.get("version") or _derive_version(path)
        if v.get("status") == "ERROR":
            err = v.get("errors") or [{"error": "неизвестная ошибка"}]
            first = err[0]
            CORPUS_ERRORS.append({
                "version": v["version"], "path": path,
                "error": f"{first.get('stage', 'version')}: {first.get('error', first)}"})
            continue
        versions.append(v)
    return versions


# ---------------------------------------------------------------------------
# 2a. discover_versions — найти версии в каталоге (main/extra/skipped)
# ---------------------------------------------------------------------------

def discover_versions(versions_dir: str) -> dict:
    """Найти версии Автореферата в каталоге.

    Возвращает {"dir", "main": [{version, path}], "extra": [{version, path}],
    "skipped": [{version, path, error}], "errors": []}.
    main  — каноническая цепочка (v1..v12), по одной версии на номер
            (приоритет: vN > vN_актуальная > vN_редакция);
    extra — суб-версии (v2_0, v6_бэкап, проигравшие каноничности vN) —
            без полного разбора;
    skipped — .doc (python-docx не читает) и нераспознанные файлы.
    """
    out: dict = {"dir": versions_dir, "main": [], "extra": [],
                 "skipped": [], "errors": []}
    if not os.path.isdir(versions_dir):
        out["errors"].append({"error": f"каталог не найден: {versions_dir}"})
        return out

    main_candidates: dict[str, list[dict]] = {}
    for name in sorted(os.listdir(versions_dir)):
        p = os.path.join(versions_dir, name)
        if not os.path.isfile(p):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext == ".doc":
            out["skipped"].append({"version": _derive_version(p), "path": p,
                                   "error": "python-docx не читает .doc"})
            continue
        if ext != ".docx":
            continue
        kind, label = _classify_version_path(p)
        if kind == "skip":
            out["errors"].append({"path": p,
                                  "error": "не распознан как версия Автореферата"})
            continue
        entry = {"version": label, "path": p}
        if kind == "main":
            main_candidates.setdefault(label, []).append(entry)
        else:
            out["extra"].append(entry)

    for label, entries in main_candidates.items():
        entries.sort(key=lambda e: _main_priority(e["path"]), reverse=True)
        out["main"].append(entries[0])
        for e in entries[1:]:  # проигравшие каноничность -> extra
            e["version"] = _full_label(e["path"])
            out["extra"].append(e)
    out["main"].sort(key=_version_sort_key)
    out["extra"].sort(key=_version_sort_key)
    return out


# ---------------------------------------------------------------------------
# 3. compute_evolution — попарные дельты и суммарный тренд
# ---------------------------------------------------------------------------

def _pair_delta(a: dict, b: dict) -> dict:
    """Динамические дельты версии a -> b (новое минус старое)."""
    sa = set(a.get("sections_unique") or [])
    sb = set(b.get("sections_unique") or [])
    ga = set(a.get("gap_expected") or [])
    gb = set(b.get("gap_expected") or [])
    d: dict = {
        "from": a.get("version"), "to": b.get("version"),
        "delta_claims": _i(b, "claims_total") - _i(a, "claims_total"),
        "delta_grounded": _i(b, "grounded_total") - _i(a, "grounded_total"),
        "delta_objects": _i(b, "objects_total") - _i(a, "objects_total"),
        "delta_nodes_total": _i(b, "nodes_total") - _i(a, "nodes_total"),
        "delta_edges_total": _i(b, "edges_total") - _i(a, "edges_total"),
        "delta_causal": _i(b, "digest.causal_count") - _i(a, "digest.causal_count"),
        "delta_scope_expansion":
            _i(b, "digest.scope_expansion") - _i(a, "digest.scope_expansion"),
        "delta_sections": _i(b, "section_count") - _i(a, "section_count"),
        "delta_gaps": _i(b, "gaps") - _i(a, "gaps"),
        "sections_added": [t for t in (b.get("sections_unique") or [])
                           if t not in sa],
        "sections_removed": [t for t in (a.get("sections_unique") or [])
                             if t not in sb],
        "gaps_added": [g for g in (b.get("gap_expected") or []) if g not in ga],
        "gaps_removed": [g for g in (a.get("gap_expected") or []) if g not in gb],
        "similarity": _cos(a.get("vector"), b.get("vector")),
    }
    dc, dn = d["delta_claims"], d["delta_nodes_total"]
    if dc > 0:
        d["growth_label"] = "growth"
    elif dc < 0:
        d["growth_label"] = "decline"
    elif dn > 0:
        d["growth_label"] = "growth"
    elif dn < 0:
        d["growth_label"] = "decline"
    else:
        d["growth_label"] = "stable"
    return d


def _total_growth(first: dict, last: dict) -> dict:
    """Суммарная динамика первой -> последней версии."""
    return {
        "from": first.get("version"), "to": last.get("version"),
        "claims": _i(last, "claims_total") - _i(first, "claims_total"),
        "grounded": _i(last, "grounded_total") - _i(first, "grounded_total"),
        "objects": _i(last, "objects_total") - _i(first, "objects_total"),
        "nodes": _i(last, "nodes_total") - _i(first, "nodes_total"),
        "edges": _i(last, "edges_total") - _i(first, "edges_total"),
        "causal": _i(last, "digest.causal_count") - _i(first, "digest.causal_count"),
        "scope_expansion":
            _i(last, "digest.scope_expansion") - _i(first, "digest.scope_expansion"),
        "sections": _i(last, "section_count") - _i(first, "section_count"),
        "gaps": _i(last, "gaps") - _i(first, "gaps"),
    }


def _trend(pairs: list[dict], total: dict) -> dict:
    """Тренд по claims: рост/падение/стабильность по всей траектории."""
    claim_deltas = [p["delta_claims"] for p in pairs]
    if claim_deltas and all(d > 0 for d in claim_deltas):
        label = "growth"
    elif claim_deltas and all(d < 0 for d in claim_deltas):
        label = "decline"
    elif claim_deltas and all(d == 0 for d in claim_deltas):
        label = "stable"
    else:
        label = "mixed"
    labels = [p["growth_label"] for p in pairs]
    return {
        "claims": label,
        "claims_total_delta": int(total.get("claims", 0)),
        "per_pair": [
            {"from": p["from"], "to": p["to"],
             "delta_claims": p["delta_claims"], "label": p["growth_label"]}
            for p in pairs],
        "growth_pairs": sum(1 for l in labels if l == "growth"),
        "decline_pairs": sum(1 for l in labels if l == "decline"),
        "stable_pairs": sum(1 for l in labels if l == "stable"),
    }


def _section_counts(v: dict) -> dict[str, int]:
    """Число вхождений (ранов) каждого типа секции в упорядоченном списке."""
    c: dict[str, int] = {}
    for t in v.get("sections") or []:
        c[t] = c.get(t, 0) + 1
    return c


def _most_changed(pairs: list[dict], versions: list[dict]) -> list[dict]:
    """Самые изменчивые секции.

    Изменчивость = суммарная по переходам |разница числа вхождений типа|
    (появление/исчезновение рана секции в структуре документа) + 1 за каждое
    появление/исчезновение типа между версиями.
    """
    by_version = {v.get("version"): v for v in versions}
    inst: dict[str, int] = {}
    for p in pairs:
        a = by_version.get(p.get("from")) or {}
        b = by_version.get(p.get("to")) or {}
        ca, cb = _section_counts(a), _section_counts(b)
        for t in set(ca) | set(cb):
            inst[t] = inst.get(t, 0) + abs(ca.get(t, 0) - cb.get(t, 0))
    for p in pairs:
        for t in list(p.get("sections_added") or []) + \
                list(p.get("sections_removed") or []):
            inst[t] = inst.get(t, 0) + 1
    return [{"section": t, "changes": n}
            for t, n in sorted(inst.items(), key=lambda kv: (-kv[1], kv[0]))]


def compute_evolution(versions: list[dict]) -> dict:
    """Эволюция корпуса версий: попарные дельты + суммарный тренд.

    Пары — соседние версии ОТСОРТИРОВАННОГО списка (v1->v2->...->v12;
    при пропущенных версиях — v9->v12 и т.п.). Возвращает
    {"summary": {...}, "pairs": [...]}; summary содержит total_growth,
    trend, most_changed_sections, similarity_first_last.
    """
    vers = sorted([v for v in versions if isinstance(v, dict)],
                  key=_version_sort_key)
    summary: dict = {
        "versions_processed": len(vers),
        "version_chain": [v.get("version", "?") for v in vers],
        "first_version": vers[0].get("version") if vers else None,
        "last_version": vers[-1].get("version") if vers else None,
        "total_growth": {},
        "trend": {},
        "most_changed_sections": [],
        "pairs_count": 0,
        "similarity_first_last": None,
    }
    pairs: list[dict] = []
    if len(vers) >= 2:
        pairs = [_pair_delta(a, b) for a, b in zip(vers, vers[1:])]
        total = _total_growth(vers[0], vers[-1])
        summary["total_growth"] = total
        summary["trend"] = _trend(pairs, total)
        summary["most_changed_sections"] = _most_changed(pairs, vers)
        summary["pairs_count"] = len(pairs)
        summary["similarity_first_last"] = _cos(
            vers[0].get("vector"), vers[-1].get("vector"))
    return {"summary": summary, "pairs": pairs}


# ---------------------------------------------------------------------------
# 4. version_similarity — попарная косинусная схожесть версий
# ---------------------------------------------------------------------------

def version_similarity(versions: list[dict]) -> dict:
    """Попарный cosine между средними векторами версий.

    Возвращает {"n", "versions": [метки], "matrix": [[cos]], "pairs":
    [{"from","to","similarity"}]}. Матрица n x n, диагональ 1.0,
    значения округлены до 4 знаков. Пустой корпус -> n=0, пустые списки.
    """
    vers = sorted([v for v in versions if isinstance(v, dict)],
                  key=_version_sort_key)
    names = [v.get("version", "?") for v in vers]
    n = len(vers)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        vi = vers[i].get("vector") or _zero_vector()
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
                continue
            vj = vers[j].get("vector") or _zero_vector()
            matrix[i][j] = _cos(vi, vj) or 0.0
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append({"from": names[i], "to": names[j],
                          "similarity": matrix[i][j]})
    return {"n": n, "versions": names, "matrix": matrix, "pairs": pairs}


# ---------------------------------------------------------------------------
# 5. write_report — артефакты отчёта (json + md)
# ---------------------------------------------------------------------------

def _fmt_delta(x: Any) -> str:
    x = int(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else x
    if isinstance(x, int):
        return f"+{x}" if x > 0 else str(x)
    return str(x)


def _md_table(lines: list[str], headers: list[str], rows: list[list]) -> None:
    lines.append("| " + " | ".join(str(h) for h in headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    lines.append("")


def _render_md(evolution: dict, versions: list[dict],
               similarity: dict | None = None) -> str:
    """Человекочитаемый evolution_summary.md — детерминированно из данных."""
    summary = (evolution or {}).get("summary") or {}
    pairs = (evolution or {}).get("pairs") or []
    sim = similarity or {}
    L: list[str] = []
    chain = summary.get("version_chain") or []
    L.append("# Отчёт эволюции диссертации (Автореферат)")
    L.append("")
    L.append(f"**Версий обработано:** {summary.get('versions_processed', 0)}"
             f" — {', '.join(chain)}")
    L.append("")
    L.append("## 1. Сводка по версиям")
    L.append("")
    headers = ["версия", "параграфы", "claims", "grounded", "объекты",
               "узлы", "рёбер", "секций", "gaps", "неоднозн.", "каузал.",
               "scope_exp"]
    rows = []
    for v in versions:
        dig = v.get("digest") or {}
        rows.append([
            v.get("version", "?"), v.get("paragraphs", 0),
            v.get("claims_total", 0), v.get("grounded_total", 0),
            v.get("objects_total", 0), v.get("nodes_total", 0),
            v.get("edges_total", 0), v.get("section_count", 0),
            v.get("gaps", 0), v.get("ambiguities_total", 0),
            dig.get("causal_count", 0), dig.get("scope_expansion", 0)])
    _md_table(L, headers, rows)

    L.append("## 2. Динамика между версиями (дельты)")
    L.append("")
    if pairs:
        headers2 = ["переход", "claims", "grounded", "объекты", "узлы",
                    "рёбер", "каузал.", "scope_exp", "секций", "gaps",
                    "growth", "cos"]
        rows2 = []
        for p in pairs:
            rows2.append([
                f"{p.get('from')} → {p.get('to')}",
                _fmt_delta(p.get("delta_claims")),
                _fmt_delta(p.get("delta_grounded")),
                _fmt_delta(p.get("delta_objects")),
                _fmt_delta(p.get("delta_nodes_total")),
                _fmt_delta(p.get("delta_edges_total")),
                _fmt_delta(p.get("delta_causal")),
                _fmt_delta(p.get("delta_scope_expansion")),
                _fmt_delta(p.get("delta_sections")),
                _fmt_delta(p.get("delta_gaps")),
                p.get("growth_label", ""),
                p.get("similarity") if p.get("similarity") is not None else "-"])
        _md_table(L, headers2, rows2)
        L.append("sections_added/removed по переходам:")
        L.append("")
        for p in pairs:
            L.append(f"- {p.get('from')} → {p.get('to')}: добавлено "
                     f"{', '.join(p.get('sections_added') or ['-'])}; удалено "
                     f"{', '.join(p.get('sections_removed') or ['-'])}")
        L.append("")

    tg = summary.get("total_growth") or {}
    L.append("## 3. Суммарный рост "
             f"({summary.get('first_version')} → {summary.get('last_version')})")
    L.append("")
    if tg:
        L.append(f"- claims: {_fmt_delta(tg.get('claims'))}")
        L.append(f"- grounded: {_fmt_delta(tg.get('grounded'))}")
        L.append(f"- объекты: {_fmt_delta(tg.get('objects'))}")
        L.append(f"- узлы графов: {_fmt_delta(tg.get('nodes'))}")
        L.append(f"- рёбра графов: {_fmt_delta(tg.get('edges'))}")
        L.append(f"- каузальные предложения: {_fmt_delta(tg.get('causal'))}")
        L.append(f"- scope-неоднозначности: {_fmt_delta(tg.get('scope_expansion'))}")
        L.append(f"- секции: {_fmt_delta(tg.get('sections'))}")
        L.append(f"- gaps (незакрытые слоты): {_fmt_delta(tg.get('gaps'))}")
    else:
        L.append("- нет пар версий для расчёта дельт")
    L.append("")

    tr = summary.get("trend") or {}
    L.append("## 4. Тренд по claims")
    L.append("")
    if tr:
        L.append(f"- Тренд: **{tr.get('claims', 'n/a')}** "
                 f"(суммарная дельта {_fmt_delta(tr.get('claims_total_delta'))})")
        L.append(f"- Переходы: growth × {tr.get('growth_pairs', 0)}, "
                 f"decline × {tr.get('decline_pairs', 0)}, "
                 f"stable × {tr.get('stable_pairs', 0)}")
        for pp in tr.get("per_pair") or []:
            L.append(f"  - {pp.get('from')} → {pp.get('to')}: "
                     f"{_fmt_delta(pp.get('delta_claims'))} ({pp.get('label')})")
    else:
        L.append("- нет данных")
    L.append("")

    mcs = summary.get("most_changed_sections") or []
    mcs_active = [m for m in mcs if m.get("changes", 0) > 0]
    L.append("## 5. Самые изменчивые секции")
    L.append("")
    if mcs_active:
        for m in mcs_active:
            L.append(f"- {m.get('section')}: {m.get('changes')} × "
                     f"(изменение числа вхождений/появление-исчезновение)")
    else:
        L.append("- секции не менялись между версиями")
    L.append("")

    L.append("## 6. Схожесть версий (косинус средних векторов)")
    L.append("")
    m = sim.get("matrix") or []
    snames = sim.get("versions") or []
    if m and snames:
        _md_table(L, [""] + snames,
                  [[snames[i]] + [f"{c:.4f}" for c in row]
                   for i, row in enumerate(m)])
        for p in sim.get("pairs") or []:
            L.append(f"- {p.get('from')} ~ {p.get('to')}: "
                     f"{p.get('similarity'):.4f}")
        L.append("")

    L.append("## 7. Как менялась диссертация (вывод)")
    L.append("")
    if tg:
        first = summary.get("first_version")
        last = summary.get("last_version")
        L.append(f"- Объём утверждений: claims {first} → {last}: "
                 f"{_fmt_delta(tg.get('claims'))}; grounded "
                 f"{_fmt_delta(tg.get('grounded'))}.")
        L.append(f"- Графы знаний: суммарно за эволюцию узлов "
                 f"{_fmt_delta(tg.get('nodes'))}, рёбер "
                 f"{_fmt_delta(tg.get('edges'))}.")
        L.append(f"- Структура: секций {_fmt_delta(tg.get('sections'))}, "
                 f"незакрытых слотов (gaps) {_fmt_delta(tg.get('gaps'))}.")
        L.append(f"- Каузальная аргументация: дельта предложений с каузальной "
                 f"силой {_fmt_delta(tg.get('causal'))}; "
                 f"scope-неоднозначностей {_fmt_delta(tg.get('scope_expansion'))}.")
        if tr:
            L.append(f"- Общий тренд по claims: **{tr.get('claims')}** "
                     f"(суммарно {_fmt_delta(tr.get('claims_total_delta'))}).")
        if mcs_active:
            desc = ", ".join(f"{m.get('section')} ({m.get('changes')}x)"
                             for m in mcs_active)
            L.append(f"- Наиболее изменчивые секции: {desc}.")
        sfl = summary.get("similarity_first_last")
        if sfl is not None:
            L.append(f"- Косинусная схожесть {first} ~ {last}: {sfl:.4f} "
                     f"(1.0 — идентичны, 0.0 — ортогональны).")
    else:
        L.append("- Недостаточно версий для вывода.")
    L.append("")

    L.append("## 8. Ошибки и пропуски")
    L.append("")
    if CORPUS_ERRORS:
        for e in CORPUS_ERRORS:
            L.append(f"- {e.get('version', '?')}: {e.get('error')} "
                     f"({e.get('path', '')})")
    else:
        L.append("- нет ошибок корпуса")
    L.append("")
    L.append("---")
    L.append("Сгенерировано m_consolidation (детерминированно, без LLM).")
    L.append("")
    return "\n".join(L)


def write_report(evolution: dict, versions: list[dict]) -> None:
    """Сохранить эволюционный отчёт: evolution_report.json + evolution_summary.md.

    evolution — выход compute_evolution; versions — выход collect_corpus.
    Схожесть версий считается заново (version_similarity) и попадает в оба
    артефакта. Каталог consolidation создаётся при необходимости.
    """
    os.makedirs(CONSOLIDATION_DIR, exist_ok=True)
    sim = version_similarity(versions)
    report: dict = {
        "schema": "writer_core.evolution_report.v1",
        "generated_by": "m_consolidation",
        "pipeline": {
            "extract": f"hybrid_extract_document(max_paragraphs=100)",
            "structure": ("structure_annotator: build_document_tree + "
                          "build_writing_plan + fill_slots (конвейер "
                          "annotate_document, один проход экстракции)"),
            "graphs": ("graph_builder_hybrid.build_paragraph_graphs "
                       "(7 графов параграфного уровня)"),
            "vector": f"graph_vector.vectorize (dim={len(vector_schema())}, "
                      "среднее по параграфам)",
        },
        "evolution": evolution,
        "similarity": sim,
        "versions": versions,
        "corpus_errors": CORPUS_ERRORS,
    }
    with open(EVOLUTION_REPORT_JSON, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, sort_keys=True)
    md = _render_md(evolution, versions, sim)
    with open(EVOLUTION_SUMMARY_MD, "w", encoding="utf-8") as fh:
        fh.write(md)


# ---------------------------------------------------------------------------
# самопроверка: полный прогон каталога версий
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time
    import argparse

    ap = argparse.ArgumentParser(description="Консолидация версий автореферата")
    ap.add_argument("--versions-dir", default=os.environ.get("WRITER_VERSIONS_DIR"),
                    required="WRITER_VERSIONS_DIR" not in os.environ)
    ap.add_argument("--max-paragraphs", type=int, default=100)
    args = ap.parse_args()

    disc = discover_versions(args.versions_dir)
    files = disc["main"]
    print(f"main: {len(files)}", [f["version"] for f in files])
    print(f"extra: {len(disc['extra'])}", [f["version"] for f in disc["extra"]])
    print(f"skipped (.doc): {len(disc['skipped'])}")

    t0 = time.perf_counter()
    v = collect_corpus(files, max_paragraphs=args.max_paragraphs)
    t1 = time.perf_counter()
    print(f"collect_corpus: {len(v)} версий за {t1 - t0:.1f} с; "
          f"ошибок корпуса: {len(CORPUS_ERRORS)}")
    e = compute_evolution(v)
    print(json.dumps(e["summary"], ensure_ascii=False, indent=2)[:800])
    sim = version_similarity(v)
    print("similarity n =", sim["n"])
    write_report(e, v)
    print("report ->", EVOLUTION_REPORT_JSON)
    print("summary ->", EVOLUTION_SUMMARY_MD)
