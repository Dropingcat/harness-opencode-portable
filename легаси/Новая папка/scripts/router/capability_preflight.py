#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, os, shutil, socket, sqlite3, subprocess
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT_ENV='OPENCODE_HARNESS_ROOT'

def repo_root()->Path:
    return Path(os.environ.get(ROOT_ENV, Path(__file__).resolve().parents[2])).resolve()

def load_json(rel:str)->dict:
    return json.loads((repo_root()/rel).read_text(encoding='utf-8'))

def _probe_one(spec:dict, network:bool=True)->dict:
    kind=spec.get('kind','always')
    try:
        if kind=='always': return {'ok':True,'detail':'always'}
        if kind=='python_module':
            mod=spec['module']; ok=importlib.util.find_spec(mod) is not None
            return {'ok':ok,'detail':f'module:{mod}'}
        if kind=='executable':
            p=shutil.which(spec['name']); return {'ok':bool(p),'detail':p or f'missing:{spec["name"]}'}
        if kind=='file':
            p=(repo_root()/spec['path']).resolve(); return {'ok':p.exists(),'detail':str(p)}
        if kind=='env':
            key=spec['name']; return {'ok':bool(os.environ.get(key)),'detail':f'env:{key}'}
        if kind=='sqlite_fts5':
            c=sqlite3.connect(':memory:'); c.execute('create virtual table x using fts5(t)'); c.close(); return {'ok':True,'detail':'sqlite:fts5'}
        if kind in {'tcp','http_json'} and not network:
            return {'ok':False,'detail':'network_probe_disabled','degraded':True}
        if kind=='tcp':
            u=urlparse(spec['url']); host=u.hostname; port=u.port or (443 if u.scheme=='https' else 80)
            with socket.create_connection((host,port),timeout=float(spec.get('timeout',1))): pass
            return {'ok':True,'detail':f'tcp:{host}:{port}'}
        if kind=='http_json':
            url=spec['url']; req=Request(url,headers={'User-Agent':'opencode-harness-preflight/1.0'})
            with urlopen(req,timeout=float(spec.get('timeout',2))) as r:
                raw=r.read(int(spec.get('max_bytes',131072)))
                if getattr(r,'status',200) >= 400: raise RuntimeError(f'http:{r.status}')
                json.loads(raw.decode('utf-8','replace'))
            return {'ok':True,'detail':f'http_json:{url}'}
        if kind=='command':
            argv=list(spec['argv'])
            executable_env=spec.get('executable_env')
            if executable_env:
                executable=os.environ.get(executable_env) or spec.get('executable_default')
                if not executable:
                    return {'ok':False,'detail':f'missing_executable:{executable_env}'}
                argv.insert(0,executable)
                executable_source=(
                    f'env:{executable_env}'
                    if os.environ.get(executable_env)
                    else f'default:{executable}'
                )
            else:
                executable_source='argv'
            cp=subprocess.run(argv,cwd=repo_root(),text=True,capture_output=True,timeout=float(spec.get('timeout',5)))
            return {'ok':cp.returncode==0,'detail':f'exit:{cp.returncode};executable:{executable_source}'}
        return {'ok':False,'detail':f'unknown_probe:{kind}'}
    except Exception as e:
        return {'ok':False,'detail':f'{kind}:{e.__class__.__name__}:{e}'}

def probe_provider(provider:dict, network:bool=True)->dict:
    # installed_probe proves the adapter/provider implementation exists.
    # live_probe proves that its current backend is usable now.
    installed_spec=provider.get('installed_probe') or provider.get('probe') or {'kind':'always'}
    installed=_probe_one(installed_spec,network=False)
    if not installed['ok']:
        return {'status':'missing','available':False,'implemented':False,'detail':installed['detail']}
    if provider.get('enabled') is False:
        return {'status':'disabled','available':False,'implemented':True,'detail':'provider_disabled'}
    live_spec=provider.get('live_probe')
    if live_spec:
        live=_probe_one(live_spec,network=network)
        if not live['ok']:
            return {'status':'degraded','available':False,'implemented':True,'detail':live['detail']}
        return {'status':'available','available':True,'implemented':True,'detail':live['detail']}
    return {'status':'available','available':True,'implemented':True,'detail':installed['detail']}

def snapshot(network:bool=True)->dict:
    providers=load_json('config/providers_authority.json')['providers']
    caps=load_json('config/capabilities_authority.json')['capabilities']
    pstate={}
    cap_avail={c:[] for c in caps}; cap_impl={c:[] for c in caps}
    for pid,p in providers.items():
        st=probe_provider(p,network=network)
        pstate[pid]={**st,'kind':p.get('kind'),'provides':p.get('provides',[]),'priority':p.get('priority',0)}
        for c in p.get('provides',[]):
            if st['implemented']: cap_impl.setdefault(c,[]).append(pid)
            if st['available']: cap_avail.setdefault(c,[]).append(pid)
    def sort_ids(ids): return sorted(ids,key=lambda x:(-int(providers[x].get('priority',0)),x))
    cstate={}
    for cid,cfg in caps.items():
        a=sort_ids(cap_avail.get(cid,[])); i=sort_ids(cap_impl.get(cid,[]))
        if a: status='available'
        elif i: status='degraded'
        else: status='missing'
        cstate[cid]={'status':status,'available':bool(a),'implemented':bool(i),'providers':a,'implemented_providers':i,'trust_class':cfg.get('trust_class'),'evidence_eligible':cfg.get('evidence_eligible',False)}
    return {'schema':'capability-preflight/1.0','network_probes':network,'providers':pstate,'capabilities':cstate}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output'); ap.add_argument('--no-network',action='store_true'); args=ap.parse_args()
    s=snapshot(network=not args.no_network); text=json.dumps(s,ensure_ascii=False,indent=2)
    if args.output: Path(args.output).write_text(text+'\n',encoding='utf-8')
    print(text); return 0
if __name__=='__main__': raise SystemExit(main())
