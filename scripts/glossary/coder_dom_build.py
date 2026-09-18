#!/usr/bin/env python3
"""Build ``coder_dom.yaml`` for the Coder DOM capsule.

Combines (as importable, independent modules):
  - gen_api_index.scan_tree   -> structure (functions/classes per contour/module)
  - call_graph.scan_call_graph -> CALLS edges
  - stub_detect.scan_stubs    -> stub/interface status per function

Output: canonical YAML mirroring Writer DOM: product + structure + graphs
(G-call, G-import, G-stub, G-ownership) + uncertainty. Deterministic, JCS-like
stable ordering (sorted keys) so that a verify-gate ``git diff --exit-code``
stays stable across runs.

Uses PyYAML if available; otherwise falls back to a plain-text YAML emitter
(universal, no dependency).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import call_graph as cg
import gen_api_index as gai
import stub_detect as sd

SCHEMA = "coder-dom/1.0"


def _fallback_yaml(data: Any, indent: int = 0) -> str:
    """Minimal deterministic YAML emitter (no PyYAML dependency)."""
    pad = "  " * indent
    if isinstance(data, dict):
        if not data:
            return pad + "{}\n"
        lines = []
        for k in sorted(data.keys()):
            v = data[k]
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}:\n" + _fallback_yaml(v, indent + 1).rstrip("\n") + "\n")
            else:
                lines.append(f"{pad}{k}: {json.dumps(v, ensure_ascii=False)}\n")
        return "".join(lines)
    if isinstance(data, list):
        if not data:
            return pad + "[]\n"
        lines = []
        for v in data:
            if isinstance(v, (dict, list)):
                # inline for small lists
                lines.append(pad + "- " + json.dumps(v, ensure_ascii=False) + "\n")
            else:
                lines.append(pad + "- " + json.dumps(v, ensure_ascii=False) + "\n")
        return "".join(lines)
    return pad + json.dumps(data, ensure_ascii=False) + "\n"


def build_coder_dom(root: str | Path, include_tests: bool = False) -> dict[str, Any]:
    root_path = Path(root if isinstance(root, str) else root)
    registry = gai.scan_tree(root_path, label="coder", include_tests=include_tests)
    graph = cg.scan_call_graph(root_path, include_tests=include_tests)
    stubs = sd.scan_stubs(root_path, include_tests=include_tests)

    # node status lookup: qname -> stub/interface/normal
    status_by_qname: dict[str, str] = {}
    for s in stubs["stubs"]:
        key = f"{s['module']}:{s['name']}"
        status_by_qname[key] = "stub"
    for s in stubs["interfaces"]:
        key = f"{s['module']}:{s['name']}"
        status_by_qname[key] = "interface"

    structure: list[dict[str, Any]] = []
    for contour in registry["contours"]:
        modules = []
        for mod in contour["modules"]:
            funcs = []
            for fn in mod["functions"]:
                qname = f"{mod['path']}:{fn['name']}"
                funcs.append({
                    "id": f"F-{abs(hash(qname)) % 100000:05d}",
                    "name": fn["name"],
                    "signature": fn["signature"],
                    "contour": contour["id"],
                    "status": status_by_qname.get(qname, "done"),
                    "doc": fn["doc"],
                })
            modules.append({"path": mod["path"], "functions": funcs})
        structure.append({"id": contour["id"], "modules": modules})

    edges = graph["edges"]
    # G-call: edges as list of {src,dst,confidence}
    g_call = [{"src": e["src"], "dst": e["dst"], "confidence": e["confidence"]} for e in edges]

    # fingerprint: canonical JSON of stable parts (exclude generated_at)
    fp_source = {
        "schema": SCHEMA,
        "structure": structure,
        "g_call": g_call,
        "stubs": stubs["counts"],
    }
    fingerprint = hashlib.sha256(
        json.dumps(fp_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return {
        "schema": SCHEMA,
        "product": {"id": "CDOM-001", "kind": "code", "status": "drafted",
                    "contours": [c["id"] for c in registry["contours"]]},
        "structure": {"contours": structure},
        "graphs": {
            "G-call": {"node_types": ["function"], "edge_types": ["CALLS"], "edges": g_call},
            "G-import": {"node_types": ["module"], "edge_types": ["IMPORTS"], "edges": []},
            "G-stub": {"node_types": ["function"], "edge_types": ["STUB", "INTERFACE"],
                       "counts": stubs["counts"]},
            "G-ownership": {"node_types": ["function"], "edge_types": ["OWNED_BY"]},
        },
        "counts": {
            "functions": registry["meta"]["counts"]["functions"],
            "classes": registry["meta"]["counts"]["classes"],
            "call_edges": len(g_call),
            "stubs": stubs["counts"]["stubs"],
            "interfaces": stubs["counts"]["interfaces"],
        },
        "generated_at": None,  # excluded from fingerprint (FASTEN pattern)
        "fingerprint": f"sha256:{fingerprint}",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build coder_dom.yaml.")
    ap.add_argument("--root", default=r"E:\Documents\Документы\doc_Opencode_agern-new")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    data = build_coder_dom(args.root)
    out = Path(args.out) if args.out else Path(args.root) / "docs/glossary/coder_dom.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        import yaml
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=True)
    except ImportError:
        text = _fallback_yaml(data)

    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}: functions={data['counts']['functions']} "
          f"call_edges={data['counts']['call_edges']} "
          f"stubs={data['counts']['stubs']} interfaces={data['counts']['interfaces']}")
    print(f"fingerprint={data['fingerprint'][:24]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())