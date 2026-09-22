from __future__ import annotations
import hashlib,json
from typing import Any
SCHEMA='reference_profile/1.1'

def build(bundle:dict[str,Any],fragment_set:dict[str,Any],fragment_graphs:list[dict[str,Any]]|None=None)->dict[str,Any]:
 if bundle.get('schema')!='reference_bundle/1.0':raise ValueError('reference_bundle/1.0 required')
 fr=fragment_set.get('fragments') or []
 gf={str(x.get('fragment_id')):x.get('fingerprint') for x in fragment_graphs or [] if x.get('ok')}
 payload={'reference_id':bundle.get('reference_id'),'source':bundle.get('source'),'profile':bundle.get('profile'),'permissions':bundle.get('permissions'),'fragment_count':len(fr),'section_roles':{},'languages':{},'fragment_graphs':{k:v for k,v in gf.items()}}
 for f in fr:
  payload['section_roles'][f.get('section_role')]=payload['section_roles'].get(f.get('section_role'),0)+1
  payload['languages'][f.get('language')]=payload['languages'].get(f.get('language'),0)+1
 h=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 return {'ok':True,'schema':SCHEMA,'profile_id':'RP-'+h[:16],**payload,'content_hash':h}
