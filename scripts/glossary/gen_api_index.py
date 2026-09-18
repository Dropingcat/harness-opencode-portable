#!/usr/bin/env python3
"""M1: AST-based function registry generator for the harness tree.

Scans the selected source contours of the harness tree with stdlib ``ast`` only
(no imports, no execution, no type resolution) and builds a machine-readable
JSON registry of all public functions/methods/classes grouped by "contour",
plus a flat ``name -> [occurrences]`` index for cross-lookup - the same spirit
as pydoc/importlib directory walking.

Deterministic contract:
  * only the declared scope directories are scanned;
  * junk / backup / foreign-tree paths are always excluded;
  * a name is public unless it starts with ``_`` (a ``@api`` / ``@export`` /
    ``@public`` decorator or membership in module ``__all__`` promotes it);
  * paths in the output are relative to the root and use ``/`` separators.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

#: Decorator names that promote a private (``_*``) name to public.
PUBLIC_DECORATORS = frozenset({"api", "export", "public"})

#: Path components that always disqualify a file. A file is excluded only when
#: one of its path components (a directory name, or the file stem without the
#: ``.py`` suffix) *equals* one of these markers - never by substring. Matching
#: is case-insensitive. This keeps legitimate modules whose names merely contain
#: a marker-like substring (``sync_to_live.py``, ``dom_builder.py``, ...).
EXCLUDE_COMPONENTS = frozenset({
    ".venv", "__pycache__", "node_modules", "site-packages",
    "\u043f\u0430\u0442\u0447\u0438",           # патчи
    "\u0430\u0440\u0445\u0438\u0432",           # архив
    "\u0431\u044d\u043a\u0430\u043f",           # бэкап
    "backup", "copy", "\u043a\u043e\u043f\u0438\u044f",  # копия
    "server2-corpus", "opencode-current", "doc_Opencode_agern",
    "HARNESS-WRITER", "researcher_r4", "opencode_harness.7z",
    "slim", "audit_graph", "run", "artifacts",
})
# Case-insensitive matching: keep markers in lowercase.
EXCLUDE_COMPONENTS = frozenset(m.lower() for m in EXCLUDE_COMPONENTS)

#: Contour id -> display name.
CONTOUR_DISPLAY = {
    "code-factory": "Code Factory",
    "writer-core": "Writer Core",
    "writer_core_handoff": "Writer Core Handoff",
    "remote_acceptance": "Remote Acceptance",
    "global-kanban": "Global Kanban",
    "plugin": "Plugin",
    "kanban": "Kanban",
    "guard": "Guard",
    "mcp": "MCP",
    "tests": "Tests",
}


# --------------------------------------------------------------------------
# Path / scope helpers
# --------------------------------------------------------------------------
def _excluded(rel_path: str) -> bool:
    """Return True when any path component equals an exclusion marker.

    Components are the directory names and the file stem (name without the
    ``.py`` suffix), split on ``/``. Pure component comparison, not substring.
    """
    low = rel_path.replace("\\", "/").lower()
    parts = low.split("/")
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return any(part in EXCLUDE_COMPONENTS for part in parts)


def _is_test_file(name: str) -> bool:
    return name.startswith("test_") or name.endswith("_test.py") or name == "tests.py"


def _iter_py_files(root: Path, include_tests: bool) -> Iterator[tuple[Path, str]]:
    """Yield (absolute file, posix-relative path) for every in-scope ``.py``.

    Scope is fixed to the declared contours; files outside the scope are never
    touched even if they exist on disk.
    """
    spec_dirs = [
        (root / "scripts", "scripts"),
        (root / "packages", "packages"),
        (root / "references" / "global-kanban", "references/global-kanban"),
        (root / "guard" / "src", "guard/src"),
        (root / "mcp", "mcp"),
    ]
    if include_tests:
        spec_dirs.append((root / "tests", "tests"))

    seen: set[str] = set()
    for base_dir, _base_rel in spec_dirs:
        if not base_dir.is_dir():
            continue
        for py_file in sorted(base_dir.rglob("*.py")):
            try:
                rel = os.path.relpath(str(py_file), str(root)).replace("\\", "/")
            except ValueError:
                continue
            if _excluded(rel) or _is_test_file(py_file.name):
                continue
            key = rel.lower()
            if key in seen:
                continue
            seen.add(key)
            yield py_file, rel


def _contour_for(rel: str) -> str:
    """Map a relative path to its contour id.

    The contour is the *first directory* after the scope prefix. Top-level
    ``scripts/*.py`` files (no sub-directory) share the single ``scripts``
    contour - never the file name.
    """
    parts = rel.split("/")
    if parts[0] == "scripts":
        # Only a sub-directory names a contour; flat scripts/*.py -> "scripts".
        if len(parts) >= 3:
            return parts[1]
        return "scripts"
    if parts[0] == "packages":
        if len(parts) >= 2 and parts[1] == "opencode-harness-plugin":
            return "plugin"
        return parts[1] if len(parts) >= 2 else "packages"
    if parts[0] == "references":
        return "kanban"
    if parts[0] == "guard":
        return "guard"
    if parts[0] == "mcp":
        return "mcp"
    if parts[0] == "tests":
        return "tests"
    return parts[0]


def _display(contour_id: str) -> str:
    if contour_id in CONTOUR_DISPLAY:
        return CONTOUR_DISPLAY[contour_id]
    return " ".join(p.capitalize() for p in contour_id.replace("_", "-").split("-"))


# --------------------------------------------------------------------------
# AST extraction (pure, deterministic - no imports, no execution)
# --------------------------------------------------------------------------
def _module_all(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    for el in node.value.elts:
                        if isinstance(el, ast.Constant) and isinstance(el.value, str):
                            names.add(el.value)
    return names


def _deco_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> set[str]:
    out: set[str] = set()
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            out.add(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            out.add(decorator.attr)
    return out


def _is_public(name: str, deco_names: set[str], module_all: set[str]) -> bool:
    if name in module_all:
        return True
    if name.startswith("_"):
        return bool(deco_names & PUBLIC_DECORATORS)
    return True


def _first_line(doc: str | None) -> str:
    if not doc:
        return ""
    stripped = doc.strip().splitlines()
    return stripped[0][:140] if stripped else ""


def _arg_str(arg: ast.arg) -> str:
    s = arg.arg
    if arg.annotation is not None:
        s += ": " + ast.unparse(arg.annotation)
    return s


def _signature(name: str, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = fn.args
    prefix = "async def " if isinstance(fn, ast.AsyncFunctionDef) else "def "
    # Defaults are bound to the *tail* of (posonlyargs + args) as a single
    # sequence (Python 3.8+). Computing the offset from the combined length is
    # what keeps ``def f(a=1, /, b: int = 2)`` from IndexError.
    pos_only = list(args.posonlyargs)
    pos_or_kw = list(args.args)
    total = pos_only + pos_or_kw
    defaults = list(args.defaults)
    offset = len(total) - len(defaults)
    toks: list[str] = []
    for i, a in enumerate(total):
        s = _arg_str(a)
        if i >= offset:
            s += " = " + ast.unparse(defaults[i - offset])
        toks.append(s)
        # ``/`` must immediately follow the last positional-only argument.
        if args.posonlyargs and i == len(pos_only) - 1:
            toks.append("/")
    if args.vararg:
        toks.append("*" + _arg_str(args.vararg))
    elif args.kwonlyargs:
        toks.append("*")
    for i, a in enumerate(args.kwonlyargs):
        s = _arg_str(a)
        if args.kw_defaults[i] is not None:
            s += " = " + ast.unparse(args.kw_defaults[i])
        toks.append(s)
    if args.kwarg:
        toks.append("**" + _arg_str(args.kwarg))
    sig = f"{prefix}{name}(" + ", ".join(toks) + ")"
    if fn.returns is not None:
        sig += " -> " + ast.unparse(fn.returns)
    return sig


def _function_entry(node: ast.FunctionDef | ast.AsyncFunctionDef, deco: set[str], kind: str) -> dict:
    return {
        "name": node.name,
        "kind": kind,
        "signature": _signature(node.name, node),
        "doc": _first_line(ast.get_docstring(node)),
        "decorators": sorted(deco),
        "line": node.lineno,
    }


def _class_entry(node: ast.ClassDef, module_all: set[str]) -> dict:
    methods: list[dict[str, Any]] = []
    for member in node.body:
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
            deco = _deco_names(member)
            if not _is_public(member.name, deco, module_all):
                continue
            kind = ("async_" if isinstance(member, ast.AsyncFunctionDef) else "") + "method"
            entry = _function_entry(member, deco, kind)
            entry["class"] = node.name
            methods.append(entry)
    return {
        "name": node.name,
        "bases": [ast.unparse(b) for b in node.bases],
        "doc": _first_line(ast.get_docstring(node)),
        "line": node.lineno,
        "methods": methods,
    }


def _extract_module(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    """Return (functions, classes, __all__ names) for one module's source text."""
    tree = ast.parse(text)
    module_all = _module_all(tree)
    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            deco = _deco_names(node)
            if not _is_public(node.name, deco, module_all):
                continue
            kind = ("async_" if isinstance(node, ast.AsyncFunctionDef) else "") + "function"
            functions.append(_function_entry(node, deco, kind))
        elif isinstance(node, ast.ClassDef):
            deco = _deco_names(node)
            if not _is_public(node.name, deco, module_all):
                continue
            classes.append(_class_entry(node, module_all))
    return functions, classes, module_all


def _module_entry(rel: str, text: str) -> dict[str, Any] | None:
    try:
        functions, classes, _module_all_names = _extract_module(text)
    except (SyntaxError, ValueError):
        return None  # unparsable modules are skipped (deterministic)
    return {"path": rel, "functions": functions, "classes": classes}


# --------------------------------------------------------------------------
# scan_tree: public, importable API
# --------------------------------------------------------------------------
def scan_tree(root: str | Path, label: str = "workspace", include_tests: bool = False) -> dict:
    """Scan the tree and return the registry dict (see module docstring for the schema)."""
    root_path = Path(root if isinstance(root, Path) else str(root))
    if not root_path.is_absolute():
        root_path = root_path.resolve()
    root_str = str(root_path)

    contours_map: dict[str, dict[str, Any]] = {}
    index: dict[str, list[dict[str, Any]]] = {}
    n_functions = 0
    n_classes = 0
    n_methods = 0

    for py_file, rel in _iter_py_files(root_path, include_tests):
        try:
            text = py_file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        module_entry = _module_entry(rel, text)
        if module_entry is None:
            continue
        contour_id = _contour_for(rel)
        contour = contours_map.setdefault(
            contour_id, {"id": contour_id, "display": _display(contour_id), "modules": []}
        )
        contour["modules"].append(module_entry)

        for fn in module_entry["functions"]:
            n_functions += 1
            index.setdefault(fn["name"], []).append(
                {"module": rel, "contour": contour_id, "signature": fn["signature"], "doc": fn["doc"]}
            )
        for cls in module_entry["classes"]:
            n_classes += 1
            class_sig = "class " + cls["name"] + ("(" + ", ".join(cls["bases"]) + ")") if cls["bases"] else "class " + cls["name"]
            index.setdefault(cls["name"], []).append(
                {"module": rel, "contour": contour_id, "signature": class_sig, "doc": cls["doc"]}
            )
            for method in cls["methods"]:
                n_methods += 1
                index.setdefault(method["name"], []).append(
                    {"module": rel, "contour": contour_id, "signature": method["signature"], "doc": method["doc"]}
                )

    contours = sorted(contours_map.values(), key=lambda c: c["id"])
    for occurrences in index.values():
        occurrences.sort(key=lambda entry: (entry["module"], entry["signature"]))

    return {
        "meta": {
            "label": label,
            "root": root_str,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "python": "3.11",
            "counts": {
                "modules": sum(len(c["modules"]) for c in contours),
                "functions": n_functions,
                "classes": n_classes,
                "methods": n_methods,
            },
        },
        "contours": contours,
        "index": dict(sorted(index.items())),
    }


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the harness function/class registry JSON (stdlib-only AST scan)."
    )
    parser.add_argument(
        "--root",
        default=r"E:\Documents\Документы\doc_Opencode_agern-new",
        help="root of the harness tree (default: the workspace root)",
    )
    parser.add_argument("--out", default=None, help="output JSON path (default: <root>/docs/glossary/function_index.json)")
    parser.add_argument("--label", default="workspace", help="tree label, e.g. workspace / portable")
    parser.add_argument(
        "--include-tests", action="store_true", dest="include_tests", help="also scan tests/** (default: no)"
    )
    args = parser.parse_args(argv)

    root_path = Path(args.root)
    out_path = Path(args.out) if args.out else root_path / "docs" / "glossary" / "function_index.json"
    data = scan_tree(root_path, args.label, args.include_tests)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = data["meta"]["counts"]
    print(f"wrote {out_path}: modules={counts['modules']} functions={counts['functions']} "
          f"classes={counts['classes']} methods={counts['methods']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())