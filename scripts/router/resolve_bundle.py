#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, os, re
from pathlib import Path

def root()->Path: return Path(os.environ.get('OPENCODE_HARNESS_ROOT',Path(__file__).resolve().parents[2])).resolve()
def read(rel): return json.loads((root()/rel).read_text(encoding='utf-8'))
def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(m); return m

def choose_stage(route_cfg:dict,text:str,requested:str|None)->str:
    stages=route_cfg['stages']
    if requested:
        if requested not in stages: raise ValueError(f'unknown stage {requested}')
        return requested
    low=text.lower()
    signals=[('source-resolution',r'\bdoi\b|crossref|openalex|resolve source|провер.*doi'),('document-analysis',r'pdf|docx|xlsx|tiff|извлеч|проанализ.*документ'),('evidence-validation',r'fact.?check|verify claim|провер.*утверж|валид.*клайм'),('semantic-validation',r'semantic|round.?trip|проверь текст|валид.*текст'),('review',r'code review|ревью код|аудит код'),('test',r'run tests|тестир'),('acceptance',r'acceptance|приемк')]
    for sid,rx in signals:
        if sid in stages and re.search(rx,low,re.I): return sid
    return route_cfg['default_stage']

def _load_preflight(path:str|None):
    if path: return json.loads(Path(path).read_text(encoding='utf-8'))
    return load_module(root()/'scripts/router/capability_preflight.py','cap_preflight').snapshot()

def _state_for_requirements(scfg,pf):
    req=list(scfg.get('required_capabilities',[])); groups=list(scfg.get('required_any_of',[]))
    missing=[c for c in req if not pf['capabilities'].get(c,{}).get('available')]
    failed_groups=[]
    for g in groups:
        if not any(pf['capabilities'].get(c,{}).get('available') for c in g): failed_groups.append(g)
    if missing or failed_groups:
        implemented_missing=[c for c in missing if pf['capabilities'].get(c,{}).get('implemented')]
        group_impl=[g for g in failed_groups if any(pf['capabilities'].get(c,{}).get('implemented') for c in g)]
        state='DEGRADED_CAPABILITY' if (implemented_missing or group_impl) else 'BLOCKED_MISSING_CAPABILITY'
        return state,missing,failed_groups
    return 'READY',[],[]

def resolve_bundle(task:str,route_id=None,stage=None,profile=None,preflight_path=None):
    rr=load_module(root()/'scripts/router/resolve_route.py','base_resolver')
    hints={}
    if route_id: hints['route_id']=route_id
    if profile: hints['preferred_profile']=profile
    base=rr.resolve(task,hints)
    if not base.get('ok'): return base
    snap_path=root()/'config/capability_runtime_snapshot.json'
    if not snap_path.exists(): return {'ok':False,'error':'capability_runtime_snapshot missing; run compile_capability_runtime.py'}
    snap=read('config/capability_runtime_snapshot.json'); route=base['route_id']; route_cfg=snap.get('routes',{}).get(route)
    if not route_cfg:
        return {**base,'bundle_mode':'legacy','bundle_state':'LEGACY'}
    sid=choose_stage(route_cfg,task,stage); scfg=route_cfg['stages'][sid]; pf=_load_preflight(preflight_path)
    req=list(scfg.get('required_capabilities',[])); opt=list(scfg.get('optional_capabilities',[])); forb=set(scfg.get('forbidden_capabilities',[]))
    domains=[]; overlay_caps=[]; overlay_tools=[]; overlay_skills=[]
    for did,d in snap.get('domain_overlays',{}).items():
        if re.search(d['match_regex'],task,re.I):
            domains.append(did); overlay_caps+=d.get('capabilities',[]); overlay_tools+=d.get('tools',[]); overlay_skills+=d.get('skills',[])
    opt+=overlay_caps
    state,missing,failed_groups=_state_for_requirements(scfg,pf)
    all_caps=[]
    for c in req+opt+[c for g in scfg.get('required_any_of',[]) for c in g]:
        if c not in all_caps and c not in forb: all_caps.append(c)
    providers={}
    for c in all_caps:
        ids=pf['capabilities'].get(c,{}).get('providers',[])
        if ids: providers[c]=ids[0]
    logical=[]
    for t in scfg.get('tools',[])+overlay_tools:
        cap=snap.get('logical_tools',{}).get(t,{}).get('capability')
        if cap not in forb and t not in logical: logical.append(t)
    if (scfg.get('optional_capabilities') or scfg.get('escalation')) and 'capability.request' not in logical:
        logical.append('capability.request')
    skills=[]
    for s in scfg.get('skills',[])+overlay_skills:
        if s not in skills: skills.append(s)
    return {'ok':state=='READY','bundle_state':state,'route_id':route,'stage':sid,'domains':domains,'profile':base.get('profile'),'execution_mode':base.get('execution_mode'),'skills':skills,'logical_tools':logical,'required_capabilities':req,'required_any_of':scfg.get('required_any_of',[]),'optional_capabilities':list(dict.fromkeys(opt)),'forbidden_capabilities':sorted(forb),'providers':providers,'missing_required':missing,'failed_requirement_groups':failed_groups,'next_stages':scfg.get('next',[]),'escalation':scfg.get('escalation',{}),'base_policy_hash':base.get('policy_hash'),'capability_policy_hash':snap.get('policy_hash'),'bundle_mode':'capability','guard_required':base.get('guard_required',False)}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('task'); ap.add_argument('--route-id'); ap.add_argument('--stage'); ap.add_argument('--profile'); ap.add_argument('--preflight')
    a=ap.parse_args()
    try: out=resolve_bundle(a.task,a.route_id,a.stage,a.profile,a.preflight)
    except Exception as e: out={'ok':False,'error':f'{e.__class__.__name__}: {e}'}
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if out.get('ok') or out.get('bundle_mode')=='legacy' else 4
if __name__=='__main__': raise SystemExit(main())
