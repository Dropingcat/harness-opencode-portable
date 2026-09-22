from __future__ import annotations
import hashlib,json
from typing import Any
SCHEMA='writing_policy/1.0'
_DEFAULT={
 'introduction':(['BACKGROUND','LITERATURE_STATE','RESEARCH_GAP'],['NEW_EXPERIMENTAL_FACT','UNSUPPORTED_CAUSALITY']),
 'literature_review':(['LITERATURE_SYNTHESIS','COMPARISON','RESEARCH_GAP'],['NEW_EXPERIMENTAL_FACT','UNSUPPORTED_CAUSALITY']),
 'methods':(['METHOD_DESCRIPTION','PARAMETER_DESCRIPTION'],['UNSUPPORTED_CAUSALITY','LITERATURE_GENERALIZATION']),
 'results':(['OBSERVATION','MEASUREMENT','RESULT_STATEMENT'],['UNSUPPORTED_CAUSALITY','NEW_EXTERNAL_FACT']),
 'discussion':(['RESULT_INTERPRETATION','LITERATURE_COMPARISON','QUALIFIED_CAUSAL_HYPOTHESIS'],['NEW_EXPERIMENTAL_FACT','UNQUALIFIED_CAUSALITY']),
 'conclusion':(['SUPPORTED_SYNTHESIS','RESULT_SUMMARY'],['NEW_FACT','NEW_CAUSALITY']),
 'body':(['AUTHORIZED_CLAIM'],['NEW_FACT','UNSUPPORTED_CAUSALITY']),
}

def build(object_decision:dict[str,Any],section_role:str,style_selection:dict[str,Any],*,target_language:str|None=None)->dict[str,Any]:
    if object_decision.get('schema')!='writing_object_decision/1.0':raise ValueError('writing_object_decision/1.0 required')
    if style_selection.get('schema') not in {'reference_selection/1.0','reference_selection/1.1'}:raise ValueError('reference_selection/1.x required')
    allow,forbid=_DEFAULT.get(section_role,_DEFAULT['body'])
    sel=style_selection.get('selected') or []
    cits=[(x.get('components') or {}).get('style') for x in sel if (x.get('components') or {}).get('style') is not None]
    payload={'document_kind':object_decision.get('kind'),'section_role':section_role,'language':target_language or object_decision.get('language'),'allowed_claim_classes':allow,'forbidden_claim_classes':forbid,'style_reference_fragment_ids':[x.get('fragment_id') for x in sel], 'style_authority':{'full':[x.get('fragment_id') for x in sel if x.get('style_authority','FULL')=='FULL'],'structure_only':[x.get('fragment_id') for x in sel if x.get('style_authority')=='STRUCTURE_ONLY']}, 'constraints':{'style_refs_are_not_evidence':True,'new_facts_require_research_debt':True,'causality_must_preserve_authorized_strength':True,'citation_required_for_external_fact':True},'style_targets':{'reference_count':len(sel),'style_similarity_mean':round(sum(cits)/len(cits),4) if cits else None}}
    h=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'ok':True,'schema':SCHEMA,'policy_id':'WP-'+h[:16],**payload,'content_hash':h}

if __name__=='__main__':
 import argparse
 from pathlib import Path
 ap=argparse.ArgumentParser();ap.add_argument('--object',required=True);ap.add_argument('--style-selection',required=True);ap.add_argument('--section-role',required=True);ap.add_argument('--language');a=ap.parse_args()
 load=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
 print(json.dumps(build(load(a.object),a.section_role,load(a.style_selection),target_language=a.language),ensure_ascii=False,indent=2))
