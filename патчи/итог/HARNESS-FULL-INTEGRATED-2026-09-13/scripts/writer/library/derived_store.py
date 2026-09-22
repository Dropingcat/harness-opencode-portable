from __future__ import annotations
import argparse,hashlib,json,sqlite3,time
from pathlib import Path
from typing import Any
SCHEMA='derived_artifact_store/1.0'

def _db(path:str):
 c=sqlite3.connect(path);c.execute('pragma journal_mode=WAL');c.execute('''create table if not exists derived_artifacts(artifact_id text primary key,source_id text,source_sha256 text,kind text,version text,locator text,content_hash text,path text,metadata_json text,created_at text)''');c.execute('create index if not exists idx_derived_source on derived_artifacts(source_id,source_sha256,kind)');return c

def register(db:str,record:dict[str,Any])->dict[str,Any]:
 required=['source_id','source_sha256','kind','version','content_hash'];
 for k in required:
  if not record.get(k):raise ValueError(f'{k} required')
 aid=record.get('artifact_id') or 'ART-'+hashlib.sha256(json.dumps({k:record.get(k) for k in required+['locator']},sort_keys=True).encode()).hexdigest()[:16]
 now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());c=_db(db);c.execute('insert or replace into derived_artifacts values(?,?,?,?,?,?,?,?,?,?)',(aid,record['source_id'],record['source_sha256'],record['kind'],record['version'],record.get('locator'),record['content_hash'],record.get('path'),json.dumps(record.get('metadata') or {},ensure_ascii=False,sort_keys=True),now));c.commit();c.close();return {'ok':True,'schema':SCHEMA,'artifact_id':aid}

def find(db:str,source_id:str,source_sha256:str,kind:str,locator:str|None=None)->dict[str,Any]|None:
 c=_db(db);c.row_factory=sqlite3.Row;q='select * from derived_artifacts where source_id=? and source_sha256=? and kind=?';args=[source_id,source_sha256,kind]
 if locator is not None:q+=' and locator=?';args.append(locator)
 q+=' order by created_at desc limit 1';r=c.execute(q,args).fetchone();c.close();
 if not r:return None
 d=dict(r);d['metadata']=json.loads(d.pop('metadata_json') or '{}');return d

def list_for_source(db:str,source_id:str,source_sha256:str|None=None)->list[dict[str,Any]]:
 c=_db(db);c.row_factory=sqlite3.Row
 if source_sha256:rows=c.execute('select * from derived_artifacts where source_id=? and source_sha256=? order by kind,locator,created_at',(source_id,source_sha256)).fetchall()
 else:rows=c.execute('select * from derived_artifacts where source_id=? order by source_sha256,kind,locator,created_at',(source_id,)).fetchall()
 c.close();out=[]
 for r in rows:
  d=dict(r);d['metadata']=json.loads(d.pop('metadata_json') or '{}');out.append(d)
 return out
