from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from scripts.jobs import job_ctl
SCHEMA='writer_invalidation_event_bridge/1.0'

def register(state_path:str,plan_path:str,artifact_id:str)->dict:
 sp=Path(state_path);pp=Path(plan_path);state=job_ctl.load(sp);plan=json.loads(pp.read_text(encoding='utf8'));h=hashlib.sha256(pp.read_bytes()).hexdigest()
 state['artifacts'][artifact_id]={'path':str(pp),'sha256':h,'registered_at':job_ctl.now(),'media_type':'application/json','kind':'writer_invalidation_plan'}
 job_ctl.event(state,'ARTIFACT_REGISTERED',{'artifact_id':artifact_id,'sha256':h,'kind':'writer_invalidation_plan'})
 job_ctl.event(state,'WRITER_SOURCE_INVALIDATED',{'artifact_id':artifact_id,'changed_sources':plan.get('changed_sources') or [],'claims_to_revalidate':plan.get('claims_to_revalidate') or [],'paragraphs_to_repair':plan.get('paragraphs_to_repair') or []})
 job_ctl.save(state,sp);return {'ok':True,'schema':SCHEMA,'artifact_id':artifact_id,'events_added':2}

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--state',required=True);ap.add_argument('--plan',required=True);ap.add_argument('--artifact-id',required=True);a=ap.parse_args()
 try:print(json.dumps(register(a.state,a.plan,a.artifact_id),ensure_ascii=False,indent=2));return 0
 except Exception as e:print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
