#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, time
from pathlib import Path
from typing import Any
SCHEMA='source_catalog/1.1'

def _db(path:str):
    c=sqlite3.connect(path); c.execute('pragma journal_mode=WAL')
    c.execute('''create table if not exists source_catalog(
      source_id text primary key, path text, sha256 text not null, media_type text,
      title text, authors_json text, year integer, doi text, language text, document_kind text,
      extractor_version text, metadata_json text, created_at text, updated_at text)''')
    c.execute('''create table if not exists source_versions(
      source_id text, sha256 text, path text, first_seen_at text, metadata_json text,
      primary key(source_id,sha256))''')
    c.execute('create index if not exists idx_source_sha on source_catalog(sha256)'); c.execute('create index if not exists idx_source_path on source_catalog(path)')
    return c

def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

def upsert(db:str, source:dict[str,Any])->dict[str,Any]:
    sid=str(source.get('source_id') or ''); sha=str(source.get('sha256') or '')
    if not sid or len(sha)!=64: raise ValueError('source_id and sha256 required')
    now=_now(); c=_db(db); old=c.execute('select source_id,sha256,metadata_json from source_catalog where source_id=?',(sid,)).fetchone(); old_sha=old[1] if old else None; old_meta=json.loads(old[2] or '{}') if old else {}
    meta=json.dumps(source.get('metadata') or {},ensure_ascii=False,sort_keys=True)
    c.execute('insert or ignore into source_versions(source_id,sha256,path,first_seen_at,metadata_json) values(?,?,?,?,?)',(sid,sha,source.get('path'),now,meta))
    c.execute('''insert into source_catalog(source_id,path,sha256,media_type,title,authors_json,year,doi,language,document_kind,extractor_version,metadata_json,created_at,updated_at)
    values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    on conflict(source_id) do update set path=excluded.path,sha256=excluded.sha256,media_type=excluded.media_type,title=excluded.title,authors_json=excluded.authors_json,year=excluded.year,doi=excluded.doi,language=excluded.language,document_kind=excluded.document_kind,extractor_version=excluded.extractor_version,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at''',(
      sid,source.get('path'),sha,source.get('media_type'),source.get('title'),json.dumps(source.get('authors') or [],ensure_ascii=False),source.get('year'),source.get('doi'),source.get('language'),source.get('document_kind'),source.get('extractor_version'),meta,now if not old else None,now))
    new_meta=source.get('metadata') or {}; old_norm=old_meta.get('normalized_text_hash'); new_norm=new_meta.get('normalized_text_hash'); byte_changed=bool(old_sha and old_sha!=sha); semantic_changed=byte_changed if not (old_norm and new_norm) else old_norm!=new_norm
    c.commit(); c.close(); return {'ok':True,'schema':SCHEMA,'source_id':sid,'change':'updated' if old else 'added','old_sha256':old_sha,'sha256':sha,'content_changed':byte_changed,'semantic_changed':semantic_changed,'change_class':'SEMANTIC' if semantic_changed else ('BYTE_ONLY' if byte_changed else 'UNCHANGED')}

def get(db:str,sid:str)->dict[str,Any]|None:
    c=_db(db); c.row_factory=sqlite3.Row; r=c.execute('select * from source_catalog where source_id=?',(sid,)).fetchone(); c.close()
    if not r:return None
    d=dict(r); d['authors']=json.loads(d.pop('authors_json') or '[]'); d['metadata']=json.loads(d.pop('metadata_json') or '{}'); return d

def by_path_or_sha(db:str,path:str|None,sha:str|None)->dict[str,Any]|None:
    c=_db(db); c.row_factory=sqlite3.Row; r=None
    if sha: r=c.execute('select * from source_catalog where sha256=? order by updated_at desc limit 1',(sha,)).fetchone()
    if not r and path: r=c.execute('select * from source_catalog where path=? order by updated_at desc limit 1',(path,)).fetchone()
    c.close()
    if not r:return None
    d=dict(r); d['authors']=json.loads(d.pop('authors_json') or '[]'); d['metadata']=json.loads(d.pop('metadata_json') or '{}'); return d

def versions(db:str,sid:str)->list[dict[str,Any]]:
    c=_db(db); c.row_factory=sqlite3.Row; rows=c.execute('select * from source_versions where source_id=? order by first_seen_at',(sid,)).fetchall(); c.close(); return [dict(x) for x in rows]
def list_sources(db:str)->list[dict[str,Any]]:
    c=_db(db); c.row_factory=sqlite3.Row; rows=c.execute('select source_id,path,sha256,media_type,title,year,doi,language,document_kind,updated_at from source_catalog order by source_id').fetchall(); c.close(); return [dict(x) for x in rows]

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('upsert'); p.add_argument('json_file'); p=sp.add_parser('get'); p.add_argument('source_id'); p=sp.add_parser('versions'); p.add_argument('source_id'); sp.add_parser('list')
    a=ap.parse_args()
    try:
        if a.cmd=='upsert':out=upsert(a.db,json.loads(Path(a.json_file).read_text(encoding='utf8')))
        elif a.cmd=='get':out={'ok':True,'schema':SCHEMA,'source':get(a.db,a.source_id)}
        elif a.cmd=='versions':out={'ok':True,'schema':SCHEMA,'versions':versions(a.db,a.source_id)}
        else:out={'ok':True,'schema':SCHEMA,'sources':list_sources(a.db)}
        print(json.dumps(out,ensure_ascii=False,indent=2));return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
