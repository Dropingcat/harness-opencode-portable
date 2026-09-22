from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any
from scripts.writer.references.fragment_graph import build as build_graph,VERSION
from scripts.writer.library.derived_store import find,register
SCHEMA='reference_fragment_enrichment/1.0'

def enrich(fragment:dict[str,Any],*,db:str|None=None,artifact_root:str|None=None)->dict[str,Any]:
 sid=str(fragment.get('source_id') or '');sha=str(fragment.get('source_sha256') or '');loc=str(fragment.get('locator') or '')
 if db and sid and sha:
  cached=find(db,sid,sha,'fragment_graph',loc)
  if cached and Path(cached.get('path') or '').is_file():
   data=json.loads(Path(cached['path']).read_text(encoding='utf8'));return {'ok':True,'schema':SCHEMA,'cache':'HIT','artifact':data}
 art=build_graph(fragment)
 if db and artifact_root:
  root=Path(artifact_root)/sid/sha/'fragment_graphs';root.mkdir(parents=True,exist_ok=True);p=root/f"{fragment.get('fragment_id')}.json";p.write_text(json.dumps(art,ensure_ascii=False,indent=2),encoding='utf8');ch=hashlib.sha256(p.read_bytes()).hexdigest();register(db,{'source_id':sid,'source_sha256':sha,'kind':'fragment_graph','version':VERSION,'locator':loc,'content_hash':ch,'path':str(p),'metadata':{'fragment_id':fragment.get('fragment_id')}})
 return {'ok':True,'schema':SCHEMA,'cache':'MISS','artifact':art}

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('fragment_json');ap.add_argument('--db');ap.add_argument('--artifact-root');a=ap.parse_args()
 try:
  d=json.loads(Path(a.fragment_json).read_text(encoding='utf8'));print(json.dumps(enrich(d,db=a.db,artifact_root=a.artifact_root),ensure_ascii=False,indent=2));return 0
 except Exception as e:print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
