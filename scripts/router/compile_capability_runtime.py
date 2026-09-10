#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path

def root()->Path: return Path(os.environ.get('OPENCODE_HARNESS_ROOT',Path(__file__).resolve().parents[2])).resolve()
def read(rel): return json.loads((root()/rel).read_text(encoding='utf-8'))
def canon(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

def validate(base,caps,prov,stages,tools):
    errors=[]; known_caps=set(caps['capabilities']); known_routes=set(base['routes']); known_tools=set(tools['tools'])
    skillreg=read('config/skills_registry.json'); known_skills=set(skillreg.get('core_runtime_skills',[]))|set(skillreg.get('optional_domain_skills',[]))|set(skillreg.get('reference_only_skills',[])); [known_skills.update(r.get('skills',[])) for r in base.get('routes',{}).values()]; [known_skills.update(c.get('provided_skills',[])) for c in base.get('capsules',{}).values()]
    for rid,rcfg in stages.get('routes',{}).items():
        if rid not in known_routes: errors.append(f'unknown route in stage policy: {rid}')
        ss=rcfg.get('stages',{})
        if rcfg.get('default_stage') not in ss: errors.append(f'{rid}: default_stage missing')
        for sid,s in ss.items():
            for c in s.get('required_capabilities',[])+s.get('optional_capabilities',[])+s.get('forbidden_capabilities',[]):
                if c not in known_caps: errors.append(f'{rid}/{sid}: unknown capability {c}')
            for group in s.get('required_any_of',[]):
                if not group: errors.append(f'{rid}/{sid}: empty required_any_of group')
                for c in group:
                    if c not in known_caps: errors.append(f'{rid}/{sid}: unknown capability {c}')
            for t in s.get('tools',[]):
                if t not in known_tools: errors.append(f'{rid}/{sid}: unknown logical tool {t}')
            for sk in s.get('skills',[]):
                if sk not in known_skills: errors.append(f'{rid}/{sid}: unknown skill {sk}')
            for n in s.get('next',[]):
                if n not in ss: errors.append(f'{rid}/{sid}: unknown next stage {n}')
    for did,d in stages.get('domain_overlays',{}).items():
        try: __import__('re').compile(d['match_regex'])
        except Exception as e: errors.append(f'domain {did}: invalid regex {e}')
        for c in d.get('capabilities',[]):
            if c not in known_caps: errors.append(f'domain {did}: unknown capability {c}')
        for t in d.get('tools',[]):
            if t not in known_tools: errors.append(f'domain {did}: unknown tool {t}')
        for sk in d.get('skills',[]):
            if sk not in known_skills: errors.append(f'domain {did}: unknown skill {sk}')
    for tid,t in tools['tools'].items():
        if t.get('capability') not in known_caps: errors.append(f'tool {tid}: unknown capability {t.get("capability")}')
    valid_probe={'always','python_module','executable','file','env','sqlite_fts5','tcp','http_json','command'}
    for pid,p in prov['providers'].items():
        if not p.get('provides'): errors.append(f'provider {pid}: provides empty')
        for c in p.get('provides',[]):
            if c not in known_caps: errors.append(f'provider {pid}: unknown capability {c}')
        for key in ('installed_probe','live_probe','probe'):
            if key in p and p[key].get('kind','always') not in valid_probe: errors.append(f'provider {pid}: invalid {key} kind')
            if key in p and p[key].get('kind')=='command':
                probe=p[key]; argv=probe.get('argv')
                if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and x for x in argv):
                    errors.append(f'provider {pid}: {key} command argv must be a non-empty string list')
                executable_env=probe.get('executable_env')
                if executable_env is not None and (not isinstance(executable_env,str) or not executable_env):
                    errors.append(f'provider {pid}: {key} executable_env must be a non-empty string')
                executable_default=probe.get('executable_default')
                if executable_default is not None and (not isinstance(executable_default,str) or not executable_default):
                    errors.append(f'provider {pid}: {key} executable_default must be a non-empty string')
    return errors

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    base=read('config/runtime_snapshot.json'); caps=read('config/capabilities_authority.json'); prov=read('config/providers_authority.json'); stages=read('config/stage_capsules_authority.json'); tools=read('config/logical_tools.json')
    errors=validate(base,caps,prov,stages,tools)
    if errors: print(json.dumps({'ok':False,'errors':errors},ensure_ascii=False,indent=2)); return 2
    sources={'base_policy_hash':base.get('policy_hash'),'capabilities':caps,'providers':prov,'stages':stages,'logical_tools':tools}; ph=hashlib.sha256(canon(sources)).hexdigest()
    out={'version':2,'generated':True,'policy_hash':ph,'base_policy_hash':base.get('policy_hash'),'capabilities':caps['capabilities'],'providers':prov['providers'],'routes':stages['routes'],'domain_overlays':stages.get('domain_overlays',{}),'logical_tools':tools['tools']}
    path=root()/'config/capability_runtime_snapshot.json'; text=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
    if args.check:
        if not path.exists() or path.read_text(encoding='utf-8')!=text:
            print(json.dumps({'ok':False,'error':'capability_runtime_snapshot stale or missing','expected_policy_hash':ph},ensure_ascii=False,indent=2)); return 3
    else: path.write_text(text,encoding='utf-8')
    print(json.dumps({'ok':True,'policy_hash':ph,'path':str(path),'routes':len(out['routes']),'providers':len(out['providers'])},ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
