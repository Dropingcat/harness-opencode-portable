#!/usr/bin/env python3
"""verifier.py — оркестратор верификации claim (инкапсулированный модуль).

Конвейер (verification-plan.md B.2):
  1. Классификация claim (claim_classifier.py): gap/attribute/numeric/framing.
  2. Построение запросов (RU для локального корпуса, EN для openalex/arxiv/web).
  3. Каскад источников (cascade.py): локальный корпус → OpenAlex → arXiv → DDG
     (→ sci-bot только по явному запросу/--simulate).
  4. Анти-циркулярность (circularity.py): origin=external|document_derived.
  5. Вердикт с низкой неопределённостью, чёткими ссылками и контекстом
     (аналог Perplexity): вердикт + confidence + неопределённость + ссылки
     (title/url/doi) + контекст (excerpt).

Решения принимаются КОДОМ (детерминированно), не LLM: число независимых внешних
подтверждений и их релевантность определяют вердикт и уверенность.

CLI:
  python3 verifier.py "claim текст" [--document input.txt] [--json]
  python3 verifier.py --stage3 --claims claims.json --document input.txt \
      --out-sources sources.json [--out-verdicts verdicts.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from claim_classifier import classify
from cascade import (
    build_queries,
    run_cascade,
    LAYER_ORDER,
    RU_EN_GLOSSARY,
)
from circularity import annotate_source
from gap_rules import decide_gap_verdict, cap_unsupported_high_conf

CONTRADICTION_MARKERS = [
    "не подтвержда", "не подтвержд", "противореч", "опроверг",
    "не наблюдается", "отсутств", "не обнаруж", "не установлено",
    "невозможно", "не согласует", "вопреки", "противополож",
    "не приводит к ускорению", "не влияет", "не увеличивает",
]

NEGATION_BAG = {
    "не", "нет", "отсутств", "против", "вопреки", "без", "никак",
}


def _distinct_external(ext_sources):
    """Независимые внешние источники (дедуп по doi/url, без ошибок)."""
    seen = set()
    out = []
    for s in ext_sources:
        if s.get("error"):
            continue
        key = s.get("doi") or s.get("url") or s.get("title", "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(s)
    return out


def _claim_search_terms(claim_text):
    """RU+EN термины claim для сверки с источниками любых языков.

    RU-термины дополняются EN-переводами через глоссарий каскада: локальный
    корпус отдаёт русские фрагменты, openalex/arxiv/web — английские.
    """
    ru_terms = [t for t in re.findall(r"[а-яё]{4,}", claim_text.lower())]
    en_terms = [t for t in re.findall(r"[a-z]{4,}", claim_text.lower())]
    for ru in ru_terms:
        for stem, en in RU_EN_GLOSSARY.items():
            if ru.startswith(stem):
                en_terms.extend(en.split())
                break
    stop = {"данных", "котор", "при", "для", "что", "это", "также", "однако"}
    return list(dict.fromkeys([t for t in ru_terms + en_terms if t not in stop]))


def _stem_match(term, text, min_stem=5):
    """Поиск термина в тексте со стем-совпадением (общий префикс >= min_stem)."""
    if term in text:
        return True
    stem = term[:min_stem]
    if len(stem) >= min_stem and stem in text:
        return True
    # окончания -ing/-ion/-ия/-е и т.п.
    for suf in ("ing", "ation", "ирование", "ния", "ние"):
        base = term[:len(term) - len(suf)] if term.endswith(suf) else None
        if base and len(base) >= min_stem and base in text:
            return True
    return False


def _source_supports_claim(source, claim_terms, min_relevance=0.5):
    """Эвристика поддержки: источник внешний, релевантен и содержит >=3 стем-терминов claim.

    Стем-совпадение снимает разнобой RU/EN и словоформ («нитрид»↔«nitride»↔
    «nitriding», «ускорение»↔«acceleration»).
    """
    if (source.get("relevance") or 0.0) < min_relevance:
        return False
    hay = (source.get("text") or source.get("excerpt") or source.get("title") or "").lower()
    if not claim_terms:
        return True
    hits = sum(1 for t in claim_terms if _stem_match(t, hay))
    if hits >= 3:
        return True
    if hits >= 2 and (source.get("relevance") or 0.0) >= 0.65:
        return True
    return False


def _source_contradicts(source, claim_terms):
    """Эвристика опровержения: негативные маркеры рядом с терминами claim."""
    hay = (source.get("text") or source.get("excerpt") or "").lower()
    if not hay or not claim_terms:
        return False
    hit_terms = [t for t in claim_terms if t in hay]
    if not hit_terms:
        return False
    for m in CONTRADICTION_MARKERS:
        if m in hay:
            return True
    return False


def _source_supports_gap(source):
    from gap_rules import is_gap_supported_by_source, is_gap_contradicted_by_source
    hay = (source.get("text") or source.get("excerpt") or "").lower()
    if is_gap_contradicted_by_source(hay):
        return "contradicts"
    if is_gap_supported_by_source(hay):
        return "supports"
    return "neutral"


def _uncertainty(confidence, n_sources, verdict):
    """Качественная неопределённость: низкая/средняя/высокая + числовая."""
    conf = float(confidence or 0.0)
    numeric = round(1.0 - conf, 2)
    if verdict in ("GAP-UNVERIFIED",):
        return {"level": "high", "value": numeric,
                "note": "gap не подтверждён и не опровергнут — отсутствие данных"}
    if verdict in ("UNSUPPORTED",):
        return {"level": "high", "value": numeric,
                "note": "нет независимых внешних подтверждений"}
    if n_sources < 2:
        return {"level": "medium", "value": numeric,
                "note": "мало независимых внешних источников"}
    if conf >= 0.8:
        return {"level": "low", "value": numeric,
                "note": "несколько независимых внешних подтверждений"}
    return {"level": "medium", "value": numeric, "note": ""}


def verify_claim(claim_text, document_text=None, config=None,
                 claim_id=None, claim_class=None):
    """Полный конвейер верификации одного claim.

    Возвращает словарь-ответ:
      {claim_id, claim_text, claim_class, verdict, confidence, uncertainty,
       reason, references, context, sources, verification_meta, cap_applied}.
    """
    config = config or {}
    claim_class = claim_class or classify(claim_text)["claim_class"]

    ru_q, en_q = build_queries(claim_text, claim_class)
    # локальный корпус ищет по RU; остальные — по EN
    queries = [ru_q, en_q]

    all_sources = []
    meta = {"cascade_used": [], "queries_used": [], "iterations": 0,
            "external_found": 0, "document_derived_found": 0, "budget_tokens": 0}
    for q in queries:
        res = run_cascade(
            q,
            layers=config.get("layers") or LAYER_ORDER,
            use_scibot=config.get("use_scibot", False),
            simulate_scibot=config.get("simulate_scibot", False),
            question=claim_text,
        )
        all_sources.extend(res["sources"])
        for k in ("cascade_used", "queries_used", "iterations"):
            meta[k] = res["verification_meta"].get(k, meta[k])
        meta["external_found"] += res["verification_meta"]["external_found"]
        meta["document_derived_found"] += res["verification_meta"]["document_derived_found"]
        meta["budget_tokens"] += res["verification_meta"].get("budget_tokens", 0)

    # анти-циркулярность
    annotated = []
    for s in all_sources:
        if s.get("error"):
            continue
        annotate_source(s, claim_text, document_text)
        annotated.append(s)

    external = _distinct_external(
        [s for s in annotated if s.get("origin") == "external" and s.get("accepted")]
    )
    derived = [s for s in annotated if s.get("origin") == "document_derived"]

    claim_terms = _claim_search_terms(claim_text)

    # вердикт
    if claim_class == "gap":
        gap_contradictions = sum(1 for s in external if _source_supports_gap(s) == "contradicts")
        gap_support = sum(1 for s in external if _source_supports_gap(s) == "supports")
        res = decide_gap_verdict(external,
                                 gap_support_hits=gap_support,
                                 gap_contradictions=gap_contradictions)
        verdict = res["verdict"]
        confidence = res["confidence"]
        reason = res["reason"]
    else:
        supporting = [s for s in external if _source_supports_claim(s, claim_terms)]
        contradicting = [s for s in external if _source_contradicts(s, claim_terms)]
        if contradicting and len(contradicting) >= len(supporting):
            verdict = "CONTRADICTED"
            confidence = 0.85
            reason = "внешний источник противоречит claim"
        elif len(supporting) >= 2:
            avg_rel = sum(s.get("relevance", 0.5) for s in supporting) / len(supporting)
            confidence = min(0.95, 0.6 + 0.1 * len(supporting) + 0.1 * avg_rel)
            verdict = "SUPPORTED"
            reason = f"{len(supporting)} независимых внешних подтверждений"
        elif len(supporting) == 1:
            verdict = "AMBIGUOUS"
            confidence = 0.6
            reason = "одно внешнее подтверждение — недостаточно для SUPPORTED"
        elif external:
            verdict = "AMBIGUOUS"
            confidence = 0.5
            reason = "внешние источники найдены, но не подтверждают claim напрямую"
        else:
            verdict = "UNSUPPORTED"
            confidence = 0.3
            reason = "нет независимых внешних подтверждений"

    # cap-правило (UNSUPPORTED + conf>0.6)
    cap_applied = False
    if verdict == "UNSUPPORTED":
        _, cap_applied = cap_unsupported_high_conf(
            {"verdict": verdict, "confidence": confidence}, threshold=0.6, cap_value=0.5
        )
        if cap_applied:
            confidence = 0.5

    unc = _uncertainty(confidence, len(supporting) if claim_class != "gap" else len(external),
                       verdict)

    references = []
    for s in external[:10]:
        references.append({
            "title": s.get("title", ""),
            "url": s.get("url"),
            "doi": s.get("doi"),
            "venue": s.get("venue", ""),
            "year": s.get("year"),
            "authors": s.get("authors", []),
            "found_via": s.get("found_via"),
            "relevance": s.get("relevance"),
        })

    context = [{
        "found_via": s.get("found_via"),
        "origin": s.get("origin"),
        "excerpt": (s.get("excerpt") or "")[:500],
        "overlap": s.get("overlap", 0.0),
        "relevance": s.get("relevance"),
    } for s in annotated[:8]]

    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "claim_class": claim_class,
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "uncertainty": unc,
        "reason": reason,
        "references": references,
        "context": context,
        "sources": annotated,
        "verification_meta": meta,
        "cap_applied": cap_applied,
        "_n_external": len(external),
        "_n_supporting": len(supporting) if claim_class != "gap" else 0,
        "_n_derived": len(derived),
    }


def verify_claims(claims, document_text=None, config=None):
    """Верифицирует список claims. Возвращает (answers, verification_meta)."""
    answers = []
    agg_meta = {"cascade_used": [], "queries_used": [], "iterations": 0,
                "external_found": 0, "document_derived_found": 0, "budget_tokens": 0,
                "claims_verified": 0}
    for claim in claims:
        text = claim.get("text") or claim.get("claim_text") or str(claim)
        cid = claim.get("claim_id", claim.get("original_index"))
        ans = verify_claim(text, document_text, config, claim_id=cid)
        answers.append(ans)
        agg_meta["claims_verified"] += 1
        agg_meta["external_found"] += ans["verification_meta"].get("external_found", 0)
        agg_meta["document_derived_found"] += ans["verification_meta"].get("document_derived_found", 0)
        for u in ans["verification_meta"].get("cascade_used", []):
            if u not in agg_meta["cascade_used"]:
                agg_meta["cascade_used"].append(u)
        for q in ans["verification_meta"].get("queries_used", []):
            if q not in agg_meta["queries_used"]:
                agg_meta["queries_used"].append(q)
    return answers, agg_meta


def build_sources_contract(answers):
    """Собирает sources.json в формате B.6 verification-plan.md."""
    sources = {}
    for ans in answers:
        cid = ans["claim_id"] if ans["claim_id"] is not None else 0
        srcs = []
        for s in ans.get("sources", []):
            if s.get("error"):
                continue
            srcs.append({
                "title": s.get("title", ""),
                "type": s.get("type", ""),
                "trust": s.get("trust", 0.5),
                "excerpt": (s.get("excerpt") or "")[:500],
                "text": (s.get("text") or "")[:1000],
                "doi": s.get("doi", ""),
                "year": s.get("year"),
                "url": s.get("url"),
                "authors": s.get("authors", []),
                "found_via": s.get("found_via", ""),
                "found_query": s.get("found_query", ""),
                "origin": s.get("origin", "external"),
                "relevance": s.get("relevance", 0.0),
                "overlap": s.get("overlap", 0.0),
                "accepted": bool(s.get("accepted")),
            })
        sources[str(cid)] = srcs

    ext = sum(1 for a in answers for s in a.get("sources", [])
              if s.get("origin") == "external" and s.get("accepted") and not s.get("error"))
    derived = sum(1 for a in answers for s in a.get("sources", [])
                  if s.get("origin") == "document_derived")
    return {
        "sources": sources,
        "verification_meta": {
            "cascade_used": list({u for a in answers for u in a["verification_meta"].get("cascade_used", [])}),
            "external_found": ext,
            "document_derived_found": derived,
            "queries_used": list({q for a in answers for q in a["verification_meta"].get("queries_used", [])}),
            "iterations": max((a["verification_meta"].get("iterations", 0) for a in answers), default=0),
            "budget_tokens": sum(a["verification_meta"].get("budget_tokens", 0) for a in answers),
            "claims_verified": len(answers),
        },
    }


def verdicts_from_answers(answers):
    """Вердикты в формате, совместимом с пайплайном (verdicts.json)."""
    out = []
    for a in answers:
        out.append({
            "claim_id": a["claim_id"] if a["claim_id"] is not None else 0,
            "claim_text": a["claim_text"],
            "claim_class": a["claim_class"],
            "verdict": a["verdict"],
            "confidence": a["confidence"],
            "reason": a["reason"],
            "sources": a["sources"],
            "caveats": [
                {"severity": "info", "text": f"внешних подтверждений: {a['_n_external']}, "
                                             f"документных источников: {a['_n_derived']}"}
            ],
            "references": a["references"],
            "uncertainty": a["uncertainty"],
        })
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("claim_text", nargs="?", help="текст claim")
    ap.add_argument("--document", help="путь к документу (анти-циркулярность)")
    ap.add_argument("--json", dest="as_json", action="store_true")
    ap.add_argument("--use-scibot", action="store_true")
    ap.add_argument("--simulate-scibot", action="store_true")
    ap.add_argument("--stage3", action="store_true",
                    help="режим этапа 3: sources.json + verdicts.json из claims.json")
    ap.add_argument("--claims", help="claims.json (для --stage3)")
    ap.add_argument("--out-sources", help="выход sources.json (--stage3)")
    ap.add_argument("--out-verdicts", help="выход verdicts.json (--stage3)")
    args = ap.parse_args()

    if args.stage3:
        if not args.claims or not args.out_sources:
            ap.error("--stage3 требует --claims и --out-sources")
        with open(args.claims, encoding="utf-8") as f:
            claims_data = json.load(f)
        claims = claims_data.get("claims", claims_data)
        if isinstance(claims, dict):
            claims = claims.get("validated", list(claims.values()))
        doc_text = None
        if args.document and Path(args.document).is_file():
            doc_text = Path(args.document).read_text(encoding="utf-8")
        answers, agg = verify_claims(
            claims, doc_text,
            {"use_scibot": args.use_scibot, "simulate_scibot": args.simulate_scibot},
        )
        contract = build_sources_contract(answers)
        Path(args.out_sources).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_sources, "w", encoding="utf-8") as f:
            json.dump(contract, f, ensure_ascii=False, indent=2)
        print(f"✅ sources.json: {len(answers)} claims, "
              f"внешних={contract['verification_meta']['external_found']}, "
              f"документных={contract['verification_meta']['document_derived_found']}")
        if args.out_verdicts:
            verdicts = verdicts_from_answers(answers)
            Path(args.out_verdicts).parent.mkdir(parents=True, exist_ok=True)
            with open(args.out_verdicts, "w", encoding="utf-8") as f:
                json.dump({"status": "success", "verdicts": verdicts,
                           "verification_meta": contract["verification_meta"]},
                          f, ensure_ascii=False, indent=2)
            print(f"✅ verdicts.json: {len(verdicts)} вердиктов")
        return

    if not args.claim_text:
        ap.print_help()
        sys.exit(2)

    doc_text = None
    if args.document and Path(args.document).is_file():
        doc_text = Path(args.document).read_text(encoding="utf-8")

    ans = verify_claim(
        args.claim_text, doc_text,
        {"use_scibot": args.use_scibot, "simulate_scibot": args.simulate_scibot},
    )
    if args.as_json:
        print(json.dumps(ans, ensure_ascii=False, indent=2))
    else:
        print(f"Claim: {ans['claim_text'][:80]}")
        print(f"Класс: {ans['claim_class']}")
        print(f"Вердикт: {ans['verdict']} (confidence={ans['confidence']})")
        print(f"Неопределённость: {ans['uncertainty']['level']} ({ans['uncertainty']['value']})")
        print(f"Причина: {ans['reason']}")
        print(f"Внешних источников: {ans['_n_external']}, документных: {ans['_n_derived']}")
        print("Ссылки:")
        for r in ans["references"][:5]:
            print(f"  - {r['title'][:70]} | {r.get('doi') or r.get('url')}")
        print("Контекст:")
        for c in ans["context"][:4]:
            print(f"  [{c['found_via']}/{c['origin']} ovl={c['overlap']}] {c['excerpt'][:90]}")


if __name__ == "__main__":
    main()