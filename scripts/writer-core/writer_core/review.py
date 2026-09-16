# -*- coding: utf-8 -*-
"""writer_core.review — ветвистое ревью (L1/L2/L3) с циклами и эскалацией.

Структура ревью по образцу фабрики кода:

    черновик.md
       ├── L1 (микро): proofreader — стиль/термины/повторы (T0-слой t0_ru +
       │               реестры лингвистики: повторы, канцелярит, терминология
       │               (объекты v2), длина предложений)
       ├── L2 (мезо): editor — структура/полнота слотов/gaps
       │               (structure_annotator.classify_paragraph + plan -> GAP_OPEN /
       │                SECTION_MISSING / ORDER)
       └── L3 (макро): reviewer — RTT-семантика + traceability
                        (factory_process.draftcheck + citation_trace)
              ↓
        review_report.json (verdict + issues по уровням + рекомендации)
              ↓
        если FAIL → constrained repair (L3, apply_constrained_repair)
                    → повторный цикл (max 3)
        если после max_iterations не сходится → escalation = true
                    (human approval required)

Ключевые функции (сигнатуры — контракт m_review):
  L1_PROOFREAD(text)                       — детерминированный proofread -> list[issue];
  L2_EDITOR(plan_or_dom, paragraphs)       — структурная проверка против плана -> list[issue];
  L3_REVIEWER(draft_text, contract_claims, dom=None)
                                           — RTT-дифф + traceability -> dict
                                             {verdict, rtt_defects, trace_checks,
                                              issues: {L1, L2, L3}};
  run_review_levels(draft_text, contract_claims, plan=None, dom=None)
                                           — L1 + L2 + L3 ПАРАЛЛЕЛЬНО (threads),
                                             fail-closed на уровне каждого тира;
  REVIEW_CYCLE(draft_path, contract_claims, plan=None, dom=None,
               max_iterations=3, max_contract_claims=None, out_path=None)
                                           — цикл ревью: draft -> L1/L2/L3 -> repair
                                             -> повтор -> отчёт + эскалация.

Fail-closed: битый ввод (нет черновика / пустой или битый контракт) ->
ValueError наружу (CLI превращает в JSON-ошибку + exit 2); ошибка ОТДЕЛЬНОГО
тира внутри цикла -> отчёт с "error" по тиру, цикл продолжается.

Детерминированно, без LLM. Reuse: t0_ru, registry_loader, extraction_engine
(v2 objects), structure_annotator, factory_process, citation_trace — код не
дублируется.
"""
from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_WC_ROOT = os.environ.get("WRITER_CORE_ROOT") or (os.path.dirname(_HERE) if os.path.basename(_HERE) == "writer_core" else _HERE)
_HARNESS_ROOT = os.path.dirname(os.path.dirname(_WC_ROOT))
_V2_DIR = os.path.join(_WC_ROOT, "v2_extractor")
_CITATION_TRACE_DIRS = (
    os.path.join(_HARNESS_ROOT, "scripts", "writer"),
    os.path.join(_WC_ROOT, "v2_extractor"),
)
for _p in (_WC_ROOT, _V2_DIR, os.path.join(_WC_ROOT, "writer_core")) + _CITATION_TRACE_DIRS:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Разумный порядок секций автореферата (зеркалит live_cycle._DEFAULT_SECTION_ORDER).
_DEFAULT_SECTION_ORDER: list[str] = [
    "TITLE", "RELEVANCE", "OBJECT_SUBJECT", "TOPIC_STATE", "GOAL",
    "TASKS", "NOVELTY", "METHODS", "RESULTS", "CONCLUSION", "LITERATURE",
]

# Служебные слова, не участвующие в проверке повторов.
_STOPWORDS: frozenset[str] = frozenset({
    "и", "в", "на", "с", "по", "от", "для", "при", "к", "из", "до", "о", "об",
    "не", "ни", "а", "но", "или", "же", "то", "что", "как", "так", "это", "его",
    "ее", "её", "их", "мы", "вы", "они", "он", "она", "оно", "все", "всё", "также",
    "уже", "еще", "ещё", "однако", "поэтому", "таким", "образом", "который",
    "которая", "которое", "которые", "этого", "этой", "этих", "этом", "всего",
    "всех", "эта", "эти", "том", "тем", "тех", "был", "была", "были", "было",
    "если", "только", "очень", "более", "менее", "чтобы", "можно", "надо",
})

# Детерминированный реестр канцелярит-маркеров (клише официально-делового стиля).
_KANTSELLARIT: tuple[str, ...] = (
    "в рамках", "осуществляется", "осуществление", "на сегодняшний день",
    "в целях", "представляет собой", "имеет место", "по вопросу",
    "следует отметить", "необходимо отметить", "в процессе",
)

_LONG_SENTENCE_WORDS = 30   # порог длины предложения (слов)
_REPETITION_THRESHOLD = 3   # повтор слова в одном предложении
_MAX_L1_ISSUES = 120        # кэп шума (гигантские склеенные предложения v12)

_REPORT_SCHEMA = "writer_core.review_report.v1"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _split_paragraphs(text: str) -> list[str]:
    """Текст -> [абзац].

    Два правила (markdown-совместимо):
      1. пустые строки разделяют абзацы (как .md / draftcheck);
      2. markdown-заголовок (#, ##, ###, ####, ..., или "ОБЩАЯ ХАРАКТЕРИСТИКА"
         и подобные жирные заголовки без #) НАЧИНАЕТ новый абзац — иначе
         секции, идущие сразу после [Cxx][Sxx]-строки, сливаются с предыдущим
         абзацем и L2 их не видит.
    """
    text = text or ""
    # 1) сначала режем по пустым строкам
    blocks = [b.strip() for b in re.split(r"\n[ \t]*\n", text) if b.strip()]
    # 2) внутри каждого блока режем по markdown-заголовкам
    out: list[str] = []
    for block in blocks:
        parts = re.split(r"(?m)(?=^(?:#{1,6}\s+|[Оо]бщая\s+[Хх]арактеристика|"
                         r"[Аа]ктуальность|[Цц]ель\s+[дД]анной|[Зз]адачи|"
                         r"[Нн]аучная\s+[Нн]овизна|[Оо]бъект\s+и\s+[Пп]редмет|"
                         r"[Пп]роработанность|[Пп]оложения[,\s]+[Вв]ыносимые|"
                         r"[Пп]рактическая\s+[Зз]начимость|[Дд]остоверность|"
                         r"[Аа]пробация|[Лл]ичный\s+[Вв]клад|"
                         r"[Мм]етоды?|[Рр]езультаты|[Вв]ыводы|[Лл]итература))", block)
        for part in parts:
            part = part.strip()
            if part:
                out.append(part)
    return out


def _sentence_spans(text: str, sentences: list[str]) -> list[list[int]]:
    """Предложения -> абсолютные [start, end] в тексте (последовательный поиск)."""
    spans: list[list[int]] = []
    offset = 0
    low = text.lower()
    for s in sentences:
        if not s:
            continue
        idx = text.find(s, offset)
        if idx < 0:
            idx = low.find(s.lower(), offset)
        if idx < 0:
            idx = offset
        spans.append([idx, idx + len(s)])
        offset = idx + len(s)
    return spans


def _defect_span(d: Any) -> list[int] | None:
    """[start, end] из дефекта RTT (span dict) либо None (claim_omission)."""
    if not isinstance(d, dict):
        return None
    sp = d.get("span")
    if isinstance(sp, dict) and isinstance(sp.get("start"), int) \
            and isinstance(sp.get("end"), int):
        return [sp["start"], sp["end"]]
    if isinstance(sp, (list, tuple)) and len(sp) >= 2 \
            and isinstance(sp[0], int) and isinstance(sp[1], int):
        return [sp[0], sp[1]]
    return None


def _l3_issues(rtt_defects: list[dict] | None) -> list[dict]:
    """RTT-дефекты draftcheck -> issues уровня L3 (BLOCKER)."""
    out: list[dict] = []
    for d in rtt_defects or []:
        sp = d.get("span")
        span_text = sp.get("text", "") if isinstance(sp, dict) else ""
        out.append({
            "level": "L3",
            "type": d.get("defect_type"),
            "span": _defect_span(d),
            "text": span_text[:300],
            "suggestion": d.get("suggestion") or "",
            "claim_id": d.get("claim_id"),
            "severity": "BLOCKER",
        })
    return out


# ---------------------------------------------------------------------------
# 1. L1_PROOFREAD — микро-тир: стиль/термины/повторы (детерминированно)
# ---------------------------------------------------------------------------

def _split_sentences_fallback(text: str) -> list[str]:
    """Регекс-сплиттер на случай недоступности t0_ru (fail-closed)."""
    parts = re.split(r"(?<=[.;!?…])\s+(?=[А-ЯЁA-Z0-9«\"(])", text)
    return [p.strip() for p in parts if p.strip()]


def _sentences_t0(text: str) -> list[str]:
    """T0-слой (t0_ru.split_sentences, razdel) с регекс-фолбэком."""
    try:
        from t0_ru import split_sentences  # noqa: F401
        return split_sentences(text)
    except Exception:
        return _split_sentences_fallback(text)


def _kantsellarit_from_lexicon() -> list[str]:
    """Канцелярит-сигналы из академического реестра (booster-класс).

    academic_ru_lexicon не содержит клише-канцелярита, но несёт booster-лексику
    (epistemic_force=BOOSTED, risk=HIGH — «очевидно», «несомненно») — стилевые
    риски, которые proofreader относит к канцелярит/стилю.
    """
    out: list[str] = []
    try:
        from registry_loader import get_registries  # noqa: F401
        r = get_registries()
        for expr, info in r.expr_force.items():
            if info.get("class") == "booster":
                out.append(expr)
    except Exception:
        pass
    return out


def _kantsellarit_registry() -> list[str]:
    return sorted(set(_KANTSELLARIT) | set(_kantsellarit_from_lexicon()))


def _terminology_issues(text: str) -> list[dict]:
    """Терминология по объектам v2 (extraction_engine.extract_object_b).

    Детерминированные проверки (без LLM):
      ABBR_AMBIGUOUS   — одна аббревиатура с РАЗНЫМИ расшифровками в тексте;
      ABBR_REEXPANDED  — расшифровка повторно использована ПОСЛЕ введения
                         аббревиатуры (без «(АББР)») — непоследовательная
                         терминология.
    Fail-closed: сбой v2-извлечения -> [] (proofreader не падает).
    """
    try:
        from extraction_engine import extract_object_b  # noqa: F401
        objs = extract_object_b(text, "REV_L1", 0)
    except Exception:
        return []

    issues: list[dict] = []
    abbr_defs = [o for o in objs
                 if isinstance(o, dict) and o.get("class") == "B_abbr_def"]

    # 1) одна аббревиатура -> разные расшифровки
    by_abbr: dict[str, set[str]] = {}
    for o in abbr_defs:
        abbr = str(o.get("abbr") or "").strip()
        exp = str(o.get("expansion") or "").strip()
        if abbr and exp:
            by_abbr.setdefault(abbr.upper(), set()).add(exp.lower())
    for abbr, exps in by_abbr.items():
        if len(exps) > 1:
            issues.append({
                "type": "TERMINOLOGY",
                "kind": "ABBR_AMBIGUOUS",
                "abbr": abbr,
                "expansions": sorted(exps)[:5],
                "span": None,
                "text": f"аббревиатура «{abbr}» расшифровывается неоднозначно: "
                        f"{', '.join(sorted(exps)[:3])}",
                "suggestion": "закрепить одну расшифровку аббревиатуры на весь текст",
            })

    # 2) расшифровка повторно после введения аббревиатуры
    low = text.lower()
    for o in abbr_defs:
        abbr = str(o.get("abbr") or "").strip()
        exp = str(o.get("expansion") or "").strip()
        if not abbr or not exp:
            continue
        def_end = o.get("end")
        if not isinstance(def_end, int):
            continue
        needle = exp.lower()
        pos = low.find(needle, def_end)
        while pos != -1:
            tail = low[pos + len(needle): pos + len(needle) + len(abbr) + 3]
            if not re.match(r"\(\s*" + re.escape(abbr.lower()) + r"\s*\)", tail):
                issues.append({
                    "type": "TERMINOLOGY",
                    "kind": "ABBR_REEXPANDED",
                    "abbr": abbr,
                    "span": [pos, pos + len(needle)],
                    "text": exp[:200],
                    "suggestion": f"после введения «{abbr}» использовать "
                                  f"аббревиатуру, а не расшифровку",
                })
                break
            pos = low.find(needle, pos + 1)
    return issues


def L1_PROOFREAD(text: str) -> list[dict]:
    """Микро-ревью (детерминированно): повторы, канцелярит, терминология, длина.

    Вход: текст черновика. Выход: list[issue]:
      {level: "L1", type, span: [start, end]|None, text, suggestion, severity}.
    T0-слой (t0_ru.split_sentences) + реестры лингвистики + объекты v2.
    """
    text = text or ""
    issues: list[dict] = []
    sentences = _sentences_t0(text)
    spans = _sentence_spans(text, sentences)
    words_re = re.compile(r"[а-яёa-z0-9]{4,}")

    for si, sent in enumerate(sentences):
        span = spans[si] if si < len(spans) else [0, len(text)]
        low = sent.lower()
        excerpt = sent[:200]

        # --- повторы: слово >= 3 раз в одном предложении ---
        counter: dict[str, int] = {}
        for w in words_re.findall(low):
            if w not in _STOPWORDS:
                counter[w] = counter.get(w, 0) + 1
        for w, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
            if n < _REPETITION_THRESHOLD:
                continue
            issues.append({
                "level": "L1",
                "type": "REPETITION",
                "span": span,
                "text": excerpt,
                "suggestion": f"слово «{w}» повторяется {n} раз(а) в одном "
                              f"предложении — заменить часть повторов "
                              f"(синоним/местоимение/опущение)",
                "severity": "MINOR",
                "word": w,
                "count": n,
            })
            break  # одно слово-лидер на предложение (анти-шум)

        # --- длина предложения > 30 слов ---
        n_words = len(words_re.findall(low))
        if n_words > _LONG_SENTENCE_WORDS:
            issues.append({
                "level": "L1",
                "type": "LONG_SENTENCE",
                "span": span,
                "text": excerpt,
                "suggestion": f"предложение из {n_words} слов — разбить на "
                              f"несколько (целевая длина <= {_LONG_SENTENCE_WORDS})",
                "severity": "MINOR",
                "words": n_words,
            })

    # --- канцелярит (реестр + booster-лексика академического реестра) ---
    for marker in _kantsellarit_registry():
        m = re.search(re.escape(marker), text, re.IGNORECASE)
        if m:
            issues.append({
                "level": "L1",
                "type": "KANTSELLARIT",
                "span": [m.start(), m.end()],
                "text": marker,
                "suggestion": f"канцелярит «{marker}» — заменить на "
                              f"академическую формулировку",
                "severity": "MINOR",
                "marker": marker,
            })

    # --- терминология (объекты v2) ---
    issues.extend(_terminology_issues(text))

    issues.sort(key=lambda i: (i.get("span") or [0, 0])[0])
    return issues[:_MAX_L1_ISSUES]


# ---------------------------------------------------------------------------
# 2. L2_EDITOR — мезо-тир: структура/полнота слотов/gaps против плана
# ---------------------------------------------------------------------------

def _norm_paragraphs(paragraphs: Any) -> list[str]:
    """str (весь черновик) | list[str] -> list[str] абзацев."""
    if isinstance(paragraphs, str):
        return _split_paragraphs(paragraphs)
    if isinstance(paragraphs, list):
        return [str(p) for p in paragraphs if str(p).strip()]
    return []


def _detect_sections(paragraphs: list[str]) -> dict[str, dict]:
    """Абзацы -> {section_type: {"paras": [...], "first_idx": int}}.

    Классификация через structure_annotator.classify_paragraph; UNKNOWN
    наследует секцию предыдущего абзаца (как build_document_tree).
    Fail-closed: сбой классификатора -> {} (editor не падает).
    """
    try:
        from structure_annotator import classify_paragraph  # noqa: F401
    except Exception:
        return {}
    found: dict[str, dict] = {}
    current: str | None = None
    for idx, p in enumerate(paragraphs):
        try:
            sec, _conf = classify_paragraph(p)
        except Exception:
            sec = "UNKNOWN"
        if sec == "UNKNOWN":
            sec = current
        if not sec:
            continue
        current = sec
        entry = found.setdefault(sec, {"paras": [], "first_idx": idx})
        entry["paras"].append(p)
    return found


def _slot_filled(section_paras: list[str], slot: dict,
                 claim_detectors: dict[str, list[str]],
                 artifact_detectors: dict[str, list[str]],
                 quantity_units: str) -> bool:
    """Слот плана заполнен, если контент секции даёт claim/artifact-сигнатуру."""
    if not section_paras:
        return False
    expected = str(slot.get("expected") or "")
    kind = str(slot.get("kind") or "")
    if kind == "claim":
        pats = claim_detectors.get(expected) or []
    elif expected == "QUANTITY":
        pats = [quantity_units] if quantity_units else []
    else:
        pats = artifact_detectors.get(expected) or []
    if not pats:
        # неизвестный тип слота: считаем заполненным, если секция не пуста
        return True
    for p in section_paras:
        low = p.lower()
        if any(re.search(pat, low) for pat in pats):
            return True
    return False


def L2_EDITOR(plan_or_dom: Any, paragraphs: Any) -> list[dict]:
    """Мезо-ревью: gaps плана (незаполненные слоты), отсутствующие секции,
    порядок секций.

    plan_or_dom — structure_plan.json (dict | путь), либо DOM-словарь
    (structure.chapters[].sections[]) — best-effort; None -> [].
    paragraphs — str (черновик) | list[str].

    Выход: list[issue]: {level: "L2", type: GAP_OPEN|SECTION_MISSING|ORDER,
    slot_id, section, span: None, text, suggestion, severity: BLOCKER|INFO}.
    """
    paragraphs = _norm_paragraphs(paragraphs)
    issues: list[dict] = []

    # --- загрузка/нормализация плана ---
    if isinstance(plan_or_dom, str):
        try:
            with open(plan_or_dom, "r", encoding="utf-8-sig") as fh:
                plan_or_dom = json.load(fh)
        except Exception:
            raise ValueError(f"review L2: план не читается: {plan_or_dom}")
    if plan_or_dom is None:
        return []
    if not isinstance(plan_or_dom, dict):
        raise ValueError(f"review L2: план должен быть dict/path, "
                         f"получен {type(plan_or_dom).__name__}")

    # DOM-вид (литературный объект): секции по structure.chapters
    if "structure" in plan_or_dom and isinstance(
            plan_or_dom["structure"].get("chapters"), list):
        expected_sections: list[dict] = []
        for ch in plan_or_dom["structure"]["chapters"]:
            for s in ch.get("sections") or []:
                expected_sections.append({"id": s.get("id"),
                                          "title": s.get("title") or ""})
        low_paras = [p.lower() for p in paragraphs]
        for sec in expected_sections:
            sid = str(sec.get("id") or "")
            title = str(sec.get("title") or "")
            present = bool(sid and any(sid.lower() in p for p in low_paras))
            if not present and title and len(title) > 3:
                present = any(title[:40].lower() in p for p in low_paras)
            if not present and sid:
                issues.append({
                    "level": "L2", "type": "SECTION_MISSING", "slot_id": None,
                    "section": sid, "span": None,
                    "text": f"секция DOM «{title or sid}» отсутствует в черновике",
                    "suggestion": "добавить секцию по структуре DOM",
                    "severity": "BLOCKER",
                })
        return issues

    # structure_plan-вид
    try:
        from structure_annotator import (  # noqa: F401
            SECTION_REGISTRY, _ARTIFACT_DETECTORS, _CLAIM_DETECTORS,
            _QUANTITY_UNITS,
        )
        claim_det = dict(_CLAIM_DETECTORS or {})
        artifact_det = dict(_ARTIFACT_DETECTORS or {})
        qunits = _QUANTITY_UNITS or ""
    except Exception:  # fail-closed: минимальные детекторы-фолбэк
        claim_det = {"RESULT_CLAIM": [r"установлено", r"показано", r"составл"],
                     "PROBLEM_STATEMENT": [r"проблем", r"актуальн"]}
        artifact_det = {"TABLE": [r"табл", r"table"],
                        "FIGURE": [r"рис"], "CITATION": [r"опубликован"]}
        qunits = r"\d+[.,]?\d*\s*(%|мкм|нм|мм|МПа|ГПа|К|ч|°C)"

    sections = plan_or_dom.get("sections") or []
    order = [str(s.get("section_type") or "")
             for s in sections if s.get("section_type")]
    if not order:
        order = list(_DEFAULT_SECTION_ORDER)
    slots = plan_or_dom.get("slots") or plan_or_dom.get("gaps") or []
    section_status = plan_or_dom.get("section_status") or {}

    found = _detect_sections(paragraphs)

    # --- SECTION_MISSING: секции с требованиями, которых нет в черновике ---
    for stype in order:
        if stype in found:
            continue
        if section_status.get(stype) == "N/A":
            continue
        spec = (SECTION_REGISTRY or {}).get(stype) or {}
        if not (spec.get("required_claims") or spec.get("required_artifacts")):
            continue
        issues.append({
            "level": "L2", "type": "SECTION_MISSING", "slot_id": None,
            "section": stype, "span": None,
            "text": f"секция «{stype}» отсутствует в черновике",
            "suggestion": f"добавить секцию «{stype}» с требуемым содержимым",
            "severity": "BLOCKER",
        })

    # --- GAP_OPEN: слоты плана, не заполненные контентом своей секции ---
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        sec = str(slot.get("section") or "")
        if sec not in found:
            continue  # отсутствие секции уже покрыто SECTION_MISSING
        expected = str(slot.get("expected") or "")
        if _slot_filled(found[sec]["paras"], slot, claim_det, artifact_det, qunits):
            continue
        issues.append({
            "level": "L2", "type": "GAP_OPEN", "slot_id": slot.get("id"),
            "section": sec, "span": None,
            "text": f"слот «{slot.get('id')}» ({expected}) секции «{sec}» "
                    f"не заполнен контентом черновика",
            "suggestion": f"заполнить слот «{expected}» в секции «{sec}»",
            "severity": "BLOCKER",
            "expected": expected,
        })

    # --- ORDER: нарушение канонического порядка следования секций ---
    found_order = sorted(found.items(), key=lambda kv: kv[1]["first_idx"])
    canon_pos = {stype: i for i, stype in enumerate(order)}
    for i in range(1, len(found_order)):
        prev_stype = found_order[i - 1][0]
        cur_stype = found_order[i][0]
        cp_prev = canon_pos.get(prev_stype)
        cp_cur = canon_pos.get(cur_stype)
        if cp_prev is None or cp_cur is None or cp_prev <= cp_cur:
            continue
        issues.append({
            "level": "L2", "type": "ORDER", "slot_id": None,
            "section": cur_stype, "span": None,
            "text": f"секция «{cur_stype}» следует раньше «{prev_stype}», "
                    f"но в каноническом порядке «{prev_stype}» идёт раньше",
            "suggestion": f"переместить секцию «{cur_stype}» после "
                          f"«{prev_stype}»",
            "severity": "INFO",
        })
    return issues


# ---------------------------------------------------------------------------
# 3. L3_REVIEWER — макро-тир: RTT-семантика + traceability
# ---------------------------------------------------------------------------

def _load_dom(dom: Any) -> Any:
    """dom: dict | путь (.yaml/.yml/.json) -> dict | None."""
    if dom is None:
        return None
    if isinstance(dom, dict):
        return dom
    if isinstance(dom, str):
        if not os.path.exists(dom):
            raise ValueError(f"review: файл DOM не найден: {dom}")
        try:
            if dom.lower().endswith((".yaml", ".yml")):
                import yaml  # noqa: F401
                with open(dom, "r", encoding="utf-8") as fh:
                    return yaml.safe_load(fh)
            with open(dom, "r", encoding="utf-8-sig") as fh:
                return json.load(fh)
        except Exception:
            raise ValueError(f"review: DOM не читается: {dom}")
    raise ValueError(f"review: DOM не распознан ({type(dom).__name__})")


def _run_citation_trace(draft_text: str, dom: Any) -> dict | None:
    """Traceability: citation_trace.run(text, dom) -> checks (fail-closed).

    Возвращает dict отчёта цитатного гейта либо {"error": ...} при сбое.
    """
    if dom is None:
        return None
    try:
        from citation_trace import run as _ct_run  # noqa: F401
        return _ct_run(draft_text, _load_dom(dom), strict=False, fail_on="high")
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "verdict": "FAIL"}


def L3_REVIEWER(draft_text: str, contract_claims: Any, dom: Any = None) -> dict:
    """Макро-ревью: RTT-дифф (draftcheck) + traceability (citation_trace).

    Вход:
      draft_text      — текст черновика;
      contract_claims — list[dict] | WriterContract | writing_contract dict |
                        путь к .json / документу-эталону (v8);
      dom             — DOM (dict | путь yaml/json) для цитатного гейта | None.

    Выход: {"verdict": "PASS"|"FAIL", "rtt_defects": [...],
            "trace_checks": dict|None, "n_defects": int,
            "issues": {"L1": [...], "L2": [...], "L3": [...]}}.
    """
    from writer_core.factory_process import draftcheck  # noqa: F402

    claims = _resolve_contract_claims(contract_claims)
    rtt = draftcheck(draft_text or "", claims)
    rtt_defects = rtt.get("defects") or []
    trace = _run_citation_trace(draft_text, dom)

    trace_verdict = None
    if isinstance(trace, dict):
        trace_verdict = "FAIL" if (trace.get("verdict") == "FAIL"
                                   or "error" in trace) else "PASS"

    verdict = "FAIL" if (rtt.get("verdict") != "PASS" or trace_verdict == "FAIL") \
        else "PASS"
    return {
        "verdict": verdict,
        "rtt_defects": rtt_defects,
        "n_defects": len(rtt_defects),
        "trace_checks": trace,
        "trace_verdict": trace_verdict,
        "issues": {
            "L1": L1_PROOFREAD(draft_text or ""),
            "L2": L2_EDITOR(None, draft_text or ""),
            "L3": _l3_issues(rtt_defects),
        },
    }


# ---------------------------------------------------------------------------
# 4. параллельный запуск тиров + мерж вердикта
# ---------------------------------------------------------------------------

def _run_parallel(jobs: dict[str, Any]) -> dict:
    """{имя: callable} -> {имя: result|{"error": ...}} (ThreadPoolExecutor).

    Fail-closed на уровне задачи: исключение -> {"error": ...} в отчёте.
    """
    results: dict[str, Any] = {}
    names = list(jobs.keys())
    if not names:
        return results
    with ThreadPoolExecutor(max_workers=len(names)) as ex:
        futures = {n: ex.submit(jobs[n]) for n in names}
        for n in names:
            try:
                results[n] = futures[n].result()
            except Exception as e:
                results[n] = {"error": f"{type(e).__name__}: {e}"}
    return results


def run_review_levels(draft_text: str, contract_claims: Any,
                      plan: Any = None, dom: Any = None) -> dict:
    """L1 + L2 + L3 ПАРАЛЛЕЛЬНО -> {"L1": [...], "L2": [...], "L3": {...}}.

    L2 пропускается ({"skipped": True}), если plan не передан — без
    структурного базиса мезо-тир не запускается (не выдумываем секции).
    """
    def _l1() -> Any:
        return L1_PROOFREAD(draft_text)

    def _l2() -> Any:
        if plan is None:
            return {"skipped": True, "note": "plan не передан — L2 не запущен",
                    "issues": []}
        return L2_EDITOR(plan, draft_text)

    def _l3() -> Any:
        return L3_REVIEWER(draft_text, contract_claims, dom)

    return _run_parallel({"L1": _l1, "L2": _l2, "L3": _l3})


def _merge_verdict(levels: dict) -> dict:
    """Вердикт цикла из результатов тиров (fail-closed)."""
    l1 = levels.get("L1")
    l2 = levels.get("L2")
    l3 = levels.get("L3")

    errors = [k for k, v in levels.items()
              if isinstance(v, dict) and "error" in v]
    rtt_verdict = (l3 or {}).get("verdict") if isinstance(l3, dict) else None
    trace = (l3 or {}).get("trace_checks") if isinstance(l3, dict) else None
    trace_verdict = (l3 or {}).get("trace_verdict")
    if trace_verdict is None and isinstance(trace, dict):
        trace_verdict = "FAIL" if "error" in trace else trace.get("verdict")

    l2_blockers: list[dict] = []
    if isinstance(l2, list):
        l2_blockers = [i for i in l2 if i.get("severity") == "BLOCKER"]

    verdict = "PASS"
    reasons: list[str] = []
    if rtt_verdict != "PASS":
        verdict = "FAIL"
        reasons.append("RTT_FAIL")
    if trace_verdict == "FAIL":
        verdict = "FAIL"
        reasons.append("TRACE_FAIL")
    if l2_blockers:
        verdict = "FAIL"
        reasons.append("L2_STRUCTURE_BLOCKERS")
    if errors:
        verdict = "FAIL"
        reasons.append("LEVEL_ERROR:" + ",".join(sorted(errors)))

    return {
        "verdict": verdict,
        "reasons": reasons,
        "rtt_verdict": rtt_verdict,
        "trace_verdict": trace_verdict,
        "l2_blockers": len(l2_blockers),
    }


# ---------------------------------------------------------------------------
# 5. REVIEW_CYCLE — цикл ревью с ограничением итераций и эскалацией
# ---------------------------------------------------------------------------

def _resolve_contract_claims(contract_claims: Any) -> list[dict]:
    """Нормализация контракта (list/dict/WriterContract/путь json|документ)."""
    from writer_core.factory_process import load_contract_claims  # noqa: F402

    if isinstance(contract_claims, str):
        if not os.path.exists(contract_claims):
            raise ValueError(f"review: файл контракта не найден: "
                             f"{contract_claims}")
        if contract_claims.lower().endswith(".json"):
            with open(contract_claims, "r", encoding="utf-8-sig") as fh:
                return load_contract_claims(json.load(fh))
        # документ-эталон (docx/pdf/md): как v8 в run_live_cycle
        from writer_core.live_cycle import writer_contract_from_path  # noqa: F402
        return [c.model_dump() for c in writer_contract_from_path(contract_claims)]
    return load_contract_claims(contract_claims)


def _load_plan(plan: Any) -> Any:
    if plan is None:
        return None
    if isinstance(plan, str):
        if not os.path.exists(plan):
            raise ValueError(f"review: файл плана не найден: {plan}")
        with open(plan, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    return plan


def write_review_report(report: dict, out_path: str) -> None:
    """Отчёт -> review_report.json (UTF-8, ensure_ascii=False)."""
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)


def REVIEW_CYCLE(draft_path: str, contract_claims: Any, plan: Any = None,
                 dom: Any = None, max_iterations: int = 3,
                 max_contract_claims: int | None = None,
                 out_path: str | None = None) -> dict:
    """Цикл ревью: draft -> L1/L2/L3 (параллельно) -> constrained repair -> ...

    Остановка:
      - approved      — вердикт PASS (RTT + trace + структура L2);
      - iteration_limit — исчерпан max_iterations (FAIL остался);
      - no_progress   — constrained repair не изменил текст.
    Если после цикла вердикт != PASS -> escalation = true (human approval).

    Выход: review_report dict {schema, iterations, final_verdict,
    stopped_reason, escalation, escalation_reasons, issues_by_level,
    rtt_defects_final, trace_checks_final, repaired_spans, rounds, inputs}.
    Если out_path задан — пишет review_report.json.
    """
    if not os.path.exists(draft_path):
        raise ValueError(f"review: черновик не найден: {draft_path}")
    with open(draft_path, "r", encoding="utf-8-sig") as fh:
        draft_text = fh.read()

    claims_all = _resolve_contract_claims(contract_claims)
    if not claims_all:
        raise ValueError("review: пустой список claims контракта")
    claims = claims_all
    if max_contract_claims is not None:
        claims = claims_all[:int(max_contract_claims)]
    if not claims:
        raise ValueError("review: max_contract_claims=0 — нечего сверять")

    plan = _load_plan(plan)
    max_iterations = max(0, int(max_iterations))

    text = draft_text
    rounds: list[dict] = []
    repaired_spans: list[dict] = []
    final_verdict = "FAIL"
    stopped_reason = "iteration_limit"
    final_levels: dict = {"L1": [], "L2": [], "L3": []}

    for it in range(max_iterations + 1):
        levels = run_review_levels(text, claims, plan=plan, dom=dom)
        merged = _merge_verdict(levels)

        l1 = levels.get("L1") if isinstance(levels.get("L1"), list) else []
        l2 = levels.get("L2")
        l3 = levels.get("L3") if isinstance(levels.get("L3"), dict) else {}
        rtt_defects = l3.get("rtt_defects") or []
        trace = l3.get("trace_checks")

        rounds.append({
            "iteration": it,
            "verdict": merged["verdict"],
            "reasons": merged["reasons"],
            "n_l1": len(l1),
            "n_l2": (len(l2) if isinstance(l2, list) else 0),
            "n_l3_defects": len(rtt_defects),
            "trace_verdict": merged["trace_verdict"],
            "changed": None,
        })
        final_levels = {
            "L1": l1,
            "L2": l2 if isinstance(l2, list) else
                  (l2 if isinstance(l2, dict) else []),
            "L3": _l3_issues(rtt_defects),
        }
        final_verdict = merged["verdict"]
        trace_final = trace

        if merged["verdict"] == "PASS":
            stopped_reason = "approved"
            break
        if it >= max_iterations:
            stopped_reason = "iteration_limit"
            break

        # constrained repair ТОЛЬКО по L3-дефектам (defect_type + span)
        from writer_core.factory_process import (  # noqa: F402
            apply_constrained_repair,
        )
        repaired = apply_constrained_repair(text, rtt_defects)
        if repaired["text"] == text:
            stopped_reason = "no_progress"
            rounds[-1]["changed"] = False
            break
        repaired_spans.extend(repaired["applied"])
        rounds[-1]["changed"] = True
        text = repaired["text"]

    escalation = final_verdict != "PASS"
    escalation_reasons: list[str] = []
    if escalation:
        if any(round_.get("verdict") != "PASS" for round_ in rounds):
            escalation_reasons.append(
                f"вердикт FAIL после {len(rounds)} итераций (максимум "
                f"{max_iterations}): semantic/структурные дефекты не "
                f"устраняются детерминированным constrained repair — "
                f"требуется approval человека")
        if stopped_reason == "no_progress":
            escalation_reasons.append(
                "constrained repair не изменил текст (нерепарируемые дефекты: "
                "claim_omission/структурные gaps) — нет сходимости")

    report: dict = {
        "schema": _REPORT_SCHEMA,
        "generated_by": "writer_core.review.REVIEW_CYCLE",
        "created_at": _utc_now_iso(),
        "inputs": {
            "draft": os.path.normpath(draft_path),
            "contract": (os.path.normpath(contract_claims)
                         if isinstance(contract_claims, str)
                         else f"inline({type(contract_claims).__name__})"),
            "plan": (os.path.normpath(plan) if isinstance(plan, str) else
                     (plan.get("schema") if isinstance(plan, dict) else None)),
            "dom": (os.path.normpath(dom) if isinstance(dom, str) else None),
            "max_iterations": max_iterations,
            "max_contract_claims": max_contract_claims,
            "draft_chars": len(draft_text),
        },
        "iterations": len(rounds),
        "final_verdict": final_verdict,
        "stopped_reason": stopped_reason,
        "escalation": escalation,
        "escalation_reasons": escalation_reasons,
        "issues_by_level": final_levels,
        "rtt_defects_final": _l3_issues(final_levels.get("L3") or []),
        "trace_checks_final": trace_final,
        "repaired_spans": repaired_spans,
        "rounds": rounds,
    }

    if out_path:
        write_review_report(report, out_path)
    return report


if __name__ == "__main__":
    print(json.dumps({
        "module": "writer_core.review",
        "functions": ["L1_PROOFREAD", "L2_EDITOR", "L3_REVIEWER",
                      "run_review_levels", "REVIEW_CYCLE",
                      "write_review_report"],
        "schema": _REPORT_SCHEMA,
    }, ensure_ascii=False, indent=2))
