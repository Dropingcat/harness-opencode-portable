#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sqlite3
from pathlib import Path
TEXT_EXT={'.txt','.md','.py','.json','.jsonl','.yaml','.yml','.csv','.rst'}
DOC_EXT={'.pdf','.docx','.odt','.djvu','.djv'}

def dbopen(p):
    c=sqlite3.connect(p); c.execute('pragma journal_mode=WAL');
    c.execute('create table if not exists docs(path text primary key,sha256 text,size integer,mtime real,extractor text)')
    c.execute('create virtual table if not exists fts using fts5(path UNINDEXED, sha256 UNINDEXED, locator UNINDEXED, content)')
    return c

def iter_segments(p:Path,b:bytes):
    if p.suffix.lower() in DOC_EXT:
        try:
            from scripts.capsules import document_inspect as di
        except ModuleNotFoundError:
            import document_inspect as di
        ext=p.suffix.lower()
        if ext=='.pdf': d=di.inspect_pdf(p)
        elif ext=='.docx': d=di.inspect_docx(p)
        elif ext=='.odt': d=di.inspect_odt(p)
        else: d=di.inspect_djvu(p)
        for seg in d.get('segments') or []:
            text=str(seg.get('text') or '')
            if text.strip(): yield str(seg.get('locator') or 'segment:?'), text[:500000]
        return
    text=b.decode('utf-8','replace')
    if p.suffix.lower()=='.jsonl':
        for i,line in enumerate(text.splitlines(),1):
            try:
                j=json.loads(line); content=str(j.get('text') or j.get('content') or j.get('excerpt') or '')
                locator=json.dumps(j.get('locator') or {'line':i},ensure_ascii=False,sort_keys=True)
                if content: yield locator,content[:500000]
            except Exception: yield f'line:{i}',line[:500000]
    else:
        # stable bounded chunks; lexical search can return exact originating chunk.
        lines=text.splitlines(); step=200
        for i in range(0,len(lines),step):
            chunk='\n'.join(lines[i:i+step])
            if chunk.strip(): yield f'lines:{i+1}-{min(i+step,len(lines))}',chunk[:500000]

def index(db,root):
    c=dbopen(db); rootp=Path(root).resolve(); seen=set(); added=changed=skipped=deleted=segments=0
    for p in rootp.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in (TEXT_EXT | DOC_EXT): continue
        rp=str(p.resolve()); seen.add(rp); b=p.read_bytes(); h=hashlib.sha256(b).hexdigest(); old=c.execute('select sha256 from docs where path=?',(rp,)).fetchone()
        if old and old[0]==h: skipped+=1; continue
        c.execute('delete from fts where path=?',(rp,))
        for loc,txt in iter_segments(p,b): c.execute('insert into fts(path,sha256,locator,content) values(?,?,?,?)',(rp,h,loc,txt)); segments+=1
        c.execute('insert into docs(path,sha256,size,mtime,extractor) values(?,?,?,?,?) on conflict(path) do update set sha256=excluded.sha256,size=excluded.size,mtime=excluded.mtime,extractor=excluded.extractor',(rp,h,len(b),p.stat().st_mtime,'corpus_fts.v3+documents'))
        if old: changed+=1
        else: added+=1
    stale=[r[0] for r in c.execute('select path from docs').fetchall() if r[0].startswith(str(rootp)) and r[0] not in seen]
    for rp in stale: c.execute('delete from fts where path=?',(rp,)); c.execute('delete from docs where path=?',(rp,)); deleted+=1
    c.commit(); c.close(); return {'added':added,'changed':changed,'skipped':skipped,'deleted':deleted,'segments_written':segments}

def search(db,q,limit):
    c=dbopen(db); rows=c.execute('select path,sha256,locator,snippet(fts,3,"[","]"," … ",32),bm25(fts) from fts where fts match ? order by bm25(fts) limit ?',(q,limit)).fetchall(); c.close()
    return [{'path':a,'sha256':h,'locator':loc,'excerpt':b,'rank':r} for a,h,loc,b,r in rows]

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('index'); p.add_argument('root'); p.add_argument('--db',required=True)
    p=sub.add_parser('search'); p.add_argument('query'); p.add_argument('--db',required=True); p.add_argument('--limit',type=int,default=20)
    a=ap.parse_args()
    try:
        result=index(a.db,a.root) if a.cmd=='index' else search(a.db,a.query,max(1,min(a.limit,100)))
        print(json.dumps({'ok':True,'schema':'corpus_fts.v3','command':a.cmd,'result':result},ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':'corpus_fts.v3','error':f'{e.__class__.__name__}: {e}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
