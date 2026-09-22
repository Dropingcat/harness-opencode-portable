#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from scripts.writer.references.select import select

SCHEMA = 'claim_evidence_selection/1.0'

def _cid(c: dict[str, Any]) -> str:
    return str(c.get('id') or c.get('claim_id') or '').strip()

def select_for_claims(fragments: list[dict[str, Any]], claims: list[dict[str, Any]], *, limit_per_claim: int = 3, max_per_reference: int = 2) -> dict[str, Any]:
    rows=[]; aggregate=[]; seen=set(); missing=[]
    for claim in claims:
        if not isinstance(claim,dict):
            continue
        cid=_cid(claim)
        text=str(claim.get('text') or claim.get('proposition') or '').strip()
        if not cid or not text:
            continue
        r=select(fragments,role='evidence',target_text=text,limit=limit_per_claim,max_per_reference=max_per_reference)
        picked=[]
        for hit in r.get('selected') or []:
            x=dict(hit); x['claim_id']=cid; picked.append(x)
            key=(str(x.get('fragment_id')),str(x.get('reference_id')))
            if key not in seen:
                seen.add(key);aggregate.append(x)
        if not picked:
            missing.append(cid)
        rows.append({'claim_id':cid,'claim_text':text,'status':r.get('status'),'reason_code':r.get('reason_code'),'selected':picked})
    return {
        'ok':not bool(missing),'schema':SCHEMA,'status':'READY' if not missing else 'DEGRADED',
        'claims':rows,'missing_claim_ids':missing,'selected':aggregate,
        'constraints':{'selection_is_per_claim':True,'style_filters_do_not_apply_to_evidence':True}
    }

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('fragment_sets',nargs='+');ap.add_argument('--claims',required=True);ap.add_argument('--limit-per-claim',type=int,default=3);a=ap.parse_args()
    try:
        fr=[]
        for p in a.fragment_sets:
            fr.extend(json.loads(Path(p).read_text(encoding='utf8')).get('fragments') or [])
        d=json.loads(Path(a.claims).read_text(encoding='utf8'));claims=d.get('claims',d) if isinstance(d,dict) else d
        out=select_for_claims(fr,claims,limit_per_claim=a.limit_per_claim)
        print(json.dumps(out,ensure_ascii=False,indent=2));return 0 if out.get('ok') else 4
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
