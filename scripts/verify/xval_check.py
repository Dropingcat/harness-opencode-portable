#!/usr/bin/env python3
"""Общий чекер X-серий диаграмм Excel (TD-FACTORY-1, HIGH).

Ловит Excel-баг «X→1..N»: когда у графика X и Y-массивы разной длины/шага, Excel
заменяет реальные X на 1,2,3,...,N. Работает на уровне ЗНАЧЕНИЙ (xVal против
эталонной linspace-сетки), а не только адресов ссылок.

Переиспользуемый механизм — не привязан к конкретному ГОСТ/фабрике.

API:
    check_xval(workbook_or_path, sheet_name=None, atol=1e-12, grid_filter=None) -> dict
    CheckResult = {
        "ok": bool,
        "series_count": int,
        "issues":  [ {"series_idx": {...}, "issue": str, "detail": str}, ... ],
        "xvals":   [ [float, ...] | None, ... ],   # значения X каждой серии (для отладки)
        "warnings":[ {"series_idx": {...}, "issue": str, "detail": str}, ... ],
    }

Значения issue (fail-проверки):
    enum_reset_x | non_monotonic | grid_mismatch | len_mismatch | no_xval | degenerate
Значения warning (не фейлят):
    len_formula_no_cache | y_missing | y_empty | x_no_cached_values | sheet_not_found

CLI:
    python scripts/verify/xval_check.py <workbook.xlsx> [--sheet NAME] [--json]
    exit 0 — ok; exit 1 — найдены проблемы (issues)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from openpyxl import load_workbook
from openpyxl.utils import range_boundaries


#: atol для детекции сигнатуры «X == 1..N» (float-значения 1.0, 2.0, ... — точные;
#: запас 1e-9 не даёт FP для реальных сеток, но ловит индексы-категории).
ENUM_RESET_ATOL = 1e-9


# ---------------------------------------------------------------- helpers

def _split_ref(f: str) -> tuple[str | None, str | None]:
    """Разбить диапазон вида `'Лист'!$A$1:$A$6` или `Лист1!$A$1:$A$6`
    на (имя_листа, адрес_без_$)."""
    if not f:
        return None, None
    f = f.strip()
    if f.startswith("'"):
        end = f.find("'", 1)
        if end < 0:
            return None, f
        sheet = f[1:end]
        rest = f[end + 1:]
        if rest.startswith("!"):
            rest = rest[1:]
        return sheet, rest.replace("$", "").strip()
    if "!" in f:
        sheet, rng = f.split("!", 1)
        return sheet, rng.replace("$", "").strip()
    return None, f.replace("$", "").strip()


def _ref_bounds(f: str) -> tuple[int, int, int, int] | None:
    sheet, rng = _split_ref(f)
    if not rng:
        return None
    try:
        min_col, min_row, max_col, max_row = range_boundaries(rng)
    except Exception:
        return None
    return min_col, min_row, max_col, max_row


def _ref_size(f: str) -> int:
    """Число ячеек в диапазоне ссылки (доступно даже без кэша значений)."""
    b = _ref_bounds(f)
    if b is None:
        return 0
    min_col, min_row, max_col, max_row = b
    return (max_col - min_col + 1) * (max_row - min_row + 1)


def _read_ref_values(wb, f: str) -> list | None:
    """Прочитать значения ячеек диапазона. None — ссылка/лист не резолвится."""
    sheet, rng = _split_ref(f)
    if sheet is None or rng is None:
        return None
    b = _ref_bounds(f)
    if b is None:
        return None
    try:
        ws = wb[sheet]
    except (KeyError, TypeError):
        return None
    min_col, min_row, max_col, max_row = b
    vals = []
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            vals.append(ws.cell(row=row, column=col).value)
    return vals


def _numeric(vals) -> list[float]:
    """Только числовые значения (формулы-без-кэша дают None/строки → отбрасываются)."""
    if vals is None:
        return []
    out = []
    for v in vals:
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out.append(float(v))
    return out


def _data_source_ref(series, attr_names: tuple[str, ...]) -> str | None:
    """Достать ссылку (numRef.f) из первого доступного поля серии."""
    for name in attr_names:
        ds = getattr(series, name, None)
        if ds is None:
            continue
        ref = getattr(ds, "numRef", None)
        if ref is not None and getattr(ref, "f", None):
            return ref.f
    return None


def _series_xref(series) -> str | None:
    """X: для ScatterChart — xVal; для Line/Bar — cat."""
    return _data_source_ref(series, ("xVal", "cat"))


def _series_yref(series) -> str | None:
    """Y: для ScatterChart (XYSeries) — yVal; для обычных Series — val."""
    return _data_source_ref(series, ("yVal", "val"))


# ---------------------------------------------------------------- core

def _is_uniform_grid(X: list[float], rel_tol: float = 1e-6) -> bool:
    """Похож ли ряд X на равномерную сетку (константный шаг)?"""
    if X is None or len(X) < 3:
        return False
    step0 = X[1] - X[0]
    if step0 <= 0:
        return False
    return all(abs((X[i + 1] - X[i]) - step0) <= rel_tol * abs(step0) for i in range(len(X) - 1))


def _auto_grid_filter(X: list[float]) -> bool:
    """grid_filter для CLI --grid-filter: применять linspace-проверку только к
    рядам с константным шагом (равномерные сетки). Точки калибровки / маркеры
    с неравномерным X пропускаются."""
    return _is_uniform_grid(X)


def check_xval(workbook_or_path, sheet_name: str | None = None, atol: float = 1e-12,
               grid_filter=None, allow_singletons: bool = False) -> dict:
    """Проверить X-значения всех серий всех диаграмм.

    workbook_or_path: путь к .xlsx (загружается data_only=True) ИЛИ открытый Workbook.
    sheet_name: если задан — только этот лист; иначе все листы с диаграммами.
    atol: допуск сверки с linspace-сеткой (FP-дрейф < 5e-16, запас 3 порядка).
    grid_filter: опциональный callable(X_list) -> bool: применять ли linspace-проверку
        (в) к серии. По умолчанию — ко всем с len(X)>=3. Для серий, чьи X — РЕАЛЬНЫЕ
        данные (точки калибровки, маркеры, не linspace-сетка), вызывающий передаёт
        предикат, возвращающий False для неравномерных рядов. Проверки (а)/(б)/(г)
        применяются всегда.
    allow_singletons: если True — серии с len(X)==1 (одиночные маркеры, напр. x_pred)
        НЕ считаются issues (идут в warnings как singleton_marker).
    """
    if isinstance(workbook_or_path, (str, Path)):
        wb = load_workbook(str(workbook_or_path), data_only=True)
    else:
        wb = workbook_or_path

    if sheet_name is not None:
        if sheet_name not in wb.sheetnames:
            return {
                "ok": False,
                "series_count": 0,
                "issues": [{
                    "series_idx": {"sheet": sheet_name, "chart": -1, "series": -1},
                    "issue": "sheet_not_found",
                    "detail": f"sheet {sheet_name!r} not found in workbook",
                }],
                "xvals": [],
                "warnings": [],
            }
        targets = [sheet_name]
    else:
        targets = [n for n in wb.sheetnames if wb[n]._charts]

    issues: list[dict] = []
    warnings: list[dict] = []
    xvals: list = []
    series_count = 0

    for sn in targets:
        ws = wb[sn]
        for ci, chart in enumerate(ws._charts):
            for si, series in enumerate(chart.series):
                sidx = {"sheet": sn, "chart": ci, "series": si}
                series_count += 1
                xvals.append(None)

                # 1. Достать ссылку X: xVal (Scatter) или cat (прочие)
                xf = _series_xref(series)
                if xf is None:
                    issues.append({
                        "series_idx": sidx, "issue": "no_xval",
                        "detail": "series has neither xVal nor cat reference",
                    })
                    continue

                # Прочитать значения X
                xraw = _read_ref_values(wb, xf)
                X = _numeric(xraw)
                if not X:
                    warnings.append({
                        "series_idx": sidx, "issue": "x_no_cached_values",
                        "detail": f"xVal {xf}: no numeric cached values (live formulas?)",
                    })
                    continue
                xvals[-1] = X

                # (а) сигнатура Excel-бага: X == 1..N
                if len(X) > 1 and all(abs(x - (i + 1)) <= ENUM_RESET_ATOL for i, x in enumerate(X)):
                    issues.append({
                        "series_idx": sidx, "issue": "enum_reset_x",
                        "detail": f"X == 1..N: Excel replaced real X values with row indices (len={len(X)})",
                    })

                # degenerate: слишком мало точек (без сетки/монотонности смысла нет)
                if len(X) <= 1:
                    if not allow_singletons:
                        issues.append({
                            "series_idx": sidx, "issue": "degenerate",
                            "detail": f"len(X)={len(X)} <= 1",
                        })
                    else:
                        warnings.append({
                            "series_idx": sidx, "issue": "singleton_marker",
                            "detail": f"len(X)=1 (single marker, e.g. x_pred); skipped as non-grid",
                        })
                    continue

                # (б) строгая монотонность
                if not all(b > a for a, b in zip(X, X[1:])):
                    issues.append({
                        "series_idx": sidx, "issue": "non_monotonic",
                        "detail": "X is not strictly increasing (possible unsorted/permuted categories)",
                    })

                # (в) эталонная сетка: linspace(X[0], X[-1], len(X))
                if len(X) >= 3 and (grid_filter is None or grid_filter(X)):
                    grid = np.linspace(X[0], X[-1], len(X))
                    if not np.allclose(X, grid, rtol=0.0, atol=atol):
                        issues.append({
                            "series_idx": sidx, "issue": "grid_mismatch",
                            "detail": f"X diverges from np.linspace({X[0]!r}, {X[-1]!r}, {len(X)}) at atol={atol}",
                        })

                # (г) len(X) vs len(Y)
                yf = _series_yref(series)
                if yf is None:
                    warnings.append({
                        "series_idx": sidx, "issue": "y_missing",
                        "detail": "series has neither yVal nor val reference — length not verifiable",
                    })
                    continue
                yraw = _read_ref_values(wb, yf)
                Y = _numeric(yraw)
                if not Y:
                    if _ref_size(yf) > 0:
                        # живые формулы без кэша (например, =G*E): значений нет,
                        # по размеру ссылки совпадать не обязаны — НЕ фейлим
                        warnings.append({
                            "series_idx": sidx, "issue": "len_formula_no_cache",
                            "detail": f"yVal {yf}: live formulas without cached values; length not comparable",
                        })
                    else:
                        warnings.append({
                            "series_idx": sidx, "issue": "y_empty",
                            "detail": f"yVal {yf}: reference has no cells",
                        })
                elif len(Y) != len(X):
                    issues.append({
                        "series_idx": sidx, "issue": "len_mismatch",
                        "detail": f"len(X)={len(X)} != len(Y)={len(Y)} (Excel resets categories on mismatched arrays)",
                    })

    return {
        "ok": not issues,
        "series_count": series_count,
        "issues": issues,
        "xvals": xvals,
        "warnings": warnings,
    }


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Check Excel chart X-series values (Excel 'X->1..N' bug).",
    )
    p.add_argument("workbook", help="path to .xlsx workbook")
    p.add_argument("--sheet", default=None, help="sheet name to check (default: all sheets with charts)")
    p.add_argument("--grid-filter", action="store_true",
                   help="apply linspace grid check ONLY to series whose X is a uniform grid "
                        "(auto-detected: constant step). Skips non-grid series (calibration points, "
                        "markers). Checks (a)/(b)/(d) still apply to every series.")
    p.add_argument("--allow-singletons", action="store_true",
                   help="treat len(X)==1 series (single markers, e.g. x_pred) as warnings, not failures")
    p.add_argument("--json", action="store_true", help="print CheckResult as JSON")
    a = p.parse_args(argv)

    filter_fn = _auto_grid_filter if a.grid_filter else None
    result = check_xval(a.workbook, sheet_name=a.sheet, grid_filter=filter_fn,
                        allow_singletons=a.allow_singletons)

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"series scanned: {result['series_count']}  ok={result['ok']}")
        for iss in result["issues"]:
            print(f"  FAIL  {iss['issue']}: {iss['detail']}  series={iss['series_idx']}")
        for w in result["warnings"]:
            print(f"  WARN  {w['issue']}: {w['detail']}  series={w['series_idx']}")
        print("RESULT: " + ("PASS" if result["ok"] else "FAIL"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())