from __future__ import annotations
import hashlib,json,statistics
from typing import Any
SCHEMA='style_instruction_artifact/1.1'

def build(selection:dict[str,Any], fragments_by_id:dict[str,dict[str,Any]], policy:dict[str,Any])->dict[str,Any]:
    if selection.get('role')!='style':raise ValueError('style selection required')
    rows=[]
    for s in selection.get('selected') or []:
        f=fragments_by_id.get(str(s.get('fragment_id')))
        if not f:continue
        sf=f.get('style_features') or {}; gd=f.get('graph_digest') or {}
        rows.append({'fragment_id':f.get('fragment_id'),'section_role':f.get('section_role'),'authority':s.get('style_authority') or 'FULL','words':sf.get('words'),'citation_density':sf.get('citation_density_per_1000'),'hedge_density':sf.get('hedge_density_per_1000'),'causal_density':sf.get('causal_density_per_1000'),'graph_ids':gd.get('graph_ids') or [],'edge_relations':list((gd.get('edge_relations') or {}).keys())[:12]})
    def med(k,rows_):
        vals=[float(x[k]) for x in rows_ if x.get(k) is not None];return round(statistics.median(vals),3) if vals else None
    full=[x for x in rows if x.get('authority')=='FULL']
    structural=rows
    instr={
      'section_role':policy.get('section_role'),
      'paragraph_words_target':med('words',structural),
      'citation_density_target':med('citation_density',structural),
      'hedging_target':med('hedge_density',full),
      'causal_density_target':med('causal_density',full),
      'preferred_argument_patterns':sorted({r for x in structural for r in x.get('edge_relations') or []})[:16],
      'architecture_hint':'OBSERVATION → COMPARISON → INTERPRETATION → LIMITATION' if policy.get('section_role')=='discussion' else 'CLAIM → SUPPORT → QUALIFIER',
      'cross_language_policy':'STRUCTURE_ONLY',
      'surface_style_requires_same_language':True,
      'prohibitions':['do not copy lexical wording from references','do not import reference claims as facts','preserve authorized claim modality and causal strength','do not transfer cross-language syntax or lexical style']
    }
    h=hashlib.sha256(json.dumps(instr,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'ok':True,'schema':SCHEMA,'compatible_with':['style_instruction_artifact/1.0'],'style_instruction_id':'SI-'+h[:16],
            'source_fragment_ids':[x['fragment_id'] for x in rows],
            'surface_style_source_fragment_ids':[x['fragment_id'] for x in full],
            'structure_only_source_fragment_ids':[x['fragment_id'] for x in rows if x.get('authority')!='FULL'],
            'instructions':instr,'content_hash':h}

if __name__=='__main__':
 import argparse
 from pathlib import Path
 ap=argparse.ArgumentParser();ap.add_argument('--selection',required=True);ap.add_argument('--fragments',nargs='+',required=True);ap.add_argument('--policy',required=True);a=ap.parse_args()
 load=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
 fmap={}
 for p in a.fragments:
  d=load(p)
  for f in d.get('fragments') or []:fmap[str(f.get('fragment_id'))]=f
 print(json.dumps(build(load(a.selection),fmap,load(a.policy)),ensure_ascii=False,indent=2))
