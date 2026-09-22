#!/usr/bin/env python3
"""citation_trace.py — детерминированный цитатный аудит прослеживаемости (WS-18).

Связывает текст научного/инженерного произведения с DOM YAML и дет-ядром
декомпозиции (scripts/writer/extractor): каждое утверждение должно быть
прослеживаемо (claim -> source+span) и маркировано по неопределённости.

Принцип (инвариант): LLM ПРЕДЛАГАЕТ текст, код ПРИНИМАЕТ/ОТКЛОНЯЕТ по span.
Координаты утверждений (start/end) берём из дет-ядра extractor, а не пересказываем.

Проверки (fail-closed, модель-агностично):
  1. DOM валиден (product.kind, structure[id], claims[id], sources[id], uncertainty).
  2. Ссылки [Sxx] резолвятся в sources; [Cxx] в claims; [§N] в structure.
  3. Бесхозные фактические утверждения (цифры/предикат без [S]/[C]) -> orphan_claim.
  4. Маскировка неопределённости: claim с level in (assumed, disputed) или
     verdict in (UNSUPPORTED, AMBIGUOUS, OPEN) без маркера мягкости рядом -> masked_uncertainty.
  5. Числа: [Cxx] с числом, но без numeric_comparison -> numeric_unverified.
  6. Связанность: claim с derived_from, но без перекрёстной [§N] -> missing_crossref (warn).
  7. Битые/неизвестные ссылки -> dangling_reference.

Выход: JSON + exit 0/1/2.

Примеры:
  python citation_trace.py --text draft.md --dom product_dom.yaml
  python citation_trace.py --text draft.md --dom dom.yaml --strict
  python citation_trace.py --text draft.md --dom dom.yaml --fail-on medium
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# ------------------------- DOM loading -------------------------

def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML required (pip install PyYAML)")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"DOM {path} top-level must be mapping")
    return data


def _load_text(path_or_dash: str) -> str:
    if path_or_dash == "-":
        return sys.stdin.read()
    with open(path_or_dash, "r", encoding="utf-8") as f:
        return f.read()


# ------------------------- ссылки -------------------------

_S_REF = re.compile(r"\[(S-[0-9A-Za-z._:-]+)\]")
_C_REF = re.compile(r"\[(C-[0-9A-Za-z._:-]+)\]")
_SECT_REF = re.compile(r"\[(§[0-9][0-9A-Za-z._:-]*)\]")

_HEDGE_MARKERS = (
    "предположи", "по-видимому", "вероятно", "возможно", "может",
    "по предварительн", "можно ожидать", "гипотез", "с осторожност",
    "not confirmed", "likely", "possibly", "may indicate", "according to assumption",
    "по нашему предположению", "можно предположить",
    # русские клише атрибуции (дефект 2): маркируют рискованные клаймы как мягкие
    "по данным литературы", "по литературным данным", "по данным расчёта",
    "по оценкам авторов", "по оценкам", "согласно литературе", "по данным",
)

_NUMERIC_FACT_RE = re.compile(
    r"\d+[,.]\d+\s*[%°]|\d+\s*(?:МПа|ГПа|мкм|мм|мг/[а-яёa-zA-Z/]+|м/с|кг/га)"
)

_FACT_PREDICATE_RE = re.compile(
    r"\b(является|составляет|происходит|показано|установлено|следует|повышает|"
    r"снижает|соответствует|достигает|образует|оказывает|обладает|наблюдается)\b",
    re.IGNORECASE,
)


def _soft(sentence: str) -> bool:
    low = sentence.lower()
    return any(m in low for m in _HEDGE_MARKERS)


def _is_factual(sentence: str) -> bool:
    return bool(_NUMERIC_FACT_RE.search(sentence) or _FACT_PREDICATE_RE.search(sentence))


# Робастная сегментация предложений (дефект 1).
# Инвариант: предложение заканчивается ТОЛЬКО на терминальных . ! ? … (с учётом
# закрывающих кавычек/скобок и пробела перед следующей заглавной/цифрой). НЕ режем
# по внутрипредложенческим разделителям ; : — и НЕ режем внутри сокращений с точками
# (т.е., г., С.И., мас.%, ат.%, десятичные 0.5). Ссылка [C-xxx] и факт-предикат/число
# должны оставаться в одном сегменте.
_TERMINAL = ".!?…"

# Точки, которые НЕ являются концом предложения: внутри сокращений/инициалов/чисел.
# Маскируем их одним символом \x00 (1:1 по длине — координаты не сдвигаются).
_ABBREV_PROTECT_RE = re.compile(
    r"(?:"
    r"[а-яё]{1,4}\.[а-яё]{1,4}\.|"     # т.е. т.д. т.п. т.к. напр. (обе точки)
    r"[а-яё]{1,5}\.%|"                  # мас.% ат.% (точка перед %)
    r"[А-ЯЁ][а-яё]?(?:\-[А-ЯЁ][а-яё]?)*\.|"  # инициалы С. Ю.М. Э.Дж. Дж.-С. Н.Н.
    r"\d+\.\d+|"                        # десятичные 0.05 3.2
    r"\d{1,4}\s*гг?\.|"                 # 2020 г. 2020 гг.
    r"\b(?:см|рис|табл|с)\.|"           # см. рис. табл. с. (стр.)
    r")"
)


def _mask_dots(m: "re.Match[str]") -> str:
    return m.group(0).replace(".", "\x00")


# Граница предложений: терминальная пунктуация + закрывающие + пробел + старт нового.
# Старт — заглавная/цифра/кавычка/скобка/знак markdown-разметки (**/##/`).
_SENT_END_RE = re.compile(
    r"[.!?…]+[»\"'”\)\]]*\s+(?=[А-ЯЁA-Z0-9«\"'(#*_`])"
)


def _sentence_at(text: str, pos: int) -> str:
    """Предложение, содержащее позицию (робастно, stdlib)."""
    t = _ABBREV_PROTECT_RE.sub(_mask_dots, text)
    s, e = max(0, pos), max(0, pos)
    n = len(t)
    while s > 0 and t[s - 1] not in _TERMINAL:
        s -= 1
    while e < n and t[e] not in _TERMINAL:
        e += 1
    return text[s:e].strip()


def _detect_sentences(text: str) -> list[dict]:
    """Предложения с абсолютными координатами (робастно, stdlib)."""
    t = _ABBREV_PROTECT_RE.sub(_mask_dots, text)
    out, prev = [], 0
    for m in _SENT_END_RE.finditer(t):
        end = m.end()
        raw = text[prev:end].strip()
        if raw:
            out.append({"text": raw, "start": prev, "end": end})
        prev = end
    tail = text[prev:].strip()
    if tail:
        out.append({"text": tail, "start": prev, "end": len(text)})
    return out


# ============================ проверки ============================

def _check_dom(dom: dict) -> list[str]:
    errs = []
    sources = dom.get("sources", [])
    claims = dom.get("claims", [])
    if not dom.get("product"):
        errs.append("DOM: product missing")
    if not isinstance(dom.get("structure", {}).get("chapters"), list):
        errs.append("DOM: structure.chapters must be list")
    if not sources:
        errs.append("DOM: sources empty")
    if not claims:
        errs.append("DOM: claims empty")
    s_ids = [str(s.get("id")) for s in sources if isinstance(s, dict) and s.get("id")]
    if len(s_ids) != len(set(s_ids)):
        errs.append("DOM: duplicate source id")
    c_ids = [str(c.get("id")) for c in claims if isinstance(c, dict) and c.get("id")]
    if len(c_ids) != len(set(c_ids)):
        errs.append("DOM: duplicate claim id")
    return errs


def _dom_indexes(dom: dict) -> tuple[dict, dict, set[str]]:
    sources = {str(s.get("id")): s for s in dom.get("sources", []) if isinstance(s, dict) and s.get("id")}
    claims = {str(c.get("id")): c for c in dom.get("claims", []) if isinstance(c, dict) and c.get("id")}
    sections = set()
    for ch in dom.get("structure", {}).get("chapters", []):
        for s in ch.get("sections", []) or []:
            sections.add(str(s.get("id", "")))
    return sources, claims, sections


def _check_references(text: str, dom: dict) -> dict:
    sources, claims, sections = _dom_indexes(dom)
    used_s = set(_S_REF.findall(text))
    used_c = set(_C_REF.findall(text))
    used_sect = set(_SECT_REF.findall(text))

    dangling_s = [r for r in used_s if r not in sources]
    dangling_c = [r for r in used_c if r not in claims]
    dangling_sect = [
        r for r in used_sect
        if not any(r == sec_id or r.startswith(sec_id + ".") for sec_id in sections)
    ]
    return {
        "sources_used": sorted(used_s),
        "claims_used": sorted(used_c),
        "sections_used": sorted(used_sect),
        "dangling_sources": sorted(dangling_s),
        "dangling_claims": sorted(dangling_c),
        "dangling_sections": sorted(dangling_sect),
    }


def _check_orphans(text: str, dom: dict, strict: bool) -> list[dict]:
    claims_dom = [str(c.get("id")) for c in dom.get("claims", []) if isinstance(c, dict) and c.get("id")]
    orphans = []
    for c in _detect_sentences(text):
        sent = c.get("text") or _sentence_at(text, c.get("start") or 0)
        if not sent:
            continue
        start, end = c.get("start"), c.get("end")
        has_s = bool(_S_REF.search(sent))
        has_c = bool(_C_REF.search(sent))
        factual = _is_factual(sent)
        if factual and not has_s and not has_c:
            orphans.append({"sentence": sent[:200], "start": start, "end": end})
        elif strict and factual and not has_c:
            orphans.append({"sentence": sent[:200], "start": start, "end": end, "strict_no_claim": True})
    # deduplicate по sentence
    seen, out = set(), []
    for o in orphans:
        k = o["sentence"]
        if k not in seen:
            seen.add(k)
            out.append(o)
    return out


def _check_uncertainty(text: str, dom: dict) -> list[dict]:
    claims = {str(c.get("id")): c for c in dom.get("claims", []) if isinstance(c, dict) and c.get("id")}
    unc = dom.get("uncertainty", {}) or {}
    masked = []
    for cid, c in claims.items():
        ver = c.get("verification", {}) or {}
        verdict = ver.get("verdict")
        level = None
        u = unc.get(str(cid))
        if isinstance(u, dict):
            level = u.get("level")
        risky = verdict in ("UNSUPPORTED", "AMBIGUOUS", "OPEN") or level in ("assumed", "disputed", "assumption", "speculative")
        if not risky:
            continue
        for m in _C_REF.finditer(text):
            if m.group(1) != cid:
                continue
            sent = _sentence_at(text, m.start())
            if sent and not _soft(sent):
                masked.append({
                    "claim_id": cid, "verdict": verdict, "level": level,
                    "sentence": sent[:200],
                })
                break
    return masked


def _check_numeric(text: str, dom: dict) -> list[dict]:
    claims = {str(c.get("id")): c for c in dom.get("claims", []) if isinstance(c, dict) and c.get("id")}
    out = []
    for cid, c in claims.items():
        ver = c.get("verification", {}) or {}
        has_num = _NUMERIC_FACT_RE.search(str(c.get("text", "")))
        if not has_num:
            continue
        if ver.get("numeric_comparison") is None and cid in _C_REF.findall(text):
            for m in _C_REF.finditer(text):
                if m.group(1) == cid:
                    sent = _sentence_at(text, m.start())
                    out.append({"claim_id": cid, "reason": "numeric_without_comparison",
                                "sentence": sent[:200]})
                    break
    return out


def _check_crossref(text: str, dom: dict) -> list[dict]:
    claims = {str(c.get("id")): c for c in dom.get("claims", []) if isinstance(c, dict) and c.get("id")}
    used_c = set(_C_REF.findall(text))
    missing = []
    for cid, c in claims.items():
        dep = c.get("derived_from")
        if not dep:
            continue
        deps = [dep] if isinstance(dep, str) else (dep if isinstance(dep, list) else [])
        for d in deps:
            if isinstance(d, dict):
                d = d.get("claim_id") or d.get("id")
            if d and d not in used_c:
                missing.append({"claim_id": cid, "depends_on": d})
    # deduplicate
    seen, out = set(), []
    for x in missing:
        k = (x["claim_id"], x["depends_on"])
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


# ============================ main ============================

SEVERITY = {"none": 0, "medium": 1, "high": 2}


def run(text: str, dom: dict, strict: bool = False, fail_on: str = "high") -> dict:
    dom_errs = _check_dom(dom)
    refs = _check_references(text, dom)
    orphans = _check_orphans(text, dom, strict)
    masked = _check_uncertainty(text, dom)
    numeric = _check_numeric(text, dom)
    crossref = _check_crossref(text, dom)

    fail_reasons: list[str] = []
    if dom_errs:
        fail_reasons.append("DOM_INVALID: " + "; ".join(dom_errs[:5]))
    dangling = refs["dangling_sources"] + refs["dangling_claims"] + refs["dangling_sections"]
    if dangling:
        fail_reasons.append("DANGLING_REFERENCE: " + ", ".join(sorted(dangling)[:10]))
    if masked:
        fail_reasons.append("MASKED_UNCERTAINTY: " + ", ".join(x["claim_id"] for x in masked[:10]))
    if numeric and fail_on in ("medium", "high"):
        fail_reasons.append("NUMERIC_UNVERIFIED: " + ", ".join(x["claim_id"] for x in numeric[:10]))
    if strict and orphans:
        fail_reasons.append("ORPHAN_CLAIM: " + ", ".join(f"pos:{o['start']}" for o in orphans[:10]))
    elif orphans and fail_on == "high":
        fail_reasons.append("ORPHAN_CLAIM: " + ", ".join(f"pos:{o['start']}" for o in orphans[:10]))

    verdict = "PASS" if not fail_reasons else "FAIL"
    return {
        "text_len": len(text),
        "dom": {
            "sources": len(refs["sources_used"]),
            "claims": len(refs["claims_used"]),
            "sections": len(refs["sections_used"]),
        },
        "checks": {
            "dangling_reference": dangling,
            "orphan_claims": orphans,
            "masked_uncertainty": masked,
            "numeric_unverified": numeric,
            "missing_crossref": crossref,
        },
        "summary": {
            "sentences_checked": len(_detect_sentences(text)),
            "claims_traced": len(refs["claims_used"]),
            "references_ok": len(dangling) == 0,
            "references_dangling": len(dangling),
            "uncertainty_masked": len(masked),
            "orphan_claims": len(orphans),
            "numeric_unverified": len(numeric),
            "missing_crossref": len(crossref),
        },
        "verdict": verdict,
        "fail_reasons": fail_reasons,
    }


def main() -> int:
    ap = argparse.ArgumentParser(prog="citation_trace", description="Цитатный аудит прослеживаемости")
    ap.add_argument("--text", required=True, help="путь к тексту или '-' для stdin")
    ap.add_argument("--dom", required=True, help="путь к DOM YAML")
    ap.add_argument("--strict", action="store_true", help="требовать [Cxx] на каждое фактическое предложение")
    ap.add_argument("--fail-on", default="high", choices=["none", "medium", "high"])
    ap.add_argument("--json", action="store_true", help="выводить полный JSON")
    args = ap.parse_args()

    try:
        text = _load_text(args.text)
        dom = _load_yaml(Path(args.dom))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2

    result = run(text, dom, strict=args.strict, fail_on=args.fail_on)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())