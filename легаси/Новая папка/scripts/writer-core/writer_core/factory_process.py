# -*- coding: utf-8 -*-
"""writer_core.factory_process — фабрика письма: draft -> RTT -> constrained repair.

Цикл по образцу фабрики кода (shared/code-factory-process.md), но для письма:

    draft
      -> draftcheck   (re-extraction черновика ДЕТЕРМИНИРОВАННО через
                       hybrid_extract + RTT-дифф против WriterContract)
      -> reject/approve
      -> constrained repair  (ТОЛЬКО дефектные claim_id + span; чужие
                              фрагменты не модифицируются)
      -> повтор draftcheck
      -> иттерации ОГРАНИЧЕНЫ (max_iterations) — нет бесконечного цикла.

Ключевые функции:
  extract_draft_claims(draft_text)          — re-extraction черновика
                                              (детерминированно, hybrid_extract);
  match_contract_claims(contract_claims,    — сопоставление claim контракта
                        draft_claims)         с claim черновика (token overlap);
  draftcheck(draft_text, contract_claims)   — полный RTT-дифф -> отчёт;
  apply_constrained_repair(draft_text,      — ремонт только span'ов дефектов;
                           defects)
  run_writer_cycle(draft_text, contract_claims, max_iterations) — цикл фабрики.

Fail-closed: любой сбой на этапе re-extraction/диффа -> отчёт с errors,
исключения наружу не пробрасываются (кроме явных ValueError на битом вводе
контракта — их ловит CLI и превращает в JSON-ошибку).
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_WC_ROOT = os.environ.get("WRITER_CORE_ROOT") or (os.path.dirname(_HERE) if os.path.basename(_HERE) == "writer_core" else _HERE)
for _p in (_WC_ROOT, os.path.join(_WC_ROOT, "v2_extractor"), os.path.join(_WC_ROOT, "writer_core")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from writer_core.contracts import Defect, Span, WriterContract  # noqa: E402

# RTT-причина -> defect_type (snake_case, контракт Defect).
_REASON_TO_DEFECT = {
    "CLAIM_OMISSION": "claim_omission",
    "UNAUTHORIZED_CLAIM": "unauthorized_claim",
    "SCOPE_EXPANSION": "scope_expansion",
    "SCOPE_NARROWING": "scope_narrowing",
    "MODALITY_UPGRADE": "modality_upgrade",
    "MODALITY_DOWNGRADE": "modality_downgrade",
    "CAUSALITY_UPGRADE": "causality_upgrade",
    "CAUSALITY_LOSS": "causality_loss",
    "QUALIFIER_LOSS": "qualifier_loss",
    "NEGATION_FLIP": "negation_flip",
    "ENTITY_SUBSTITUTION": "entity_substitution",
    "TEMPORAL_SHIFT": "temporal_shift",
    "NUMERIC_DRIFT": "numeric_drift",
    "UNIT_DRIFT": "unit_drift",
    "PRECISION_INFLATION": "precision_inflation",
    "UNCERTAINTY_LOSS": "uncertainty_loss",
    "EVIDENCE_MISATTRIBUTION": "evidence_misattribution",
    "DISCOURSE_CONNECTIVE_UNJUSTIFIED": "discourse_connective_unjustified",
    "REFORMULATION_DRIFT": "reformulation_drift",
}

# Детерминированные подсказки ремонта по причине.
_SUGGESTIONS = {
    "causality_upgrade": "заменить каузальный маркер на условный/гипотетический"
                         " ('вызывает' -> 'может вызывать', 'приводит к' -> "
                         "'может приводить к') в пределах span",
    "modality_upgrade": "ослабить модальность в пределах span"
                        " ('установлено, что' -> 'показано, что', добавить "
                        "квалификатор 'по-видимому')",
    "scope_expansion": "восстановить ограничение области в пределах span"
                       " (добавить 'в исследованном диапазоне')",
    "qualifier_loss": "вернуть квалификатор в пределах span",
    "claim_omission": "добавить отсутствующее утверждение целиком"
                      " (вне текущих span-ов)",
}


def _tok(text: str) -> list[str]:
    """Токены для сопоставления: lower, только буквы/цифры (кириллица ок)."""
    return re.findall(r"[a-zа-яё0-9]+", (text or "").lower())


# ---------------------------------------------------------------------------
# 1. re-extraction черновика (детерминированно через hybrid_extract)
# ---------------------------------------------------------------------------

def _split_draft_paragraphs(text: str) -> list[tuple[str, int]]:
    """Черновик -> [(абзац, глобальный_offset)], по пустым строкам (как .md)."""
    out: list[tuple[str, int]] = []
    offset = 0
    for block in re.split(r"\n[ \t]*\n", text or ""):
        stripped = block.strip()
        if not stripped:
            offset += len(block) + 1
            continue
        lead = len(block) - len(block.lstrip())
        start = offset + lead
        out.append((stripped, start))
        offset += len(block) + 1
    return out


def extract_draft_claims(draft_text: str, max_paragraphs: int = 100) -> dict:
    """Re-extraction черновика: claims с ГЛОБАЛЬНЫМИ span'ами.

    Детерминированно через hybrid_extract.hybrid_extract_paragraph (v2 claims
    + v0.3 digest + links). Spans пересчитываются в координаты всего
    черновика (внутри параграфа span'ы относительны).

    Возвращает {"claims": [...], "digests": [...], "errors": [...]} —
    claims: {claim_id, text, raw_span, start, end, sentence_idx, qa_status,
             paragraph_id}.
    """
    from hybrid_extract import hybrid_extract_paragraph  # noqa: F401

    claims: list[dict] = []
    digests: list[dict] = []
    errors: list[dict] = []
    for i, (para, para_offset) in enumerate(_split_draft_paragraphs(draft_text)):
        if i >= max_paragraphs:
            break
        try:
            art = hybrid_extract_paragraph(para, f"DRAFT_P{i:04d}", None)
        except Exception as e:  # fail-closed на уровне параграфа
            errors.append({"paragraph": i, "error": f"{type(e).__name__}: {e}"})
            continue
        digests.append(art.get("digest") or {})
        for ci, c in enumerate(art.get("claims") or []):
            cs = c.get("start")
            ce = c.get("end")
            start = (para_offset + cs) if isinstance(cs, int) else None
            end = (para_offset + ce) if isinstance(ce, int) else None
            claims.append({
                "claim_id": f"DRAFT_P{i:04d}_C{ci}",
                "text": c.get("text") or "",
                "raw_span": c.get("raw_span") or c.get("text") or "",
                "start": start,
                "end": end,
                "sentence_idx": c.get("sentence_idx"),
                "qa_status": c.get("qa_status") or "PROPOSED",
                "paragraph_id": f"DRAFT_P{i:04d}",
            })
    return {"claims": claims, "digests": digests, "errors": errors}


# ---------------------------------------------------------------------------
# 2. сопоставление contract claims <-> draft claims
# ---------------------------------------------------------------------------

def match_contract_claims(contract_claims: list[dict],
                          draft_claims: list[dict]) -> list[dict]:
    """Каждый contract claim -> лучший draft claim по пересечению токенов.

    Возвращает [{"contract": dict, "draft": dict|None, "overlap": int}].
    draft=None (overlap=0) означает: утверждение в черновике отсутствует
    (-> CLAIM_OMISSION). Детерминированно, без LLM.
    """
    out: list[dict] = []
    for cc in contract_claims:
        prop = str(cc.get("proposition") or "")
        ptoks = set(_tok(prop))
        best: dict | None = None
        best_score = 0
        for dc in draft_claims:
            ctext = (dc.get("raw_span") or dc.get("text") or "")
            toks = set(_tok(ctext))
            score = len(ptoks & toks)
            if score > best_score:
                best, best_score = dc, score
        out.append({"contract": cc, "draft": best, "overlap": best_score})
    return out


# ---------------------------------------------------------------------------
# 3. draftcheck — RTT-дифф против WriterContract
# ---------------------------------------------------------------------------

def _find_span_in(needle: str, haystack: str) -> tuple[int, int]:
    """Абсолютный span первого вхождения needle в haystack (нормализация пробелов).

    Фолбэк: span всего haystack (0, len). Возвращает (start, end).
    """
    if not needle:
        return 0, len(haystack)
    norm_n = re.sub(r"\s+", " ", needle).strip()
    norm_h = re.sub(r"\s+", " ", haystack)
    idx = norm_h.lower().find(norm_n.lower())
    if idx < 0:
        # усечённая версия: первые 80 симв. needle
        head = norm_n[:80]
        idx = norm_h.lower().find(head.lower())
        if idx < 0:
            return 0, len(haystack)
        return idx, idx + len(head)
    return idx, idx + len(norm_n)


def draftcheck(draft_text: str, contract_claims: list[dict]) -> dict:
    """Полный RTT-дифф черновика против контракта.

    Вход:  contract_claims — list[dict] с полями WriterContract
           (claim_id, proposition, ...) ИЛИ WriterContract-объекты.
    Выход: {"schema", "verdict": "PASS"|"FAIL", "defects": [Defect],
            "checked": [{claim_id, matched, overlap, reasons, notes}],
            "re_extraction": {claims, digests, errors}}.

    Дефект (контракт Defect): defect_type (snake_case), claim_id, span
    (абсолютные координаты в черновике), suggestion. Только причины из
    forbidden_transformations контракта становятся дефектами; остальные
    фиксируются в checked (PASS-информативно).
    """
    from rtt_compare import compare  # noqa: F401

    ccs = [c.model_dump() if isinstance(c, WriterContract) else dict(c)
           for c in contract_claims]

    reext = extract_draft_claims(draft_text or "")
    draft_claims = reext["claims"]
    matched = match_contract_claims(ccs, draft_claims)

    defects: list[Defect] = []
    checked: list[dict] = []
    for m in matched:
        cc, dc = m["contract"], m["draft"]
        cid = str(cc.get("claim_id") or "C0")
        prop = str(cc.get("proposition") or "")
        forbidden = set(cc.get("forbidden_transformations") or [])
        entry: dict = {"claim_id": cid, "matched": dc is not None,
                       "overlap": m["overlap"], "reasons": [], "notes": []}
        if dc is None:
            if "CLAIM_OMISSION" in forbidden or not forbidden:
                defects.append(Defect(
                    defect_type="claim_omission",
                    claim_id=cid,
                    span=None,
                    suggestion=_SUGGESTIONS["claim_omission"],
                    reason_code="CLAIM_OMISSION",
                ))
            entry["reasons"].append("CLAIM_OMISSION")
            checked.append(entry)
            continue
        # RTT: contract.proposition (source) vs draft claim (candidate)
        cand_text = dc.get("raw_span") or dc.get("text") or ""
        try:
            r = compare(prop, cand_text)
        except Exception as e:  # fail-closed: считаем дефектом нечитаемость
            defects.append(Defect(
                defect_type="rtt_error",
                claim_id=cid,
                span=Span(start=dc.get("start") or 0,
                          end=dc.get("end") or len(draft_text),
                          text=cand_text[:200]),
                suggestion="переформулировать утверждение в пределах span",
                reason_code="RTT_ERROR",
            ))
            entry["reasons"].append("RTT_ERROR")
            entry["notes"].append(f"{type(e).__name__}: {e}")
            checked.append(entry)
            continue
        for rc in r.reason_codes:
            rc_name = rc.value if hasattr(rc, "value") else str(rc)
            entry["reasons"].append(rc_name)
        entry["notes"].extend(r.notes or [])

        if r.verdict != "PASS":
            hstart, hend = dc.get("start"), dc.get("end")
            if not (isinstance(hstart, int) and isinstance(hend, int)):
                hstart, hend = _find_span_in(cand_text, draft_text)
            span_text = draft_text[hstart:hend] if (isinstance(hstart, int)
                                                    and isinstance(hend, int)) else ""
            for rc in r.reason_codes:
                rc_name = rc.value if hasattr(rc, "value") else str(rc)
                if forbidden and rc_name not in forbidden:
                    continue
                dname = _REASON_TO_DEFECT.get(rc_name, rc_name.lower())
                defects.append(Defect(
                    defect_type=dname,
                    claim_id=cid,
                    span=Span(start=hstart, end=hend, text=span_text[:300]),
                    suggestion=_SUGGESTIONS.get(dname, "переформулировать в пределах span"),
                    reason_code=rc_name,
                ))
        checked.append(entry)

    verdict = "PASS" if not defects else "FAIL"
    return {
        "schema": "writer_core.rtt_report.v1",
        "generated_by": "writer_core.factory_process.draftcheck",
        "verdict": verdict,
        "defects": [d.model_dump() for d in defects],
        "checked": checked,
        "re_extraction": {
            "claims": draft_claims,
            "digests": reext["digests"],
            "errors": reext["errors"],
        },
    }


# ---------------------------------------------------------------------------
# 4. constrained repair — только дефектные claim_id + span
# ---------------------------------------------------------------------------

# Детерминированные трансформации внутри span (regex -> замена).
_REPAIR_RULES: list[tuple[str, re.Pattern, str]] = [
    # causality_upgrade: каузальный маркер -> гипотетический
    ("causality_upgrade", re.compile(r"вызывает", re.IGNORECASE), "может вызывать"),
    ("causality_upgrade", re.compile(r"приводит\s+к", re.IGNORECASE), "может приводить к"),
    ("causality_upgrade", re.compile(r"обусловлено", re.IGNORECASE), "может быть обусловлено"),
    ("causality_upgrade", re.compile(r"обуславливает", re.IGNORECASE), "может обусловливать"),
    ("causality_upgrade", re.compile(r"является\s+причиной", re.IGNORECASE),
     "может быть причиной"),
    # modality_upgrade: сильное утверждение -> эвиденциальное/ослабленное
    ("modality_upgrade", re.compile(r"установлено,\s*что", re.IGNORECASE), "показано, что"),
    ("modality_upgrade", re.compile(r"установлено", re.IGNORECASE), "показано"),
    ("modality_upgrade", re.compile(r"доказано,\s*что", re.IGNORECASE), "показано, что"),
    ("modality_upgrade", re.compile(r"несомненно", re.IGNORECASE), "по-видимому"),
    # qualifier_loss: добавить квалификатор после вводной части (первого слова)
    ("qualifier_loss", re.compile(r"^(.{0,40}?)(?=,?\s)", re.IGNORECASE),
     r"\1, по-видимому"),
]


def apply_span_repair(text: str, start: int, end: int, defect_type: str) -> str:
    """Применить правила ремонта ТОЛЬКО внутри [start, end) текста.

    Возвращает изменённый текст (длина может измениться). Если ни одно
    правило не сработало — текст не меняется.
    """
    start = max(0, int(start))
    end = min(len(text), int(end))
    if start >= end:
        return text
    seg = text[start:end]
    new_seg = seg
    for dtype, pat, repl in _REPAIR_RULES:
        if dtype != defect_type:
            continue
        new_seg = pat.sub(repl, new_seg)
    if new_seg == seg:
        return text
    return text[:start] + new_seg + text[end:]


def apply_constrained_repair(draft_text: str, defects: list[dict]) -> dict:
    """Ремонт ТОЛЬКО span'ов дефектов (defect_type + claim_id + span).

    - дефекты без span (claim_omission) пропускаются — добавление целого
      утверждения вне зоны компетенции детерминированного слоя;
    - spans сортируются по убыванию start (правка справа налево), поэтому
      координаты более ранних span'ов остаются валидными;
    - каждый применённый ремонт фиксируется в "applied".
    Возвращает {"text": repaired, "applied": [...], "skipped": [...]}.
    """
    valid = []
    for d in defects:
        span = d.get("span") or {}
        if not isinstance(span, dict) or span.get("start") is None:
            continue
        try:
            valid.append({
                "claim_id": str(d.get("claim_id") or "?"),
                "defect_type": str(d.get("defect_type") or ""),
                "start": int(span["start"]),
                "end": int(span["end"]),
            })
        except (TypeError, ValueError):
            continue
    valid.sort(key=lambda v: v["start"], reverse=True)

    text = draft_text
    applied: list[dict] = []
    for v in valid:
        new_text = apply_span_repair(text, v["start"], v["end"], v["defect_type"])
        if new_text != text:
            applied.append(v)
            text = new_text
    skipped = [d for d in defects
               if not (isinstance(d.get("span"), dict)
                       and d.get("span", {}).get("start") is not None)]
    return {"text": text, "applied": applied, "skipped": skipped}


# ---------------------------------------------------------------------------
# 5. writer cycle — фабрика письма с ограничением иттераций
# ---------------------------------------------------------------------------

def run_writer_cycle(draft_text: str, contract_claims: list[dict],
                     max_iterations: int = 3) -> dict:
    """Цикл фабрики письма: draft -> draftcheck -> constrained repair -> ...

    Остановка:
      - approve: draftcheck вернул PASS;
      - iteration_limit: исчерпан max_iterations (даже если дефекты остались);
      - no_progress: ремонт не изменил текст (защита от зацикливания).
    Возвращает {"verdict": "APPROVED"|"REJECTED", "iterations": int,
                "stopped_reason": str, "rounds": [{iteration, verdict,
                defects_count, changed}], "final_draft": str,
                "final_report": dict|None}.
    """
    max_iterations = max(0, int(max_iterations))
    text = draft_text
    rounds: list[dict] = []
    final_report = None
    for it in range(max_iterations + 1):
        report = draftcheck(text, contract_claims)
        final_report = report
        defects = report.get("defects") or []
        rounds.append({"iteration": it, "verdict": report.get("verdict"),
                       "defects_count": len(defects)})
        if report.get("verdict") == "PASS":
            return {"verdict": "APPROVED", "iterations": it,
                    "stopped_reason": "approved", "rounds": rounds,
                    "final_draft": text, "final_report": report}
        if it >= max_iterations:
            break
        repaired = apply_constrained_repair(text, defects)
        rounds[-1]["changed"] = repaired["text"] != text
        if repaired["text"] == text:
            return {"verdict": "REJECTED", "iterations": it + 1,
                    "stopped_reason": "no_progress", "rounds": rounds,
                    "final_draft": text, "final_report": report}
        text = repaired["text"]
    return {"verdict": "REJECTED", "iterations": max_iterations + 1,
            "stopped_reason": "iteration_limit", "rounds": rounds,
            "final_draft": text, "final_report": final_report}


# ---------------------------------------------------------------------------
# helpers для CLI
# ---------------------------------------------------------------------------

def load_contract_claims(contract: Any) -> list[dict]:
    """Нормализация writing_contract.json -> list[dict] WriterContract-полей.

    Принимает: list[{...}], {"claims":[...]}, WriterContract, ResearchBundleLA
    (to_contract_claims). Кидает ValueError на структурно битый ввод.
    """
    if isinstance(contract, WriterContract):
        return [contract.model_dump()]
    if isinstance(contract, dict):
        if "claims" in contract and isinstance(contract["claims"], list):
            return load_contract_claims(contract["claims"])
        if contract.get("schema", "").startswith("writer_core.research_bundle"):
            bundle = contract
            from writer_core.contracts import ResearchBundleLA
            try:
                rb = ResearchBundleLA.model_validate(bundle)
            except Exception as e:
                raise ValueError(f"ResearchBundleLA invalid: {e}") from e
            return [c.model_dump() for c in rb.to_contract_claims()]
        if "claim_id" in contract and "proposition" in contract:
            return [dict(contract)]
        raise ValueError("writing_contract: не распознан формат (нужен list "
                         "или {\"claims\": [...]})")
    if isinstance(contract, list):
        out: list[dict] = []
        for item in contract:
            if isinstance(item, WriterContract):
                out.append(item.model_dump())
            elif isinstance(item, dict) and "claim_id" in item:
                out.append(dict(item))
            else:
                raise ValueError(f"writing_contract: элемент не WriterContract: "
                                 f"{type(item).__name__}")
        return out
    raise ValueError(f"writing_contract: неожиданный тип {type(contract).__name__}")
