#!/usr/bin/env python3
"""Coder DOM adapter — single capsule port for workers (C2).

Universal entry point for any worker (Coder, Writer, Researcher via router) to
operate through the capsule:

  lookup(function)        -> node info (status/owner/calls/called_by/doc)
  context_for(task, module)-> capsule context injected into the worker prompt
  verify_after_edit()     -> regenerate + schema check (verify-gate)

Independent module: uses gen_api_index/call_graph/stub_detect/coder_dom_build
(no cross-import cycles). All paths relative to the harness root.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import coder_dom_build as cdb

SCHEMA = "coder-dom-adapter/1.0"


def _load_dom(root: Path) -> dict[str, Any] | None:
    dom_path = root / "docs/glossary/coder_dom.yaml"
    if not dom_path.is_file():
        return None
    try:
        import yaml
        return yaml.safe_load(dom_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def _index_functions(dom: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Flat index: function name -> node (first occurrence)."""
    if not dom:
        return {}
    index: dict[str, dict[str, Any]] = {}
    for contour in dom.get("structure", {}).get("contours", []):
        for mod in contour.get("modules", []):
            for fn in mod.get("functions", []):
                index.setdefault(fn["name"], {**fn, "module": mod["path"], "contour": contour["id"]})
    return index


def lookup(root: str | Path, function: str) -> dict[str, Any]:
    """Return capsule info for a function (status/owner/calls/...)."""
    root_path = Path(root if isinstance(root, str) else root)
    dom = _load_dom(root_path)
    idx = _index_functions(dom)
    node = idx.get(function)
    if node is None:
        return {
            "schema": SCHEMA,
            "found": False,
            "function": function,
            "hint": "not in coder_dom — run coder_dom_build.py first",
        }
    return {
        "schema": SCHEMA,
        "found": True,
        "function": function,
        "id": node.get("id"),
        "module": node.get("module"),
        "contour": node.get("contour"),
        "signature": node.get("signature"),
        "status": node.get("status"),
        "routing": node.get("routing"),
        "calls": node.get("calls", []),
        "called_by": node.get("called_by", []),
        "doc": node.get("doc", ""),
    }


def context_for(root: str | Path, task: str, function: str) -> dict[str, Any]:
    """Capsule context injected into a worker prompt for one function."""
    info = lookup(root, function)
    root_path = Path(root if isinstance(root, str) else root)
    return {
        "schema": SCHEMA,
        "task": task,
        "function": info,
        "rules": [
            "do not reimplement an existing function — extend it",
            "after edit, regenerate coder_dom.yaml and commit DOM with code",
            "if function is stub, mark it # stub: <id> until implemented",
        ],
        "verify_gate": "python scripts/glossary/verify_coder_dom.py --root " + str(root_path),
    }


def verify_after_edit(root: str | Path, out: str | Path | None = None) -> dict[str, Any]:
    """Regenerate + schema-check; return {ok, fingerprint, stale}."""
    import verify_coder_dom

    root_path = Path(root if isinstance(root, str) else root)
    dom_out = out if out else root_path / "docs/glossary/coder_dom.yaml"
    rc = verify_coder_dom.main(["--root", str(root_path), "--out", str(dom_out)])
    data = cdb.build_coder_dom(root_path)
    return {"schema": SCHEMA, "ok": rc == 0, "fingerprint": data["fingerprint"], "stale": rc == 1}


def router_context(root: str | Path, coder_dom_hint: dict[str, Any] | None) -> dict[str, Any]:
    """CD-002 final: expand a router's coder_dom_hint into a worker capsule prompt.

    Called when harness_run (code-implementation route) returned coder_dom_hint.
    Produces the exact paths/rules a worker needs, plus current stub gate status.
    """
    root_path = Path(root if isinstance(root, str) else root)
    if not coder_dom_hint:
        return {"schema": SCHEMA, "enabled": False, "reason": "no coder_dom_hint from router"}

    import coder_dom_stub_gate

    gate_rc = coder_dom_stub_gate.main(["--root", str(root_path)])
    return {
        "schema": SCHEMA,
        "enabled": True,
        "dom_path": str(root_path / coder_dom_hint.get("dom_path", "docs/glossary/coder_dom.yaml")),
        "builder": coder_dom_hint.get("builder", "scripts/glossary/coder_dom_build.py"),
        "verify_gate": coder_dom_hint.get("verify_gate", "scripts/glossary/verify_coder_dom.py"),
        "rule": coder_dom_hint.get("rule", "work through the capsule; regen + commit DOM with code"),
        "stub_gate_ok": gate_rc == 0,
        "adapter": "scripts/glossary/coder_dom_adapter.py (lookup/context/verify)",
        "skill": "skills/coder-dom/SKILL.md",
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Coder DOM adapter (lookup/context/verify).")
    ap.add_argument("--root", default=r"E:\Documents\Документы\doc_Opencode_agern-new")
    ap.add_argument("--function", required=True)
    ap.add_argument("--task", default="")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    if args.verify:
        out = verify_after_edit(args.root)
    elif args.task:
        out = context_for(args.root, args.task, args.function)
    else:
        out = lookup(args.root, args.function)
    print(json.dumps(out, ensure_ascii=False, indent=2))