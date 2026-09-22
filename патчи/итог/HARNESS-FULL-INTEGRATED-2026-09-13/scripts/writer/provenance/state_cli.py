from __future__ import annotations
import argparse,json
from pathlib import Path
from scripts.writer.provenance.state_policy import apply_invalidation
SCHEMA='claim_state_cli/1.0'
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--dom',required=True);ap.add_argument('--invalidation',required=True);ap.add_argument('--out');a=ap.parse_args()
 try:
  import yaml
  p=Path(a.dom);txt=p.read_text(encoding='utf8');dom=json.loads(txt) if p.suffix.lower()=='.json' else yaml.safe_load(txt);inv=json.loads(Path(a.invalidation).read_text(encoding='utf8'));out=apply_invalidation(dom,inv)
  if a.out:Path(a.out).write_text(yaml.safe_dump(out['dom'],allow_unicode=True,sort_keys=False),encoding='utf8')
  print(json.dumps({k:v for k,v in out.items() if k!='dom'},ensure_ascii=False,indent=2));return 0
 except Exception as e:print(json.dumps({'ok':False,'schema':SCHEMA,'error':f'{type(e).__name__}: {e}'},ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
