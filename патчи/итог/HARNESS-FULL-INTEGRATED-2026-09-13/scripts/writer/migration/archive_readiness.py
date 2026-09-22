#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
LEGACY_NEEDLES=("scripts/writer-core", "writer-core/wc_cli.py")
HANDOFF_NEEDLES=("scripts/writer_core_handoff", "writer_core_handoff")
SCAN_ROOTS=("agents","shared","config","plugins","skills","tests","scripts")
SKIP_PARTS={".git","__pycache__","writer-core","writer_core_handoff","migration"}
ALLOW_FILES={"config/writer_migration_manifest.json"}
TEXT_SUFFIXES={".py",".md",".json",".yaml",".yml",".sh",".ps1",".ts",".js"}
MARKER=ROOT/'scripts/writer/migration/handoff_integration.json'
LEGACY_ARCHIVE=ROOT/'легаси/writer/writer-core-pre-unification'
HANDOFF_ARCHIVE=ROOT/'легаси/writer/writer_core_handoff-v0.3.0'

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def scan(needles):
    hits=[]
    for rel in SCAN_ROOTS:
        base=ROOT/rel
        if not base.exists(): continue
        files=[base] if base.is_file() else base.rglob('*')
        for p in files:
            if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES: continue
            if any(part in SKIP_PARTS for part in p.relative_to(ROOT).parts): continue
            rp=p.relative_to(ROOT).as_posix()
            if rp in ALLOW_FILES: continue
            text=p.read_text(encoding='utf-8-sig',errors='replace')
            for needle in needles:
                if needle in text: hits.append({"path":rp,"needle":needle})
    return hits

def validate_handoff_marker():
    if not MARKER.is_file(): return "FAIL", ["handoff integration marker missing"]
    try: d=json.loads(MARKER.read_text(encoding='utf-8'))
    except Exception as exc: return "FAIL", [f"handoff integration marker invalid JSON: {exc}"]
    errs=[]
    if d.get('schema')!='writer-handoff-integration/1.0': errs.append('unexpected handoff integration schema')
    if d.get('migration_id')!='WRITER-UNIFY-001': errs.append('unexpected migration id')
    if not d.get('items'): errs.append('handoff integration items empty')
    for item in d.get('items',[]):
        src_rel=item.get('source'); dst_rel=item.get('target')
        if not isinstance(src_rel,str) or not isinstance(dst_rel,str): errs.append('invalid handoff mapping'); continue
        src=ROOT/src_rel
        if not src.is_file() and HANDOFF_ARCHIVE.is_dir() and src_rel.startswith('scripts/writer_core_handoff/'):
            src=HANDOFF_ARCHIVE/src_rel.removeprefix('scripts/writer_core_handoff/')
        dst=ROOT/dst_rel
        if not src.is_file(): errs.append(f"handoff provenance source missing: {src_rel}"); continue
        if not dst.is_file(): errs.append(f"canonical handoff target missing: {dst_rel}"); continue
        hs,hd=_sha256(src),_sha256(dst)
        if hs!=item.get('source_sha256'): errs.append(f"source hash mismatch: {src_rel}")
        if hd!=item.get('target_sha256'): errs.append(f"target hash mismatch: {dst_rel}")
        if hs!=hd: errs.append(f"source/target bytes diverged: {src_rel}")
    return ("PASS" if not errs else "FAIL"), errs

def evaluate():
    legacy=scan(LEGACY_NEEDLES); handoff_refs=scan(HANDOFF_NEEDLES)
    handoff_status,handoff_errors=validate_handoff_marker()
    legacy_source=ROOT/'scripts/writer-core'; handoff_source=ROOT/'scripts/writer_core_handoff'
    legacy_archived=LEGACY_ARCHIVE.is_dir() and not legacy_source.exists()
    handoff_archived=HANDOFF_ARCHIVE.is_dir() and not handoff_source.exists()
    blockers=[]
    if legacy: blockers.append('legacy writer-core still has external/test references')
    if handoff_refs: blockers.append('writer_core_handoff still has external/test references')
    if handoff_status!='PASS': blockers.extend(handoff_errors)
    if legacy_source.exists() and LEGACY_ARCHIVE.exists(): blockers.append('legacy writer-core exists in both source and archive')
    if handoff_source.exists() and HANDOFF_ARCHIVE.exists(): blockers.append('handoff exists in both source and archive')
    if legacy_archived and handoff_archived and not blockers: archive_status='ARCHIVED'
    elif not blockers: archive_status='READY'
    else: archive_status='BLOCKED'
    return {
      'schema':'writer-archive-readiness/1.1', 'migration_id':'WRITER-UNIFY-001',
      'p6a_external_bindings':'PASS' if not legacy else 'FAIL',
      'handoff_integration':handoff_status, 'archive_status':archive_status,
      'legacy_reference_hits':legacy, 'handoff_reference_hits':handoff_refs,
      'legacy_source_present':legacy_source.exists(), 'handoff_source_present':handoff_source.exists(),
      'legacy_archive_present':LEGACY_ARCHIVE.exists(), 'handoff_archive_present':HANDOFF_ARCHIVE.exists(),
      'handoff_integration_marker':MARKER.relative_to(ROOT).as_posix(), 'blockers':blockers,
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--require-archive-ready',action='store_true'); a=ap.parse_args()
    result=evaluate(); text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.out: (ROOT/a.out).write_text(text,encoding='utf-8')
    print(text,end='')
    if a.require_archive_ready and result['archive_status'] not in {'READY','ARCHIVED'}: return 2
    return 0
if __name__=='__main__': raise SystemExit(main())
