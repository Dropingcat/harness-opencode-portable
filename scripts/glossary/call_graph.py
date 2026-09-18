#!/usr/bin/env python3
"""Call-graph edge builder (stdlib ast only, universal).

Builds ``CALLS`` edges ``function -> [callees]`` for the Coder DOM capsule.
Independent module: takes a list of module file paths, returns a deterministic
graph keyed by qualified function name. No external dependencies.

Design (universal, reusable):
  - name = module-qualified: ``module:ClassName.method`` or ``module:function``.
  - For each top-level function/method we scan its body AST for direct
    ``ast.Call`` to a name defined in the same module/class.
  - confidence: "exact" when the callee resolves to a known local name,
    "syntax" when it is an attribute/import we cannot resolve statically.
  - This is intentionally a heuristic; the DOM marks it, never pretends it is
    a perfect call graph.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

PUBLIC_DECORATORS = frozenset({"api", "export", "public"})


def _iter_py_files(root: Path) -> Iterator[Path]:
    """Yield .py files in the declared source scope (mirrors gen_api_index)."""
    spec_dirs = [
        root / "scripts",
        root / "packages",
        root / "references" / "global-kanban",
        root / "guard" / "src",
        root / "mcp",
    ]
    seen: set[str] = set()
    for base in spec_dirs:
        if not base.is_dir():
            continue
        for py in sorted(base.rglob("*.py")):
            rel = str(py.relative_to(root)).replace("\\", "/")
            if any(m in rel.lower() for m in (
                ".venv", "__pycache__", "node_modules", "site-packages",
                "патчи", "архив", "бэкап", "backup", "copy", "копия",
                "server2-corpus", "opencode-current", "doc_Opencode_agern",
                "HARNESS-WRITER", "researcher_r4", ".slim", "audit_graph",
                "run/", "artifacts/",
            )):
                continue
            key = rel.lower()
            if key in seen:
                continue
            seen.add(key)
            yield py


def _qualified(module_rel: str, cls: str | None, name: str) -> str:
    base = module_rel.replace("/", ".").removesuffix(".py")
    if cls:
        return f"{base}:{cls}.{name}"
    return f"{base}:{name}"


def _direct_calls(tree: ast.AST) -> set[str]:
    """Return names of directly called functions in the given AST body."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                names.add(f.id)
            elif isinstance(f, ast.Attribute):
                # method call: obj.attr(...) -> attr (syntax-level)
                names.add(f.attr)
    return names


def _defined_in_module(tree: ast.Module) -> dict[str, str]:
    """Map plain name -> module-qualified name for top-level defs and class methods."""
    mapping: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mapping.setdefault(node.name, node.name)
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    mapping.setdefault(member.name, member.name)
    return mapping


def scan_call_graph(root: str | Path, include_tests: bool = False) -> dict[str, Any]:
    """Return {nodes: {qname: {...}}, edges: [{src, dst, confidence}]}."""
    root_path = Path(root if isinstance(root, str) else root)
    root_str = str(root_path)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    for py in _iter_py_files(root_path):
        try:
            text = py.read_text(encoding="utf-8-sig")
            tree = ast.parse(text)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        rel = str(py.relative_to(root_path)).replace("\\", "/")
        local = _defined_in_module(tree)

        def process_fn(node, cls: str | None) -> None:
            qname = _qualified(rel, cls, node.name)
            nodes.setdefault(qname, {
                "module": rel,
                "name": node.name,
                "class": cls,
                "kind": "method" if cls else "function",
            })
            for callee in _direct_calls(node):
                dst = local.get(callee)
                if dst:
                    edges.append({"src": qname, "dst": _qualified(rel, cls, dst) if dst else dst, "confidence": "exact"})
                elif cls and callee in {m.name for m in tree.body if isinstance(m, ast.ClassDef) for m in m.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}:
                    # method called inside class context (approximate)
                    edges.append({"src": qname, "dst": f"{rel.replace('/','.').removesuffix('.py')}:{cls}.{callee}", "confidence": "syntax"})

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                process_fn(node, None)
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        process_fn(member, node.name)

    # de-dup edges
    seen_edges: set[tuple[str, str, str]] = set()
    dedup: list[dict[str, str]] = []
    for e in edges:
        key = (e["src"], e["dst"], e["confidence"])
        if key in seen_edges:
            continue
        seen_edges.add(key)
        dedup.append(e)

    fingerprint = hashlib.sha256(
        json.dumps({"nodes": sorted(nodes), "edges": sorted((e["src"], e["dst"], e["confidence"]) for e in dedup)},
                   ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return {
        "schema": "coder-call-graph/1.0",
        "root": root_str,
        "counts": {"nodes": len(nodes), "edges": len(dedup)},
        "nodes": nodes,
        "edges": dedup,
        "fingerprint": f"sha256:{fingerprint}",
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Build CALLS call-graph (stdlib ast).")
    ap.add_argument("--root", default=r"E:\Documents\Документы\doc_Opencode_agern-new")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    data = scan_call_graph(args.root)
    out = Path(args.out) if args.out else Path(args.root) / "docs/glossary/call_graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}: nodes={data['counts']['nodes']} edges={data['counts']['edges']}")