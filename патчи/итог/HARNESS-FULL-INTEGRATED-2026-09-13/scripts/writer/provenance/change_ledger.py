#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any
try: import yaml
except ImportError: yaml=None
SCHEMA='writer_change_ledger/1.1'

def load(p:Path)->dict[str,Any]:
 text=p.read_text(encoding='utf-8')
 if p.suffix.lower()=='.json':return json.loads(text)
 if yaml is None:raise RuntimeError('PyYAML required for YAML DOM')
 d=yaml.safe_load(text) or {}
 if not isinstance(d,dict):raise ValueError('DOM must be mapping')
 return d

def sha_obj(x:Any)->str:return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def _eid(x:dict,*keys):
 for k in keys:
  if x.get(k):return str(x[k])
 return None

def _paragraphs(dom:dict):
 for p in dom.get('paragraphs') or []:
  if isinstance(p,dict):yield p,'paragraphs'
 for ci,ch in enumerate((dom.get('structure') or {}).get('chapters') or []):
  if not isinstance(ch,dict):continue
  for si,sec in enumerate(ch.get('sections') or []):
   if not isinstance(sec,dict):continue
   for pi,p in enumerate(sec.get('paragraphs') or []):
    if isinstance(p,dict):yield p,f'structure.chapters[{ci}].sections[{si}].paragraphs[{pi}]'

def _index_dom(dom:dict,coll:str):
 out={}
 if coll=='paragraphs':
  for x,path in _paragraphs(dom):
   i=_eid(x,'paragraph_id','id')
   if i:out[i]={'value':x,'path':path}
  return out
 keys={'claims':('claim_id','id'),'sources':('source_id','id')}[coll]
 for x in dom.get(coll) or []:
  if isinstance(x,dict):
   i=_eid(x,*keys)
   if i:out[i]={'value':x,'path':coll}
 return out

def diff(old:dict,new:dict)->dict[str,Any]:
 changes=[]
 for coll in ('claims','sources','paragraphs'):
  a=_index_dom(old,coll);b=_index_dom(new,coll)
  for i in sorted(a.keys()-b.keys()):changes.append({'entity':coll,'id':i,'change':'removed','before':a[i]['value'],'before_path':a[i]['path']})
  for i in sorted(b.keys()-a.keys()):changes.append({'entity':coll,'id':i,'change':'added','after':b[i]['value'],'after_path':b[i]['path']})
  for i in sorted(a.keys()&b.keys()):
   av,bv=a[i]['value'],b[i]['value']
   if av!=bv or a[i]['path']!=b[i]['path']:
    fields=sorted(set(av)|set(bv));changed=[f for f in fields if av.get(f)!=bv.get(f)]
    changes.append({'entity':coll,'id':i,'change':'modified','fields':changed,'before':av,'after':bv,'before_path':a[i]['path'],'after_path':b[i]['path']})
 touched_claims=sorted({c['id'] for c in changes if c['entity']=='claims'})
 touched_paragraphs=sorted({c['id'] for c in changes if c['entity']=='paragraphs'})
 touched_sources=sorted({c['id'] for c in changes if c['entity']=='sources'})
 # Paragraph claim/source links make dependency impact explicit even when claim object did not change.
 for c in changes:
  if c['entity']=='paragraphs':
   for side in ('before','after'):
    p=c.get(side) or {}
    for cid in p.get('claims') or p.get('claim_ids') or []:
     if isinstance(cid,str):touched_claims.append(cid)
    for sid in p.get('evidence_refs') or []:
     if isinstance(sid,str):touched_sources.append(sid)
 return {'changes':changes,'touched_claims':sorted(set(touched_claims)),'touched_paragraphs':touched_paragraphs,'touched_sources':sorted(set(touched_sources))}

def build(old:dict,new:dict)->dict[str,Any]:return {'ok':True,'schema':SCHEMA,'old':{'sha256':sha_obj(old)},'new':{'sha256':sha_obj(new)},**diff(old,new)}

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('old');ap.add_argument('new');a=ap.parse_args();po,pn=Path(a.old),Path(a.new);old,new=load(po),load(pn);out={'ok':True,'schema':SCHEMA,'old':{'path':str(po),'sha256':sha(po)},'new':{'path':str(pn),'sha256':sha(pn)},**diff(old,new)};print(json.dumps(out,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
