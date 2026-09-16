# -*- coding: utf-8 -*-
"""M_STRUCT_ANNOTATOR — разметчик будущей структуры научного произведения (автореферата).

Модуль строит «дерево для заполнения блоками»: для произвольного документа
(docx/pdf/md) он определяет структуру секций автореферата, строит DocumentNode-
дерево (G1: Document->Section->Paragraph) и Writing Decomposition (G2: WritingObjective
-> DocumentGoal -> SectionGoal -> ClaimSlot/ArtifactSlot), затем сверяет фактическое
содержание параграфов со слотами (SATISFIED/GAP/PARTIAL + WriterGap).

Основные сущности (контракт coder-factory, worker m_struct_annotator):

  1. SECTION_REGISTRY   — эталонный набор секций автореферата и требования к их
                          содержимому (формат близок WritingSlotContract из
                          docs/05_WRITING_CONTRACT.md): discourse_role,
                          argument_role, required_claims, optional_claims,
                          required_artifacts, completion.
  2. classify_paragraph — тип секции для произвольного параграфа:
                          (a) заголовочные сигнатуры (regex по эталону),
                          (b) эвристики содержимого (claims/objects/digest).
                          Возвращает (section, confidence 0..1).
  3. build_document_tree— G1-дерево: {tree, sections, node_index}; поля узлов
                          DocumentNode-совместимы (id/type/parent/order/children).
                          Последовательные параграфы одной секции группируются,
                          заголовочный параграф открывает новую секцию.
  4. build_writing_plan — G2-DAG: WritingObjective -> DocumentGoal -> SectionGoal
                          -> ClaimSlot/ArtifactSlot, рёбра DECOMPOSES_TO / REQUIRES.
  5. fill_slots         — сверка содержания секций со слотами: SATISFIED (есть
                          claim/artifact), GAP (нет), PARTIAL (часть слотов секции);
                          рёбра SATISFIES (фактический элемент -> слот) и список
                          gaps (WriterGap: что не заполнено).
  6. annotate_document  — обёртка: hybrid_extract_document -> tree -> plan -> slots;
                          fail-closed: ошибки собираются в meta["errors"].

Совместимость (graph_registry.yaml):
  G1 node_types: Document/Section/Paragraph/...; рёбра PARENT_OF/CONTAINS/NEXT.
  G2 node_types: WritingObjective/DocumentGoal/SectionGoal/ClaimSlot/ArtifactSlot;
                 рёбра DECOMPOSES_TO/REQUIRES/SATISFIES/BLOCKED_BY.

Входной артефакт параграфа — формат hybrid_extract:
  {paragraph_id, text, claims, objects, discourse, philology, digest,
   sentences, links}.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

_WC_ROOT = os.environ.get("WRITER_CORE_ROOT") or os.path.dirname(os.path.abspath(__file__))
_HARNESS_ROOT = os.path.dirname(os.path.dirname(_WC_ROOT))
_ETALON_DEFAULT = os.path.join(os.environ.get("WRITER_RUNS_DIR", os.path.join(_WC_ROOT, "runs")), "diag", "etalon_sections.json")

for _p in (_WC_ROOT, os.path.join(_WC_ROOT, "v2_extractor")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# graph_vector — параллельный модуль (может ещё не существовать).
# Если доступен — используется для уточнения классификации параграфов БЕЗ
# заголовка (сличение по граф-вектору). Контракт модуля не требует его наличия.
try:  # pragma: no cover
    import graph_vector  # type: ignore  # noqa: F401

    _GRAPH_VECTOR_AVAILABLE = True
except Exception:  # pragma: no cover
    _GRAPH_VECTOR_AVAILABLE = False

try:
    from hybrid_extract import hybrid_extract_document  # noqa: F401

    _HYBRID_AVAILABLE = True
except Exception:  # pragma: no cover
    _HYBRID_AVAILABLE = False

# --------------------------------------------------------------------------
# SECTION_REGISTRY — эталонный набор секций автореферата (11 типов из
# etalon_sections.json / docx v8) и требования к содержимому каждой секции.
# Формат: discourse_role (G3), argument_role (G4), required_claims (C1 semantic
# bind), optional_claims, required_artifacts (C4 artifact bind), completion.
# --------------------------------------------------------------------------

SECTION_REGISTRY: dict[str, dict] = {
    "TITLE": {
        "discourse_role": "title",
        "argument_role": None,
        "required_claims": [],
        "optional_claims": [],
        "required_artifacts": [],
        "required_relations": [],
        "completion": ["заголовок работы"],
    },
    "RELEVANCE": {
        "discourse_role": "motivation",
        "argument_role": "motivation_premise",
        "required_claims": ["PROBLEM_STATEMENT"],
        "optional_claims": ["PRIOR_ART_SUMMARY"],
        "required_artifacts": [],
        "required_relations": [],
        "completion": ["обоснована актуальность"],
    },
    "OBJECT_SUBJECT": {
        "discourse_role": "scope",
        "argument_role": "scope_definition",
        "required_claims": ["SCOPE_STATEMENT"],
        "optional_claims": [],
        "required_artifacts": [],
        "required_relations": [],
        "completion": ["определены объект и предмет исследования"],
    },
    "TOPIC_STATE": {
        "discourse_role": "prior_art",
        "argument_role": "state_of_art",
        "required_claims": ["PRIOR_ART_SUMMARY"],
        "optional_claims": [],
        "required_artifacts": [],
        "required_relations": [],
        "completion": ["охарактеризована проработанность темы"],
    },
    "GOAL": {
        "discourse_role": "goal",
        "argument_role": "goal_statement",
        "required_claims": ["GOAL_STATEMENT"],
        "optional_claims": [],
        "required_artifacts": [],
        "required_relations": [],
        "completion": ["сформулирована цель работы"],
    },
    "TASKS": {
        "discourse_role": "plan",
        "argument_role": "task_plan",
        "required_claims": ["TASK_STATEMENT"],
        "optional_claims": [],
        "required_artifacts": [],
        "required_relations": [],
        "completion": ["перечислены задачи исследования"],
    },
    "NOVELTY": {
        "discourse_role": "novelty",
        "argument_role": "novelty_claim",
        "required_claims": ["NOVELTY_CLAIM"],
        "optional_claims": [],
        "required_artifacts": [],
        "required_relations": [],
        "completion": ["заявлена научная новизна"],
    },
    "METHODS": {
        "discourse_role": "methods",
        "argument_role": "method_description",
        "required_claims": ["METHOD_STATEMENT"],
        "optional_claims": [],
        "required_artifacts": ["METHOD_DESC"],
        "required_relations": [],
        "completion": ["описаны методы исследования"],
    },
    "RESULTS": {
        "discourse_role": "results",
        "argument_role": "result_claim",
        "required_claims": ["RESULT_CLAIM"],
        "optional_claims": ["NOVELTY_CLAIM"],
        "required_artifacts": ["QUANTITY", "TABLE", "FIGURE"],
        "required_relations": [],
        "completion": ["приведены результаты исследования"],
    },
    "CONCLUSION": {
        "discourse_role": "conclusion",
        "argument_role": "conclusion_claim",
        "required_claims": ["CONCLUSION_CLAIM"],
        "optional_claims": ["RECOMMENDATION"],
        "required_artifacts": [],
        "required_relations": [],
        "completion": ["сформулированы выводы"],
    },
    "LITERATURE": {
        "discourse_role": "references",
        "argument_role": "citation_list",
        "required_claims": [],
        "optional_claims": [],
        "required_artifacts": ["CITATION"],
        "required_relations": [],
        "completion": ["приведён список публикаций/литературы"],
    },
}

# Заголовочные сигнатуры секций (regex по эталону, порядок = приоритет первого
# совпадения). Зеркалит SECTION_PATTERNS из diag/build_etalon_sections.py —
# чтобы заголовочные параграфы эталона распознавались с теми же типами.
_HEADING_PATTERNS: list[tuple[str, str]] = [
    ("TITLE", r"^(общая характеристика работы|на правах рукописи)"),
    ("RELEVANCE", r"актуальность"),
    ("OBJECT_SUBJECT", r"(объект|предмет)\s+(и\s+)?исследования"),
    ("TOPIC_STATE", r"проработанность|степень\s+разработанности|состояние\s+вопроса"),
    ("GOAL", r"цель\s+(данной\s+)?работы"),
    ("TASKS", r"задачи"),
    ("NOVELTY", r"научная\s+новизна"),
    ("METHODS", r"методологи|методы|методик"),
    ("RESULTS", r"положения|результаты|выносимые\s+на\s+защиту"),
    ("CONCLUSION", r"заключени|выводы|практическая\s+значимость"),
    ("LITERATURE", r"список\s+(литературы|публикаций)|опубликован"),
]

# Эвристики содержимого для параграфов БЕЗ заголовка: (секция, regex, вес).
# Срабатывают только на сильных сигналах; иначе параграф наследует секцию
# предыдущего (тело секции продолжает заголовок).
_CONTENT_SIGNALS: list[tuple[str, str, float]] = [
    ("TITLE", r"^(общая характеристика работы|на правах рукописи)", 0.95),
    ("OBJECT_SUBJECT", r"(объектом|предметом|объект и предмет)\s+исследования", 0.65),
    ("GOAL", r"цель(ю)? (данной )?(работы|исследования)", 0.68),
    ("TASKS", r"решались следующие задачи|поставлены следующие задачи|задачами (работы|исследования)", 0.68),
    ("NOVELTY", r"научная новизна|новизна работы", 0.80),
    ("NOVELTY", r"впервые (установлено|предложен|разработан|показано|получен|экспериментально)", 0.70),
    ("NOVELTY", r"разработан (физико|метод|подход|алгоритм|комплекс)|разработана (методика|модель)|предложен (метод|подход|алгоритм)", 0.62),
    ("CONCLUSION", r"практическая значимость|в заключении|по результатам работы можно (сделать|заключить)", 0.70),
    # ВАЖНО: контентные сигналы RESULTS намеренно узкие — «установлено, что» /
    # «показано, что» — типичная проза тела секции и НЕ должна открывать новую
    # секцию (эталон: границы секций задаются заголовками).
    ("RESULTS", r"результаты (исследования|эксперимента|работы)", 0.62),
    ("METHODS", r"методология|методика (исследования|проведения)", 0.62),
    ("LITERATURE", r"опубликован|список (литературы|публикаций)", 0.70),
    ("RELEVANCE", r"актуальность|актуальн(ая|ой|ым|ость|ыми)", 0.62),
    ("TOPIC_STATE", r"проработанность|степень разработанности|состояние вопроса", 0.70),
]

# Детекторы требуемых CLAIM-типов (C1 semantic bind): claim-тип -> сигнатуры.
# Используются fill_slots для сверки фактического содержания со слотами.
_CLAIM_DETECTORS: dict[str, list[str]] = {
    "PROBLEM_STATEMENT": [r"проблем", r"актуальн", r"важн(ой|ых|ым)", r"значимость"],
    "SCOPE_STATEMENT": [r"объект", r"предмет"],
    "PRIOR_ART_SUMMARY": [r"в работах", r"показано", r"известн", r"установлено",
                          r"исследован", r"в обзорах"],
    "GOAL_STATEMENT": [r"цель", r"необходимо", r"требуется"],
    "TASK_STATEMENT": [r"задач", r"решались"],
    "NOVELTY_CLAIM": [r"впервые", r"новизн", r"разработан", r"предложен",
                      r"отличающийся от известных"],
    "METHOD_STATEMENT": [r"метод", r"методик", r"использован", r"примен", r"провед"],
    "RESULT_CLAIM": [r"установлено", r"показано", r"получен", r"составл",
                     r"количественн", r"достигнут", r"существует связь"],
    "CONCLUSION_CLAIM": [r"вывод", r"заключени", r"практическая значимость",
                         r"рекомендован", r"состоит из"],
    "RECOMMENDATION": [r"рекомендован", r"целесообразн", r"представляется"],
}

# Детекторы требуемых ARTIFACT-типов (C4 artifact bind).
# TABLE: "табл" (русские подписи) + "table" (блоки "TABLE: ...", которые
# hybrid_extract_document вставляет для таблиц .docx — MAJOR-2 ревью).
_ARTIFACT_DETECTORS: dict[str, list[str]] = {
    "TABLE": [r"табл", r"table"],
    "FIGURE": [r"рис\.?\s*\d", r"рисун"],
    "CITATION": [r"опубликован", r"список (литературы|публикаций)", r"\[\d+\]",
                 r"и соавт", r"и др\."],
    "METHOD_DESC": [r"метод", r"методик", r"провед", r"использован", r"примен",
                    r"анализ"],
}

# Числовые сигнатуры для QUANTITY (число + единица).
_QUANTITY_UNITS = r"\d+[.,]?\d*\s*(%|°|мкм|нм|мм|МПа|ГПа|К|ч|°C|HV|мас\.)"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _norm_heading(text: str) -> str:
    """Нормализация заголовка: нижний регистр, снятие markdown/пунктуации."""
    low = (text or "").lower().strip()
    low = re.sub(r"[#*_`\-\u2013\u2014]", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def _trunc(s: str, n: int = 80) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s[:n] + ("..." if len(s) > n else "")


def _lcs_len(a: list[str], b: list[str]) -> int:
    """Длина наибольшей общей подпоследовательности (для сверки с эталоном)."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, start=1):
            cur[j] = prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


# --------------------------------------------------------------------------
# 2. classify_paragraph
# --------------------------------------------------------------------------

def classify_heading(text: str) -> str | None:
    """Тип секции по заголовочной сигнатуре (regex по эталону).

    Сигнатуры ищутся в НАЧАЛЕ параграфа (первые 70 символов — зеркалит
    `head = text[:70]` из diag/build_etalon_sections.py): заголовок секции стоит
    в начале абзаца, а упоминания слов («актуальность», «методы») в теле текста
    не должны открывать новые секции.

    Returns None, если сигнатура не найдена.
    """
    low = _norm_heading((text or "")[:70])
    for sec, pat in _HEADING_PATTERNS:
        if re.search(pat, low):
            return sec
    return None


def classify_content(text: str, claims: list[dict] | None = None,
                     objects: list[dict] | None = None) -> tuple[str, float] | None:
    """Эвристика типа секции по содержимому параграфа (без заголовка).

    Returns (section, confidence) или None, если сигнал недостаточно силён.
    """
    claims = claims or []
    objects = objects or []
    low = _norm_heading(text)
    for sec, pat, weight in _CONTENT_SIGNALS:
        if re.search(pat, low):
            return sec, weight
    return None


def classify_paragraph(text: str, claims: list[dict] | None = None,
                       objects: list[dict] | None = None) -> tuple[str, float]:
    """Тип секции произвольного параграфа.

    Стратегия: (1) заголовочная сигнатура -> confidence 0.95;
    (2) эвристика содержимого -> confidence по силе сигнала;
    (3) иначе "UNKNOWN" (0.0) — вызывающий код наследует секцию предыдущего.

    Returns (section, confidence 0..1).
    """
    claims = claims or []
    objects = objects or []
    h = classify_heading(text)
    if h:
        return h, 0.95
    c = classify_content(text, claims, objects)
    if c:
        return c
    return "UNKNOWN", 0.0


# --------------------------------------------------------------------------
# 3. build_document_tree (G1)
# --------------------------------------------------------------------------

def build_document_tree(doc_artifact: dict) -> dict:
    """G1-дерево документа: Document -> Section -> Paragraph.

    Вход:  {"paragraphs": [{paragraph_id, text, claims, objects, ...}]}
    Выход: {"tree": {id/type/parent/order/children},      # корень DOC
            "sections": [{id, type, section_type, order, children,
                          head, head_paragraph_id, paragraph_ids}],
            "node_index": {id: node}}                     # DocumentNode-совместимо

    Разбивка на секции: последовательные параграфы одного типа группируются;
    заголовочный параграф (classify_heading != None) открывает новую секцию;
    параграфы с уверенной контентной классификацией тоже открывают новую;
    слабые/неизвестные параграфы наследуют секцию предыдущего.
    """
    paragraphs = (doc_artifact or {}).get("paragraphs") or []
    node_index: dict[str, dict] = {}
    sections: list[dict] = []
    doc_id = "DOC"
    node_index[doc_id] = {"id": doc_id, "type": "document", "parent": None,
                          "order": 0, "children": []}
    current: dict | None = None
    occ: dict[str, int] = {}

    for order, p in enumerate(paragraphs):
        pid = p.get("paragraph_id") or f"PAR_{order:04d}"
        text = p.get("text") or ""
        claims = p.get("claims") or []
        objects = p.get("objects") or []
        sec, conf = classify_paragraph(text, claims, objects)
        if sec == "UNKNOWN" and current is not None:
            sec = current["section_type"]
            conf = 0.35
        pnode: dict = {
            "id": pid,
            "type": "paragraph",
            "parent": None,
            "order": None,
            "children": [],
            "section": sec,
            "confidence": round(float(conf), 2),
            "claims": [f"{pid}_C{i}" for i in range(len(claims))],
        }
        if current is None or sec != current["section_type"]:
            k = occ.get(sec, 0)
            occ[sec] = k + 1
            sid = f"SEC_{sec}" if k == 0 else f"SEC_{sec}_{k + 1}"
            snode: dict = {
                "id": sid,
                "type": "section",
                "parent": doc_id,
                "order": len(sections),
                "children": [],
                "section_type": sec,
                "head": _trunc(text),
                "head_paragraph_id": pid,
                "paragraph_ids": [],
            }
            node_index[sid] = snode
            node_index[doc_id]["children"].append(sid)
            sections.append(snode)
            current = snode
        pnode["parent"] = current["id"]
        pnode["order"] = len(current["children"])
        current["children"].append(pid)
        current["paragraph_ids"].append(pid)
        node_index[pid] = pnode

    return {"tree": node_index[doc_id], "sections": sections,
            "node_index": node_index}


# --------------------------------------------------------------------------
# 4. build_writing_plan (G2)
# --------------------------------------------------------------------------

def _sec_part(section_id: str) -> str:
    """Из id секции (SEC_T / SEC_T_2) -> часть для id слотов (T / T_2)."""
    return section_id[len("SEC_"):]


def build_writing_plan(tree: dict) -> dict:
    """G2-Writing Decomposition DAG для секций дерева.

    Выход:
      writing_objective — WritingObjective (корень, WO_DOC)
      document_goal     — DocumentGoal (DG_DOC)
      goals             — [SectionGoal: id/type/section_type/required_claims/
                           required_artifacts/children]
      slots             — [ClaimSlot/ArtifactSlot: id/type/section/kind/expected]
      edges             — [{source,target,type}] DECOMPOSES_TO / REQUIRES

    Для каждой секции из tree создаётся SectionGoal + слоты из SECTION_REGISTRY
    (ClaimSlot для required_claims, ArtifactSlot для required_artifacts).
    """
    sections = (tree or {}).get("sections") or []
    wo: dict = {"id": "WO_DOC", "type": "WritingObjective", "parent": None,
                "order": 0, "children": ["DG_DOC"]}
    dg: dict = {"id": "DG_DOC", "type": "DocumentGoal", "parent": "WO_DOC",
                "order": 0, "children": []}
    goals: list[dict] = []
    slots: list[dict] = []
    edges: list[dict] = [
        {"source": "WO_DOC", "target": "DG_DOC", "type": "DECOMPOSES_TO"},
    ]

    for si, snode in enumerate(sections):
        stype = snode.get("section_type")
        spec = SECTION_REGISTRY.get(stype)
        if spec is None:  # секция вне эталона (напр. UNKNOWN) — без слотов
            continue
        gid = f"SG_{_sec_part(snode['id'])}"
        dg["children"].append(gid)
        edges.append({"source": "DG_DOC", "target": gid, "type": "DECOMPOSES_TO"})
        goal: dict = {
            "id": gid,
            "type": "SectionGoal",
            "parent": "DG_DOC",
            "order": si,
            "children": [],
            "section_type": stype,
            "discourse_role": spec.get("discourse_role"),
            "required_claims": list(spec.get("required_claims", [])),
            "required_artifacts": list(spec.get("required_artifacts", [])),
        }
        for claim in spec.get("required_claims", []):
            sid = f"CS_{_sec_part(snode['id'])}_{claim}"
            slot = {"id": sid, "type": "ClaimSlot", "parent": gid,
                    "order": len(goal["children"]), "section": stype,
                    "kind": "claim", "expected": claim}
            goal["children"].append(sid)
            slots.append(slot)
            edges.append({"source": gid, "target": sid, "type": "REQUIRES"})
        for art in spec.get("required_artifacts", []):
            sid = f"AS_{_sec_part(snode['id'])}_{art}"
            slot = {"id": sid, "type": "ArtifactSlot", "parent": gid,
                    "order": len(goal["children"]), "section": stype,
                    "kind": "artifact", "expected": art}
            goal["children"].append(sid)
            slots.append(slot)
            edges.append({"source": gid, "target": sid, "type": "REQUIRES"})
        goals.append(goal)

    return {"writing_objective": wo, "document_goal": dg, "goals": goals,
            "slots": slots, "edges": edges}


# --------------------------------------------------------------------------
# 5. fill_slots
# --------------------------------------------------------------------------

def _count_claim_type(texts: list[str], para_claims: list[tuple[str, int, dict]],
                      claim_type: str, pids: list[str]) -> tuple[int, list[str]]:
    """Сколько фактических элементов удовлетворяют claim-типу (и где).

    para_claims: [(paragraph_id, idx_в_параграфе, claim), ...] — claims всех
    параграфов секции (idx — позиция claim в списке claims параграфа, как в
    pnode["claims"] = [f"{pid}_C{i}"]).

    Returns (count, evidence_ids): evidence — id фактических элементов,
    которыми слот закрывается: параграф (f"{pid}") для текстового совпадения
    или claim (f"{pid}_C{i}") для совпадения по span claim'а. Эти id затем
    используются как source рёбер SATISFIES (ревью MAJOR-1: ребро должно идти
    от фактического элемента, а НЕ от слота).
    """
    pats = _CLAIM_DETECTORS.get(claim_type, [])
    ev: list[str] = [pid for pid, t in zip(pids, texts)
                     if any(re.search(p, (t or "").lower()) for p in pats)]
    cev: list[str] = []
    for pid, ci, c in para_claims:
        ct = (c.get("raw_span") or c.get("text") or "").lower()
        if any(re.search(p, ct) for p in pats):
            cev.append(f"{pid}_C{ci}")
    return len(ev) + len(cev), ev + cev


def _count_artifact_type(texts: list[str], objects: list[dict], artifact: str,
                         pids: list[str]) -> tuple[int, list[str]]:
    """Сколько артефактов типа artifact найдено в секции (и где).

    Returns (count, evidence_ids) — evidence: id параграфов, где найден
    артефакт (фактические элементы для рёбер SATISFIES).
    """
    if artifact == "QUANTITY":
        nobj = sum(1 for o in objects
                   if re.search(r"\d", str(o.get("raw") or o.get("value") or "")))
        if nobj:
            return nobj, pids[:1]
        ev = [pid for pid, t in zip(pids, texts)
              if re.search(_QUANTITY_UNITS, (t or "").lower())]
        return (len(ev), ev) if ev else (0, [])
    pats = _ARTIFACT_DETECTORS.get(artifact, [])
    ev = [pid for pid, t in zip(pids, texts)
          if any(re.search(p, (t or "").lower()) for p in pats)]
    return len(ev), ev


def _mk_slot(slot_id: str, section: str, kind: str, expected: str,
             count: int, evidence: list[str] | None = None) -> dict:
    return {"slot_id": slot_id, "section": section, "kind": kind,
            "expected": expected, "actual_counts": count,
            "actual_evidence": list(evidence or []),
            "status": "SATISFIED" if count > 0 else "GAP"}


def _register_claim_nodes(node_index: dict) -> None:
    """Добавить claim-узлы в node_index (дети своих параграфов).

    pnode["claims"] = [f"{pid}_C{i}"] уже объявляет claim-id, но узлов для них
    в node_index нет. Здесь каждый объявленный claim становится DocumentNode
    (type="claim", parent=pid), дерево остаётся согласованным (parent/children
    ссылки), а рёбра SATISFIES получают реальные узлы-источники.
    """
    if not isinstance(node_index, dict):
        return
    for pid, pnode in list(node_index.items()):  # snapshot: добавляем узлы
        if pnode.get("type") != "paragraph":
            continue
        for cid in pnode.get("claims") or []:
            if cid in node_index:
                continue
            node_index[cid] = {"id": cid, "type": "claim", "parent": pid,
                               "order": len(pnode["children"]),
                               "children": [], "evidence": False}
            pnode["children"].append(cid)


def _mark_evidence(node_index: dict, evidence_ids: list[str]) -> None:
    """Пометить фактические элементы (параграфы/claims), закрывающие слот."""
    if not isinstance(node_index, dict):
        return
    for eid in evidence_ids:
        nd = node_index.get(eid)
        if isinstance(nd, dict):
            nd["evidence"] = True


def fill_slots(tree: dict, doc_artifact: dict) -> dict:
    """Сверка фактического содержания секций со слотами плана.

    Для каждой секции дерева берутся её параграфы (texts/claims/objects из
    doc_artifact) и для каждого required_claims/required_artifacts вычисляется
    наличие факта (SATISFIED) или отсутствие (GAP). Статус секции:
    SATISFIED (все слоты закрыты), PARTIAL (часть), GAP (ни одного).

    SATISFIES-рёбра строятся от ФАКТИЧЕСКОГО элемента к слоту (MAJOR-1 ревью):
    source — первый id из actual_evidence (параграф f"{pid}" или claim
    f"{pid}_C{i}"), НЕ id слота; каждый такой элемент добавлен в node_index
    (claim-узлы регистрируются как дети параграфов, помечаются evidence=True).

    Выход:
      slots           — [{slot_id, section, kind, expected, actual_counts,
                          actual_evidence, status}]
      gaps            — WriterGap'ы: не заполненные слоты (+severity/research_request)
      satisfies       — рёбра SATISFIES: [{"source": факт/параграф, "target": слот}]
      section_status  — {section_id: SATISFIED/PARTIAL/GAP/N/A}
    """
    paragraphs = (doc_artifact or {}).get("paragraphs") or []
    by_id = {p.get("paragraph_id"): p for p in paragraphs}
    sections = (tree or {}).get("sections") or []
    node_index = (tree or {}).get("node_index")
    plan = build_writing_plan(tree)

    # claim-узлы (id из pnode["claims"]) -> реальные узлы node_index:
    # рёбра SATISFIES от фактических элементов, а не от слотов.
    _register_claim_nodes(node_index)

    slots_out: list[dict] = []
    gaps: list[dict] = []
    satisfies: list[dict] = []
    section_status: dict[str, str] = {}

    for snode in sections:
        stype = snode.get("section_type")
        spec = SECTION_REGISTRY.get(stype)
        if spec is None:
            section_status[snode["id"]] = "N/A"
            continue
        pids = snode.get("paragraph_ids", [])
        texts = [(by_id.get(pid) or {}).get("text") or "" for pid in pids]
        para_claims: list[tuple[str, int, dict]] = []
        objects: list[dict] = []
        for pid in pids:
            p = by_id.get(pid) or {}
            for ci, c in enumerate(p.get("claims") or []):
                para_claims.append((pid, ci, c))
            objects.extend(p.get("objects") or [])

        section_slots: list[dict] = []
        for claim in spec.get("required_claims", []):
            n, ev = _count_claim_type(texts, para_claims, claim, pids)
            slot = _mk_slot(f"CS_{_sec_part(snode['id'])}_{claim}", stype,
                            "claim", claim, n, ev)
            section_slots.append(slot)
        for art in spec.get("required_artifacts", []):
            n, ev = _count_artifact_type(texts, objects, art, pids)
            slot = _mk_slot(f"AS_{_sec_part(snode['id'])}_{art}", stype,
                            "artifact", art, n, ev)
            section_slots.append(slot)

        for slot in section_slots:
            slots_out.append(slot)
            if slot["status"] == "SATISFIED":
                # SATISFIES: фактический элемент -> слот (первое свидетельство)
                target = slot["slot_id"]
                ev = slot.get("actual_evidence") or []
                source = ev[0] if ev else target
                _mark_evidence(node_index, ev)
                satisfies.append({"source": source, "target": target,
                                 "type": "SATISFIES"})
            else:
                gaps.append({"slot_id": slot["slot_id"], "section": stype,
                             "kind": slot["kind"], "expected": slot["expected"],
                             "status": "GAP", "severity": "WORK_BLOCKING",
                             "research_request": True,
                             "note": f"требуется {slot['expected']} — не найдено "
                                     f"в секции {stype}"})

        statuses = [s["status"] for s in section_slots]
        if not statuses:
            section_status[snode["id"]] = "N/A"
        elif all(st == "SATISFIED" for st in statuses):
            section_status[snode["id"]] = "SATISFIED"
        elif all(st == "GAP" for st in statuses):
            section_status[snode["id"]] = "GAP"
        else:
            section_status[snode["id"]] = "PARTIAL"

    return {"slots": slots_out, "gaps": gaps, "satisfies": satisfies,
            "section_status": section_status}


# --------------------------------------------------------------------------
# 6. annotate_document — обёртка всего пайплайна
# --------------------------------------------------------------------------

def annotate_document(path: str, max_paragraphs: int = 100) -> dict:
    """Полный пайплайн разметки: extract -> tree -> plan -> slots.

    Выход: {"path", "tree", "sections", "plan", "slots", "gaps", "satisfies",
            "section_status", "meta"}. Fail-closed: сбои на любом этапе
    фиксируются в meta["errors"], документ не роняем.
    """
    result: dict = {
        "path": os.path.normpath(path),
        "tree": None,
        "document": None,
        "sections": [],
        "plan": None,
        "slots": [],
        "gaps": [],
        "satisfies": [],
        "tables": [],
        "section_status": {},
        "meta": {"count": 0, "chars": 0, "table_count": 0, "errors": [],
                 "sections_recognized": [], "slot_summary": {}},
    }
    if not _HYBRID_AVAILABLE:
        result["meta"]["errors"].append(
            {"stage": "import", "path": path,
             "error": "hybrid_extract_document unavailable"})
        return result

    try:
        doc = hybrid_extract_document(path, max_paragraphs=max_paragraphs)
    except Exception as e:  # pragma: no cover
        result["meta"]["errors"].append(
            {"stage": "extract", "path": path,
             "error": f"{type(e).__name__}: {e}"})
        return result
    result["meta"]["count"] = (doc.get("meta") or {}).get("count", 0)
    result["meta"]["chars"] = (doc.get("meta") or {}).get("chars", 0)
    result["meta"]["table_count"] = (doc.get("meta") or {}).get("table_count", 0)
    result["tables"] = doc.get("tables") or []
    result["meta"]["errors"].extend((doc.get("meta") or {}).get("errors", []))

    try:
        tree = build_document_tree(doc)
        result["tree"] = tree            # полный результат build_document_tree
        result["document"] = tree["tree"]  # корневой узел Document
        result["sections"] = tree["sections"]
    except Exception as e:
        result["meta"]["errors"].append(
            {"stage": "tree", "path": path,
             "error": f"{type(e).__name__}: {e}"})
        return result

    try:
        result["plan"] = build_writing_plan(tree)
    except Exception as e:
        result["meta"]["errors"].append(
            {"stage": "plan", "path": path,
             "error": f"{type(e).__name__}: {e}"})
        result["plan"] = None

    try:
        filled = fill_slots(tree, doc)
        result["slots"] = filled["slots"]
        result["gaps"] = filled["gaps"]
        result["satisfies"] = filled["satisfies"]
        result["section_status"] = filled["section_status"]
    except Exception as e:
        result["meta"]["errors"].append(
            {"stage": "slots", "path": path,
             "error": f"{type(e).__name__}: {e}"})

    seen: list[str] = []
    for s in result["sections"]:
        if s["section_type"] not in seen:
            seen.append(s["section_type"])
    result["meta"]["sections_recognized"] = seen
    summary = {"SATISFIED": 0, "GAP": 0, "PARTIAL": 0, "N/A": 0}
    for s in result["slots"]:
        summary[s["status"]] = summary.get(s["status"], 0) + 1
    result["meta"]["slot_summary"] = summary
    return result


# --------------------------------------------------------------------------
# Сверка с эталоном etalon_sections.json (для проверки точности разметки)
# --------------------------------------------------------------------------

def compare_with_etalon(tree: dict, etalon_path: str | None = None) -> dict:
    """Сверка размеченного дерева с эталонной структурой.

    etalon_path — путь к etalon_sections.json (или dict с тем же форматом).
    Метрики:
      heading_accuracy      — доля заголовочных параграфов эталона (section !=
                              null), классифицированных с тем же типом секции;
      sequence_lcs_ratio    — сходство последовательностей секций
                              (LCS / len(эталон));
      first11_match         — совпадение первых 11 типов секций по позициям.
    """
    if isinstance(etalon_path, dict):
        etalon = etalon_path
    else:
        etalon_path = etalon_path or _ETALON_DEFAULT
        try:
            with open(etalon_path, encoding="utf-8") as fh:
                etalon = json.load(fh)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}",
                    "heading_accuracy": None, "sequence_lcs_ratio": None,
                    "first11_match": None}
    vec = {v.get("paragraph_id"): v.get("section")
           for v in etalon.get("paragraph_vectors", [])}
    node_index = (tree or {}).get("node_index", {})
    hits = total = 0
    wrong: list[tuple] = []
    for nid, node in node_index.items():
        if node.get("type") != "paragraph":
            continue
        exp = vec.get(nid)
        if exp:
            total += 1
            if exp == node.get("section"):
                hits += 1
            else:
                wrong.append((nid, exp, node.get("section")))
    heading_accuracy = (hits / total) if total else None

    my_seq = [s.get("section_type") for s in (tree or {}).get("sections", [])]
    eta_seq = [s.get("section") for s in etalon.get("sections", [])]
    lcs = _lcs_len(my_seq, eta_seq)
    sequence_lcs_ratio = lcs / len(eta_seq) if eta_seq else None

    n11 = min(11, len(eta_seq))
    matches11 = sum(1 for i in range(n11)
                    if i < len(my_seq) and my_seq[i] == eta_seq[i])
    first11_match = (matches11 / n11) if n11 else None

    return {
        "heading_accuracy": round(heading_accuracy, 4)
        if heading_accuracy is not None else None,
        "sequence_lcs_ratio": round(sequence_lcs_ratio, 4)
        if sequence_lcs_ratio is not None else None,
        "first11_match": round(first11_match, 4) if first11_match is not None else None,
        "first11_mismatches": [
            (my_seq[i] if i < len(my_seq) else None, eta_seq[i])
            for i in range(n11)
            if (my_seq[i] if i < len(my_seq) else None) != eta_seq[i]
        ],
        "wrong_headings": wrong,
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Разметка структуры автореферата")
    ap.add_argument("path", help="путь к документу (docx/pdf/md)")
    ap.add_argument("--max-paragraphs", type=int, default=100)
    args = ap.parse_args()
    out = annotate_document(args.path, max_paragraphs=args.max_paragraphs)
    print(json.dumps({
        "path": out["path"],
        "sections": [s["section_type"] for s in out["sections"]],
        "sections_recognized": out["meta"]["sections_recognized"],
        "slots": len(out["slots"]),
        "gaps": len(out["gaps"]),
        "slot_summary": out["meta"]["slot_summary"],
        "errors": len(out["meta"]["errors"]),
    }, ensure_ascii=False, indent=2))