from __future__ import annotations
import hashlib,json
from typing import Any
SCHEMA='repair_request/1.0'

def build(dom:dict[str,Any],invalidation:dict[str,Any],style_instruction_by_paragraph:dict[str,Any]|None=None)->dict[str,Any]:
    wanted=set(invalidation.get('paragraphs_to_repair') or []); paras=[]
    for ch in (dom.get('structure') or {}).get('chapters') or []:
        for sec in (ch.get('sections') or []) if isinstance(ch,dict) else []:
            for p in (sec.get('paragraphs') or []) if isinstance(sec,dict) else []:
                if isinstance(p,dict) and str(p.get('id')) in wanted:paras.append({'paragraph_id':p.get('id'),'old_text':p.get('text'),'claims':p.get('claims') or [],'style_instruction':(style_instruction_by_paragraph or {}).get(str(p.get('id')))})
    payload={'affected_claims':invalidation.get('claims_to_revalidate') or [],'paragraphs':paras,'changed_sources':invalidation.get('changed_sources') or []}
    h=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'ok':True,'schema':SCHEMA,'repair_request_id':'RR-'+h[:16],**payload,'constraints':{'repair_only_affected_paragraphs':True,'preserve_unaffected_claims':True,'requires_revalidated_evidence_before_release':True}}

if __name__=='__main__':
 import argparse
 from pathlib import Path
 import yaml
 ap=argparse.ArgumentParser();ap.add_argument('--dom',required=True);ap.add_argument('--invalidation',required=True);a=ap.parse_args();p=Path(a.dom);t=p.read_text(encoding='utf8');dom=json.loads(t) if p.suffix.lower()=='.json' else yaml.safe_load(t);inv=json.loads(Path(a.invalidation).read_text(encoding='utf8'));print(json.dumps(build(dom,inv),ensure_ascii=False,indent=2))
