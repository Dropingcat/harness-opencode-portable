#!/usr/bin/env python3
"""M4: Render GLOSSARY.md from a function_index.json registry.

Reads a registry produced by ``gen_api_index.py`` and renders a deterministic
markdown glossary in the "Python-libraries" spirit:

    contour -> module -> public functions / classes (with signatures and the
    first docstring line).

Structure of the output document:

  * header (title, date, toolchain note);
  * "Полный список функций по контурам" - per-contour summary counts with the
    sample module files (same shape as the old GLOSSARY.md auto-collected
    section);
  * per-contour sections (sorted by contour id), inside them modules sorted by
    path, then functions and classes (in source order) with signatures.

Stdlib only. Output is utf-8. Importable via :func:`render_glossary`.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

#: Maximum length of a docstring excerpt in the glossary.
DOC_MAX = 140


# --------------------------------------------------------------------------
# Small rendering helpers
# --------------------------------------------------------------------------
def _doc_excerpt(doc: str | None) -> str:
    """First docstring line, trimmed to DOC_MAX chars; ``—`` when empty."""
    if not doc:
        return "—"
    text = doc.strip().splitlines()[0] if doc.strip() else ""
    if not text:
        return "—"
    return text[:DOC_MAX]


def _strip_def(signature: str) -> str:
    """Drop the ``def `` / ``async def `` / ``class `` prefix from a signature."""
    for prefix in ("async def ", "def ", "class "):
        if signature.startswith(prefix):
            return signature[len(prefix):]
    return signature


def _summary_line(contour: dict[str, Any], files: list[str]) -> str:
    """One ``- `id`: N публичных функций (файлы: ...)`` summary line."""
    n_functions = sum(len(m.get("functions", [])) for m in contour.get("modules", []))
    sample = files[:3]
    if len(sample) == 1:
        files_text = f"файлы: {sample[0]}"
    elif sample:
        files_text = "файлы: " + ", ".join(sample) + " и др."
    else:
        files_text = "файлы: —"
    return f"- `{contour.get('id', '')}`: {n_functions} публичных функций ({files_text})"


def _module_paths(contour: dict[str, Any]) -> list[str]:
    paths = [m.get("path", "") for m in contour.get("modules", [])]
    return sorted(p for p in paths if p)


# --------------------------------------------------------------------------
# render_glossary: public, importable API
# --------------------------------------------------------------------------
def render_glossary(index: dict[str, Any], label: str) -> str:
    """Render the full GLOSSARY.md document for a registry and label."""
    today = datetime.now().strftime("%Y-%m-%d")
    contours = sorted(index.get("contours", []), key=lambda c: c.get("id", ""))

    lines = [
        f"# Harness Glossary — {label}",
        "",
        f"Дата: {today}. Автосбор: scripts/glossary/gen_api_index.py + render_glossary.py.",
        "«По принципу Python-библиотек»: контур → модуль → публичные функции/классы с сигнатурами.",
        "",
        "## Полный список функций по контурам",
    ]
    for contour in contours:
        lines.append(_summary_line(contour, _module_paths(contour)))
    lines.append("")

    for contour in contours:
        display = contour.get("display") or contour.get("id", "")
        lines += [f"## {display}", ""]
        modules = sorted(contour.get("modules", []), key=lambda m: m.get("path", ""))
        for module in modules:
            path = module.get("path", "")
            if not path:
                continue
            lines += [f"### `{path}`", ""]
            for fn in module.get("functions", []):
                sig = _strip_def(fn.get("signature", ""))
                doc = _doc_excerpt(fn.get("doc", ""))
                line_no = fn.get("line", "?")
                lines.append(f"- `{sig}` — {doc} [строка {line_no}]")
            for cls in module.get("classes", []):
                sig = _class_sig(cls)
                doc = _doc_excerpt(cls.get("doc", ""))
                line_no = cls.get("line", "?")
                lines.append(f"- `{sig}` — {doc} [строка {line_no}]")
                for method in cls.get("methods", []):
                    method_sig = _strip_def(method.get("signature", ""))
                    method_doc = _doc_excerpt(method.get("doc", ""))
                    lines.append(f"  - `{method_sig}` — {method_doc}")
            lines.append("")

    return "\n".join(lines)


def _class_sig(cls: dict[str, Any]) -> str:
    """Render ``ClassName(bases...)`` for a class entry."""
    bases = cls.get("bases", [])
    inner = ", ".join(bases) if bases else ""
    return f"{cls.get('name', '')}({inner})"


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render GLOSSARY.md from a function_index.json registry."
    )
    parser.add_argument("--index", required=True,
                        help="function_index.json produced by gen_api_index.py")
    parser.add_argument("--out", default=None,
                        help="output markdown (default: <index_dir>/GLOSSARY.md)")
    parser.add_argument("--label", default=None,
                        help="glossary label (default: registry meta.label)")
    args = parser.parse_args(argv)

    index_path = Path(args.index)
    with open(index_path, encoding="utf-8") as fh:
        index = json.load(fh)

    label = args.label or (index.get("meta") or {}).get("label", "glossary")
    out_path = Path(args.out) if args.out else index_path.parent / "GLOSSARY.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_glossary(index, label), encoding="utf-8")

    print(f"wrote {out_path}: label={label} contours={len(index.get('contours', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())