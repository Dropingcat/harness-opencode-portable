#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path
from typing import Any
SCHEMA='draft_request/1.0'

def build(object_decision:dict[str,Any], style_selection:dict[str,Any], evidence_selection:dict[str,Any], claims:list[dict[str,Any]], section_role:str, instructions:str='', writing_policy:dict[str,Any]|None=None, style_instruction:dict[str,Any]|None=None)->dict[str,Any]:
    if object_decision.get('schema')!='writing_object_decision/1.0': raise ValueError('writing_object_decision/1.0 required')
    if style_selection.get('schema') not in {'reference_selection/1.0','reference_selection/1.1'} or style_selection.get('role')!='style': raise ValueError('style reference_selection/1.x required')
    if evidence_selection.get('schema') not in {'reference_selection/1.0','reference_selection/1.1','claim_evidence_selection/1.0'}: raise ValueError('evidence reference_selection/1.x or claim_evidence_selection/1.0 required')
    if evidence_selection.get('schema')!='claim_evidence_selection/1.0' and evidence_selection.get('role')!='evidence': raise ValueError('evidence role required')
    payload={'document_kind':object_decision.get('kind'),'section_role':section_role,'style_fragments':style_selection.get('selected') or [],'evidence_fragments':evidence_selection.get('selected') or [],'claims':claims,'instructions':instructions,'writing_policy_id':(writing_policy or {}).get('policy_id'),'style_instruction_id':(style_instruction or {}).get('style_instruction_id')}
    evidence_by_claim={}
    if evidence_selection.get('schema')=='claim_evidence_selection/1.0':
        evidence_by_claim={str(r.get('claim_id')):list(r.get('selected') or []) for r in evidence_selection.get('claims') or [] if r.get('claim_id')}
    else:
        for c in claims:
            cid=str(c.get('id') or c.get('claim_id') or '') if isinstance(c,dict) else ''
            if cid:evidence_by_claim[cid]=list(payload['evidence_fragments'])
    payload['evidence_by_claim']=evidence_by_claim
    h=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'ok':True,'schema':SCHEMA,'request_id':'DR-'+h[:16],'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'object':object_decision,'section_role':section_role,'style_references':payload['style_fragments'],'evidence_references':payload['evidence_fragments'],
            'writing_policy':writing_policy,'style_instruction':style_instruction,'authorized_claims':claims,'evidence_by_claim':evidence_by_claim,'instructions':instructions,'constraints':{'style_refs_are_not_evidence':True,'writer_may_search_web':False,'new_factual_claims_require_research_debt':True,'claim_realization_authority':'DraftArtifact→DOM paragraph.claims','rendered_claim_markers_are_projection':True},'content_hash':h}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--object',required=True); ap.add_argument('--style-selection',required=True); ap.add_argument('--evidence-selection',required=True); ap.add_argument('--claims',required=True); ap.add_argument('--section-role',required=True); ap.add_argument('--instructions',default=''); ap.add_argument('--writing-policy'); ap.add_argument('--style-instruction'); a=ap.parse_args()
    try:
        load=lambda p: json.loads(Path(p).read_text(encoding='utf8'))
        claims=load(a.claims); claims=claims.get('claims',claims) if isinstance(claims,dict) else claims
        out=build(load(a.object),load(a.style_selection),load(a.evidence_selection),claims,a.section_role,a.instructions,load(a.writing_policy) if a.writing_policy else None,load(a.style_instruction) if a.style_instruction else None)
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
