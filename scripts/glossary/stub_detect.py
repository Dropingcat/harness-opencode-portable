#!/usr/bin/env python3
"""Stub / interface detector for the Coder DOM capsule (stdlib ast only).

Independent module. Classifies each top-level function/method as one of:

  interface  — abstract contract: class inherits ABC/Protocol OR has
               @abstractmethod; body is `...`/docstring-only. NOT a debt.
  stub       — concrete function with empty body (docstring + pass / ... /
               return None) OR raises NotImplementedError. THIS is a debt.
  normal     — has real body.

Marker support (for conscious stubs):
  - source comment `# stub: <id>` or `# dead: disable` on the def line / first
    body line marks the function as a conscious stub (status=stub, conscious=True).

Also returns radon-like raw metrics (cc, sloc) computed locally (no dependency).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Iterator

INTERFACE_BASES = {"abc.ABC", "ABC", "Protocol"}
DECORATORS_INTERFACE = {"abstractmethod", "abstractproperty"}
STUB_MARKERS = ("# stub:", "# dead: disable", "# STUB:", "# TODO: implement")


def _iter_py_files(root: Path, include_tests: bool = False) -> Iterator[Path]:
    spec_dirs = [
        root / "scripts",
        root / "packages",
        root / "references" / "global-kanban",
        root / "guard" / "src",
        root / "mcp",
    ]
    if include_tests:
        spec_dirs.append(root / "tests")
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


def _class_is_interface(cls: ast.ClassDef, module_imports: set[str]) -> bool:
    # bases: ABC / Protocol / abc.ABC
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id in INTERFACE_BASES:
            return True
        if isinstance(base, ast.Attribute) and base.attr in INTERFACE_BASES:
            return True
        if isinstance(base, ast.Name) and base.id in module_imports and base.id in {"ABC", "Protocol"}:
            return True
    # any @abstractmethod
    for member in cls.body:
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decos = {d.id for d in member.decorator_list if isinstance(d, ast.Name)}
            if decos & DECORATORS_INTERFACE:
                return True
    return False


def _body_is_empty(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [n for n in fn.body if not (
        isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
    )]
    if not body:
        return True  # docstring-only
    if all(isinstance(n, ast.Pass) or (
        isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and n.value.value == Ellipsis
    ) for n in body):
        return True
    # return None only
    if len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is None:
        return True
    return False


def _raises_not_implemented(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Raise):
            exc = node.exc
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "NotImplementedError":
                return True
    return False


def _has_stub_marker(fn: ast.FunctionDef | ast.AsyncFunctionDef, source_lines: list[str]) -> bool:
    start = fn.lineno - 1
    end = fn.end_lineno if fn.end_lineno else start + 1
    for i in range(start, min(end, len(source_lines))):
        line = source_lines[i]
        if any(m in line for m in STUB_MARKERS):
            return True
    return False


def _cc(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Cyclomatic complexity (McCabe), local computation."""
    complexity = 1
    for node in ast.walk(fn):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Try)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        elif isinstance(node, ast.Match):
            complexity += len(node.cases)
    return complexity


def scan_stubs(root: str | Path, include_tests: bool = False) -> dict[str, Any]:
    root_path = Path(root if isinstance(root, str) else root)
    stubs: list[dict[str, Any]] = []
    interfaces: list[dict[str, Any]] = []
    normal_count = 0
    module_imports: set[str] = set()

    def classify(fn, cls, rel, lines) -> None:
        nonlocal normal_count
        marker = _has_stub_marker(fn, lines)
        if _body_is_empty(fn) or _raises_not_implemented(fn):
            stubs.append({
                "module": rel, "class": cls, "name": fn.name, "line": fn.lineno,
                "kind": "stub", "conscious": marker, "cc": _cc(fn), "sloc": (fn.end_lineno or fn.lineno) - fn.lineno + 1,
            })
        else:
            normal_count += 1

    for py in _iter_py_files(root_path, include_tests):
        try:
            text = py.read_text(encoding="utf-8-sig")
            tree = ast.parse(text)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        rel = str(py.relative_to(root_path)).replace("\\", "/")
        lines = text.splitlines()
        # collect imports for ABC/Protocol detection
        module_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                module_imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                module_imports.update(a.name for a in node.names)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                classify(node, None, rel, lines)
            elif isinstance(node, ast.ClassDef):
                is_iface = _class_is_interface(node, module_imports)
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if is_iface or any(
                            isinstance(d, ast.Name) and d.id in DECORATORS_INTERFACE
                            for d in member.decorator_list
                        ):
                            interfaces.append({
                                "module": rel, "class": node.name, "name": member.name,
                                "line": member.lineno, "kind": "interface",
                            })
                        else:
                            classify(member, node.name, rel, lines)

    total = len(stubs) + len(interfaces) + normal_count
    return {
        "schema": "coder-stub-detector/1.0",
        "root": str(root_path),
        "counts": {"stubs": len(stubs), "interfaces": len(interfaces), "normal": normal_count, "total": total},
        "stubs": stubs,
        "interfaces": interfaces,
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Detect stubs vs interfaces (stdlib ast).")
    ap.add_argument("--root", default=r"E:\Documents\Документы\doc_Opencode_agern-new")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    data = scan_stubs(args.root)
    out = Path(args.out) if args.out else Path(args.root) / "docs/glossary/stub_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}: stubs={data['counts']['stubs']} interfaces={data['counts']['interfaces']} normal={data['counts']['normal']}")