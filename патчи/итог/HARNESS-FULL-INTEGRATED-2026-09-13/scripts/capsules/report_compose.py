#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('manifest'); ap.add_argument('--output',required=True); args=ap.parse_args()
    m=json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    lines=[]
    if m.get('title'): lines += ['# '+m['title'],'']
    for s in m.get('sections',[]):
        lines += ['## '+s.get('title','Section'),'']
        body=s.get('body','').rstrip(); lines += [body,'']
        refs=s.get('claim_refs',[])
        if refs: lines += ['Claims: '+', '.join(refs),'']
    unresolved=m.get('unresolved',[])
    if unresolved:
        lines += ['## Unresolved','']+[f'- {x}' for x in unresolved]+['']
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
    h=hashlib.sha256(out.read_bytes()).hexdigest()
    print(json.dumps({'ok':True,'schema':'report_artifact.v1','output':str(out.resolve()),'sha256':h,'sections':len(m.get('sections',[])),'unresolved_count':len(unresolved)},ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
