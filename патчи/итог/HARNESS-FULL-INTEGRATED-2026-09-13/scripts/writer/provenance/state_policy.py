from __future__ import annotations
from typing import Any
SCHEMA='claim_state_transition/1.1'

def apply_invalidation(dom:dict[str,Any],invalidation:dict[str,Any])->dict[str,Any]:
    affected=set(invalidation.get('claims_to_revalidate') or []); changed=[]
    for c in dom.get('claims') or []:
        cid=str(c.get('id') or c.get('claim_id') or '')
        if cid not in affected:continue
        ver=c.setdefault('verification',{})
        evidence_verdict=str(ver.get('evidence_verdict') or ver.get('verdict') or 'OPEN')
        old_claim_state=str(c.get('state') or evidence_verdict)
        evidence=c.get('evidence') or c.get('evidence_refs') or []
        # Operational claim state is distinct from evidence verdict and epistemic state.
        if evidence_verdict=='SUPPORTED' and len(evidence)>=2:
            new_claim_state='SUPPORTED_WITH_STALE_EVIDENCE'
            new_verification_state='VERIFIED'
            epistemic=ver.get('epistemic_state') or 'ESTABLISHED'
        else:
            new_claim_state='PENDING_REVALIDATION'
            new_verification_state='UNCHECKED'
            epistemic='UNKNOWN'
        c['state']=new_claim_state
        ver['previous_claim_state']=old_claim_state
        ver['verification_state']=new_verification_state
        ver['epistemic_state']=epistemic
        ver['evidence_verdict']=evidence_verdict
        # Compatibility field for older consumers; never use it as evidence authority.
        ver['verdict']=new_claim_state
        ver['invalidation_sources']=invalidation.get('changed_sources') or []
        changed.append({'claim_id':cid,'from':old_claim_state,'to':new_claim_state,'evidence_verdict':evidence_verdict,'verification_state':new_verification_state,'epistemic_state':epistemic})
    return {'ok':True,'schema':SCHEMA,'transitions':changed,'dom':dom}
