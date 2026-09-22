#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any,Iterable
SCHEMA='writer_dependency_graph/1.1'

def _id(d:dict[str,Any],*keys:str)->str|None:
    for k in keys:
        if d.get(k): return str(d[k])
    return None

def _paragraphs(dom:dict[str,Any])->Iterable[dict[str,Any]]:
    for p in dom.get('paragraphs') or []:
        if isinstance(p,dict): yield p
    st=dom.get('structure') or {}
    for ch in st.get('chapters') or []:
        for sec in (ch.get('sections') or []) if isinstance(ch,dict) else []:
            for p in (sec.get('paragraphs') or []) if isinstance(sec,dict) else []:
                if isinstance(p,dict): yield p

def build(dom:dict[str,Any])->dict[str,Any]:
    edges=[];nodes={}
    for s in dom.get('sources') or []:
        if not isinstance(s,dict): continue
        sid=_id(s,'source_id','id')
        if sid: nodes[sid]={'id':sid,'type':'source','sha256':s.get('sha256') or s.get('content_hash')}
    for c in dom.get('claims') or []:
        if not isinstance(c,dict): continue
        cid=_id(c,'claim_id','id')
        if not cid: continue
        nodes[cid]={'id':cid,'type':'claim','text':c.get('text')}
        refs=[]
        if c.get('source_id'):refs.append(c.get('source_id'))
        for e in c.get('evidence') or c.get('evidence_refs') or []:
            if isinstance(e,dict):refs.append(e.get('source_id') or e.get('source'))
            elif isinstance(e,str):refs.append(e)
        for sid in sorted({str(x) for x in refs if x}):
            nodes.setdefault(sid,{'id':sid,'type':'source'})
            edges.append({'src':sid,'dst':cid,'relation':'SUPPORTS'})
    for p in _paragraphs(dom):
        pid=_id(p,'paragraph_id','id')
        if not pid:continue
        nodes[pid]={'id':pid,'type':'paragraph'}
        refs=p.get('claim_ids') or p.get('claims') or []
        for c in refs:
            cid=_id(c,'claim_id','id') if isinstance(c,dict) else (str(c) if c else None)
            if cid:edges.append({'src':cid,'dst':pid,'relation':'REALIZED_IN'})
    # DOM graph edges can encode derived-claim dependencies; preserve only known IDs.
    for g in dom.get('graphs') or []:
        if not isinstance(g,dict):continue
        for e in g.get('edges') or []:
            if not isinstance(e,dict):continue
            src=e.get('from') or e.get('src');dst=e.get('to') or e.get('dst');rel=e.get('relation') or 'DEPENDS_ON'
            if src and dst:edges.append({'src':str(src),'dst':str(dst),'relation':str(rel)})
    return {'ok':True,'schema':SCHEMA,'nodes':list(nodes.values()),'edges':edges}

def invalidate(graph:dict[str,Any],source_ids:list[str])->dict[str,Any]:
    adjacency={}
    for e in graph.get('edges') or []: adjacency.setdefault(str(e.get('src')),[]).append((str(e.get('dst')),str(e.get('relation'))))
    q=list(source_ids);seen=set(q);claims=set();paras=set();paths=[]
    while q:
        src=q.pop(0)
        for dst,rel in adjacency.get(src,[]):
            paths.append({'src':src,'dst':dst,'relation':rel})
            if rel=='SUPPORTS' or dst.startswith('C-'): claims.add(dst)
            if rel=='REALIZED_IN' or dst.startswith('PAR-'): paras.add(dst)
            if dst not in seen:seen.add(dst);q.append(dst)
    return {'ok':True,'schema':'writer_invalidation_plan/1.1','changed_sources':sorted(source_ids),'claims_to_revalidate':sorted(claims),'paragraphs_to_repair':sorted(paras),'dependency_paths':paths}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('dom');ap.add_argument('--changed-source',action='append',default=[]);a=ap.parse_args()
    try:
        import yaml
        p=Path(a.dom);txt=p.read_text(encoding='utf8');d=json.loads(txt) if p.suffix.lower()=='.json' else yaml.safe_load(txt)
        g=build(d);out={'graph':g}
        if a.changed_source:out['invalidation']=invalidate(g,a.changed_source)
        print(json.dumps(out,ensure_ascii=False,indent=2));return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
