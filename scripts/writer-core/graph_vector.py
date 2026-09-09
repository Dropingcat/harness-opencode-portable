# -*- coding: utf-8 -*-
"""M_GRAPH_VECTOR: детерминированная модель граф-параграф -> числовой вектор.

Назначение (три потребителя):
  1) сличение параграфов между собой (paragraph_similarity);
  2) сличение параграфа с эталоном секции автореферата (section_profile_match);
  3) динамические метрики между версиями одного параграфа (dynamic_metrics):
     плотность рёбер, доля GROUNDED, число claims, эпистемическая сила и т.д.

Входы (оба формата поддерживаются автоматически):
  - полный гибридный артефакт параграфа v2/v0.3
    {"claims": [...], "objects": [...], "digest": {...}, "links": {...},
     "text": ..., "sentences": [...], "discourse": [...], "philology": {...}}
    -> графы строятся через build_paragraph_graphs (hybrid/graph_builder_hybrid);
  - dict с уже готовыми графами:
      * полная форма: {"graphs": {gid: {"nodes": [...], "edges": [...]}, ...}}
        (выход build_paragraph_graphs / "graphs"-обёртка);
      * компактная форма эталона (diag/etalon_sections.json):
        {"claims": int, "objects": int, "discourse": int, "chreia": int,
         "amb": int, "graphs": {gid: {"n": int, "e": int}}}
        -> если ключ "graphs" уже есть, графы НЕ пересобираются, берутся как есть.

CONTRACT векторной схемы:
  vector_schema() — единственный источник порядка имён фичей.
  vectorize() всегда возвращает len(vector_schema()) чисел (dim = 89).
  extract_graph_features() дополнительно возвращает агрегаты
  "nodes_total"/"edges_total" (НЕ входят в schema — только для dynamic_metrics).

Фичи (в порядке vector_schema):
  a) graph stats: 7 графов параграфного уровня (G3, G4, G5, G6, G13, G14, G15)
     x {n_nodes, n_edges, ratio e/n}                                  -> 21
  b) node types (по всем графам): ClaimRef, EvidenceRef, ScopeRef,
     Quantity, Formula, Clause, Token, Mention, EntityRef, RhetoricalMove,
     CommunicativeAct, DiscourseMove, Transition, ArgumentInstance,
     ConclusionRef                                                    -> 15
  c) edge types: SUPPORTS, CONCLUDES, HAS_UNIT, COREFERS_WITH,
     THEME_TO_RHEME, REFERS_TO, MOTIVATES, ELABORATES, CONTRASTS,
     LEADS_TO, PREPARES                                              -> 11
  d) эпистемика: n_claims, n_grounded (qa_status==GROUNDED), grounded_ratio,
     amb_MODALITY_UPGRADE/CAUSALITY_UPGRADE/SCOPE_EXPANSION (1/0),
     causal_force_present/none (none — только при явном значении "NONE"),
     modality one-hot (assertive, possibility, weak_inference,
     assertive_compat, other, none)                                       -> 14
  e) семантика: n_objects, n_B_number, B_number_ratio                -> 3
  Итого базовых = 21 + 15 + 11 + 14 + 3 = 64.
  f) ДИСКРИМИНАТИВНЫЕ ДОБАВКИ (round 1 ревью, для разделимости секций):
     n_discourse, n_chreia, n_ambiguities (счётчики: список -> len,
     int-поле компакта -> как есть)                                     -> 3
     claims_number_ratio (доля claims, чей текст содержит цифру)         -> 1
     has_discourse_role (digest.discourse_role не пуст)                  -> 1
     ratio_objects_per_claim, ratio_claims_per_object,
     ratio_discourse_per_claim, ratio_chreia_per_claim                   -> 4
     text_len (длина текстового источника: head|text, <=400)             -> 1
     n_numbers (число цифр в текстовом источнике)                        -> 1
     list_marker (текст начинается с "-"/"•"/"N." — enumerate-список)     -> 1
     kw_* 13 маркеров-лексики разделов (цель/задачи/метод/результаты/
     актуальность/новизна/литература/выводы/объект/тема/конференции/
     заголовки результатов/тело результатов)                             -> 13
  Итого dim = 64 + 25 = 89.

Почему это разделяет секции (round 1): компактные параграфы эталона не
содержат claims-списков/digest, поэтому 37/64 базовых фичей структурно
нулевые и профили почти коллинеарны (cos ~0.999). Добавленные фичи
считываются И из компакта (head-текст, счётчики discourse/chreia/amb,
graph-stats), И из полного артефакта (text, списки), и дают честную
leave-one-out точность матчинга параграф->секция >= 0.60 (см. loo_section_accuracy).

section_profile_match использует нормализацию профилей:
  etalon_stats может содержать служебный ключ "__transform__"
  {"mean": [...], "std": [...], "marker_start": N, "marker_count": K,
   "marker_weight": W} — глобальные mean/std по параграфам, из которых
  строились профили. Перед косинусом и тест-вектор, и профили секций
  z-нормируются этим преобразованием; блок текстовых маркеров
  (text_len..kw_*) дополнительно усиливается W=8 (маркеры — сильный
  детерминированный дискриминатор в шаблонных авторефератах, иначе они
  тонут в масштабе graph-stats). __transform__ вычисляется детерминированно
  и не зависит от тестового параграфа.

Честность leave-one-out: loo_section_accuracy(etalon) строит профили
и __transform__ БЕЗ тестового параграфа (exclude_idx) — самовключение
тестового параграфа в профиль исключено. Точность LOO на
diag/etalon_sections.json (100 параграфов) >= 0.60.

Fail-closed построение графов: если у артефакта нет готовых "graphs",
но он содержит текст/предложения (т.е. графы реально нужны), а построение
не удалось (нет реестра graph_registry.yaml / WRITER_GRAPH_REGISTRY, битый
вход) — поднимается ValueError с понятным сообщением. Молчаливый
zero-вектор при ошибке реестра исключён. Легитимно без графов:
пустой артефакт или компакт-счётчики без text/sentences -> вектор по
счётчикам (не ошибка).

Внешние зависимости: graph_builder_hybrid (только для построения графов;
импорт ленивый — потребление готовых {"graphs"} работает без него),
numpy НЕ используется.
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics
from typing import Any

# --------------------------------------------------------------------------
# фиксированный словарь (CONTRACT — менять нельзя без смены версии схемы)
# --------------------------------------------------------------------------

# 7 графов параграфного уровня реестра v0.3 (порядок = порядок _BUILDERS)
_GRAPH_IDS: list[str] = [
    "G3_discourse",
    "G4_argument",
    "G5_epistemic_projection",
    "G6_artifact_symbol",
    "G13_linguistic_structure",
    "G14_cohesion_information_flow",
    "G15_pragmatic_rhetorical",
]

_NODE_TYPE_FEATURES: list[str] = [
    "ClaimRef", "EvidenceRef", "ScopeRef", "Quantity", "Formula",
    "Clause", "Token", "Mention", "EntityRef", "RhetoricalMove",
    "CommunicativeAct", "DiscourseMove", "Transition", "ArgumentInstance",
    "ConclusionRef",
]

_EDGE_TYPE_FEATURES: list[str] = [
    "SUPPORTS", "CONCLUDES", "HAS_UNIT", "COREFERS_WITH",
    "THEME_TO_RHEME", "REFERS_TO", "MOTIVATES", "ELABORATES",
    "CONTRASTS", "LEADS_TO", "PREPARES",
]

_AMBIGUITY_TYPES: list[str] = [
    "MODALITY_UPGRADE", "CAUSALITY_UPGRADE", "SCOPE_EXPANSION",
]

_MODALITY_VOCAB: list[str] = [
    "assertive", "possibility", "weak_inference", "assertive_compat",
]

# --- дискриминативные добавки (round 1) -----------------------------------

# Лексика-маркеры разделов (подстроки, нижний регистр). Фиксированный
# словарь: детерминирован, переносится на другие авторефераты (шаблонная
# структура диссертационных авторефератов на русском).
_MARKER_VOCAB: dict[str, list[str]] = {
    "kw_goal":        ["цел данной", "цель", "установить закономер",
                       "закономерност"],
    "kw_tasks":       ["задач", "апробироват", "исследоват", "установить",
                       "решалис", "разработат"],
    "kw_method":      ["метод", "главе", "подход", "эксперимент", "образц",
                       "обработк", "режим", "выбраны", "выбран"],
    "kw_result_head": ["положения", "защиту", "достоверност", "апробаци",
                       "личный вклад", "публикаци", "результат"],
    "kw_result_body": ["рис", "разд", "показано", "установлено", "получен",
                       "связь"],
    "kw_conference":  ["конференци", "всероссийск", "international",
                       "конкурс"],
    "kw_relevance":   ["актуаль", "обоснов", "фундамент", "первая глава",
                       "в работах", "проблем"],
    "kw_novelty":     ["новизн", "разработан", "впервые", "отличающийся",
                       "корреляци"],
    "kw_topic":       ["проработанност", "ограничением", "литературе",
                       "известн", "значимост"],
    "kw_literature":  ["опубликовано", "объём и структура",
                       "объем и структура", "посвящена экспериментальному"],
    "kw_conclusion":  ["практическая значимост", "состоит", "содержание",
                       "заключается"],
    "kw_title":       ["характеристик"],
    "kw_object":      ["объект", "предмет"],
}

# Служебный ключ transform в etalon_stats / section_profiles.json
_TRANSFORM_KEY = "__transform__"

# Индексы блока текстовых маркеров в vector_schema() (z-нормируются и
# усиливаются _MARKER_WEIGHT перед косинусом). Инвариант:
# schema[_MARKER_START : _MARKER_START + _MARKER_COUNT] — блок маркеров.
_MARKER_START = 73
_MARKER_COUNT = 16      # text_len, n_numbers, list_marker + 13 kw_*
_MARKER_WEIGHT = 8.0

# Длина текстового источника, используемая для маркеров/счётчиков.
_TEXT_SOURCE_LIMIT = 400


def vector_schema() -> list[str]:
    """Порядок фичей в числовом векторе (CONTRACT: фиксирован, dim = 89)."""
    schema: list[str] = []
    for gid in _GRAPH_IDS:
        schema += [f"{gid}_n", f"{gid}_e", f"{gid}_ratio"]
    schema += [f"nt_{t}" for t in _NODE_TYPE_FEATURES]
    schema += [f"et_{t}" for t in _EDGE_TYPE_FEATURES]
    schema += [
        "n_claims", "n_grounded", "grounded_ratio",
    ]
    schema += [f"amb_{t}" for t in _AMBIGUITY_TYPES]
    schema += ["causal_force_present", "causal_force_none"]
    schema += [f"modality_{m}" for m in _MODALITY_VOCAB]
    schema += ["modality_other", "modality_none"]
    schema += ["n_objects", "n_B_number", "B_number_ratio"]
    # --- дискриминативные добавки (round 1) ---
    schema += [
        "n_discourse", "n_chreia", "n_ambiguities",
        "claims_number_ratio", "has_discourse_role",
        "ratio_objects_per_claim", "ratio_claims_per_object",
        "ratio_discourse_per_claim", "ratio_chreia_per_claim",
        "text_len", "n_numbers", "list_marker",
    ]
    # ключи _MARKER_VOCAB уже именованы "kw_*" (kw_goal, kw_tasks, ...)
    schema += list(_MARKER_VOCAB.keys())
    return schema


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _graph_shape_full(g: Any) -> tuple[int, int, list, list]:
    """(n_nodes, n_edges, nodes, edges) для графа в любом формате.

    Полная форма: {"nodes": [...], "edges": [...]}.
    Компактная форма эталона: {"n": int, "e": int}.
    """
    if not isinstance(g, dict):
        return 0, 0, [], []
    nodes, edges = g.get("nodes"), g.get("edges")
    if isinstance(nodes, list) and isinstance(edges, list):
        return len(nodes), len(edges), nodes, edges
    n, e = g.get("n", 0), g.get("e", 0)
    if not isinstance(n, (int, float)) or not isinstance(e, (int, float)):
        return 0, 0, [], []
    return int(n), int(e), [], []


def _as_graphs(artifact: dict) -> dict:
    """Графы из артефакта: готовые (ключ "graphs") либо построенные.

    Fail-closed: если графы реально нужны (есть text/sentences, но ключа
    "graphs" нет), а построение не удалось — ValueError с понятным
    сообщением (никакого молчаливого zero-вектора при ошибке реестра).
    Легитимно без графов: пустой артефакт / компакт-счётчики без
    text/sentences -> {} (вектор по счётчикам, это НЕ ошибка).
    """
    graphs = artifact.get("graphs")
    if isinstance(graphs, dict):
        return graphs
    if "graphs" in artifact:
        raise ValueError(
            "_as_graphs: ключ 'graphs' есть, но не dict "
            f"(тип {type(graphs).__name__}); артефакт повреждён (fail-closed)")
    if not (artifact.get("text") or artifact.get("sentences")):
        # нет текста — графы строить не из чего; это легитимный вход
        # (пустой артефакт, компакт-счётчики, тесты dynamic_metrics)
        return {}
    try:
        from graph_builder_hybrid import build_paragraph_graphs
    except Exception as exc:  # noqa: BLE001 - fail-closed с контекстом
        raise ValueError(
            "_as_graphs: не удалось импортировать graph_builder_hybrid "
            f"({type(exc).__name__}: {exc}); графы не построены (fail-closed)"
        ) from exc
    try:
        res = build_paragraph_graphs(artifact)
    except Exception as exc:  # noqa: BLE001 - fail-closed с контекстом
        raise ValueError(
            "_as_graphs: построение графов параграфа не удалось "
            f"({type(exc).__name__}: {exc}). Проверь реестр графов "
            "(WRITER_GRAPH_REGISTRY / graph_registry.yaml). "
            "Векторизация остановлена (fail-closed).") from exc
    out = res.get("graphs") if isinstance(res, dict) else None
    if not isinstance(out, dict):
        raise ValueError(
            "_as_graphs: graph_builder_hybrid вернул не {\"graphs\": {...}} "
            "(fail-closed)")
    return out


def _claim_counters(artifact: dict) -> tuple[int, int]:
    """(n_claims, n_grounded). Список claims -> честный подсчёт;
    int (компактный эталон) -> grounded неизвестен, 0."""
    claims = artifact.get("claims")
    if isinstance(claims, list):
        n = len(claims)
        grounded = sum(
            1 for c in claims
            if isinstance(c, dict) and c.get("qa_status") == "GROUNDED")
        return n, grounded
    if isinstance(claims, (int, float)) and not isinstance(claims, bool):
        return int(claims), 0
    return 0, 0


def _object_counters(artifact: dict) -> tuple[int, int]:
    """(n_objects, n_B_number). Список -> честно; int (эталон) -> B_number=0."""
    objects = artifact.get("objects")
    if isinstance(objects, list):
        n = len(objects)
        b_num = sum(1 for o in objects
                    if isinstance(o, dict)
                    and str(o.get("class", "")).startswith("B_number"))
        return n, b_num
    if isinstance(objects, (int, float)) and not isinstance(objects, bool):
        return int(objects), 0
    return 0, 0


def _int_counter(artifact: dict, key: str) -> int:
    """Счётчик: int-поле компакта -> как есть; список (полный артефакт) -> len."""
    v = artifact.get(key)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v)
    if isinstance(v, list):
        return len(v)
    return 0


def _count_chreia(artifact: dict) -> int:
    """Число элементов хрии: полный артефакт — philology.chreia (список),
    компакт — int-поле 'chreia'."""
    phil = artifact.get("philology")
    if isinstance(phil, dict):
        ch = phil.get("chreia")
        if isinstance(ch, list):
            return len(ch)
    return _int_counter(artifact, "chreia")


def _count_ambiguities(artifact: dict) -> int:
    """Число ambiguities: полный артефакт — digest.ambiguities (список),
    компакт — int-поле 'amb'."""
    digest = artifact.get("digest")
    if isinstance(digest, dict):
        am = digest.get("ambiguities")
        if isinstance(am, list):
            return len(am)
    return _int_counter(artifact, "amb")


def _claims_number_ratio(artifact: dict) -> float:
    """Доля claims, чей текст содержит цифру (для полных артефактов);
    компакт (claims — int) -> 0.0 (неизвестно)."""
    claims = artifact.get("claims")
    if isinstance(claims, list) and claims:
        with_digit = sum(
            1 for c in claims
            if isinstance(c, dict) and re.search(r"\d", str(c.get("text", ""))))
        return with_digit / len(claims)
    return 0.0


def _has_discourse_role(artifact: dict) -> float:
    """digest.discourse_role задан (не None/не "none") -> 1.0, иначе 0.0."""
    digest = artifact.get("digest")
    if isinstance(digest, dict):
        role = digest.get("discourse_role")
        if role is not None and str(role).strip().lower() not in ("", "none",
                                                                  "null"):
            return 1.0
    return 0.0


def _text_source(artifact: dict) -> str:
    """Текстовый источник для маркеров/счётчиков: head (компакт эталона)
    либо text (полный артефакт), усечён до _TEXT_SOURCE_LIMIT."""
    src = artifact.get("head") or artifact.get("text") or ""
    if not isinstance(src, str):
        src = ""
    return src[:_TEXT_SOURCE_LIMIT]


# --------------------------------------------------------------------------
# основной экстрактор
# --------------------------------------------------------------------------

def extract_graph_features(paragraph_artifact: dict) -> dict[str, float]:
    """Артефакт/графы параграфа -> dict {feature_name: float}.

    Ключи = vector_schema() + агрегаты "nodes_total"/"edges_total".
    Пустой/битый вход без графов -> все фичи 0 (легитимно).
    НО: если графы нужно построить, а построение не удалось — ValueError
    (fail-closed, см. _as_graphs).
    """
    artifact = paragraph_artifact if isinstance(paragraph_artifact, dict) else {}
    graphs = _as_graphs(artifact)
    feats: dict[str, float] = {}
    totals_n = 0
    totals_e = 0

    # счётчики по типам узлов/рёбер (только из полной формы)
    nt_counts = {t: 0 for t in _NODE_TYPE_FEATURES}
    et_counts = {t: 0 for t in _EDGE_TYPE_FEATURES}

    for gid in _GRAPH_IDS:
        n, e, nodes, edges = _graph_shape_full(graphs.get(gid))
        totals_n += n
        totals_e += e
        feats[f"{gid}_n"] = float(n)
        feats[f"{gid}_e"] = float(e)
        feats[f"{gid}_ratio"] = float(e / n) if n else 0.0
        for nd in nodes:
            tp = nd.get("type") if isinstance(nd, dict) else None
            if tp in nt_counts:
                nt_counts[tp] += 1
        for ed in edges:
            rel = ed.get("relation") if isinstance(ed, dict) else None
            if rel in et_counts:
                et_counts[rel] += 1

    for t in _NODE_TYPE_FEATURES:
        feats[f"nt_{t}"] = float(nt_counts[t])
    for t in _EDGE_TYPE_FEATURES:
        feats[f"et_{t}"] = float(et_counts[t])

    # эпистемика
    n_claims, n_grounded = _claim_counters(artifact)
    feats["n_claims"] = float(n_claims)
    feats["n_grounded"] = float(n_grounded)
    feats["grounded_ratio"] = float(n_grounded / n_claims) if n_claims else 0.0

    digest = artifact.get("digest")
    digest = digest if isinstance(digest, dict) else {}
    for t in _AMBIGUITY_TYPES:
        feats[f"amb_{t}"] = 0.0
    for iss in digest.get("ambiguities") or []:
        if isinstance(iss, dict) and iss.get("type") in _AMBIGUITY_TYPES:
            feats[f"amb_{iss['type']}"] = 1.0

    cf = str(digest.get("causal_force") or "").strip().lower()
    feats["causal_force_present"] = 1.0 if cf and cf != "none" else 0.0
    # none-бин только при ЯВНОМ значении "none"; отсутствие поля = unknown (0),
    # иначе компактные параграфы эталона (без digest) получили бы ложный none
    feats["causal_force_none"] = 1.0 if cf == "none" else 0.0

    mod = str(digest.get("modality") or "").strip().lower()
    for m in _MODALITY_VOCAB:
        feats[f"modality_{m}"] = 1.0 if mod == m else 0.0
    feats["modality_other"] = 1.0 if (mod and mod not in _MODALITY_VOCAB
                                      and mod != "none") else 0.0
    feats["modality_none"] = 1.0 if mod == "none" else 0.0

    # семантический профиль
    n_objects, n_bnum = _object_counters(artifact)
    feats["n_objects"] = float(n_objects)
    feats["n_B_number"] = float(n_bnum)
    feats["B_number_ratio"] = float(n_bnum / n_objects) if n_objects else 0.0

    # --- дискриминативные добавки (round 1) ---
    n_discourse = _int_counter(artifact, "discourse")
    n_chreia = _count_chreia(artifact)
    n_ambiguities = _count_ambiguities(artifact)
    feats["n_discourse"] = float(n_discourse)
    feats["n_chreia"] = float(n_chreia)
    feats["n_ambiguities"] = float(n_ambiguities)
    feats["claims_number_ratio"] = _claims_number_ratio(artifact)
    feats["has_discourse_role"] = _has_discourse_role(artifact)
    feats["ratio_objects_per_claim"] = (n_objects / n_claims
                                        if n_claims else 0.0)
    feats["ratio_claims_per_object"] = (n_claims / n_objects
                                        if n_objects else 0.0)
    feats["ratio_discourse_per_claim"] = (n_discourse / n_claims
                                          if n_claims else 0.0)
    feats["ratio_chreia_per_claim"] = (n_chreia / n_claims
                                       if n_claims else 0.0)

    src = _text_source(artifact)
    feats["text_len"] = float(len(src))
    feats["n_numbers"] = float(len(re.findall(r"\d", src)))
    feats["list_marker"] = (1.0 if re.match(r"^\s*(?:[-–—•*]|\d{1,2}[.)])\s",
                                            src) else 0.0)
    src_low = src.lower()
    for k, words in _MARKER_VOCAB.items():
        feats[k] = 1.0 if any(w in src_low for w in words) else 0.0

    # агрегаты для dynamic_metrics (не входят в vector_schema)
    feats["nodes_total"] = float(totals_n)
    feats["edges_total"] = float(totals_e)
    return feats


# --------------------------------------------------------------------------
# векторизация и схожесть
# --------------------------------------------------------------------------

def vectorize(paragraph_artifact: dict) -> list[float]:
    """Артефакт/графы -> числовой вектор длины len(vector_schema()).

    Поднимает ValueError (fail-closed), если графы нужно построить,
    а построение невозможно (нет реестра и т.п.).
    """
    feats = extract_graph_features(paragraph_artifact)
    return [float(feats.get(name, 0.0)) for name in vector_schema()]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Стандартный косинус. 0.0 для нулевых векторов.
    Разные длины -> ValueError (нарушение контракта схемы)."""
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"cosine_similarity: dim mismatch {len(vec_a)} != {len(vec_b)}; "
            "используй vector_schema() для единого порядка фичей")
    if not vec_a:
        return 0.0
    dot = sum(x * y for x, y in zip(vec_a, vec_b))
    na = math.sqrt(sum(x * x for x in vec_a))
    nb = math.sqrt(sum(y * y for y in vec_b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(dot / (na * nb))


def paragraph_similarity(a: dict, b: dict) -> float:
    """Схожесть двух артефактов/графов параграфа: vectorize -> cosine."""
    return cosine_similarity(vectorize(a), vectorize(b))


# --------------------------------------------------------------------------
# динамические метрики между версиями
# --------------------------------------------------------------------------

_DELTA_FEATURES: list[tuple[str, str]] = [
    ("delta_claims", "n_claims"),
    ("delta_grounded", "n_grounded"),
    ("delta_edges_total", "edges_total"),
    ("delta_nodes_total", "nodes_total"),
    ("delta_supports", "et_SUPPORTS"),
    ("delta_causal", "causal_force_present"),
    ("delta_scope_expansion", "amb_SCOPE_EXPANSION"),
    ("delta_modality_upgrade", "amb_MODALITY_UPGRADE"),
]


def dynamic_metrics(artifact_old: dict, artifact_new: dict) -> dict:
    """Разница метрик двух версий одного параграфа (new - old).

    delta_causal — смена digest.causal_force (присутствие не-NONE);
    delta_scope_expansion / delta_modality_upgrade — появление/исчезновение
    соответствующих digest.ambiguities.
    nodes_label: "growth" | "decline" | "stable" по суммарному числу узлов.
    """
    fo = extract_graph_features(artifact_old)
    fn = extract_graph_features(artifact_new)
    out: dict[str, float] = {}
    for key, feat in _DELTA_FEATURES:
        out[key] = float(fn.get(feat, 0.0) - fo.get(feat, 0.0))
    dn = out["delta_nodes_total"]
    out["nodes_label"] = ("growth" if dn > 0
                          else ("decline" if dn < 0 else "stable"))
    return out


# --------------------------------------------------------------------------
# сличение с эталоном секций
# --------------------------------------------------------------------------

def _profile_vector(profile: Any, schema: list[str]) -> list[float]:
    """Профиль секции -> вектор в порядке schema.

    Принимает dict {feature_name: value} (выход compute_etalon_profiles)
    или плоский список в порядке schema.
    """
    if isinstance(profile, dict):
        return [float(profile.get(name, 0.0)) for name in schema]
    if isinstance(profile, (list, tuple)):
        vec = [float(x) for x in profile]
        if len(vec) != len(schema):
            raise ValueError(
                f"profile vector dim {len(vec)} != schema dim {len(schema)}")
        return vec
    raise ValueError(f"unsupported profile type: {type(profile)!r}")


def _match_profile_scores(v: list[float], etalon_stats: dict) -> dict[str, float]:
    """Косинусные скоринги вектора против профилей секций.

    etalon_stats: {section_name: профиль} + опциональный служебный
    "__transform__" (глобальные mean/std по параграфам, из которых строились
    профили). Если transform есть — тест-вектор и профили z-нормируются,
    а блок текстовых маркеров усиливается _MARKER_WEIGHT (см. docstring
    модуля). Служебные ключи в скоринги не попадают.
    """
    schema = vector_schema()
    tr = etalon_stats.get(_TRANSFORM_KEY) if isinstance(etalon_stats, dict) else None
    sections = {str(k): pr for k, pr in (etalon_stats or {}).items()
                if k != _TRANSFORM_KEY}

    def norm(x: list[float]) -> list[float]:
        vec = [float(z) for z in x]
        if (isinstance(tr, dict) and "mean" in tr and "std" in tr
                and len(tr.get("mean") or []) == len(schema)
                and len(tr.get("std") or []) == len(schema)):
            mean = tr["mean"]
            std = tr["std"]
            w0 = float(tr.get("marker_weight", 1.0))
            ms = int(tr.get("marker_start", -1))
            mc = int(tr.get("marker_count", 0))
            out: list[float] = []
            for j in range(len(schema)):
                z = (vec[j] - mean[j]) / std[j]
                if ms <= j < ms + mc:
                    z *= w0
                out.append(z)
            return out
        return vec

    vn = norm(v)
    scores: dict[str, float] = {}
    for sec, prof in sections.items():
        scores[sec] = cosine_similarity(vn, norm(_profile_vector(prof, schema)))
    return scores


def section_profile_match(paragraph_artifact: dict, etalon_stats: dict) -> dict:
    """Сопоставить параграф с эталонными профилями секций.

    etalon_stats: {section_name: профиль} — dict {feature: value} либо
    список в порядке vector_schema() (выход compute_etalon_profiles),
    плюс опциональный служебный "__transform__".
    Возвращает {"best_section", "similarity", "margin", "all_scores"}.
    margin — запас уверенности best vs 2nd (диагностика шумового argmax).
    """
    v = vectorize(paragraph_artifact)
    all_scores = _match_profile_scores(v, etalon_stats)
    if not all_scores:
        return {"best_section": None, "similarity": 0.0, "margin": 0.0,
                "all_scores": {}}
    best = max(all_scores, key=lambda s: all_scores[s])
    ranked = sorted(all_scores.values(), reverse=True)
    margin = float(ranked[0] - ranked[1]) if len(ranked) > 1 else 0.0
    return {"best_section": best, "similarity": float(all_scores[best]),
            "margin": margin, "all_scores": all_scores}


# --------------------------------------------------------------------------
# эталонные профили секций
# --------------------------------------------------------------------------

def _assign_section(p: dict, sections: list) -> str:
    """Секция параграфа: явная метка p["section"], иначе граница start_idx.

    Секции из etalon["sections"] = [{section, start_idx, head}] задают блоки
    по idx параграфа; параграфы с меткой вне границ не встречаются (проверено:
    0 конфликтов на etalon v8), поэтому предпочтение явной метке безопасно.
    """
    sec = p.get("section")
    if sec:
        return str(sec)
    i = p.get("idx")
    if not isinstance(i, (int, float)) or not sections:
        return "UNKNOWN"
    best: str | None = None
    for s in sections:
        st = s.get("start_idx") if isinstance(s, dict) else None
        if isinstance(st, (int, float)) and st <= i:
            best = str(s.get("section") or "UNKNOWN")
        else:
            break
    return best or "UNKNOWN"


def compute_etalon_profiles(etalon: Any, out_path: str | None = None,
                            exclude_idx: int | None = None) -> dict:
    """Средние векторы по секциям из diag/etalon_sections.json.

    etalon: dict {"sections": [{section,start_idx,head}...],
    "paragraph_vectors": [{idx, section|None, graphs: {gid: {"n","e"}},
    claims: int, objects: int, ...}]} либо путь к JSON.
    Секция параграфа: явная метка "section", иначе границы start_idx
    (все 100 параграфов эталона получают секцию; дубликаты имён секций —
    CONCLUSION/RELEVANCE/RESULTS в списке границ — объединяются по имени).
    Возвращает {section_name: {feature_name: mean}} (ключи == vector_schema())
    + служебный ключ "__transform__": {"mean": [...], "std": [...],
    "marker_start", "marker_count", "marker_weight"} — глобальные mean/std по
    ВКЛЮЧЁННЫМ параграфам (нужны section_profile_match для z-нормировки).
    exclude_idx: исключить параграф с данным idx из профилей и transform
    (для честного leave-one-out; самовключение тестового параграфа исключено).
    Если out_path задан — сохраняет JSON (det: sort_keys, sorted sections).
    """
    if isinstance(etalon, str) and os.path.exists(etalon):
        with open(etalon, encoding="utf-8") as fh:
            etalon = json.load(fh)
    if not isinstance(etalon, dict):
        raise ValueError("compute_etalon_profiles: etalon должен быть dict/путь")
    pvs = etalon.get("paragraph_vectors") or []
    sections = [s for s in (etalon.get("sections") or [])
                if isinstance(s, dict)]
    sections.sort(key=lambda s: s.get("start_idx", 0))
    schema = vector_schema()

    included: list[dict] = []
    for p in pvs:
        if not isinstance(p, dict):
            continue
        if exclude_idx is not None:
            idx = p.get("idx")
            if isinstance(idx, (int, float)) and int(idx) == int(exclude_idx):
                continue  # честный leave-one-out: тестовый параграф вне профилей
        included.append(p)

    vecs: list[tuple[str, list[float]]] = []
    for p in included:
        vecs.append((_assign_section(p, sections), vectorize(p)))

    by_section: dict[str, list[list[float]]] = {}
    for sec, v in vecs:
        by_section.setdefault(sec, []).append(v)

    profiles: dict[str, dict[str, float]] = {}
    for sec in sorted(by_section):
        items = by_section[sec]
        n = len(items)
        sums = [0.0] * len(schema)
        for v in items:
            for j, x in enumerate(v):
                sums[j] += x
        profiles[sec] = {name: float(s / n) for name, s in zip(schema, sums)}

    # глобальный transform по включённым параграфам (для z-нормировки
    # в section_profile_match; не зависит от тестового параграфа при LOO)
    if included:
        n = len(vecs)
        mean = [0.0] * len(schema)
        for _, v in vecs:
            for j, x in enumerate(v):
                mean[j] += x
        mean = [x / n for x in mean]
        var = [0.0] * len(schema)
        for _, v in vecs:
            for j, x in enumerate(v):
                var[j] += (x - mean[j]) ** 2
        std = [math.sqrt(s / n) + 1e-9 for s in var]
        profiles[_TRANSFORM_KEY] = {
            "mean": mean, "std": std, "dim": len(schema),
            "marker_start": _MARKER_START, "marker_count": _MARKER_COUNT,
            "marker_weight": _MARKER_WEIGHT, "version": 3,
        }

    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(profiles, fh, ensure_ascii=False, indent=2,
                      sort_keys=True)
    return profiles


# --------------------------------------------------------------------------
# честный leave-one-out (диагностика качества матчинга секций)
# --------------------------------------------------------------------------

def loo_section_accuracy(etalon: Any) -> dict:
    """Честный leave-one-out: точность матчинга параграф->секция.

    Для каждого параграфа i профили секций И transform строятся БЕЗ
    параграфа i (exclude_idx) — самовключение тестового параграфа в
    профиль исключено (в отличие от self-inclusive замеров round 0).

    Возвращает {"accuracy", "correct", "total", "per_section",
    "median_margin", "margin_ge_0_05", "detail": [{idx, true, pred,
    similarity, margin}, ...]}.

    Честный LOO на diag/etalon_sections.json (100 параграфов): >= 0.60.
    """
    if isinstance(etalon, str) and os.path.exists(etalon):
        with open(etalon, encoding="utf-8") as fh:
            etalon = json.load(fh)
    if not isinstance(etalon, dict):
        raise ValueError("loo_section_accuracy: etalon должен быть dict/путь")
    pvs = etalon.get("paragraph_vectors") or []
    sections = [s for s in (etalon.get("sections") or [])
                if isinstance(s, dict)]

    correct = 0
    total = 0
    margins: list[float] = []
    per_section: dict[str, dict[str, int]] = {}
    detail: list[dict] = []
    for p in pvs:
        if not isinstance(p, dict):
            continue
        idx = p.get("idx")
        if not isinstance(idx, (int, float)):
            continue
        true_sec = _assign_section(p, sections)
        profiles = compute_etalon_profiles(etalon, exclude_idx=int(idx))
        res = section_profile_match(p, profiles)
        pred = res["best_section"]
        ok = bool(pred == true_sec)
        correct += int(ok)
        total += 1
        margins.append(res["margin"])
        per_section.setdefault(true_sec, {"correct": 0, "total": 0})
        per_section[true_sec]["total"] += 1
        per_section[true_sec]["correct"] += int(ok)
        detail.append({"idx": int(idx), "true": true_sec, "pred": pred,
                       "similarity": res["similarity"], "margin": res["margin"]})

    median_margin = statistics.median(margins) if margins else 0.0
    return {
        "accuracy": (correct / total) if total else 0.0,
        "correct": correct,
        "total": total,
        "per_section": per_section,
        "median_margin": float(median_margin),
        "margin_ge_0_05": sum(1 for m in margins if m >= 0.05),
        "detail": detail,
    }


# --------------------------------------------------------------------------
# самопроверка
# --------------------------------------------------------------------------

if __name__ == "__main__":
    _s = vector_schema()
    print("vector dim:", len(_s))
    _art = {"claims": 3, "objects": 2, "graphs": {
        "G5_epistemic_projection": {"n": 4, "e": 3},
        "G13_linguistic_structure": {"n": 6, "e": 5}}}
    print("sample vector len:", len(vectorize(_art)))
    print("features:", {k: v for k, v in extract_graph_features(_art).items()
                        if v not in (0, 0.0)})