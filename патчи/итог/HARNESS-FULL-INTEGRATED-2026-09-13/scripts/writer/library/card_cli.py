from __future__ import annotations
import argparse,json
from pathlib import Path
from scripts.writer.library.document_card import build,write
from scripts.writer.library.derived_store import list_for_source
SCHEMA='document_card_cli/1.0'
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--inspection',required=True);ap.add_argument('--source',required=True);ap.add_argument('--fragments');ap.add_argument('--derived');ap.add_argument('--derived-db');ap.add_argument('--out-root');a=ap.parse_args();load=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
 try:
  src=load(a.source); drv=load(a.derived) if a.derived else {};
  if a.derived_db: drv={**drv,'registered_artifacts':list_for_source(a.derived_db,str(src.get('source_id')),str(src.get('sha256') or load(a.inspection).get('sha256')))}
  card=build(inspection=load(a.inspection),source_record=src,fragment_set=load(a.fragments) if a.fragments else None,derived=drv)
  if a.out_root:card['path']=write(card,a.out_root)
  print(json.dumps(card,ensure_ascii=False,indent=2));return 0
 except Exception as e:print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
