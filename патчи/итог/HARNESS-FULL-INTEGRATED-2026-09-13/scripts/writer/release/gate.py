# -*- coding: utf-8 -*-
"""Aggregate fail-closed Writer release gate.

Gate order is deliberate:
  1. Researcher evidence verification (read-only authority boundary)
  2. Traceability/citation audit
  3. Round-trip semantic validation
  4. Aggregate release decision

A later gate cannot erase an earlier failure. Writer never authors or upgrades
Researcher verdicts.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from scripts.writer.research.verify_claims_adapter import adapt_verification, VerificationAdapterError
from scripts.writer.review import citation_trace
from scripts.writer.core.factory_process import draftcheck
from scripts.writer.review.rtt_compare import compare_contract
from scripts.writer.authority.realization import resolve as resolve_realization_authority

STRICT_PASS = frozenset({"SUPPORTED"})
QUALIFIED_PASS = frozenset({"SUPPORTED", "AMBIGUOUS"})


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _load_dom(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("DOM must be a YAML mapping")
    if not isinstance(data.get("claims", []), list):
        raise ValueError("DOM claims must be a list")
    return data


def _claim_contracts(dom: dict[str, Any]) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for claim in dom.get("claims", []):
        if not isinstance(claim, dict):
            raise ValueError("DOM claim must be a mapping")
        cid = str(claim.get("id") or "").strip()
        proposition = str(claim.get("text") or claim.get("proposition") or "").strip()
        if not cid or not proposition:
            # Structural placeholder claims are not release-eligible.
            continue
        contracts.append({
            "claim_id": cid,
            "proposition": proposition,
            "scope": str(claim.get("scope") or claim.get("scope_ref") or ""),
            "modality": str(claim.get("modality") or "assertive"),
            "causal_level": str(claim.get("causal_level") or "none"),
            "forbidden_transformations": list(claim.get("forbidden_transformations") or [
                "CLAIM_OMISSION", "UNAUTHORIZED_CLAIM", "SCOPE_EXPANSION",
                "MODALITY_UPGRADE", "CAUSALITY_UPGRADE", "QUALIFIER_LOSS",
                "NEGATION_FLIP", "ENTITY_SUBSTITUTION", "NUMERIC_DRIFT",
                "UNIT_DRIFT", "PRECISION_INFLATION", "UNCERTAINTY_LOSS",
            ]),
            "required_qualifiers": list(claim.get("required_qualifiers") or []),
            "citation_policy": str(claim.get("citation_policy") or ""),
        })
    return contracts



def _realized_claim_ids(text: str) -> set[str]:
    return set(re.findall(r"\[(C-[0-9A-Za-z._:-]+)\]", text))


def _numeric_tokens(text: str) -> list[str]:
    # Scientific values only; do not parse grade/formula tokens such as Р6М5 or Fe4N.
    rx = re.compile(r"(?<![A-Za-zА-Яа-яЁё0-9])(?:\d+[.,]?\d*\s*[–—-]\s*\d+[.,]?\d*|\d+[.,]?\d*)\s*(?:%|°C|°С|K|К|МПа|ГПа|мкм|µm|мм|нм)(?![A-Za-zА-Яа-яЁё0-9])", re.I)
    return [re.sub(r"\s+", "", x.group(0)).replace(",", ".").casefold() for x in rx.finditer(text)]

def _semantic_marker_check(text: str, contracts: list[dict[str, Any]]) -> dict[str, Any]:
    """Prefer explicit [C-*] binding over heuristic re-matching.

    This is the normal Writer path. Heuristic draftcheck remains a compatibility
    fallback for unmarked historical text.
    """
    sentences = citation_trace._detect_sentences(text)
    defects=[]; checked=[]
    for cc in contracts:
        cid=str(cc.get("claim_id") or "")
        hit=None
        for sent in sentences:
            if f"[{cid}]" in str(sent.get("text") or ""):
                hit=sent; break
        if hit is None:
            defects.append({"defect_type":"claim_omission","claim_id":cid,"span":None,"suggestion":"добавить отсутствующее утверждение целиком","reason_code":"CLAIM_OMISSION"})
            checked.append({"claim_id":cid,"matched":False,"overlap":0.0,"reasons":["CLAIM_OMISSION"],"notes":[]})
            continue
        candidate=re.sub(r"\[(?:C|S)-[0-9A-Za-z._:-]+\]", "", str(hit.get("text") or ""))
        candidate=re.sub(r"[ \t]+", " ", candidate).strip()
        r=compare_contract(cc,candidate)
        reasons=[x.value if hasattr(x,"value") else str(x) for x in r.reason_codes]
        pnums=_numeric_tokens(str(cc.get("proposition") or "")); cnums=_numeric_tokens(candidate)
        if pnums and pnums != cnums and "NUMERIC_DRIFT" not in reasons:
            reasons.append("NUMERIC_DRIFT")
        checked.append({"claim_id":cid,"matched":True,"overlap":1.0,"reasons":reasons,"notes":list(r.notes or [])})
        effective_fail = any(x not in {"EXACT","PARAPHRASE_SAFE"} for x in reasons)
        if effective_fail:
            forbidden=set(cc.get("forbidden_transformations") or [])
            for rc in reasons:
                if forbidden and rc not in forbidden: continue
                defects.append({"defect_type":rc.lower(),"claim_id":cid,"span":{"start":hit.get("start"),"end":hit.get("end"),"text":str(hit.get("text") or "")[:300]},"suggestion":"переформулировать в пределах привязанного [C-*] предложения","reason_code":rc})
    return {"schema":"writer_core.rtt_report.v1","generated_by":"writer.release.marker_rtt","verdict":"PASS" if not defects else "FAIL","defects":defects,"checked":checked,"re_extraction":{"claims":[],"digests":[],"errors":[]}}

def _evidence_gate(verification: dict[str, Any], policy: str) -> dict[str, Any]:
    allowed = STRICT_PASS if policy == "strict" else QUALIFIED_PASS
    failures: list[dict[str, Any]] = []
    for row in verification.get("results", []):
        verdict = row.get("evidence_verdict") or row.get("verdict")
        vstate = row.get("verification_state")
        if not vstate:
            vstate = "UNCHECKED" if verdict in {None, "OPEN"} else "VERIFIED"
        epistemic = row.get("epistemic_state") or ("UNKNOWN" if verdict in {None,"OPEN"} else None)
        if vstate != "VERIFIED" or verdict not in allowed:
            failures.append({"claim_id": row.get("claim_id"), "verdict": verdict, "verification_state": vstate, "epistemic_state": epistemic})
    return {
        "verdict": "PASS" if not failures else "FAIL",
        "policy": policy,
        "allowed_verdicts": sorted(allowed),
        "requires_verification_state": "VERIFIED",
        "failures": failures,
        "claims_checked": len(verification.get("results", [])),
    }


def evaluate_release(dom_path: str | Path, text_path: str | Path, *,
                     evidence_policy: str = "strict", strict_trace: bool = True,
                     fail_on: str = "high") -> dict[str, Any]:
    if evidence_policy not in {"strict", "qualified"}:
        raise ValueError("evidence_policy must be strict|qualified")
    dom_p = Path(dom_path).resolve(); text_p = Path(text_path).resolve()
    if not dom_p.is_file() or not text_p.is_file():
        raise ValueError("DOM and text files must exist")
    dom_bytes = dom_p.read_bytes(); text_bytes = text_p.read_bytes()
    dom = _load_dom(dom_p); text = _read_text(text_p)

    verification = adapt_verification(dom_p)
    authority_binding = resolve_realization_authority(dom, text)
    realized_ids = set(authority_binding.get("realized_claim_ids") or [])
    if realized_ids:
        verification = dict(verification)
        verification["results"] = [r for r in verification.get("results", []) if str(r.get("claim_id")) in realized_ids]
        verification["claims_verified"] = len(verification["results"])
    evidence = _evidence_gate(verification, evidence_policy)

    # Project researcher verdicts into an in-memory Writer view. The source DOM
    # remains byte-identical; citation_trace may consume verification fields but
    # Writer never writes them back.
    trace_dom = copy.deepcopy(dom)
    by_id = {str(r.get("claim_id")): r for r in verification.get("results", [])}
    for claim in trace_dom.get("claims", []):
        if not isinstance(claim, dict):
            continue
        row = by_id.get(str(claim.get("id")))
        if row:
            claim["verification"] = {
                "verdict": row.get("verdict"),
                "confidence": row.get("confidence"),
                "numeric_comparison": row.get("numeric_comparison"),
                "guard": row.get("guard"),
                "formula": row.get("formula"),
                "verification_state": row.get("verification_state"),
                "evidence_verdict": row.get("evidence_verdict") or row.get("verdict"),
                "epistemic_state": row.get("epistemic_state"),
            }

    # Traceability and RTT are still evaluated even after evidence FAIL so the
    # report remains diagnostically complete; aggregate decision stays FAIL.
    trace = citation_trace.run(text, trace_dom, strict=strict_trace, fail_on=fail_on)
    contracts = _claim_contracts(dom)
    if realized_ids:
        contracts = [c for c in contracts if str(c.get("claim_id")) in realized_ids]
    semantic_text = re.sub(r"\[(?:C|S)-[0-9A-Za-z._:-]+\]", "", text)
    semantic_text = re.sub(r"[ \t]+", " ", semantic_text).strip()
    semantic = (_semantic_marker_check(text, contracts) if realized_ids else draftcheck(semantic_text, contracts)) if contracts else {
        "schema": "writer_core.rtt_report.v1", "verdict": "FAIL",
        "defects": [{"defect_type": "empty_contract", "reason_code": "NO_RELEASE_CLAIMS"}],
        "checked": [], "re_extraction": {"claims": [], "digests": [], "errors": []},
    }

    trace_verdict = "PASS" if trace.get("verdict") == "PASS" and authority_binding.get("verdict") == "PASS" else "FAIL"
    trace_detail = dict(trace)
    trace_detail["authority_binding"] = authority_binding
    gates = {
        "evidence": {"verdict": evidence["verdict"], "detail": evidence},
        "traceability": {"verdict": trace_verdict, "detail": trace_detail},
        "semantic_roundtrip": {"verdict": semantic.get("verdict", "FAIL"), "detail": semantic},
    }
    blockers = [name for name, gate in gates.items() if gate["verdict"] != "PASS"]
    verdict = "PASS" if not blockers else "FAIL"
    return {
        "schema": "writer.release_decision/1.0",
        "verdict": verdict,
        "release_allowed": verdict == "PASS",
        "blockers": blockers,
        "gates": gates,
        "authority": {
            "research_verdicts": "scripts/researcher/verify_claims.py",
            "traceability": "scripts/writer/review/citation_trace.py",
            "semantic_roundtrip": "scripts/writer/core/factory_process.py",
            "claim_realization": "DraftArtifact → DOM paragraph.claims; rendered [C-*] markers are checked projection",
        },
        "artifacts": {
            "dom": str(dom_p), "dom_sha256": _sha256_bytes(dom_bytes),
            "text": str(text_p), "text_sha256": _sha256_bytes(text_bytes),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="writer-release-check")
    ap.add_argument("--dom", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--evidence-policy", choices=["strict", "qualified"], default="strict")
    ap.add_argument("--no-strict-trace", action="store_true")
    ap.add_argument("--fail-on", choices=["none", "medium", "high"], default="high")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    try:
        result = evaluate_release(
            args.dom, args.text, evidence_policy=args.evidence_policy,
            strict_trace=not args.no_strict_trace, fail_on=args.fail_on,
        )
    except (ValueError, VerificationAdapterError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "fail_closed": True}, ensure_ascii=False))
        return 2
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
