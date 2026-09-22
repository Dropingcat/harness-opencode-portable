from __future__ import annotations
import copy,hashlib,json
from typing import Any
SCHEMA='writer_dom_patch/1.0'

def _hash_obj(x:Any)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def _paragraph_refs(dom:dict):
    st=dom.get('structure') or {}
    for ch in st.get('chapters') or []:
        for sec in (ch.get('sections') or []) if isinstance(ch,dict) else []:
            for p in (sec.get('paragraphs') or []) if isinstance(sec,dict) else []:
                if isinstance(p,dict):yield p

def build_patch(dom:dict[str,Any],draft:dict[str,Any])->dict[str,Any]:
    ops=[]; idx={str(p.get('id')):p for p in _paragraph_refs(dom) if p.get('id')}
    for dp in draft.get('paragraphs') or []:
        target=dp.get('target_paragraph_id')
        if target:
            old=idx.get(str(target))
            if old is None:raise ValueError(f'target paragraph missing: {target}')
            ops.append({'operation':'replace_paragraph','target':target,'expected_hash':_hash_obj(old),'new_paragraph':{'id':target,'text':dp.get('text'),'claims':dp.get('realizes_claims') or [],'evidence_refs':dp.get('evidence_refs') or [],'style_instruction_id':dp.get('style_instruction_id')}})
        else:
            ops.append({'operation':'append_paragraph','target_section_role':None,'new_paragraph':{'id':dp.get('temp_id'),'text':dp.get('text'),'claims':dp.get('realizes_claims') or [],'evidence_refs':dp.get('evidence_refs') or [],'style_instruction_id':dp.get('style_instruction_id')}})
    return {'ok':True,'schema':SCHEMA,'base_dom_hash':_hash_obj(dom),'operations':ops}

def apply(dom:dict[str,Any],patch:dict[str,Any])->dict[str,Any]:
    if _hash_obj(dom)!=patch.get('base_dom_hash'):return {'ok':False,'schema':'writer_dom_patch_apply/1.0','reason_code':'PATCH_CONFLICT_BASE_DOM'}
    out=copy.deepcopy(dom); idx={str(p.get('id')):p for p in _paragraph_refs(out) if p.get('id')}
    for op in patch.get('operations') or []:
        if op.get('operation')=='replace_paragraph':
            p=idx.get(str(op.get('target')))
            if p is None:return {'ok':False,'schema':'writer_dom_patch_apply/1.0','reason_code':'PATCH_TARGET_MISSING','target':op.get('target')}
            if _hash_obj(p)!=op.get('expected_hash'):return {'ok':False,'schema':'writer_dom_patch_apply/1.0','reason_code':'PATCH_CONFLICT_PARAGRAPH','target':op.get('target')}
            p.clear();p.update(copy.deepcopy(op.get('new_paragraph') or {}))
        elif op.get('operation')=='append_paragraph':
            sections=[sec for ch in (out.get('structure') or {}).get('chapters') or [] for sec in (ch.get('sections') or []) if isinstance(sec,dict)]
            if not sections:return {'ok':False,'schema':'writer_dom_patch_apply/1.0','reason_code':'NO_SECTION_FOR_APPEND'}
            sections[-1].setdefault('paragraphs',[]).append(copy.deepcopy(op.get('new_paragraph') or {}))
        else:return {'ok':False,'schema':'writer_dom_patch_apply/1.0','reason_code':'UNKNOWN_PATCH_OPERATION'}
    return {'ok':True,'schema':'writer_dom_patch_apply/1.0','dom':out,'new_dom_hash':_hash_obj(out)}

if __name__=='__main__':
 import argparse
 from pathlib import Path
 import yaml
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True);p=sp.add_parser('build');p.add_argument('--dom',required=True);p.add_argument('--draft',required=True);p=sp.add_parser('apply');p.add_argument('--dom',required=True);p.add_argument('--patch',required=True);p.add_argument('--out');a=ap.parse_args()
 def ldom(p):
  q=Path(p);t=q.read_text(encoding='utf8');return json.loads(t) if q.suffix.lower()=='.json' else yaml.safe_load(t)
 if a.cmd=='build':res=build_patch(ldom(a.dom),json.loads(Path(a.draft).read_text(encoding='utf8')))
 else:
  res=apply(ldom(a.dom),json.loads(Path(a.patch).read_text(encoding='utf8')))
  if res.get('ok') and a.out:Path(a.out).write_text(yaml.safe_dump(res['dom'],allow_unicode=True,sort_keys=False),encoding='utf8')
 print(json.dumps({k:v for k,v in res.items() if k!='dom'},ensure_ascii=False,indent=2))
