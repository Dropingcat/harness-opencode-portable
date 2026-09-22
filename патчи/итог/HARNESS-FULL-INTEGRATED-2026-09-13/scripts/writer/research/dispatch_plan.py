#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from scripts.router.resolve_bundle import resolve_bundle
from scripts.writer.sources.library_search import search as library_search
SCHEMA='research_dispatch_contract/1.0'
VALID_RESEARCH_STAGES={'discovery','source-resolution','document-analysis','evidence-validation','synthesis'}

def dispatch(plan:dict[str,Any],claim:dict[str,Any],*,corpus_db:str|None=None)->dict[str,Any]:
    if plan.get('schema')!='validation_plan/1.0':raise ValueError('validation_plan/1.0 required')
    entry=plan.get('entry_stage'); local=None
    if entry=='local-corpus':
        if corpus_db:
            local=library_search(corpus_db,str(claim.get('text') or ''),purpose='claim-evidence',claim_id=claim.get('claim_id'),limit=12,remember_run=True)
            entry='document-analysis' if local.get('hits') else 'discovery'
        else:
            entry='discovery'
    if entry not in VALID_RESEARCH_STAGES:raise ValueError(f'unsupported researcher stage: {entry}')
    task=f"Validate claim {claim.get('claim_id') or ''}: {claim.get('text') or ''}"
    bundle=resolve_bundle(task,route_id='academic-research',stage=entry)
    return {'ok':bool(bundle.get('ok')),'schema':SCHEMA,'claim_id':claim.get('claim_id'),'requested_entry_stage':plan.get('entry_stage'),'research_stage':entry,'local_corpus_result':local,
            'route':{'route_id':bundle.get('route_id'),'stage':bundle.get('stage'),'bundle_state':bundle.get('bundle_state'),'logical_tools':bundle.get('logical_tools') or [],'required_capabilities':bundle.get('required_capabilities') or [],'optional_capabilities':bundle.get('optional_capabilities') or [],'forbidden_capabilities':bundle.get('forbidden_capabilities') or []},
            'backend_names_exposed_to_writer':False,'writer_may_execute_web_discovery':False}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--claim',required=True);ap.add_argument('--corpus-db');a=ap.parse_args()
    try:
        load=lambda p:json.loads(Path(p).read_text(encoding='utf8'));out=dispatch(load(a.plan),load(a.claim),corpus_db=a.corpus_db);print(json.dumps(out,ensure_ascii=False,indent=2));return 0 if out.get('ok') else 4
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
