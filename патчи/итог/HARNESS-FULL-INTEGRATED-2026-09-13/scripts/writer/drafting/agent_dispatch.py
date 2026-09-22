from __future__ import annotations
import hashlib,json
from typing import Any
SCHEMA='writer_agent_dispatch_contract/1.0'
ROLE_MAP={'dissertation':'article-writer','article':'article-writer','report':'article-writer','unknown':'article-writer'}
def build(request:dict[str,Any])->dict[str,Any]:
 if request.get('schema')!='draft_request/1.0':raise ValueError('draft_request/1.0 required')
 kind=str((request.get('object') or {}).get('kind') or 'unknown');agent=ROLE_MAP.get(kind,'article-writer')
 payload={'agent_role':agent,'request_id':request.get('request_id'),'section_role':request.get('section_role'),'authorized_claim_ids':[c.get('id') or c.get('claim_id') for c in request.get('authorized_claims') or [] if isinstance(c,dict)],'style_instruction_id':(request.get('style_instruction') or {}).get('style_instruction_id'),'writer_may_search_web':False,'required_output_schema':'draft_artifact/1.1','required_claim_mapping':['realizes_claims','proposed_claims'],'claim_authority':'authorized_claims only; new claims must be proposed, never silently asserted'}
 h=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 return {'ok':True,'schema':SCHEMA,'dispatch_id':'WD-'+h[:16],**payload,'backend_names_exposed':False}

if __name__=='__main__':
 import argparse
 from pathlib import Path
 ap=argparse.ArgumentParser();ap.add_argument('--request',required=True);a=ap.parse_args();print(json.dumps(build(json.loads(Path(a.request).read_text(encoding='utf8'))),ensure_ascii=False,indent=2))
