#!/usr/bin/env python3
"""Повторная верификация среза изменённых групп (N12).

TMS-инкрементальность: перезапуск этапов 4-8 только для затронутых групп.
Сравнение вердиктов до/после: status_flow {old, new}.
"""

import json
from typing import Any

from sexpr import SExpr, format_sexpr


def compare_verdicts(
    original_verdicts: dict[int, str],
    new_verdicts: dict[int, str],
) -> dict:
    status_flow = {}
    regressions = []
    improvements = []
    unchanged = []

    all_groups = set(original_verdicts.keys()) | set(new_verdicts.keys())

    for gi in sorted(all_groups):
        old = original_verdicts.get(gi, "UNKNOWN")
        new = new_verdicts.get(gi, "UNKNOWN")
        status_flow[str(gi)] = {"old": old, "new": new}

        verdict_rank = {"CONTRADICTED": 0, "UNSUPPORTED": 1, "AMBIGUOUS": 2, "SUPPORTED": 3, "OPEN": -1}

        old_rank = verdict_rank.get(old, -1)
        new_rank = verdict_rank.get(new, -1)

        if new_rank < old_rank:
            regressions.append({"group": gi, "old": old, "new": new})
        elif new_rank > old_rank:
            improvements.append({"group": gi, "old": old, "new": new})
        else:
            unchanged.append({"group": gi, "old": old, "new": new})

    return {
        "status_flow": status_flow,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "regression_count": len(regressions),
        "improvement_count": len(improvements),
        "unchanged_count": len(unchanged),
        "has_regressions": len(regressions) > 0,
        "has_improvements": len(improvements) > 0,
    }


def reverify_to_sexpr(result: dict) -> str:
    return format_sexpr(SExpr("reverify-result",
        SExpr("regression-count", ".", result["regression_count"]),
        SExpr("improvement-count", ".", result["improvement_count"]),
        SExpr("unchanged-count", ".", result["unchanged_count"]),
        SExpr("has-regressions", ".", "#t" if result["has_regressions"] else "#f"),
        SExpr("has-improvements", ".", "#t" if result["has_improvements"] else "#f"),
        SExpr("regressions",
            *[SExpr("regression",
                SExpr("group", ".", r["group"]),
                SExpr("old", ".", r["old"]),
                SExpr("new", ".", r["new"]))
              for r in result["regressions"]]),
        SExpr("improvements",
            *[SExpr("improvement",
                SExpr("group", ".", i["group"]),
                SExpr("old", ".", i["old"]),
                SExpr("new", ".", i["new"]))
              for i in result["improvements"]]),
    ))


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    # Настоящий CLI (этап 12 run_pipeline.sh):
    #   python3 reverify.py <verdicts_processed.json> <patch_diffs.json|patch_plan.sexpr> <reverify_result.json>
    if len(sys.argv) < 4:
        print("Usage: python3 reverify.py <verdicts_processed.json> "
              "<patch_diffs.json|patch_plan.sexpr> <reverify_result.json>", file=sys.stderr)
        sys.exit(1)
    verdicts_path, patches_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        with open(verdicts_path, encoding="utf-8") as f:
            verdicts = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"ОШИБКА: не удалось прочитать {verdicts_path}: {exc}", file=sys.stderr)
        sys.exit(2)
    if isinstance(verdicts, dict):
        verdicts = verdicts.get("verdicts", [])

    def _gid(v):
        oi = v.get("original_index")
        if oi is None:
            oi = v.get("claim_id")
        return oi

    original = {}
    for v in verdicts:
        gid = _gid(v)
        if gid is None:
            continue
        original[str(gid)] = v.get("verdict", "UNKNOWN")

    # Загрузка патчей (тот же формат, что у consistency_check)
    try:
        raw = Path(patches_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ОШИБКА: не удалось прочитать {patches_path}: {exc}", file=sys.stderr)
        sys.exit(2)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        data = raw

    from consistency_check import extract_patches
    patches = extract_patches(data)

    def _patch_group(patch):
        g = patch.get("group")
        if isinstance(g, SExpr):
            g = g.args[0] if g.args else None
        return g

    new_verdicts = {}
    for p in patches:
        gi = _patch_group(p)
        if gi is None:
            continue
        new_verdicts[str(gi)] = p.get("verdict", "UNKNOWN")

    result = compare_verdicts(original, new_verdicts)
    result["_meta"] = {
        "verdicts_source": verdicts_path,
        "patches_source": patches_path,
        "n_original": len(original),
        "n_patches": len(patches),
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ reverify: регрессий {result['regression_count']}, "
          f"улучшений {result['improvement_count']}, без изменений {result['unchanged_count']}")
    print(f"   результат: {out_path}")
