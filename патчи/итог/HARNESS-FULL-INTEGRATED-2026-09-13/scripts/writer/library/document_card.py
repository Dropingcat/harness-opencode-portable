from __future__ import annotations
import hashlib,json,time
from pathlib import Path
from typing import Any
SCHEMA='document_card/1.0'

def build(*,inspection:dict[str,Any],source_record:dict[str,Any],fragment_set:dict[str,Any]|None=None,derived:dict[str,Any]|None=None)->dict[str,Any]:
    if inspection.get('schema')!='document_inspection.v1' or not inspection.get('ok'):raise ValueError('successful document inspection required')
    sid=source_record.get('source_id'); sha=inspection.get('sha256')
    if not sid or not sha:raise ValueError('source_id and sha256 required')
    fr=fragment_set or {}; drv=derived or {}
    payload={
      'source_id':sid,'source_sha256':sha,
      'identity':{k:source_record.get(k) for k in ('title','authors','year','doi','language','document_kind','media_type')},
      'inspection':{'kind':inspection.get('kind'),'size_bytes':inspection.get('size_bytes'),'page_count':inspection.get('page_count'),'extractor_version':source_record.get('extractor_version') or inspection.get('schema'),'warnings':inspection.get('warnings') or []},
      'fragments':{'schema':fr.get('schema'),'count':fr.get('count',0),'artifact_id':drv.get('fragment_index_artifact')},
      'derived_artifacts':drv,
      'profile_state':'enriched' if drv else 'base',
    }
    hid=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return {'ok':True,'schema':SCHEMA,'card_id':'DC-'+hid[:16],'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**payload,'content_hash':hid}

def write(card:dict[str,Any],root:str)->str:
    p=Path(root)/str(card['source_id'])/str(card['source_sha256']);p.mkdir(parents=True,exist_ok=True);f=p/'document_card.json';f.write_text(json.dumps(card,ensure_ascii=False,indent=2),encoding='utf8');return str(f)
