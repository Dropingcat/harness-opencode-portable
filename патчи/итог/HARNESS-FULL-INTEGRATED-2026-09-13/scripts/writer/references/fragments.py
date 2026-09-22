#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any
from scripts.writer.references.graph_profile import digest as graph_digest
from scripts.writer.references.language import detect as detect_language

SCHEMA='reference_fragment_set/1.0'
ROLE_MAP=[
 ('introduction',re.compile(r'\b(?:introduction|введение|актуальност)\b',re.I)),
 ('methods',re.compile(r'\b(?:experimental|methods?|materials?|методик|материал|оборудован)\b',re.I)),
 ('results',re.compile(r'\b(?:results?|результат|исследовани[ея])\b',re.I)),
 ('discussion',re.compile(r'\b(?:discussion|обсужден|анализ|механизм)\b',re.I)),
 ('conclusion',re.compile(r'\b(?:conclusions?|summary|заключен|вывод)\b',re.I)),
 ('literature_review',re.compile(r'\b(?:state of (?:the )?art|literature|references|современн.*состояни|обзор|литератур)\b',re.I)),
]
CITE=re.compile(r'(?:\[[0-9,\-– ]+\]|\([A-ZА-ЯЁ][A-Za-zА-Яа-яЁё-]+\s+et\s+al\.,?\s*\d{4}\))')
HEDGE=re.compile(r'\b(?:may|might|could|suggests?|approximately|about|likely|possible|вероятно|возможно|примерно|около|может)\b',re.I)
CAUSAL=re.compile(r'\b(?:because|therefore|thus|hence|leads? to|results? in|causes?|поскольку|поэтому|приводит к|обусловлен|вследствие)\b',re.I)

def _section_role(text:str)->str:
    for role,rx in ROLE_MAP:
        if rx.search(text): return role
    return 'body'

def _paragraphs(text:str):
    # preserve offsets, tolerate PDF line wrapping; blank lines preferred, then sentence groups.
    spans=[]
    for m in re.finditer(r'(?ms)(?:^|\n\s*\n)([^\n].*?)(?=\n\s*\n|\Z)',text):
        raw=m.group(1).strip(); start=m.start(1)+(len(m.group(1))-len(m.group(1).lstrip())); end=start+len(raw)
        if len(raw)>=80: spans.append((start,end,raw))
    if spans: return spans
    # PDF text layers often have no blank paragraphs.
    chunks=[]; start=0
    for m in re.finditer(r'(?<=[.!?])\s+(?=[A-ZА-ЯЁ])',text):
        if m.end()-start>300:
            raw=text[start:m.start()].strip(); s=start+len(text[start:m.start()])-len(text[start:m.start()].lstrip())
            if len(raw)>=80: chunks.append((s,s+len(raw),raw))
            start=m.end()
    raw=text[start:].strip()
    if len(raw)>=80:
        s=start+len(text[start:])-len(text[start:].lstrip()); chunks.append((s,s+len(raw),raw))
    return chunks

def build(inspection:dict[str,Any], bundle:dict[str,Any], graph_artifact:dict[str,Any]|None=None, max_fragments:int=500)->dict[str,Any]:
    if inspection.get('schema')!='document_inspection.v1' or not inspection.get('ok'): raise ValueError('successful document inspection required')
    if bundle.get('schema')!='reference_bundle/1.0': raise ValueError('reference_bundle/1.0 required')
    gd=graph_digest(graph_artifact); out=[]; current_role='body'; rid=bundle['reference_id']
    for seg in inspection.get('segments') or []:
        text=str(seg.get('text') or ''); loc=str(seg.get('locator') or '')
        # infer role from heading-like lines in current segment, then local paragraph content
        lines=[x.strip() for x in text.splitlines() if x.strip()]
        if lines:
            r=_section_role(' '.join(lines[:8]));
            if r!='body': current_role=r
        for start,end,raw in _paragraphs(text):
            role=_section_role(raw[:300]); role=current_role if role=='body' else role
            words=max(1,len(re.findall(r'\w+',raw,re.U)))
            norm=' '.join(raw.split())
            fid='RF-'+hashlib.sha256(f'{rid}|{loc}|{start}|{norm}'.encode()).hexdigest()[:16]
            out.append({'fragment_id':fid,'reference_id':rid,'source_id':bundle.get('source',{}).get('source_id') or rid,
                        'source_sha256':bundle.get('source',{}).get('sha256'),'locator':loc,
                        'span':{'coordinate_space':'segment_text','start':start,'end':end},
                        'normalized_text_hash':hashlib.sha256(norm.casefold().encode()).hexdigest(),
                        'section_role':role,'document_kind':(bundle.get('profile') or {}).get('document_kind'),'language':detect_language(raw).get('language') if detect_language(raw).get('language')!='unknown' else (bundle.get('profile') or {}).get('language'),'permissions':bundle.get('permissions') or {},
                        'style_features':{'words':words,'citation_density_per_1000':round(1000*len(CITE.findall(raw))/words,3),'hedge_density_per_1000':round(1000*len(HEDGE.findall(raw))/words,3),'causal_density_per_1000':round(1000*len(CAUSAL.findall(raw))/words,3)},
                        'graph_digest':gd,'excerpt':raw[:1200]})
            if len(out)>=max_fragments: break
        if len(out)>=max_fragments: break
    return {'ok':True,'schema':SCHEMA,'reference_id':rid,'count':len(out),'fragments':out,'graph_digest':gd}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('inspection'); ap.add_argument('bundle'); ap.add_argument('--graph-artifact'); ap.add_argument('--max-fragments',type=int,default=500); a=ap.parse_args()
    try:
        ins=json.loads(Path(a.inspection).read_text(encoding='utf8')); bun=json.loads(Path(a.bundle).read_text(encoding='utf8')); g=json.loads(Path(a.graph_artifact).read_text(encoding='utf8')) if a.graph_artifact else None
        print(json.dumps(build(ins,bun,g,a.max_fragments),ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
