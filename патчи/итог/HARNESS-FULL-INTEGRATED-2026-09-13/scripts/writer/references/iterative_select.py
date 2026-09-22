from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from scripts.writer.references.select import select
from scripts.writer.references.enrich import enrich
SCHEMA='iterative_reference_selection/1.0'

def run(fragments:list[dict[str,Any]],*,role:str,target_kind:str|None,language:str|None,section_role:str|None,target_text:str,target_style:dict[str,Any]|None,target_graph:dict[str,Any]|None,db:str|None=None,artifact_root:str|None=None,shortlist:int=10,limit:int=4,max_per_reference:int=2)->dict[str,Any]:
    cheap=select(fragments,role=role,target_kind=target_kind,language=language,section_role=section_role,target_text=target_text,target_style=target_style,target_graph={},limit=shortlist,max_per_reference=max_per_reference)
    if role!='style' or not cheap.get('selected'):
        return {'ok':True,'schema':SCHEMA,'phase':'cheap_only','selection':cheap,'enriched':[]}
    by_id={str(f.get('fragment_id')):f for f in fragments}; enriched=[]
    for x in cheap['selected']:
        f=by_id.get(str(x.get('fragment_id')))
        if not f:continue
        er=enrich(f,db=db,artifact_root=artifact_root); art=er.get('artifact') or {}; fp=art.get('fingerprint') or {}
        f=dict(f);f['graph_digest']=fp;by_id[str(f.get('fragment_id'))]=f;enriched.append({'fragment_id':f.get('fragment_id'),'cache':er.get('cache'),'cache_key':art.get('cache_key'),'fingerprint':fp})
    candidates=[by_id[str(x.get('fragment_id'))] for x in cheap['selected'] if str(x.get('fragment_id')) in by_id]
    final=select(candidates,role=role,target_kind=target_kind,language=language,section_role=section_role,target_text=target_text,target_style=target_style,target_graph=target_graph or {},limit=limit,max_per_reference=max_per_reference)
    return {'ok':True,'schema':SCHEMA,'phase':'graph_rerank','cheap_selection':cheap,'selection':final,'enriched':enriched}

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('fragment_sets',nargs='+');ap.add_argument('--role',choices=['style','evidence'],required=True);ap.add_argument('--target-kind');ap.add_argument('--language');ap.add_argument('--section-role');ap.add_argument('--target-text',default='');ap.add_argument('--target-style-json',default='{}');ap.add_argument('--target-graph-json',default='{}');ap.add_argument('--db');ap.add_argument('--artifact-root');ap.add_argument('--shortlist',type=int,default=10);ap.add_argument('--limit',type=int,default=4);a=ap.parse_args()
 try:
  fr=[]
  for p in a.fragment_sets:fr.extend(json.loads(Path(p).read_text(encoding='utf8')).get('fragments') or [])
  out=run(fr,role=a.role,target_kind=a.target_kind,language=a.language,section_role=a.section_role,target_text=a.target_text,target_style=json.loads(a.target_style_json),target_graph=json.loads(a.target_graph_json),db=a.db,artifact_root=a.artifact_root,shortlist=a.shortlist,limit=a.limit)
  print(json.dumps(out,ensure_ascii=False,indent=2));return 0
 except Exception as e:print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
