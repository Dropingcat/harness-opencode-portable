#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from typing import Any
from scripts.capsules.corpus_fts import search as fts_search
from scripts.writer.sources.source_catalog import by_path_or_sha
from scripts.writer.sources.search_memory import remember,recall
SCHEMA='library_search/1.0'

def search(db:str,query:str,*,purpose:str,claim_id:str|None=None,limit:int=20,remember_run:bool=True)->dict[str,Any]:
    rows=fts_search(db,query,max(1,min(limit,100))); hits=[]
    for r in rows:
        src=by_path_or_sha(db,r.get('path'),r.get('sha256'))
        hits.append({'source_id':src.get('source_id') if src else None,'path':r.get('path'),'source_sha256':r.get('sha256'),'locator':r.get('locator'),'excerpt':r.get('excerpt'),'fts_rank':r.get('rank'),'catalog':{'title':src.get('title'),'doi':src.get('doi'),'document_kind':src.get('document_kind'),'language':src.get('language')} if src else None})
    previous=recall(db,query,20).get('matches') or []
    rec=None
    if remember_run:
        rec=remember(db,query,purpose,claim_id,'local-corpus',[{'source_id':h.get('source_id'),'locator':h.get('locator'),'score':h.get('fts_rank'),'excerpt':h.get('excerpt'),'disposition':'unknown'} for h in hits])
    return {'ok':True,'schema':SCHEMA,'query':query,'purpose':purpose,'claim_id':claim_id,'hits':hits,'previous_search_memory':previous,'memory_record':rec}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('query');ap.add_argument('--db',required=True);ap.add_argument('--purpose',default='general');ap.add_argument('--claim-id');ap.add_argument('--limit',type=int,default=20);ap.add_argument('--no-remember',action='store_true');a=ap.parse_args()
    try:
        print(json.dumps(search(a.db,a.query,purpose=a.purpose,claim_id=a.claim_id,limit=a.limit,remember_run=not a.no_remember),ensure_ascii=False,indent=2));return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
