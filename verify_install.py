#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

def run(root,argv,env=None,timeout=60):
    e=os.environ.copy(); e['OPENCODE_HARNESS_ROOT']=str(root); e.update(env or {})
    cp=subprocess.run([sys.executable,*map(str,argv)],cwd=root,text=True,capture_output=True,env=e,timeout=timeout)
    return {'argv':[str(x) for x in argv],'exit_code':cp.returncode,'stdout':cp.stdout[-6000:],'stderr':cp.stderr[-6000:]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('harness_root'); ap.add_argument('--output'); a=ap.parse_args(); root=Path(a.harness_root).resolve(); checks=[]
    checks.append(run(root,[root/'scripts/router/compile_runtime.py','--check']))
    checks.append(run(root,[root/'scripts/router/compile_capability_runtime.py','--check']))
    checks.append(run(root,[root/'scripts/router/capability_preflight.py','--no-network']))
    checks.append(run(root,['-m','compileall','-q',root/'scripts']))
    ok=all(x['exit_code']==0 for x in checks)
    out={'ok':ok,'schema':'capability-bundle-install-check/1.0','harness_root':str(root),'checks':checks}
    text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(text+'\n',encoding='utf-8')
    print(text); return 0 if ok else 2
if __name__=='__main__': raise SystemExit(main())
