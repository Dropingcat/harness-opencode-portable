#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any
SCHEMA='reference_selection/1.1'
_COMPAT_SCHEMA='reference_selection/1.0'

def _jacc(a:set[str],b:set[str])->float: return len(a&b)/max(1,len(a|b))
def _num_sim(a:float,b:float,scale:float)->float: return max(0.0,1.0-abs(a-b)/max(scale,abs(a),abs(b),1.0))
def _tokens(s:str)->set[str]: return {x.casefold() for x in re.findall(r'[\wγ′εαβΔ]+',s,re.U) if len(x)>2}
def _graph_sim(a:dict[str,Any],b:dict[str,Any])->float:
    if not a.get('available') or not b.get('available'): return 0.0
    ga=set(a.get('graph_ids') or []); gb=set(b.get('graph_ids') or [])
    na=set((a.get('node_types') or {}).keys()); nb=set((b.get('node_types') or {}).keys())
    ea=set((a.get('edge_relations') or {}).keys()); eb=set((b.get('edge_relations') or {}).keys())
    return round(.35*_jacc(ga,gb)+.25*_jacc(na,nb)+.40*_jacc(ea,eb),6)

def _style_authority(fragment_language:str|None,target_language:str|None)->str:
    if not target_language or not fragment_language or fragment_language in {'unknown','mixed'}:
        return 'FULL' if not target_language else 'STRUCTURE_ONLY'
    return 'FULL' if fragment_language==target_language else 'STRUCTURE_ONLY'

def select(fragments:list[dict[str,Any]], *, role:str, target_kind:str|None=None, language:str|None=None, section_role:str|None=None, target_text:str='', target_style:dict[str,Any]|None=None, target_graph:dict[str,Any]|None=None, limit:int=8, max_per_reference:int=2)->dict[str,Any]:
    if role not in {'style','evidence'}: raise ValueError('role must be style or evidence')
    ranked=[]; rejected=[]; tt=_tokens(target_text); ts=target_style or {}; tg=target_graph or ts.get('graph_digest') or {}
    for f in fragments:
        perm=f.get('permissions') or {}
        if not perm.get(role,False): rejected.append({'fragment_id':f.get('fragment_id'),'reason':'ROLE_FORBIDDEN'}); continue
        authority=None
        if role=='style':
            if target_kind and f.get('document_kind') not in {target_kind,None,'unknown'}:
                rejected.append({'fragment_id':f.get('fragment_id'),'reason':'DOCUMENT_KIND_MISMATCH'}); continue
            if section_role and f.get('section_role') != section_role:
                rejected.append({'fragment_id':f.get('fragment_id'),'reason':'SECTION_ROLE_MISMATCH'}); continue
            authority=_style_authority(str(f.get('language') or 'unknown'),language)
        sf=f.get('style_features') or {}; gd=f.get('graph_digest') or {}
        score=0.; parts={}
        if role=='evidence':
            lex=_jacc(tt,_tokens(str(f.get('excerpt') or ''))) if tt else 0.; locator=1.0 if f.get('locator') else 0.0
            parts={'lexical':round(lex,6),'locator':locator}; score=.8*lex+.2*locator
            allowed=['claim_support','exact_excerpt','locator','source_hash']
        else:
            sims=[]
            for k,scale in [('words',150),('citation_density_per_1000',15),('hedge_density_per_1000',10),('causal_density_per_1000',10)]:
                if k in ts and k in sf: sims.append(_num_sim(float(ts[k]),float(sf[k]),scale))
            style=sum(sims)/len(sims) if sims else .5; graph=_graph_sim(tg,gd) if tg else 0.0
            same_language=authority=='FULL'
            # Cross-language references are useful for argument/graph structure but
            # must not steer lexical/syntactic surface style.
            if same_language:
                parts={'style':round(style,6),'graph':graph,'language_affinity':1.0}; score=.60*style+.35*graph+.05
                allowed=['paragraph_shape','citation_density','hedging_density','causal_density','graph_motifs','argument_structure','citation_architecture','surface_rhetoric']
            else:
                structural_style=sum([
                    _num_sim(float(ts[k]),float(sf[k]),scale)
                    for k,scale in [('words',150),('citation_density_per_1000',15)] if k in ts and k in sf
                ])/max(1,len([1 for k in ('words','citation_density_per_1000') if k in ts and k in sf])) if any(k in ts and k in sf for k in ('words','citation_density_per_1000')) else .5
                parts={'structural_style':round(structural_style,6),'graph':graph,'language_affinity':0.0}; score=.40*structural_style+.60*graph
                allowed=['paragraph_architecture','citation_architecture','graph_motifs','argument_structure']
        ranked.append({'fragment_id':f.get('fragment_id'),'reference_id':f.get('reference_id'),'locator':f.get('locator'),'section_role':f.get('section_role'),'document_kind':f.get('document_kind'),'language':f.get('language'),'style_authority':authority,'score':round(score,6),'components':parts,'allowed_take':allowed,'excerpt':f.get('excerpt')})
    ranked.sort(key=lambda x:(-x['score'],0 if x.get('style_authority')=='FULL' else 1,str(x['fragment_id'])))
    selected=[]; counts={}
    for x in ranked:
        rid=str(x.get('reference_id') or '')
        if counts.get(rid,0)>=max(1,max_per_reference): continue
        selected.append(x); counts[rid]=counts.get(rid,0)+1
        if len(selected)>=max(1,limit): break
    status='READY' if selected else 'DEGRADED'
    return {'ok':True,'schema':SCHEMA,'compatible_with':[_COMPAT_SCHEMA],'status':status,'reason_code':None if selected else 'NO_REFERENCE_AFTER_HARD_FILTERS','role':role,'hard_filters':{'document_kind':target_kind,'section_role':section_role},'language_policy':'tiered_style_authority' if role=='style' else 'not_applicable','target_language':language,'selected':selected,'selected_references':sorted(counts),'rejected_count':len(rejected),'rejected':rejected[:100]}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('fragment_sets',nargs='+'); ap.add_argument('--role',choices=['style','evidence'],required=True); ap.add_argument('--target-kind'); ap.add_argument('--language'); ap.add_argument('--section-role'); ap.add_argument('--target-text',default=''); ap.add_argument('--target-style-json',default='{}'); ap.add_argument('--target-graph-json',default='{}'); ap.add_argument('--limit',type=int,default=8); ap.add_argument('--max-per-reference',type=int,default=2); a=ap.parse_args()
    try:
        fr=[]
        for p in a.fragment_sets:
            d=json.loads(Path(p).read_text(encoding='utf8')); fr.extend(d.get('fragments') or [])
        out=select(fr,role=a.role,target_kind=a.target_kind,language=a.language,section_role=a.section_role,target_text=a.target_text,target_style=json.loads(a.target_style_json),target_graph=json.loads(a.target_graph_json),limit=a.limit,max_per_reference=a.max_per_reference)
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
