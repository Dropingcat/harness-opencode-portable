# -*- coding: utf-8 -*-
"""M_HYBRID_EXTRACT — гибридный экстрактор научного текста (v2 + v0.3).

Унифицированный артефакт на параграф, объединяющий два независимых слоя:

  v2 (детерминированный экстрактор, runtime-owned v2_extractor/):
    - claims   — кандидаты-утверждения с абсолютными координатами (start/end, sentence_idx)
    - objects  — числа+единицы (C5), сталь, химия, годы, аббревиатуры, термины
    - discourse— дискурс-роли (метод/результат/вывод/...) и модальность
    - philology— морфология, стилистические фигуры, хрия, коннекторы (philologcal_layer)

  v0.3 (runtime-owned T0-лингвослой, t0_ru.py + digest_builder.py):
    - digest — LinguisticDigest (pydantic → dict) на ДОМИНАНТНОМ предложении
      (первом значимом — с claims): main_statement, scope, modality,
      causal_force, discourse_role, ambiguities, affordances, scope_text

  Мост между слоями (формат — контракт graph-моста graph_builder_hybrid):
    - sentences               — предложения по razdel с координатами И токенами
                                [{text,start,end,idx,pos}]
    - links.claim_to_digest   — [{"claim": int, "sentence": int, "overlap": float}]
                                (claims в доминантном предложении)
    - links.object_to_claim   — [{"object": oi, "claim": ci}]

QA (claim_qa.py): каждый claim v2 пропускается через span-grounding на ПОЛНОМ
тексте (raw_span, не усечённые 120 симв.) + детерминированную типизацию;
статус GROUNDED/UNGROUNDED. Дословное предложение = exact (нормализация
переносов строк в claim_qa). Если claim_qa недоступен — qa_status="PROPOSED".

Fail-closed: на уровне параграфа/документа ошибки собираются в meta["errors"],
весь документ не роняем.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_WC_ROOT = os.environ.get("WRITER_CORE_ROOT") or _HERE
_V2_DIR = os.path.join(_WC_ROOT, "v2_extractor")

for _p in (_V2_DIR, _WC_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:  # python-docx для извлечения таблиц .docx (Document.tables)
    import docx as _PYDOCX  # type: ignore

    _PYDOCX_OK = True
except Exception:  # pragma: no cover
    _PYDOCX = None  # type: ignore[assignment]
    _PYDOCX_OK = False

# ------------------------- v2 слой (жёсткие зависимости) -------------------------

from extraction_engine import extract_all  # noqa: E402
from philologcal_layer import analyze as phil_analyze  # noqa: E402

# ------------------------- QA (опционально, контракт: PROPOSED fallback) ---------

try:  # pragma: no cover
    from claim_qa import classify_claim, span_locate  # noqa: E402

    _QA_AVAILABLE = True
except Exception:  # pragma: no cover
    _QA_AVAILABLE = False

# ------------------------- v0.3 слой ----------------------------------------------

from digest_builder import build_digest  # noqa: E402

try:  # pragma: no cover
    from corpus_runner import extract_document  # noqa: E402

    _CORPUS_OK = True
except Exception:  # pragma: no cover
    extract_document = None
    _CORPUS_OK = False


# ------------------------------------------------------------------------- helpers

def _split_sentences_spans(text: str) -> list[dict]:
    """Предложения с координатами и токенами (razdel, абсолютные оффсеты в абзаце).

    Токены: {text, start, end, idx, pos} — координаты в тексте параграфа.
    Фолбэк при сбое razdel — regex-сплиттер v2 (c1_c2_structure) с токенами
    по пробелам (те же ключи).
    """
    try:
        from razdel import sentenize, tokenize

        out: list[dict] = []
        for s in sentenize(text):
            raw = s.text
            stripped = raw.strip()
            if not stripped:
                continue
            lead = len(raw) - len(raw.lstrip())
            sstart = int(s.start) + lead
            send = sstart + len(stripped)
            toks: list[dict] = []
            for ti, t in enumerate(tokenize(raw)):
                tstart = int(s.start) + t.start
                toks.append({"text": t.text, "start": tstart,
                             "end": tstart + len(t.text), "idx": ti, "pos": ti})
            out.append({"sentence_idx": len(out), "text": stripped,
                        "start": sstart, "end": send, "tokens": toks})
        if out:
            return out
    except Exception:  # pragma: no cover
        pass
    # fallback: v2 splitter + последовательные оффсеты
    from c1_c2_structure import _split_sentences

    out = []
    offset = 0
    for s in _split_sentences(text):
        if not s:
            continue
        found = text.find(s, offset)
        start = found if found >= 0 else offset
        end = start + len(s)
        offset = end
        toks = []
        pos = 0
        for m in re.finditer(r"\S+", s):
            toks.append({"text": m.group(0), "start": start + m.start(),
                         "end": start + m.end(), "idx": pos, "pos": pos})
            pos += 1
        out.append({"sentence_idx": len(out), "text": s, "start": start,
                    "end": end, "tokens": toks})
    return out


def _digest_to_dict(d, scope_text: str | None = None) -> dict:
    """LinguisticDigest (pydantic) → JSON-серизуемый dict (поля контракта).

    scope_text — предложение, на котором построен digest (доминантное).
    """
    def _impact(v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v)

    out = {
        "main_statement": dict(getattr(d, "main_statement", {}) or {}),
        "scope": dict(getattr(d, "scope", {}) or {}),
        "modality": getattr(d, "modality", None),
        "causal_force": getattr(d, "causal_force", None),
        "discourse_role": getattr(d, "discourse_role", None),
        "ambiguities": [
            {"type": i.type, "impact": _impact(i.impact), "target": i.target,
             "details": dict(i.details) if getattr(i, "details", None) else {}}
            for i in getattr(d, "ambiguities", [])
        ],
        "affordances": list(getattr(d, "affordances", [])),
    }
    if scope_text:
        out["scope_text"] = scope_text
    return out


def _qa_claims(claims: list[dict], text: str) -> list[dict]:
    """Span-grounding + детерминированная типизация каждого claim v2.

    Сопоставление идёт по ПОЛНОМУ тексту claim (raw_span = полное предложение),
    а не по усечённым до 120 симв. claim['text'] — иначе span-QA бракует
    дословные предложения (см. CRITICAL-2 ревью).
    """
    if not _QA_AVAILABLE:
        for c in claims:
            c["qa_status"] = "PROPOSED"
        return claims
    try:
        for c in claims:
            ctext = (c.get("raw_span") or c.get("text") or "").strip()
            if not ctext:
                c["qa_status"] = "UNGROUNDED"
                c["qa_method"] = "none"
                continue
            loc = span_locate(ctext, text)
            grounded = loc["method"] != "none"
            cls = classify_claim(ctext)
            c["qa_status"] = "GROUNDED" if grounded else "UNGROUNDED"
            c["qa_method"] = loc["method"]
            c["role"] = cls.get("role")
            c["kind"] = cls.get("kind")
    except Exception:  # pragma: no cover
        for c in claims:
            c["qa_status"] = "PROPOSED"
    return claims


def _norm_ws(s: str) -> str:
    """Убрать все пробелы — сравнение «250 HV» vs «250HV» при substring-проверках."""
    return re.sub(r"\s+", "", s)


def _sentence_index_of_claim(c: dict, sentences: list[dict]) -> int | None:
    """Индекс предложения (razdel), которому принадлежит claim: по span-перекрытию,
    фолбэк — substring полного текста claim (raw_span) в предложении."""
    cs, ce = c.get("start"), c.get("end")
    best: tuple[int, int] | None = None
    if isinstance(cs, int) and isinstance(ce, int):
        for si, s in enumerate(sentences):
            ov = min(ce, s["end"]) - max(cs, s["start"])
            if ov > 0 and (best is None or ov > best[1]):
                best = (si, ov)
    if best is None:
        low = _norm_ws(c.get("raw_span") or c.get("text") or "").lower()
        for si, s in enumerate(sentences):
            if low and low in _norm_ws(s["text"]).lower():
                best = (si, len(low))
                break
    return best[0] if best else None


def _remap_claim_sentences(claims: list[dict], sentences: list[dict]) -> list[dict]:
    """ЕДИНАЯ нумерация предложений: sentence_idx у claims = индекс в sentences
    (razdel). Устраняет двойную нумерацию v2 vs razdel (MINOR-6 ревью)."""
    for c in claims:
        si = _sentence_index_of_claim(c, sentences)
        if si is not None:
            c["sentence_idx"] = si
    return claims


def _dominant_sentence(sentences: list[dict], claims: list[dict]) -> tuple[dict | None, int]:
    """Первое значимое предложение: первое, которому принадлежит хотя бы один
    claim (по единому sentence_idx, переразмеченному на razdel-нумерацию);
    иначе — первое предложение абзаца."""
    if not sentences:
        return None, -1
    assigned = {c.get("sentence_idx") for c in claims
                if isinstance(c.get("sentence_idx"), int)}
    for si, s in enumerate(sentences):
        if si in assigned:
            return s, si
    return sentences[0], 0


def _build_digest_for(dominant_text: str, fallback_text: str) -> dict:
    """Digest строится на доминантном (первом значимом) предложении.

    scope_text = предложение, на котором построен digest. Fail-closed:
    сбой build_digest на предложении -> пробуем абзац целиком -> статический фолбэк.
    """
    try:
        return _digest_to_dict(build_digest(dominant_text), scope_text=dominant_text)
    except Exception:  # pragma: no cover
        pass
    try:
        return _digest_to_dict(build_digest(fallback_text), scope_text=dominant_text)
    except Exception:  # pragma: no cover
        return {
            "main_statement": {"predicate": "assertion", "text": dominant_text[:300]},
            "scope": {}, "modality": None, "causal_force": None,
            "discourse_role": None, "ambiguities": [], "affordances": [],
            "scope_text": dominant_text,
        }


def _claims_in_sentence(claims: list[dict], sent_idx: int) -> list[dict]:
    """Claims, ПРИНАДЛЕЖАЩИЕ доминантному предложению (по единому
    sentence_idx, который уже переразмечен на razdel-нумерацию).

    Формат контракта (CRITICAL-1 ревью): [{"claim": int, "sentence": int,
    "overlap": float}]. overlap — доля span claim, покрытая предложением
    (1.0 = span целиком вложен; < 1.0 — частичное перекрытие, при котором
    предложение всё же является для claim ближайшим).
    """
    out: list[dict] = []
    for ci, c in enumerate(claims):
        if c.get("sentence_idx") != sent_idx:
            continue
        cs, ce = c.get("start"), c.get("end")
        if not (isinstance(cs, int) and isinstance(ce, int)):
            continue
        out.append({"claim": ci, "sentence": sent_idx, "overlap": 1.0})
    return out


# -------------------------------------------------------------------------
# TD-083: citation-маркеры и ссылки на артефакты репозитория
# -------------------------------------------------------------------------

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]*)\)")
# Путь репозитория: относительный docs/..., скрипт/исходник *.py, документ *.md,
# либо config/... — всё, что НЕ является внешним http(s) URL или якорем (#...).
_REPO_ARTIFACT_RE = re.compile(
    r"^(?:\./|\.\./)?"
    r"(?:(?:docs|scripts?|config|templates?|sources?|references?|artifacts?|guard|skills?|tests?|mcp|plugins?|compatibility)/|"
    r"[A-Za-zА-Яа-яЁё0-9_\-]+/)*"
    r"[A-Za-zА-Яа-яЁё0-9_\-\. ()]+"
    r"\.(?:py|md|json|yaml|yml|txt|csv|docx?|pdf|xlsx?|ts|js|ps1|sh|bat|sql|db|yaml\.example)$"
)
_EXTERNAL_URL_RE = re.compile(r"^(?:https?|ftp|file|mailto):", re.IGNORECASE)


def _extract_md_links(text: str) -> list[dict]:
    """Markdown-ссылки `[Text](url)` -> [{"text", "url", "span": [start, end]}].

    span — координаты ВСЕЙ ссылки `[Text](url)` в исходном тексте параграфа
    (start от '[' до закрывающей ')').

    URL-часть поддерживает вложенные скобки (R4): `[x](https://a/(b))` даёт
    url='https://a/(b)'. Первичный regex `[^)\s]*` останавливается на первой
    ')'; затем балансируем скобки depth-сканированием от открывающей '(' ссылки
    (depth=1): url заканчивается на ')' при depth==0. Это CommonMark-поведение.

    ОБРЕЗКА ПО ГРАНИЦЕ (R1-minor): если скобки НЕ сбалансированы до конца
    текста ('[x](https://a/(b)' без закрывающей ')'), span НЕ выходит за
    len(text): end = min(i+1, len(text)); url обрезается до конца текста.
    """
    out: list[dict] = []
    for m in _MD_LINK_RE.finditer(text):
        url = m.group(2)
        end = m.end()
        if url.count("(") > url.count(")"):
            # вложенные скобки: досканировать до баланса depth (CommonMark)
            depth = 1  # открывающая '(' ссылки уже потреблена
            i = m.start(2)
            while i < len(text):
                ch = text[i]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            if depth == 0:
                end = i + 1  # после закрывающей ')' ссылки
                url = text[m.start(2):i]
            else:
                # несбалансировано: закрывающая ')' ссылки не найдена.
                # url — до конца (без финальной ')' — она не часть url),
                # span не выходит за len(text).
                end = len(text)
                url = text[m.start(2):i]
                if url.endswith(")"):
                    url = url[:-1]
        out.append({"text": m.group(1), "url": url,
                    "span": [m.start(), end]})
    return out


def _is_repo_path(url: str) -> bool:
    """Путь репозитория vs внешний URL/якорь.

    Внешние http(s)/file/ftp/mailto и внутридокументные якоря (#...) НЕ
    считаются путями репозитория. Остальное — кандидат: относительный путь
    в репозитории, заканчивающийся расширением файла (*.py/*.md/...).
    """
    u = (url or "").strip()
    if not u:
        return False
    if _EXTERNAL_URL_RE.match(u):
        return False
    if u.startswith("#"):
        return False
    return bool(_REPO_ARTIFACT_RE.match(u))


def _extract_citation_markers(text: str) -> tuple[list[dict], list[dict]]:
    """TD-083: citation-маркеры из markdown-ссылок параграфа.

    Returns (citations, artifact_refs):
      citations   — [{"text", "url", "span": [start, end]}] — КАЖДАЯ ссылка
      artifact_refs — [{"path", "span": [start, end]}] — только для ссылок на
                      пути репозитория (docs/..., *.py, *.md, config/...).
    """
    citations: list[dict] = []
    artifact_refs: list[dict] = []
    for link in _extract_md_links(text):
        span = link["span"]
        citations.append({"text": link["text"], "url": link["url"],
                          "span": [span[0], span[1]]})
        if _is_repo_path(link["url"]):
            artifact_refs.append({"path": link["url"],
                                  "span": [span[0], span[1]]})
    return citations, artifact_refs


def _link_objects_to_claims(objects: list[dict], claims: list[dict]) -> list[dict]:
    """Объект связан с claim, если:
      - его raw-строка содержится в ПОЛНОМ тексте claim (raw_span, не 120 симв.),
        case-insensitive, пробелы игнорируются («38Х2МЮА» / «250HV» матчатся);
      - ИЛИ span объекта вложен в span claim (fallback для усечённых текстов).
    Формат: [{"object": oi, "claim": ci}] — контракт graph-моста.
    """
    links: list[dict] = []
    for oi, o in enumerate(objects):
        raw = (o.get("raw") or o.get("term") or o.get("value") or o.get("abbr") or "").strip()
        if not raw:
            continue
        nraw = _norm_ws(raw).lower()
        ostart, oend = o.get("start"), o.get("end")
        for ci, c in enumerate(claims):
            full = _norm_ws(c.get("raw_span") or c.get("text") or "").lower()
            hit = bool(nraw and full and nraw in full)
            if not hit and isinstance(ostart, int) and isinstance(oend, int):
                cs, ce = c.get("start"), c.get("end")
                if isinstance(cs, int) and isinstance(ce, int):
                    hit = cs <= ostart and oend <= ce
            if hit:
                links.append({"object": oi, "claim": ci})
    return links


# ------------------------------------------------------------------------- public

def hybrid_extract_paragraph(text: str, para_id: str, page: int | None = None) -> dict:
    """Гибридный артефакт параграфа: v2-детэкстракция + v0.3-дайджест.

    Схема ответа (JSON-серизуемый dict):
      paragraph_id, page, text,
      claims    — v2 claims + qa_status (GROUNDED/UNGROUNDED/PROPOSED) + единый
                  sentence_idx (индекс в sentences, razdel)
      objects   — v2 объекты (class/raw/start/end/unit...)
      discourse — v2 дискурс-роли и модальность
      philology — v2: morphology/figures/chreia/connectors
      digest    — v0.3 build_digest на доминантном предложении + scope_text
      sentences — razdel-предложения с индексами, координатами и токенами
      links     — claim_to_digest ([{claim,sentence,overlap}]) /
                   object_to_claim ([{object,claim}]) — формат graph-моста
      citations — TD-083: markdown-ссылки [Text](url) ->
                   [{"text", "url", "span": [start, end]}]
      artifact_refs — TD-083: только ссылки на пути репозитория (docs/...,
                   *.py, *.md, config/...) -> [{"path", "span": [start, end]}]
      source_links — TD-083: полный список markdown-ссылок (НЕЗАВИСИМАЯ КОПИЯ
                   citations — list(citations), не алиас; R5)
    """
    text = (text or "").strip()
    artifact: dict = {
        "paragraph_id": para_id,
        "page": page,
        "text": text,
        "claims": [],
        "objects": [],
        "discourse": [],
        "philology": {"morphology": {}, "figures": [], "chreia": [], "connectors": []},
        "digest": {},
        "sentences": [],
        "links": {"claim_to_digest": [], "object_to_claim": []},
        "citations": [],
        "artifact_refs": [],
        "source_links": [],
    }
    if not text:
        return artifact

    # ---- v2 слой ----
    det = extract_all(text, para_id, page)
    claims = [dict(c) for c in det.claims]
    objects = [dict(o) for o in det.objects]
    discourse = [dict(d) for d in det.discourse]
    phil = phil_analyze(text)
    philology = {
        "morphology": dict(phil.morphology),
        "figures": [dict(f) for f in phil.figures],
        "chreia": [dict(c) for c in phil.chreia],
        "connectors": [dict(c) for c in phil.connectors],
    }

    # ---- предложения (razdel) + ЕДИНАЯ нумерация sentence_idx у claims ----
    sentences = _split_sentences_spans(text)
    claims = _remap_claim_sentences(claims, sentences)

    # QA claims (span-grounding на полном raw_span + типизация)
    claims = _qa_claims(claims, text)

    # ---- v0.3 слой: digest на доминантном предложении ----
    dom, dom_si = _dominant_sentence(sentences, claims)
    digest = _build_digest_for(dom["text"] if dom else text, text)

    # ---- мост между слоями (формат graph-моста) ----
    links = {
        "claim_to_digest": _claims_in_sentence(claims, dom_si) if dom_si >= 0 else [],
        "object_to_claim": _link_objects_to_claims(objects, claims),
    }

    # ---- TD-083: citation-маркеры из markdown-ссылок ----
    citations, artifact_refs = _extract_citation_markers(text)

    artifact.update({
        "claims": claims,
        "objects": objects,
        "discourse": discourse,
        "philology": philology,
        "digest": digest,
        "sentences": sentences,
        "links": links,
        "citations": citations,
        "artifact_refs": artifact_refs,
        "source_links": list(citations),
    })
    return artifact


def _split_paragraphs(text: str, ext: str, clean_md: bool = True) -> list[str]:
    """Параграфы по типу документа.

    .docx — каждый абзац (python-docx склеивает их '\n');
    .md/.pdf — блоки, разделённые пустыми строками (для .pdf это обычно страницы).

    .md с clean_md=True (по умолчанию): текст сначала чистится от служебных
    блоков конвертера (frontmatter, «### Чанк N», титульные обрывки — см.
    md_clean.clean_md), затем разбивается на параграфы (md_clean.
    split_paragraphs_clean, отбрасывает пустые и короче 15 символов).
    Поведение для .docx/.pdf не меняется.
    """
    if ext == ".docx":
        return [p.strip() for p in text.split("\n") if p.strip()]
    if ext == ".md" and clean_md:
        from md_clean import clean_md as _clean_md  # noqa: E402
        from md_clean import split_paragraphs_clean as _split_clean  # noqa: E402
        return _split_clean(_clean_md(text))
    return [b.strip() for b in re.split(r"\n[ \t]*\n", text) if b.strip()]


def _extract_docx_with_tables(path: str) -> tuple[str, list[str]]:
    """docx -> (текст, таблицы): абзацы и таблицы В ПОРЯДКЕ документа.

    Проблема (ревью M_STRUCT_ANNOTATOR, MAJOR-2): извлечение только параграфов
    (corpus_runner._extract_docx) теряет Document.tables — таблица реально есть
    в документе, но экстрактор/аннотатор её не видят, и AS_RESULTS_TABLE даёт
    ложный WORK_BLOCKING gap.

    Решение: обход body-элементов документа в порядке следования; каждая таблица
    превращается в строку-блок "TABLE: <ячейки>" (ячейки строки — через " | ",
    строки — через " ; "), которая попадает в параграфы как обычный текст —
    таблица становится видимой для _split_paragraphs и для детектора TABLE
    аннотатора (lower("TABLE:") содержит "table").

    Returns (text_with_tables, table_blocks).
    """
    if not _PYDOCX_OK:
        raise RuntimeError("python-docx is not installed")
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = _PYDOCX.Document(path)
    lines: list[str] = []
    tables: list[str] = []
    for child in d.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            lines.append(Paragraph(child, d).text)
        elif tag == "tbl":
            tbl = Table(child, d)
            rows = []
            for row in tbl.rows:
                cells = [c.text.replace("\n", " ").strip() for c in row.cells]
                rows.append(" | ".join(cells))
            block = "TABLE: " + " ; ".join(rows)
            lines.append(block)
            tables.append(block)
    return "\n".join(lines), tables


def hybrid_extract_document(path: str, max_paragraphs: int = 50,
                            clean_md: bool = True) -> dict:
    """Документ → список гибридных артефактов по параграфам.

    - извлечение текста: corpus_runner.extract_document (.docx/.pdf/.md);
      для .docx — _extract_docx_with_tables (абзацы И таблицы, в порядке
      документа; каждая таблица — блок "TABLE: <ячейки>")
    - до max_paragraphs параграфов -> hybrid_extract_paragraph
    - clean_md=True: для .md перед разбиением на параграфы удаляются
      служебные блоки конвертера (md_clean.clean_md); на .docx/.pdf не влияет
    - таблицы документа возвращаются отдельно (result["tables"]) и учитываются
      в meta["table_count"]
    - fail-closed: ошибки в meta["errors"], документ не роняем
    """
    result: dict = {
        "document_path": os.path.normpath(path),
        "paragraphs": [],
        "tables": [],
        "meta": {"count": 0, "chars": 0, "table_count": 0, "errors": []},
    }
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".docx":
            text, tables = _extract_docx_with_tables(path)
        else:
            if not _CORPUS_OK or extract_document is None:
                raise RuntimeError("corpus_runner.extract_document unavailable")
            text = extract_document(path)
            tables = []
    except Exception as e:  # fail-closed: документ целиком не читается
        result["meta"]["errors"].append(
            {"path": path, "paragraph_id": None, "error": f"{type(e).__name__}: {e}"})
        return result
    result["tables"] = tables
    result["meta"]["table_count"] = len(tables)

    paras = _split_paragraphs(text, ext, clean_md=clean_md)
    base = os.path.splitext(os.path.basename(path))[0]
    for i in range(min(len(paras), max_paragraphs)):
        pid = f"{base}_P{i:04d}"
        page = (i + 1) if ext == ".pdf" else None
        try:
            art = hybrid_extract_paragraph(paras[i], pid, page)
            result["paragraphs"].append(art)
            result["meta"]["count"] += 1
            result["meta"]["chars"] += len(paras[i])
        except Exception as e:  # per-paragraph fail-closed
            result["meta"]["errors"].append(
                {"path": path, "paragraph_id": pid, "error": f"{type(e).__name__}: {e}"})
    return result


if __name__ == "__main__":
    import json

    if len(sys.argv) > 1:
        p = sys.argv[1]
        out = hybrid_extract_document(p, max_paragraphs=int(sys.argv[2]) if len(sys.argv) > 2 else 50)
        print(json.dumps({"path": p, "count": out["meta"]["count"],
                          "errors": len(out["meta"]["errors"])}, ensure_ascii=False, indent=2))
    else:
        demo = ("Установлено, что увеличение времени азотирования приводит к росту "
                "микротвердости стали 38Х2МЮА от 250 до 450 HV. Полученные результаты "
                "позволяют предположить наличие связи между температурой и толщиной "
                "диффузионного слоя.")
        a = hybrid_extract_paragraph(demo, "PAR_001", 1)
        print(json.dumps({"claims": len(a["claims"]), "objects": len(a["objects"]),
                          "digest_amb": len(a["digest"]["ambiguities"]),
                          "links": a["links"]}, ensure_ascii=False, indent=2))
