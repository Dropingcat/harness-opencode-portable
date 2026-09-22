#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path
from typing import Any,Iterable
SCHEMA='evidence_span/1.1'

def _norm_with_map(text:str)->tuple[str,list[int]]:
    out=[];pos=[];in_ws=False
    for i,ch in enumerate(text):
        if ch.isspace():
            if out and not in_ws:out.append(' ');pos.append(i)
            in_ws=True
        else:out.append(ch);pos.append(i);in_ws=False
    left=0
    while left<len(out) and out[left]==' ':left+=1
    right=len(out)
    while right>left and out[right-1]==' ':right-=1
    return ''.join(out[left:right]),pos[left:right]

def _pseudo_segments(inspection:dict[str,Any])->Iterable[dict[str,Any]]:
    for s in inspection.get('segments') or []:
        if isinstance(s,dict) and str(s.get('text') or '').strip():yield s
    for t in inspection.get('tables') or []:
        loc=str(t.get('locator') or 'table:?')
        for ri,row in enumerate(t.get('rows') or [],1):
            text='\t'.join(str(x or '') for x in row)
            if text.strip():yield {'locator':f'{loc}/row:{ri}','text':text}
    for sh in inspection.get('sheets') or []:
        name=str(sh.get('sheet') or '?')
        for c in sh.get('cells') or []:
            val=c.get('value'); val=c.get('formula') if val is None else val
            if val is not None:yield {'locator':f'sheet:{name}/cell:{c.get("cell")}', 'text':str(val)}

def _known_locators(inspection:dict[str,Any])->set[str]:
    out={str(s.get('locator')) for s in _pseudo_segments(inspection) if s.get('locator')}
    for f in inspection.get('frames') or []:
        if isinstance(f,dict) and f.get('frame') is not None:out.add(f'frame:{f.get("frame")}')
    for t in inspection.get('tables') or []:
        if isinstance(t,dict) and t.get('locator'):out.add(str(t['locator']))
    for sh in inspection.get('sheets') or []:
        if not isinstance(sh,dict):continue
        name=str(sh.get('sheet') or '?')
        for c in sh.get('cells') or []:
            if isinstance(c,dict) and c.get('cell'):out.add(f'sheet:{name}/cell:{c.get("cell")}')
    return out

def _base(inspection:dict[str,Any],source_id:str,locator:str)->dict[str,Any]:
    page=None;m=re.search(r'(?:pdf|djvu)_page:(\d+)',locator)
    if m:page=int(m.group(1))
    return {'source_id':source_id,'source_sha256':inspection.get('sha256'),'source_path':inspection.get('path'),'media_type':inspection.get('kind'),'locator':locator,'page':page,'extractor_version':f"{inspection.get('schema')}:{inspection.get('kind')}"}

def build_span(inspection:dict[str,Any],source_id:str,needle:str,*,preferred_locator:str|None=None)->dict[str,Any]:
    if inspection.get('schema')!='document_inspection.v1' or not inspection.get('ok'):raise ValueError('successful document_inspection.v1 required')
    q=' '.join(str(needle or '').split())
    if not q:raise ValueError('needle must be non-empty')
    qn=q.casefold(); candidates=[]
    for s in _pseudo_segments(inspection):
        loc=str(s.get('locator') or '')
        if preferred_locator and loc!=preferred_locator:continue
        raw=str(s.get('text') or '');norm,mapping=_norm_with_map(raw);idx=norm.casefold().find(qn)
        if idx<0:continue
        end_idx=idx+len(qn)-1
        if idx>=len(mapping) or end_idx>=len(mapping):continue
        start=mapping[idx];end=mapping[end_idx]+1;candidates.append((loc,start,end,raw[start:end]))
    if not candidates:return {'ok':False,'schema':SCHEMA,'mode':'text_span','source_id':source_id,'reason_code':'SPAN_NOT_FOUND','needle':q}
    loc,start,end,excerpt=candidates[0];norm_excerpt=' '.join(excerpt.split())
    return {'ok':True,'schema':SCHEMA,'mode':'text_span',**_base(inspection,source_id,loc),'span':{'coordinate_space':'segment_text','start':start,'end':end},'normalized_text_hash':hashlib.sha256(norm_excerpt.casefold().encode()).hexdigest(),'excerpt':excerpt,'matches':len(candidates),'ambiguous':len(candidates)>1 and preferred_locator is None}

def build_locator(inspection:dict[str,Any],source_id:str,locator:str,description:str='')->dict[str,Any]:
    if inspection.get('schema')!='document_inspection.v1' or not inspection.get('ok'):raise ValueError('successful document_inspection.v1 required')
    loc=str(locator or '').strip()
    if not loc:raise ValueError('locator required')
    known=_known_locators(inspection)
    if loc not in known:return {'ok':False,'schema':SCHEMA,'mode':'artifact_locator','source_id':source_id,'locator':loc,'reason_code':'LOCATOR_NOT_FOUND'}
    desc=' '.join(str(description or '').split())
    return {'ok':True,'schema':SCHEMA,'mode':'artifact_locator',**_base(inspection,source_id,loc),'span':None,'normalized_text_hash':hashlib.sha256(desc.casefold().encode()).hexdigest() if desc else None,'excerpt':description or None,'ambiguous':False}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('inspection');ap.add_argument('--source-id',required=True);ap.add_argument('--text');ap.add_argument('--locator');ap.add_argument('--description',default='');a=ap.parse_args()
    try:
        d=json.loads(Path(a.inspection).read_text(encoding='utf8'))
        if a.text:out=build_span(d,a.source_id,a.text,preferred_locator=a.locator)
        elif a.locator:out=build_locator(d,a.source_id,a.locator,a.description)
        else:raise ValueError('either --text or --locator required')
        print(json.dumps(out,ensure_ascii=False,indent=2));return 0 if out.get('ok') else 4
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
