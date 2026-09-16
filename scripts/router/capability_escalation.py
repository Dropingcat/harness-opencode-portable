#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('bundle'); ap.add_argument('capability'); ap.add_argument('--reason',required=True); ap.add_argument('--preflight',required=True); a=ap.parse_args()
    try:
        b=json.loads(Path(a.bundle).read_text(encoding='utf-8')); pf=json.loads(Path(a.preflight).read_text(encoding='utf-8')); cap=a.capability
        if cap in set(b.get('forbidden_capabilities',[])): raise ValueError('capability_forbidden')
        if cap not in set(b.get('optional_capabilities',[]))|set(b.get('required_capabilities',[])): raise ValueError('capability_not_declared_for_stage')
        allowed_reasons=(b.get('escalation') or {}).get(cap)
        if allowed_reasons and a.reason not in allowed_reasons: raise ValueError('escalation_reason_not_allowed')
        c=pf.get('capabilities',{}).get(cap,{})
        if not c.get('available'):
            print(json.dumps({'ok':False,'decision':'DENIED','reason':'capability_unavailable','capability':cap,'status':c.get('status','missing')},ensure_ascii=False,indent=2)); return 4
        providers=c.get('providers',[])
        print(json.dumps({'ok':True,'decision':'GRANTED','capability':cap,'reason':a.reason,'provider':providers[0] if providers else None,'policy_hash':b.get('capability_policy_hash')},ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'decision':'DENIED','reason':str(e),'capability':a.capability},ensure_ascii=False,indent=2)); return 3
if __name__=='__main__': raise SystemExit(main())
