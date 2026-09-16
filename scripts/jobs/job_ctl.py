#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, tempfile, time, uuid
from pathlib import Path

TERMINAL_ATTEMPT={'COMPLETED','FAILED','TIMED_OUT','TERMINATED','LOST'}
TERMINAL_JOB={'COMPLETED','FAILED_NO_OUTPUT','FAILED_WITH_CHECKPOINT','TERMINATED_WITH_ARTIFACTS'}
TERMINAL_STAGE={'COMPLETED','SKIPPED','FAILED'}

def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def sha(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def atomic_write(path:Path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save(s,p): s['updated_at']=now(); atomic_write(Path(p),s)
def event(s,typ,payload):
    prev=s['events'][-1]['hash'] if s['events'] else None
    e={'seq':len(s['events'])+1,'at':now(),'type':typ,'payload':payload,'prev_hash':prev}; e['hash']=sha(e); s['events'].append(e)
def contract_hash(contract): return sha(contract)
def attempt_by(s,aid):
    for a in s['attempts']:
        if a['attempt_id']==aid: return a
    raise KeyError(f'unknown attempt:{aid}')
def child_by(s,cid):
    for c in s['children']:
        if c['child_id']==cid: return c
    raise KeyError(f'unknown child:{cid}')

def create(job_id,contract,stages):
    ch=contract_hash(contract)
    s={'schema':'research-job/1.1','job_id':job_id,'contract':contract,'contract_hash':ch,'status':'RUNNING','created_at':now(),'updated_at':now(),'stages':{x:{'status':'PENDING','artifacts':[],'checkpoint':None,'updated_at':None} for x in stages},'attempts':[],'children':[],'artifacts':{},'required_artifacts':[],'gates':{},'events':[]}
    event(s,'JOB_CREATED',{'contract_hash':ch,'stages':stages}); return s

def reconcile(s):
    stage_bad=[k for k,v in s['stages'].items() if v['status'] not in {'COMPLETED','SKIPPED'}]
    child_bad=[c['child_id'] for c in s['children'] if c['mode']=='required' and c['status']!='COMPLETED']
    missing_art=[a for a in s['required_artifacts'] if a not in s['artifacts']]
    bad_gates=[k for k,v in s['gates'].items() if v.get('required') and v.get('verdict')!='PASS']
    ok=not(stage_bad or child_bad or missing_art or bad_gates)
    return {'ok':ok,'nonterminal_stages':stage_bad,'nonterminal_required_children':child_bad,'missing_required_artifacts':missing_art,'failed_required_gates':bad_gates}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--state',required=True); sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('init'); p.add_argument('job_id'); p.add_argument('--contract',required=True); p.add_argument('--stages',required=True)
    p=sub.add_parser('attempt-start'); p.add_argument('--agent',required=True); p.add_argument('--stage',required=True); p.add_argument('--external-task-id')
    p=sub.add_parser('heartbeat'); p.add_argument('attempt_id'); p.add_argument('--stage'); p.add_argument('--done',type=int); p.add_argument('--total',type=int); p.add_argument('--last-artifact')
    p=sub.add_parser('checkpoint'); p.add_argument('attempt_id'); p.add_argument('--stage',required=True); p.add_argument('--checkpoint',required=True)
    p=sub.add_parser('attempt-finish'); p.add_argument('attempt_id'); p.add_argument('status',choices=sorted(TERMINAL_ATTEMPT)); p.add_argument('--artifact',action='append',default=[])
    p=sub.add_parser('artifact'); p.add_argument('artifact_id'); p.add_argument('path'); p.add_argument('--sha256'); p.add_argument('--required',action='store_true')
    p=sub.add_parser('stage'); p.add_argument('stage'); p.add_argument('status',choices=['RUNNING','COMPLETED','SKIPPED','FAILED']); p.add_argument('--artifact',action='append',default=[])
    p=sub.add_parser('child-add'); p.add_argument('child_id'); p.add_argument('--mode',choices=['required','optional','detached'],default='required'); p.add_argument('--external-task-id')
    p=sub.add_parser('child-finish'); p.add_argument('child_id'); p.add_argument('status',choices=sorted(TERMINAL_ATTEMPT))
    p=sub.add_parser('gate'); p.add_argument('gate_id'); p.add_argument('verdict',choices=['PASS','FAIL','BLOCK','PENDING']); p.add_argument('--required',action='store_true')
    sub.add_parser('reconcile'); sub.add_parser('status'); sub.add_parser('complete')
    a=ap.parse_args(); path=Path(a.state)
    try:
        if a.cmd=='init':
            c=json.loads(Path(a.contract).read_text(encoding='utf-8')); s=create(a.job_id,c,[x for x in a.stages.split(',') if x]); save(s,path); out={'ok':True,'job_id':s['job_id'],'contract_hash':s['contract_hash']}
        else:
            s=load(path)
            if a.cmd=='attempt-start':
                if a.stage not in s['stages']: raise ValueError('unknown stage')
                if a.external_task_id:
                    for old in s['attempts']:
                        if old.get('external_task_id')==a.external_task_id: raise ValueError('external_task_id already used in this job')
                aid='ATT-'+uuid.uuid4().hex[:12]; rec={'attempt_id':aid,'agent':a.agent,'stage':a.stage,'external_task_id':a.external_task_id,'status':'RUNNING','started_at':now(),'heartbeat':None,'artifacts':[]}; s['attempts'].append(rec); s['stages'][a.stage]['status']='RUNNING'; event(s,'ATTEMPT_STARTED',rec); save(s,path); out={'ok':True,'attempt_id':aid}
            elif a.cmd=='heartbeat':
                r=attempt_by(s,a.attempt_id); hb={'at':now(),'stage':a.stage or r['stage'],'done':a.done,'total':a.total,'last_artifact':a.last_artifact}; r['heartbeat']=hb; event(s,'HEARTBEAT',{'attempt_id':a.attempt_id,**hb}); save(s,path); out={'ok':True,'heartbeat':hb}
            elif a.cmd=='checkpoint':
                r=attempt_by(s,a.attempt_id); r['status']='CHECKPOINTED'; cp={'id':a.checkpoint,'at':now(),'attempt_id':a.attempt_id}; s['stages'][a.stage]['checkpoint']=cp; event(s,'CHECKPOINT',{'stage':a.stage,**cp}); save(s,path); out={'ok':True,'checkpoint':cp}
            elif a.cmd=='attempt-finish':
                r=attempt_by(s,a.attempt_id); r['status']=a.status; r['finished_at']=now(); r['artifacts']=list(dict.fromkeys(r.get('artifacts',[])+a.artifact)); event(s,'ATTEMPT_FINISHED',{'attempt_id':a.attempt_id,'status':a.status,'artifacts':r['artifacts']});
                if a.status in {'FAILED','TIMED_OUT','TERMINATED','LOST'}: s['status']='WAITING_RETRY' if s['stages'][r['stage']].get('checkpoint') or r['artifacts'] else 'DEGRADED'
                save(s,path); out={'ok':True,'job_status':s['status']}
            elif a.cmd=='artifact':
                pth=Path(a.path); hv=a.sha256
                if hv is None and pth.exists() and pth.is_file(): hv=hashlib.sha256(pth.read_bytes()).hexdigest()
                s['artifacts'][a.artifact_id]={'path':str(pth),'sha256':hv,'registered_at':now()};
                if a.required and a.artifact_id not in s['required_artifacts']: s['required_artifacts'].append(a.artifact_id)
                event(s,'ARTIFACT_REGISTERED',{'artifact_id':a.artifact_id,'sha256':hv,'required':a.required}); save(s,path); out={'ok':True}
            elif a.cmd=='stage':
                if a.stage not in s['stages']: raise ValueError('unknown stage')
                st=s['stages'][a.stage]; st['status']=a.status; st['updated_at']=now(); st['artifacts']=list(dict.fromkeys(st.get('artifacts',[])+a.artifact)); event(s,'STAGE_UPDATED',{'stage':a.stage,'status':a.status,'artifacts':st['artifacts']}); save(s,path); out={'ok':True}
            elif a.cmd=='child-add':
                if any(c['child_id']==a.child_id for c in s['children']): raise ValueError('child exists')
                c={'child_id':a.child_id,'mode':a.mode,'external_task_id':a.external_task_id,'status':'RUNNING','created_at':now()}; s['children'].append(c); event(s,'CHILD_ADDED',c); save(s,path); out={'ok':True}
            elif a.cmd=='child-finish':
                c=child_by(s,a.child_id); c['status']=a.status; c['finished_at']=now(); event(s,'CHILD_FINISHED',{'child_id':a.child_id,'status':a.status}); save(s,path); out={'ok':True}
            elif a.cmd=='gate':
                old=s['gates'].get(a.gate_id,{}); s['gates'][a.gate_id]={'verdict':a.verdict,'required':a.required or old.get('required',False),'updated_at':now()}; event(s,'GATE_UPDATED',{'gate_id':a.gate_id,**s['gates'][a.gate_id]}); save(s,path); out={'ok':True}
            elif a.cmd=='reconcile': out={'ok':True,'reconciliation':reconcile(s),'status':s['status']}
            elif a.cmd=='complete':
                rec=reconcile(s)
                if not rec['ok']: out={'ok':False,'error':'COMPLETION_REJECTED','reconciliation':rec}; print(json.dumps(out,ensure_ascii=False,indent=2)); return 4
                s['status']='COMPLETED'; event(s,'JOB_COMPLETED',{}); save(s,path); out={'ok':True,'status':'COMPLETED'}
            else: out={'ok':True,'job':s,'reconciliation':reconcile(s)}
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'error':f'{e.__class__.__name__}: {e}'},ensure_ascii=False,indent=2)); return 3
if __name__=='__main__': raise SystemExit(main())
