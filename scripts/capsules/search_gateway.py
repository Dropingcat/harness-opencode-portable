#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, time
from pathlib import Path
from urllib.parse import urlparse
import requests

def norm_query(q): return ' '.join(q.split()).strip()
def cache_key(q,base,max_results): return hashlib.sha256(json.dumps([q,base,max_results],separators=(',',':')).encode()).hexdigest()
def dbopen(path):
    c=sqlite3.connect(path); c.execute('create table if not exists cache(k text primary key, created real, payload text)'); return c

def normalize(q,j,max_results):
    out=[]; seen=set()
    for r in j.get('results',[]):
        url=(r.get('url') or '').strip(); title=(r.get('title') or '').strip();
        if not url or url in seen: continue
        seen.add(url)
        out.append({'title':title,'url':url,'engine':r.get('engine') or ','.join(r.get('engines',[]) or []),'snippet':(r.get('content') or r.get('snippet') or '')[:1500],'rank':len(out)+1,'discovery_only':True})
        if len(out)>=max_results: break
    return {'schema':'search-discovery/1.0','query_id':'SEARCH-'+hashlib.sha1(q.encode()).hexdigest()[:10],'backend':'searxng','query':q,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'results':out}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('query'); ap.add_argument('--base-url',default=os.environ.get('SEARXNG_URL','http://127.0.0.1:8888')); ap.add_argument('--max-results',type=int,default=20); ap.add_argument('--timeout',type=float,default=8); ap.add_argument('--cache'); ap.add_argument('--offline-fixture')
    a=ap.parse_args(); q=norm_query(a.query); maxr=max(1,min(a.max_results,50)); base=a.base_url.rstrip('/'); key=cache_key(q,base,maxr)
    try:
        if a.cache:
            c=dbopen(a.cache); row=c.execute('select payload from cache where k=?',(key,)).fetchone()
            if row: print(row[0]); return 0
        if a.offline_fixture: j=json.loads(Path(a.offline_fixture).read_text(encoding='utf-8'))
        else:
            u=urlparse(base)
            if u.hostname not in {'127.0.0.1','localhost','::1'} and os.environ.get('ALLOW_REMOTE_SEARXNG')!='1': raise ValueError('remote SearXNG blocked by default')
            r=requests.get(base+'/search',params={'q':q,'format':'json'},timeout=a.timeout); r.raise_for_status(); j=r.json()
        out=normalize(q,j,maxr); text=json.dumps({'ok':True,**out},ensure_ascii=False,indent=2)
        if a.cache:
            c.execute('insert or replace into cache(k,created,payload) values(?,?,?)',(key,time.time(),text)); c.commit(); c.close()
        print(text); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':'search-discovery/1.0','query':q,'error_code':'SEARCH_BACKEND_UNAVAILABLE','error':f'{e.__class__.__name__}: {e}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
