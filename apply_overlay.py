#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path

def hashf(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main()->int:
    ap=argparse.ArgumentParser(description='Install capability bundle overlay into an OpenCode harness')
    ap.add_argument('harness_root'); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--no-compile',action='store_true'); a=ap.parse_args()
    src=Path(__file__).resolve().parent; dst=Path(a.harness_root).resolve()
    if not (dst/'config/runtime_snapshot.json').exists() or not (dst/'scripts/router/resolve_route.py').exists():
        print(json.dumps({'ok':False,'error':'target does not look like expected harness'},indent=2)); return 2
    files=[]
    for top in ('config','scripts'):
        for p in (src/top).rglob('*'):
            if p.is_file(): files.append(p)
    backup=dst/'.overlay_backups'/time.strftime('%Y%m%d-%H%M%S')
    plan=[]
    for p in files:
        rel=p.relative_to(src); q=dst/rel; plan.append({'path':str(rel),'exists':q.exists(),'source_sha256':hashf(p),'target_sha256':hashf(q) if q.exists() else None})
    if a.dry_run:
        print(json.dumps({'ok':True,'dry_run':True,'files':plan},ensure_ascii=False,indent=2)); return 0
    for p in files:
        rel=p.relative_to(src); q=dst/rel
        if q.exists():
            b=backup/rel; b.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(q,b)
        q.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,q)
    commands=[]
    if not a.no_compile:
        for rel in ('scripts/router/compile_capability_runtime.py',):
            cp=subprocess.run([sys.executable,str(dst/rel)],cwd=dst,text=True,capture_output=True)
            commands.append({'command':rel,'exit_code':cp.returncode,'stdout':cp.stdout[-4000:],'stderr':cp.stderr[-4000:]})
            if cp.returncode!=0:
                print(json.dumps({'ok':False,'backup':str(backup),'commands':commands},ensure_ascii=False,indent=2)); return cp.returncode
    print(json.dumps({'ok':True,'installed':len(files),'backup':str(backup) if backup.exists() else None,'commands':commands},ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
