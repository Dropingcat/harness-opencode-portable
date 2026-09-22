from __future__ import annotations
import re
from typing import Any
SCHEMA='writer_realization_authority/1.0'
_C=re.compile(r'\[(C-[0-9A-Za-z._:-]+)\]')

def _paragraphs(dom:dict[str,Any]):
    for ch in (dom.get('structure') or {}).get('chapters') or []:
        if not isinstance(ch,dict):continue
        for sec in ch.get('sections') or []:
            if not isinstance(sec,dict):continue
            for p in sec.get('paragraphs') or []:
                if isinstance(p,dict):yield p

def resolve(dom:dict[str,Any],rendered_text:str)->dict[str,Any]:
    registry={str(c.get('id')) for c in dom.get('claims') or [] if isinstance(c,dict) and c.get('id')}
    dom_ids=set(); paragraph_bindings=[]
    for p in _paragraphs(dom):
        ids={str(x) for x in p.get('claims') or [] if x}
        if ids:
            dom_ids.update(ids);paragraph_bindings.append({'paragraph_id':p.get('id'),'claim_ids':sorted(ids)})
    marker_ids=set(_C.findall(rendered_text or ''))
    if dom_ids:
        authority_ids=dom_ids; source='DOM_PARAGRAPH_CLAIMS'
        missing_markers=sorted(dom_ids-marker_ids); extra_markers=sorted(marker_ids-dom_ids)
        unknown_dom=sorted(dom_ids-registry); unknown_markers=sorted(marker_ids-registry)
        verdict='PASS' if not (missing_markers or extra_markers or unknown_dom or unknown_markers) else 'FAIL'
    else:
        authority_ids=marker_ids; source='RENDERED_MARKERS_COMPAT'
        missing_markers=[]; extra_markers=[]; unknown_dom=[];unknown_markers=sorted(marker_ids-registry)
        verdict='PASS' if not unknown_markers else 'FAIL'
    return {'schema':SCHEMA,'verdict':verdict,'authority_source':source,'realized_claim_ids':sorted(authority_ids),'marker_claim_ids':sorted(marker_ids),'dom_claim_ids':sorted(dom_ids),'paragraph_bindings':paragraph_bindings,'missing_markers':missing_markers,'extra_markers':extra_markers,'unknown_dom_claim_ids':unknown_dom,'unknown_marker_claim_ids':unknown_markers,'principle':'DraftArtifact→DOM paragraph.claims is authority; rendered [C-*] markers are a checked projection.'}
