from __future__ import annotations
import hashlib, json
from typing import Any
SCHEMA='proposed_claim/1.0'
_ALLOWED={'SYNTHESIS','INTERPRETATION','EXTERNAL_FACT','CAUSAL_HYPOTHESIS','COMPARISON','UNKNOWN'}

def build(*,text:str,paragraph_id:str|None=None,span:dict[str,Any]|None=None,claim_type:str='UNKNOWN',reason:str='UNAUTHORIZED_DRAFT_PROPOSITION',evidence_refs:list[str]|None=None,derived_from:list[str]|None=None)->dict[str,Any]:
    text=' '.join(str(text or '').split()).strip()
    if not text: raise ValueError('proposed claim text required')
    typ=claim_type if claim_type in _ALLOWED else 'UNKNOWN'
    payload={'text':text,'paragraph_id':paragraph_id,'span':span,'claim_type':typ,'reason':reason,'evidence_refs':list(evidence_refs or []),'derived_from':list(derived_from or [])}
    h=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return {'schema':SCHEMA,'proposed_claim_id':'PC-'+h[:16],**payload,'content_hash':h,'requires_registration':True}

def normalize(raw:dict[str,Any],*,paragraph_id:str|None=None)->dict[str,Any]:
    if raw.get('schema')==SCHEMA and raw.get('proposed_claim_id'):
        return dict(raw)
    return build(text=str(raw.get('text') or raw.get('proposition') or ''),paragraph_id=raw.get('paragraph_id') or paragraph_id,span=raw.get('span'),claim_type=str(raw.get('claim_type') or raw.get('type') or 'UNKNOWN'),reason=str(raw.get('reason') or 'UNAUTHORIZED_DRAFT_PROPOSITION'),evidence_refs=list(raw.get('evidence_refs') or []),derived_from=list(raw.get('derived_from') or []))
