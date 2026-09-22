from __future__ import annotations
import hashlib,json,time
from typing import Any
from scripts.writer.drafting.proposed_claim import normalize as normalize_proposed_claim, build as build_proposed_claim
SCHEMA='draft_artifact/1.1'

def build(request:dict[str,Any],paragraphs:list[dict[str,Any]])->dict[str,Any]:
    if request.get('schema')!='draft_request/1.0':raise ValueError('draft_request/1.0 required')
    auth={str(c.get('id') or c.get('claim_id')) for c in request.get('authorized_claims') or [] if isinstance(c,dict)}
    clean=[];unauthorized=set(); proposed=[]
    for i,p in enumerate(paragraphs,1):
        text=str(p.get('text') or '').strip()
        if not text:continue
        pid=str(p.get('temp_id') or f'DP-{i:03d}')
        claims=[str(x) for x in p.get('realizes_claims') or [] if x]
        unknown=sorted(set(claims)-auth); unauthorized.update(unknown)
        for cid in unknown:
            proposed.append(build_proposed_claim(text=f'Unregistered claim reference {cid}',paragraph_id=pid,claim_type='UNKNOWN',reason='UNKNOWN_CLAIM_ID',derived_from=[cid]))
        for raw in p.get('proposed_claims') or []:
            if isinstance(raw,dict): proposed.append(normalize_proposed_claim(raw,paragraph_id=pid))
        clean.append({'temp_id':pid,'target_paragraph_id':p.get('target_paragraph_id'),'text':text,'realizes_claims':claims,'evidence_refs':list(p.get('evidence_refs') or []),'style_instruction_id':p.get('style_instruction_id'),'proposed_claim_ids':[x['proposed_claim_id'] for x in proposed if x.get('paragraph_id')==pid]})
    payload={'request_id':request.get('request_id'),'paragraphs':clean,'unauthorized_claim_ids':sorted(unauthorized),'proposed_claims':proposed}
    h=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    blocked=bool(unauthorized or proposed)
    return {'ok':not blocked,'schema':SCHEMA,'compatible_with':['draft_artifact/1.0'],'draft_id':'DA-'+h[:16],'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**payload,'requires_research_debt':blocked,'requires_claim_registration':bool(proposed),'content_hash':h}

if __name__=='__main__':
 import argparse
 from pathlib import Path
 ap=argparse.ArgumentParser();ap.add_argument('--request',required=True);ap.add_argument('--paragraphs',required=True);a=ap.parse_args();load=lambda p:json.loads(Path(p).read_text(encoding='utf8'));d=load(a.paragraphs);pars=d.get('paragraphs',d) if isinstance(d,dict) else d;print(json.dumps(build(load(a.request),pars),ensure_ascii=False,indent=2))
