#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, time, uuid
from typing import Any
SCHEMA='search_memory/1.0'

def _norm(q:str)->str: return re.sub(r'\s+',' ',q).strip().casefold()
def _db(path:str):
    c=sqlite3.connect(path); c.execute('pragma journal_mode=WAL')
    c.execute('''create table if not exists search_runs(run_id text primary key,query text,query_norm text,query_hash text,purpose text,claim_id text,stage text,created_at text)''')
    c.execute('''create table if not exists search_hits(run_id text,rank integer,source_id text,locator text,score real,disposition text,reason text,excerpt_hash text,primary key(run_id,rank))''')
    c.execute('create index if not exists idx_search_q on search_runs(query_hash)'); c.execute('create index if not exists idx_hit_source on search_hits(source_id)')
    return c

def remember(db:str, query:str, purpose:str, claim_id:str|None, stage:str, hits:list[dict[str,Any]])->dict[str,Any]:
    qn=_norm(query); qh=hashlib.sha256(qn.encode()).hexdigest(); rid='SR-'+uuid.uuid4().hex[:12]; now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); c=_db(db)
    c.execute('insert into search_runs values(?,?,?,?,?,?,?,?)',(rid,query,qn,qh,purpose,claim_id,stage,now))
    for i,h in enumerate(hits,1):
        ex=' '.join(str(h.get('excerpt') or '').split()); eh=hashlib.sha256(ex.encode()).hexdigest() if ex else None
        c.execute('insert into search_hits values(?,?,?,?,?,?,?,?)',(rid,i,h.get('source_id'),h.get('locator'),h.get('score') if h.get('score') is not None else h.get('rank'),h.get('disposition','unknown'),h.get('reason'),eh))
    c.commit(); c.close(); return {'ok':True,'schema':SCHEMA,'run_id':rid,'query_hash':qh,'hits':len(hits)}

def recall(db:str, query:str, limit:int=10)->dict[str,Any]:
    qh=hashlib.sha256(_norm(query).encode()).hexdigest(); c=_db(db); c.row_factory=sqlite3.Row
    rows=c.execute('''select r.run_id,r.query,r.purpose,r.claim_id,r.stage,r.created_at,h.rank,h.source_id,h.locator,h.score,h.disposition,h.reason from search_runs r left join search_hits h on h.run_id=r.run_id where r.query_hash=? order by r.created_at desc,h.rank asc limit ?''',(qh,limit)).fetchall(); c.close()
    return {'ok':True,'schema':SCHEMA,'query_hash':qh,'matches':[dict(x) for x in rows]}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('remember'); p.add_argument('--query',required=True); p.add_argument('--purpose',required=True); p.add_argument('--claim-id'); p.add_argument('--stage',required=True); p.add_argument('--hits-json',default='[]')
    p=sp.add_parser('recall'); p.add_argument('--query',required=True); p.add_argument('--limit',type=int,default=10)
    a=ap.parse_args()
    try:
        out=remember(a.db,a.query,a.purpose,a.claim_id,a.stage,json.loads(a.hits_json)) if a.cmd=='remember' else recall(a.db,a.query,a.limit)
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
