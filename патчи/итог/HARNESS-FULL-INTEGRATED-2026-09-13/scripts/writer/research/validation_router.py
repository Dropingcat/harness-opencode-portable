#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from typing import Any
SCHEMA="validation_plan/1.0"
NUM=re.compile(r"\d+(?:[.,]\d+)?")
FORM=re.compile(r"(?:=|\b(?:sin|cos|exp|ln|sqrt)\s*\(|Δ|β|θ|ε)")

def route(claim:dict[str,Any])->dict[str,Any]:
    text=str(claim.get("text") or "")
    ev=claim.get("evidence") or []
    has_locator=any(isinstance(e,dict) and (e.get("locator") or e.get("source_span")) for e in ev)
    has_source=any(isinstance(e,dict) and (e.get("source") or e.get("source_id") or e.get("text")) for e in ev)
    methods=[]; tools=[]; reason=[]
    if NUM.search(text): methods.append("deterministic_numeric"); tools+= ["science.compute","evidence.verify"]; reason.append("numeric_claim")
    if FORM.search(text): methods.append("deterministic_formula"); tools+= ["science.compute","evidence.verify"]; reason.append("formula_or_symbolic_claim")
    if not has_source:
        methods.append("evidence_acquisition"); tools += ["corpus.search","source.resolve","search.discovery"]; reason.append("missing_source")
    elif not has_locator:
        methods.append("locator_recovery"); tools += ["document.inspect","corpus.search"]; reason.append("source_without_locator")
    if has_source and not NUM.search(text) and not FORM.search(text):
        methods.append("textual_entailment"); tools += ["evidence.verify"]; reason.append("semantic_claim_requires_fact_checker")
    if re.search(r"\b(?:примерно|около|не менее|не более|may|might|approximately|about|uncertain|погрешн|неопределенн)\b",text,re.I):
        methods.append("uncertainty_check"); tools += ["evidence.verify","science.compute"]; reason.append("uncertainty_or_qualifier")
    # concrete researcher entry point. Writer may request this stage but cannot execute web discovery itself.
    if has_locator:
        entry_stage='evidence-validation'
    elif has_source:
        entry_stage='document-analysis'
    elif claim.get('doi') or claim.get('source_title') or claim.get('source_candidate'):
        entry_stage='source-resolution'
    else:
        entry_stage='local-corpus'
    escalation=[]
    if entry_stage=='local-corpus': escalation=['source-resolution','discovery','document-analysis','evidence-validation']
    elif entry_stage=='source-resolution': escalation=['discovery','document-analysis','evidence-validation']
    elif entry_stage=='document-analysis': escalation=['evidence-validation']
    # stable unique order
    methods=list(dict.fromkeys(methods)); tools=list(dict.fromkeys(tools))
    return {"ok":True,"schema":SCHEMA,"claim_id":claim.get("claim_id"),"methods":methods,"tools":tools,"reasons":reason,
            "entry_stage":entry_stage,"escalation_path":escalation,
            "authority":{"numeric_formula":"deterministic researcher core","textual_entailment":"fact-checker/evidence.verify","source_discovery":"researcher route only"},
            "writer_may_search_web":False}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("claim_json"); a=ap.parse_args(); claim=json.loads(a.claim_json)
    print(json.dumps(route(claim),ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
