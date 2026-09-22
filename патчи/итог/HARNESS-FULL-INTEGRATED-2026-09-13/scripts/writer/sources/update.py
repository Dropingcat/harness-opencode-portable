#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from scripts.writer.sources.source_catalog import upsert
from scripts.writer.provenance.dependency_graph import build,invalidate
SCHEMA='source_update/1.0'

def update(db:str,dom:dict[str,Any],source_record:dict[str,Any])->dict[str,Any]:
    cat=upsert(db,source_record); sid=cat['source_id']
    inv=invalidate(build(dom),[sid]) if cat.get('semantic_changed') else {'ok':True,'schema':'writer_invalidation_plan/1.1','changed_sources':[],'claims_to_revalidate':[],'paragraphs_to_repair':[],'dependency_paths':[]}
    return {'ok':True,'schema':SCHEMA,'source_id':sid,'catalog_update':cat,'invalidation':inv,'requires_revalidation':bool(inv.get('claims_to_revalidate'))}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--dom',required=True);ap.add_argument('--source-json',required=True);a=ap.parse_args()
    try:
        import yaml
        dp=Path(a.dom);txt=dp.read_text(encoding='utf8');dom=json.loads(txt) if dp.suffix.lower()=='.json' else yaml.safe_load(txt)
        src=json.loads(Path(a.source_json).read_text(encoding='utf8'));out=update(a.db,dom,src)
        print(json.dumps(out,ensure_ascii=False,indent=2));return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
