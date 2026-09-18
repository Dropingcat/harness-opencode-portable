#!/usr/bin/env python3
"""M3: Tree delta between two function_index.json registries (workspace vs portable).

Reads two registries produced by ``gen_api_index.py`` (schema:
``contours[].modules[].path`` and ``index{}``) and computes per-contour deltas:

  * module delta    - module paths (posix, ``/`` separators) present in ``base``
                      but absent in ``target``, grouped by contour - this is
                      "what must be ported to v1.1" (TD-D1);
  * function delta  - top-level public functions present in ``base`` but absent
                      in ``target``, keyed by ``(contour, function name)``.

The result is rendered as a deterministic markdown report ``PORTABLE_DELTA.md``.

Stdlib only. Paths are posix-relative. Output is utf-8. Importable via :func:`compute_delta`.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------
# Reading helpers (defensive, deterministic)
# --------------------------------------------------------------------------
def load_index(path: str | Path) -> dict[str, Any]:
    """Read a function_index.json registry (utf-8)."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _contour_modules(index: dict[str, Any]) -> dict[str, set[str]]:
    """Return ``contour id -> set of posix module paths`` (from contours only)."""
    out: dict[str, set[str]] = {}
    for contour in index.get("contours", []):
        cid = contour.get("id", "")
        modules = {
            module.get("path", "")
            for module in contour.get("modules", [])
            if module.get("path")
        }
        out.setdefault(cid, set()).update(modules)
    return out


def _contour_functions(index: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    """Return ``contour id -> {function name: [posix module paths]}``.

    Only top-level public functions are counted (the same category as
    ``meta.counts.functions in gen_api_index.py). Deterministic ordering of the
    module list is guaranteed by sorting at use site.
    """
    out: dict[str, dict[str, list[str]]] = {}
    for contour in index.get("contours", []):
        cid = contour.get("id", "")
        funcs = out.setdefault(cid, {})
        for module in contour.get("modules", []):
            path = module.get("path", "")
            for fn in module.get("functions", []):
                name = fn.get("name", "")
                if not name:
                    continue
                funcs.setdefault(name, []).append(path)
    return out


def _display(contour_id: str) -> str:
    """Fallback display name for a contour id (used when JSON has no ``display``)."""
    return " ".join(p.capitalize() for p in contour_id.replace("_", "-").split("-"))


# --------------------------------------------------------------------------
# compute_delta: public, importable API
# --------------------------------------------------------------------------
def compute_delta(base_index: dict[str, Any], target_index: dict[str, Any]) -> dict[str, Any]:
    """Compute per-contour module/function deltas between two registries.

    "Missing" means present in ``base_index`` but absent in ``target_index``.
    Returned dict is ready for :func:`render_delta` and for programmatic
    consumers (TD-D1 porting map).
    """
    base_mods = _contour_modules(base_index)
    target_mods = _contour_modules(target_index)
    base_funcs = _contour_functions(base_index)
    target_funcs = _contour_functions(target_index)

    # contour id -> display name, prefer the value stored in the registry.
    display_map: dict[str, str] = {}
    for contour in base_index.get("contours", []) + target_index.get("contours", []):
        cid = contour.get("id", "")
        if cid and contour.get("display"):
            display_map.setdefault(cid, contour.get("display", ""))

    contours: list[dict[str, Any]] = []
    warnings: list[str] = []
    totals: dict[str, int] = {
        "modules_base": 0,
        "modules_target": 0,
        "functions_base": 0,
        "functions_target": 0,
        "modules_missing": 0,
        "functions_missing": 0,
    }

    for cid in sorted(set(base_mods) | set(target_mods)):
        bm = base_mods.get(cid, set())
        tm = target_mods.get(cid, set())
        bf = base_funcs.get(cid, {})
        tf = target_funcs.get(cid, {})

        missing_modules = sorted(bm - tm)
        missing_functions = [
            {"name": name, "module": min(bf[name])}
            for name in sorted(set(bf) - set(tf))
        ]

        # Desync warnings: a module/function exists on one side of a contour
        # and is entirely absent on the other. Informational, never fatal.
        if bm and not tm:
            warnings.append(f"контур '{cid}': {len(bm)} модулей в base, 0 в target")
        if tm and not bm:
            warnings.append(f"контур '{cid}': {len(tm)} модулей в target, 0 в base")
        if bf and not tf:
            warnings.append(f"контур '{cid}': {len(bf)} функций в base, 0 в target")
        if tf and not bf:
            warnings.append(f"контур '{cid}': {len(tf)} функций в target, 0 в base")

        row = {
            "id": cid,
            "display": display_map.get(cid) or _display(cid),
            "modules_base": len(bm),
            "modules_target": len(tm),
            "functions_base": len(bf),
            "functions_target": len(tf),
            "modules_missing": missing_modules,
            "functions_missing": missing_functions,
        }
        contours.append(row)
        totals["modules_base"] += row["modules_base"]
        totals["modules_target"] += row["modules_target"]
        totals["functions_base"] += row["functions_base"]
        totals["functions_target"] += row["functions_target"]
        totals["modules_missing"] += len(row["modules_missing"])
        totals["functions_missing"] += len(row["functions_missing"])

    return {
        "base": {"label": (base_index.get("meta") or {}).get("label", "base")},
        "target": {"label": (target_index.get("meta") or {}).get("label", "target")},
        "contours": contours,
        "totals": totals,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# render_delta: delta dict -> markdown document
# --------------------------------------------------------------------------
def render_delta(delta: dict[str, Any]) -> str:
    """Render the delta dict as the PORTABLE_DELTA.md markdown document."""
    today = datetime.now().strftime("%Y-%m-%d")
    base_label = (delta.get("base") or {}).get("label", "base")
    target_label = (delta.get("target") or {}).get("label", "target")

    lines = [
        "# Portable Delta — карта переноса v1 → v1.1",
        "",
        f"Дата: {today}. Источник: function_index.json ({base_label} vs {target_label}).",
        "",
        "## Сводка",
        "| Контур | Модули base | Модули target | Функции base | Функции target | Модулей нет в target | Функций нет в target |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in delta.get("contours", []):
        lines.append(
            "| {id} | {mb} | {mt} | {fb} | {ft} | {mm} | {fm} |".format(
                id=row["id"], mb=row["modules_base"], mt=row["modules_target"],
                fb=row["functions_base"], ft=row["functions_target"],
                mm=len(row["modules_missing"]), fm=len(row["functions_missing"]),
            )
        )

    lines += ["", "## Модули, отсутствующие в portable (перенести в v1.1)"]
    any_modules = False
    for row in delta.get("contours", []):
        if not row["modules_missing"]:
            continue
        any_modules = True
        lines += ["", f"### {row['display']}"]
        lines += [f"- `{path}`" for path in row["modules_missing"]]
    if not any_modules:
        lines += ["", "Нет."]

    lines += ["", "## Функции, отсутствующие в portable (по контурам)"]
    any_functions = False
    for row in delta.get("contours", []):
        if not row["functions_missing"]:
            continue
        any_functions = True
        lines += ["", f"### {row['display']}"]
        for fn in row["functions_missing"]:
            lines.append(f"- `{fn['name']}` — модуль `{fn['module']}`")
    if not any_functions:
        lines += ["", "Нет."]

    warnings = delta.get("warnings") or []
    if warnings:
        lines += ["", "## Предупреждения", ""]
        lines += [f"- {w}" for w in warnings]

    lines += [""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two function_index.json registries and write PORTABLE_DELTA.md."
    )
    parser.add_argument("--base", required=True,
                        help="function_index.json of the full (workspace) tree")
    parser.add_argument("--target", required=True,
                        help="function_index.json of the portable tree")
    parser.add_argument("--out", default=None,
                        help="output markdown (default: <base_dir>/PORTABLE_DELTA.md)")
    args = parser.parse_args(argv)

    base_path = Path(args.base)
    target_path = Path(args.target)
    base_index = load_index(base_path)
    target_index = load_index(target_path)

    delta = compute_delta(base_index, target_index)
    out_path = Path(args.out) if args.out else base_path.parent / "PORTABLE_DELTA.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_delta(delta), encoding="utf-8")

    totals = delta["totals"]
    print(
        f"wrote {out_path}: contours={len(delta['contours'])} "
        f"modules_missing={totals['modules_missing']} "
        f"functions_missing={totals['functions_missing']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())