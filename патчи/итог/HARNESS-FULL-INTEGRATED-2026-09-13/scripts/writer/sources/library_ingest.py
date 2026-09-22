#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, re
from pathlib import Path
from scripts.capsules.corpus_fts import index as fts_index
from scripts.writer.sources.source_catalog import upsert
from scripts.writer.planning.object_router import decide
SCHEMA='library_ingest/1.1'
CYR=re.compile(r'[А-Яа-яЁё]')
LAT=re.compile(r'[A-Za-z]')
SUPPORTED={'.txt','.md','.json','.jsonl','.yaml','.yml','.csv','.rst','.pdf','.docx','.odt','.djvu','.djv'}

def _sid(root:Path,p:Path)->str:
    rel=p.resolve().relative_to(root.resolve()) if p.resolve().is_relative_to(root.resolve()) else p.resolve()
    return 'SRC-'+hashlib.sha256(str(rel).casefold().encode('utf8')).hexdigest()[:16]

def ingest(root:str,db:str)->dict:
    rp=Path(root).expanduser().resolve(); results=[]
    if not rp.is_dir(): raise ValueError('library root must be directory')
    # FTS indexes content once; source catalog records identity/version separately.
    fts=fts_index(db,str(rp))
    for p in sorted(x for x in rp.rglob('*') if x.is_file() and x.suffix.lower() in SUPPORTED):
        cp=subprocess.run([sys.executable,'scripts/capsules/document_inspect.py',str(p)],capture_output=True,text=True,cwd=str(Path(__file__).resolve().parents[3]))
        try: ins=json.loads(cp.stdout)
        except Exception: results.append({'path':str(p),'ok':False,'reason':'INSPECTION_OUTPUT_INVALID'}); continue
        if not ins.get('ok'):
            results.append({'path':str(p),'ok':False,'reason':'INSPECTION_FAILED','error':ins.get('error'),'warnings':ins.get('warnings')}); continue
        sid=_sid(rp,p)
        sample='\n'.join(str(x.get('text') or '') for x in (ins.get('segments') or [])[:20])[:50000]
        cyr=len(CYR.findall(sample)); lat=len(LAT.findall(sample)); language='ru' if cyr>lat*1.3 else ('en_or_de' if lat>cyr*1.3 else 'mixed')
        od=decide(sample); document_kind=od.get('kind')
        r=upsert(db,{'source_id':sid,'sha256':ins['sha256'],'path':str(p.resolve()),'media_type':ins.get('kind'),'title':p.stem,'language':language,'document_kind':document_kind,'extractor_version':'document_inspection.v1','metadata':{'warnings':ins.get('warnings') or [],'page_count':ins.get('page_count'),'profile_state':'base_only','kind_confidence':od.get('confidence')}})
        results.append({'path':str(p),'ok':True,'source_id':sid,'catalog_change':r['change'],'content_changed':r['content_changed'],'language':language,'document_kind':document_kind,'warnings':ins.get('warnings') or []})
    return {'ok':True,'schema':SCHEMA,'root':str(rp),'fts':fts,'files':results,'indexed':sum(1 for x in results if x.get('ok')),'failed':sum(1 for x in results if not x.get('ok'))}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('--db',required=True);a=ap.parse_args()
    try: print(json.dumps(ingest(a.root,a.db),ensure_ascii=False,indent=2));return 0
    except Exception as e: print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
