#!/usr/bin/env python3
"""verdict_integration.py — Этап 4 пайплайна: слой оценки контента (замена stub_verifier).

Для каждого claim из claims.json + источников sources.json (каскад, Этап 3) запускает
слой оценки content_verdict.evaluate_claim → вердикт с предикатом/уверенностью/цитатой.

Выход verdicts.json — обратно совместим с последующими этапами:
  - evidence_contract (4.5): читает dict.verdicts[], каждый record {claim_id, claim_text,
    verdict, confidence, reason, caveats, sources[]};
  - numeric_comparator (5): dict-of-list sources по claim_id;
  - merge_numeric (5.1) / post_processor (6) / judge_brief (6.7): verdicts[].

Полное богатое представление content_verdict (evidence, per_source, stats, uncertainty,
llm_calls, sources) сохраняется в поле "content_verdict" каждого вердикта — не ломает
потребителей (они читают известные ключи на верхнем уровне).

Usage:
    python3 verdict_integration.py <claims.json> <sources.json> [--document DOC.txt]
                                   [--out verdicts.json] [--no-llm]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import content_verdict as cv


def load_claims(claims_path):
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


def load_sources(sources_path):
    """sources.json (B.6) → {str(claim_id): [source, ...]}."""
    with open(sources_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    inner = data.get("sources", data)
    if isinstance(inner, dict):
        return {str(k): v if isinstance(v, list) else v.get("sources", [])
                for k, v in inner.items()}
    return {}


def _cast_claim_id(cid):
    try:
        return int(cid)
    except (TypeError, ValueError):
        return cid


def build_verdicts(claims, sources_map, document_text=None, use_llm=True):
    verdicts = []
    stats = {"total": 0, "SUPPORTED": 0, "CONTRADICTED": 0, "UNSUPPORTED": 0,
             "AMBIGUOUS": 0, "GAP-UNVERIFIED": 0, "other": 0}
    for idx, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        cid = _claim_id(claim, idx)
        text = _claim_text(claim)
        srcs = sources_map.get(str(cid), [])
        res = cv.evaluate_claim(text, srcs, document_text, use_llm=use_llm,
                                claim_id=cid)
        verdict = str(res.get("verdict", "UNSUPPORTED"))
        key = verdict if verdict in stats else "other"
        stats[key] += 1
        stats["total"] += 1
        # back-compat верхний уровень + богатое представление в content_verdict
        verdicts.append({
            "claim_id": _cast_claim_id(cid),
            "claim_text": text,
            "verdict": verdict,
            "confidence": res.get("confidence", 0.0),
            "reason": res.get("reason", ""),
            "caveats": res.get("caveats", []),
            "sources": res.get("sources", []),
            "content_verdict": res,
        })
    return verdicts, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("claims", help="claims.json")
    ap.add_argument("sources", help="sources.json (каскад Этап 3)")
    ap.add_argument("--document", help="текст документа (анти-циркулярность)")
    ap.add_argument("--out", default="", help="verdicts.json (выход)")
    ap.add_argument("--no-llm", action="store_true", help="отключить LLM-валидатор")
    args = ap.parse_args()

    claims = load_claims(args.claims)
    sources_map = load_sources(args.sources)
    doc = None
    if args.document and Path(args.document).is_file():
        doc = Path(args.document).read_text(encoding="utf-8")
    verdicts, stats = build_verdicts(claims, sources_map, doc,
                                     use_llm=not args.no_llm)
    out = {
        "status": "success",
        "verdicts": verdicts,
        "statistics": stats,
    }
    out_path = args.out or str(Path(args.sources).with_name("verdicts.json"))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ verdict_integration: {stats} → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())