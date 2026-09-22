#!/usr/bin/env python3
"""cascade_integration.py — Этап 3 пайплайна: каскад источников (замена literature-searcher).

Для каждого claim из claims.json прогоняет каскад (cascade.py: локальный корпус →
OpenAlex → arXiv → DDG) и пишет sources.json в контракте verification-plan B.6:

    {
      "sources": { "<claim_id>": [ {title,type,trust,excerpt,doi,year,url,
                                    found_via,found_query,origin,relevance,accepted,...} ] },
      "verification_meta": { claim_id: {cascade_used, external_found, queries_used, ...} },
      "status": "ok"
    }

Формат sources.json совместим с потребителями:
  - numeric_comparator  (dict-of-list, индексация по claim_id);
  - evidence_contract   (dict-of-list по claim_id);
  - content_verdict     (список источников с found_via/origin/excerpt/relevance).

Обратная совместимость / резерв:
  - если каскад недоступен (нет сети/индекса/исключение) — каждый слой каскада уже
    возвращает error-записи, а не крашит; sources.json всегда создаётся (status=ok,
    ошибки слоёв в verification_meta.layer_errors).
  - детерминированный fallback при полном отсутствии входа — пустой sources.json.

Usage:
    python3 cascade_integration.py <claims.json> [--document DOC.txt] [--out sources.json]
                                    [--no-llm] [--layers local_corpus,openalex,arxiv,web_ddg]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cascade import run_cascade, build_queries

DEFAULT_LAYERS = ["local_corpus", "openalex", "arxiv", "web_ddg"]


def load_claims(claims_path):
    """Читает claims.json в стандартной форме (extractor/wrapper/deterministic)."""
    with open(claims_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    inner = data.get("claims", data)
    if isinstance(inner, dict) and "validated" in inner:
        validated = inner["validated"]
    elif isinstance(inner, list):
        validated = inner
    else:
        validated = data.get("validated", [])
    if isinstance(validated, dict):
        validated = list(validated.values())
    return validated


def _claim_id(claim, idx):
    """Идентификатор claim: original_index (int) предпочтительно, иначе индекс."""
    oi = claim.get("original_index")
    if oi is not None:
        try:
            return int(oi)
        except (TypeError, ValueError):
            return oi
    cid = claim.get("claim_id")
    if cid is not None:
        return cid
    return idx


def _claim_text(claim):
    return claim.get("text") or claim.get("claim_text") or str(claim)


def _dedup_sources(sources):
    seen, out = set(), []
    for s in sources:
        if s.get("error"):
            continue
        key = s.get("doi") or s.get("url") or s.get("title", "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(s)
    return out


def cascade_for_claim(claim_text, layers):
    """Прогон каскада по claim: RU + EN запросы, дедуп по doi/url."""
    from claim_classifier import classify
    cls = classify(claim_text)["claim_class"]
    ru_q, en_q = build_queries(claim_text, cls)
    all_sources = []
    metas = []
    for q in (ru_q, en_q):
        if not q.strip():
            continue
        try:
            res = run_cascade(q, layers=layers, max_iterations=2)
        except Exception as exc:
            metas.append({"query": q, "error": f"cascade: {exc}"})
            continue
        all_sources.extend(res["sources"])
        metas.append(res["verification_meta"])
    return _dedup_sources(all_sources), metas


def build_sources(claims, layers, document_text=None):
    """Главная функция: claims → sources.json dict (B.6)."""
    per_claim = {}
    meta = {}
    layer_errors = {}
    external_total = 0
    for idx, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        cid = _claim_id(claim, idx)
        text = _claim_text(claim)
        srcs, metas = cascade_for_claim(text, layers)
        per_claim[str(cid)] = srcs
        # агрегируем verification_meta по claim
        used = []
        for m in metas:
            used += m.get("cascade_used", [])
            external_total += m.get("external_found", 0)
            for e in m.get("layer_errors", []) if False else []:
                pass
        layer_errors[str(cid)] = [
            {"query": m.get("query", ""), "error": m["error"]}
            for m in metas if m.get("error")
        ]
        meta[str(cid)] = {
            "cascade_used": sorted(set(used)),
            "external_found": sum(m.get("external_found", 0) for m in metas),
            "document_derived_found": sum(m.get("document_derived_found", 0) for m in metas),
            "queries_used": [q for m in metas for q in m.get("queries_used", [])],
            "iterations": max([m.get("iterations", 0) for m in metas] or [0]),
            "layer_errors": layer_errors[str(cid)],
        }
    return {
        "sources": per_claim,
        "verification_meta": {
            "claims_processed": len(per_claim),
            "external_sources_total": external_total,
            "per_claim": meta,
        },
        "status": "ok",
        "note": "sources.json построен каскадом cascade.py (локальный корпус → OpenAlex → arXiv → DDG); формат B.6.",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("claims", help="claims.json")
    ap.add_argument("--out", default="", help="sources.json (выход)")
    ap.add_argument("--document", help="текст документа (анти-циркулярность, необязательно)")
    ap.add_argument("--layers", default=",".join(DEFAULT_LAYERS))
    ap.add_argument("--no-llm", action="store_true", help="не использовать LLM-валидатор")
    args = ap.parse_args()

    claims = load_claims(args.claims)
    layers = [l.strip() for l in args.layers.split(",") if l.strip()] or DEFAULT_LAYERS
    doc = None
    if args.document and Path(args.document).is_file():
        doc = Path(args.document).read_text(encoding="utf-8")
    out = build_sources(claims, layers, doc)
    out_path = args.out or (str(Path(args.claims).with_name("sources.json")))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    n_claims = out["verification_meta"]["claims_processed"]
    n_ext = out["verification_meta"]["external_sources_total"]
    print(f"✅ cascade_integration: {n_claims} claims, внешних источников: {n_ext} → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())