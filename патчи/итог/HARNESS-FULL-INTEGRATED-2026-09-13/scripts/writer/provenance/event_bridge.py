#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any
from scripts.jobs import job_ctl
SCHEMA='writer_provenance_event_bridge/1.0'

def register_change_ledger(state_path:str, ledger_path:str, artifact_id:str)->dict[str,Any]:
    sp=Path(state_path); lp=Path(ledger_path)
    if not sp.is_file() or not lp.is_file(): raise FileNotFoundError('state or ledger missing')
    ledger=json.loads(lp.read_text(encoding='utf8'))
    if ledger.get('schema') not in {'writer_change_ledger/1.0','writer_change_ledger/1.1'}: raise ValueError('writer_change_ledger/1.0 or 1.1 required')
    state=job_ctl.load(sp); hv=hashlib.sha256(lp.read_bytes()).hexdigest()
    state['artifacts'][artifact_id]={'path':str(lp),'sha256':hv,'registered_at':job_ctl.now(),'media_type':'application/json','kind':'writer_change_ledger'}
    job_ctl.event(state,'ARTIFACT_REGISTERED',{'artifact_id':artifact_id,'sha256':hv,'required':False,'kind':'writer_change_ledger'})
    job_ctl.event(state,'WRITER_CHANGE_LEDGER',{'artifact_id':artifact_id,'old_sha256':(ledger.get('old') or {}).get('sha256'),'new_sha256':(ledger.get('new') or {}).get('sha256'),'touched_claims':ledger.get('touched_claims') or [],'touched_sources':ledger.get('touched_sources') or []})
    job_ctl.save(state,sp)
    return {'ok':True,'schema':SCHEMA,'job_id':state.get('job_id'),'artifact_id':artifact_id,'sha256':hv,'events_added':2}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--state',required=True); ap.add_argument('--ledger',required=True); ap.add_argument('--artifact-id',required=True); a=ap.parse_args()
    try:
        print(json.dumps(register_change_ledger(a.state,a.ledger,a.artifact_id),ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
