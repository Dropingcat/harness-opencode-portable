#!/usr/bin/env python3
"""Phase-3 historical behavioral/cost comparison for canonical and archived extractor trees.

This migration diagnostic launches each backend in an isolated Python process. After
P6C the v2 input is read only from the immutable legacy archive; it is never runtime
authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "writer_extractor_phase3" / "fixtures.json"

BACKENDS = {
    "writer": ROOT / "scripts" / "writer" / "extractor",
    "v2": ROOT / "легаси" / "writer" / "writer-core-pre-unification" / "v2_extractor",
}

_WORKER = r'''
import dataclasses, json, os, sys, time
from pathlib import Path
backend = sys.argv[1]
backend_dir = Path(sys.argv[2]).resolve()
fixture_path = Path(sys.argv[3]).resolve()
sys.path.insert(0, str(backend_dir.parent if backend == "writer" else backend_dir))
t0=time.perf_counter()
if backend == "writer":
    import extractor as pkg
    claim_qa = pkg
    extract_all = pkg.extract_all
else:
    import claim_qa
    from extraction_engine import extract_all
import_ms=(time.perf_counter()-t0)*1000
fixtures=json.load(open(fixture_path, encoding="utf-8"))["cases"]
out=[]
run_t0=time.perf_counter()
for case in fixtures:
    loc=claim_qa.span_locate(case["claim"], case["source"])
    cls=claim_qa.classify_claim(case["claim"])
    verdicts, kept=claim_qa.qa_claims([{"text": case["claim"]}], case["source"])
    r=extract_all(case["source"], case["para_id"])
    if dataclasses.is_dataclass(r):
        r=dataclasses.asdict(r)
    v=verdicts[0]
    if dataclasses.is_dataclass(v):
        v=dataclasses.asdict(v)
    out.append({
      "id":case["id"], "span":loc, "classification":cls,
      "qa":{"status":v.get("status"),"grounded":v.get("grounded"),"reason":v.get("reason","")},
      "extract":r,
    })
run_ms=(time.perf_counter()-run_t0)*1000
third_party=[]
for name, mod in list(sys.modules.items()):
    path=getattr(mod, "__file__", None)
    if path and "site-packages" in str(path):
        third_party.append(name.split(".")[0])
print(json.dumps({"backend":backend,"import_ms":round(import_ms,6),"run_ms":round(run_ms,6),
                  "loaded_third_party":sorted(set(third_party)),"cases":out},ensure_ascii=False,sort_keys=True))
'''


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_hashes(root: Path) -> dict[str, str]:
    return {p.name: sha256(p) for p in sorted(root.glob("*.py"))}


def run_backend(name: str, fixtures: Path = FIXTURES) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-c", _WORKER, name, str(BACKENDS[name]), str(fixtures)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{name} failed rc={proc.returncode}: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    data["source_hashes"] = source_hashes(BACKENDS[name])
    return data


def stable_view(data: dict[str, Any]) -> dict[str, Any]:
    return {"backend": data["backend"], "cases": data["cases"], "source_hashes": data["source_hashes"]}


def dependency_probe(name: str, repeats: int = 5) -> dict[str, Any]:
    times=[]
    run_times=[]
    loaded=set()
    for _ in range(repeats):
        d=run_backend(name)
        times.append(float(d["import_ms"]))
        run_times.append(float(d["run_ms"]))
        loaded.update(d.get("loaded_third_party", []))
    modules = set()
    for p in BACKENDS[name].glob("*.py"):
        txt=p.read_text(encoding="utf-8", errors="replace")
        for line in txt.splitlines():
            s=line.strip()
            if s.startswith("import "):
                modules.add(s.split()[1].split(".")[0])
            elif s.startswith("from "):
                modules.add(s.split()[1].split(".")[0])
    nonstdlib=[]
    for mod in sorted(modules):
        if mod.startswith(".") or mod in {"__future__"}:
            continue
        try:
            spec=importlib.util.find_spec(mod)
        except Exception:
            spec=None
        if spec and spec.origin and "site-packages" in spec.origin:
            nonstdlib.append(mod)
    return {
        "import_ms_median": round(statistics.median(times), 4),
        "import_ms_samples": [round(x,4) for x in times],
        "fixture_run_ms_median": round(statistics.median(run_times), 4),
        "fixture_run_ms_samples": [round(x,4) for x in run_times],
        "loaded_third_party": sorted(loaded),
        "python_files": len(list(BACKENDS[name].glob("*.py"))),
        "nonstdlib_static_imports": nonstdlib,
    }


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    ac={x["id"]:x for x in a["cases"]}; bc={x["id"]:x for x in b["cases"]}
    diffs=[]
    for cid in sorted(set(ac)|set(bc)):
        if ac.get(cid) != bc.get(cid):
            fields=[]
            aa=ac.get(cid,{}); bb=bc.get(cid,{})
            for key in ("span","classification","qa","extract"):
                if aa.get(key) != bb.get(key): fields.append(key)
            diffs.append({"id":cid,"fields":fields,"writer":aa,"v2":bb})
    return {"case_count":len(ac),"equal_cases":len(ac)-len(diffs),"different_cases":len(diffs),"differences":diffs}


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    ap.add_argument("--freeze-baseline", type=Path)
    ap.add_argument("--cost", action="store_true")
    args=ap.parse_args()
    writer=run_backend("writer"); v2=run_backend("v2")
    report={
      "schema":"writer-extractor-experiment/1.0",
      "fixtures_sha256":sha256(FIXTURES),
      "writer":stable_view(writer), "v2":stable_view(v2),
      "comparison":compare(stable_view(writer),stable_view(v2)),
    }
    if args.cost:
        report["cost"]={"writer":dependency_probe("writer"),"v2":dependency_probe("v2")}
    text=json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(text,encoding="utf-8")
    else: print(text,end="")
    if args.freeze_baseline:
        args.freeze_baseline.parent.mkdir(parents=True,exist_ok=True); args.freeze_baseline.write_text(text,encoding="utf-8")
    return 0
if __name__ == "__main__": raise SystemExit(main())
