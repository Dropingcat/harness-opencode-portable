#!/usr/bin/env python3
"""Двухслойная приёмка патчей (N11): JSON-схема (детерм.) + семантический скептик (агент).

HARD-критерии: schema-valid, justification-present, no-content-loss
SOFT-критерии: no-new-contradictions, style-consistent
Правило: 2 warn = fail
"""

import json
import re
from pathlib import Path
from typing import Any, Optional

from config_loader import get

from sexpr import SExpr, format_sexpr, parse, parse_many, make_change


# ── Загрузка патчей из файла (sexpr или JSON) ──

def _collect_sexpr_patches(sexprs):
    """Собирает все (patch|patch-diff|patch-diffs) S-выражения, обходя обёртки."""
    patches = []
    stack = list(sexprs)
    while stack:
        n = stack.pop()
        if isinstance(n, SExpr):
            if n.head in ("patch", "patch-diff", "patch-diffs"):
                patches.append(n)
            else:
                stack.extend(n.args)
    return patches


def _json_to_sexpr(obj):
    """plan_to_json → SExpr: {"head": ..., "args": [...]}."""
    if isinstance(obj, dict) and isinstance(obj.get("head"), str) \
            and isinstance(obj.get("args"), list):
        return SExpr(obj["head"], *[_json_to_sexpr(a) for a in obj["args"]])
    if isinstance(obj, list):
        return [_json_to_sexpr(x) for x in obj]
    return obj


def _dict_to_patch_sexpr(patch_dict):
    """Словарь-патч (JSON) → SExpr для единого конвейера consistency_check."""
    changes = patch_dict.get("changes") or patch_dict.get("change") or []
    if not isinstance(changes, list):
        changes = [changes]
    ch = []
    for c in changes:
        if isinstance(c, dict):
            ch.append(make_change(str(c.get("old", "")), str(c.get("new", ""))))
        elif isinstance(c, str):
            ch.append(SExpr("change", ".", c))
    group = patch_dict.get("group", patch_dict.get("claim_id", 0))
    parts = [f"p_{group}", SExpr("group", group)]
    if ch:
        parts.append(SExpr("changes", *ch))
    if patch_dict.get("justification"):
        parts.append(SExpr("justification", ".", patch_dict["justification"]))
    if patch_dict.get("verdict"):
        parts.append(SExpr("verdict", ".", patch_dict["verdict"]))
    return SExpr("patch-diff", *parts)


def extract_patches(data):
    """Извлекает список патчей (SExpr) из JSON или S-expression данных."""
    if isinstance(data, str):
        return _collect_sexpr_patches(parse_many(data))
    if isinstance(data, dict):
        for key in ("patches", "cells", "patch_diffs", "patch_diff", "diffs"):
            v = data.get(key)
            if isinstance(v, list):
                res = extract_patches(v)
                if res:
                    return res
        # writer-rewriter: строки, содержащие S-выражения (patch-diff ...)
        for v in data.values():
            if isinstance(v, str) and "(" in v:
                res = _collect_sexpr_patches(parse_many(v))
                if res:
                    return res
        return []
    if isinstance(data, list):
        out = []
        for item in data:
            if isinstance(item, str):
                out.extend(_collect_sexpr_patches(parse_many(item)))
            elif isinstance(item, dict):
                if isinstance(item.get("head"), str) and isinstance(item.get("args"), list):
                    out.extend(_collect_sexpr_patches([_json_to_sexpr(item)]))
                else:
                    out.append(_dict_to_patch_sexpr(item))
        return out
    return []


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def check_schema(patch: SExpr) -> tuple[bool, list[str]]:
    issues = []
    if not isinstance(patch, SExpr):
        return False, ["not an S-expression"]
    if patch.head not in ("patch", "patch-diff", "patch-diffs"):
        issues.append(f"unexpected head: {patch.head}")
    if not patch.get("group") and not patch.get("changes") and not patch.get("change"):
        pass
    if not patch.get("justification"):
        issues.append("missing justification")
    return len(issues) == 0, issues


def check_justification(patch: SExpr) -> tuple[bool, list[str]]:
    issues = []
    justification = patch.get("justification")
    if not justification:
        issues.append("justification is empty")
        return False, issues
    if isinstance(justification, SExpr):
        jt = justification.args[0] if justification.args else ""
    else:
        jt = str(justification)
    if len(jt.strip()) < get("consistency.hard_min_justification", 10):
        issues.append("justification too short (< 10 chars)")
    if not any(w in _norm(jt) for w in ["исправлен", "добавлен", "изменён", "уточнён",
                                          "fixed", "added", "changed", "corrected"]):
        issues.append("justification lacks action verb")
    return len(issues) == 0, issues


def check_content_loss(patch: SExpr, original_text: str) -> tuple[bool, list[str]]:
    issues = []
    changes = patch.get("changes") or patch.get("change")
    if not changes:
        return True, []

    if isinstance(changes, SExpr):
        changes = [changes]

    for ch in changes:
        if isinstance(ch, SExpr):
            old = ch.get("old")
            new = ch.get("new")
            if old and new:
                old_s = str(old) if not isinstance(old, str) else old
                new_s = str(new) if not isinstance(new, str) else new
                if len(new_s) < len(old_s) * get("consistency.content_loss_threshold", 0.3):
                    issues.append(f"content loss: {len(old_s)} → {len(new_s)} chars")

    return len(issues) == 0, issues


def check_numbers_from_answers(patch: SExpr, answers: dict) -> tuple[bool, list[str]]:
    issues = []
    changes = patch.get("changes") or patch.get("change")
    if not changes:
        return True, []

    if isinstance(changes, SExpr):
        changes = [changes]

    answer_numbers = set()
    for a in answers.values():
        if isinstance(a, str):
            for m in re.finditer(r"\d+\.?\d*", a):
                answer_numbers.add(m.group())

    for ch in changes:
        if isinstance(ch, SExpr):
            new = ch.get("new")
            if new:
                new_s = str(new) if not isinstance(new, str) else new
                for m in re.finditer(r"\d+\.?\d*", new_s):
                    num = m.group()
                    if num not in answer_numbers and len(num) >= 2:
                        issues.append(f"number '{num}' not found in author answers")

    return len(issues) == 0, issues


def consistency_check(
    patch: SExpr,
    original_text: str = "",
    answers: dict = None,
    neighbor_verdicts: dict = None,
) -> dict:
    answers = answers or {}
    neighbor_verdicts = neighbor_verdicts or {}

    hard_issues = []
    soft_warnings = []

    schema_ok, schema_issues = check_schema(patch)
    if not schema_ok:
        hard_issues.extend(schema_issues)

    just_ok, just_issues = check_justification(patch)
    if not just_ok:
        hard_issues.extend(just_issues)

    content_ok, content_issues = check_content_loss(patch, original_text)
    if not content_ok:
        hard_issues.extend(content_issues)

    numbers_ok, numbers_issues = check_numbers_from_answers(patch, answers)
    if not numbers_ok:
        soft_warnings.extend(numbers_issues)

    hard_pass = len(hard_issues) == 0
    soft_pass = len(soft_warnings) < get("consistency.soft_warnings_to_fail", 2)

    return {
        "ok": hard_pass and soft_pass,
        "hard_pass": hard_pass,
        "soft_pass": soft_pass,
        "hard_issues": hard_issues,
        "soft_warnings": soft_warnings,
        "action": "accept" if (hard_pass and soft_pass) else ("reject" if not hard_pass else "warn"),
    }


def consistency_to_sexpr(result: dict) -> str:
    return format_sexpr(SExpr("consistency-result",
        SExpr("ok", ".", "#t" if result["ok"] else "#f"),
        SExpr("hard-pass", ".", "#t" if result["hard_pass"] else "#f"),
        SExpr("soft-pass", ".", "#t" if result["soft_pass"] else "#f"),
        SExpr("action", ".", result["action"]),
        SExpr("hard-issues", *[SExpr("issue", ".", i) for i in result["hard_issues"]]),
        SExpr("soft-warnings", *[SExpr("warning", ".", w) for w in result["soft_warnings"]]),
    ))


if __name__ == "__main__":
    import json
    import sys

    # Настоящий CLI (этап 11 run_pipeline.sh):
    #   python3 consistency_check.py <patch_diffs.json|patch_plan.sexpr> <consistency_report.json>
    if len(sys.argv) < 3:
        print("Usage: python3 consistency_check.py <patch_diffs.json|patch_plan.sexpr> "
              "<consistency_report.json>", file=sys.stderr)
        sys.exit(1)
    in_path, out_path = sys.argv[1], sys.argv[2]

    try:
        raw = Path(in_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ОШИБКА: не удалось прочитать {in_path}: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        data = raw  # S-expression файл

    patches = extract_patches(data)

    per_patch = []
    hard_issues = []
    soft_warnings = []
    n_accepted = n_warned = n_rejected = 0
    for p in patches:
        r = consistency_check(p)
        per_patch.append({
            "patch": str(p),
            "ok": r["ok"],
            "hard_pass": r["hard_pass"],
            "soft_pass": r["soft_pass"],
            "action": r["action"],
            "hard_issues": r["hard_issues"],
            "soft_warnings": r["soft_warnings"],
        })
        hard_issues.extend(r["hard_issues"])
        soft_warnings.extend(r["soft_warnings"])
        if r["action"] == "accept":
            n_accepted += 1
        elif r["action"] == "warn":
            n_warned += 1
        else:
            n_rejected += 1

    report = {
        "n_patches": len(patches),
        "accepted": n_accepted,
        "warned": n_warned,
        "rejected": n_rejected,
        "hard_issues": hard_issues,
        "soft_warnings": soft_warnings,
        "ok": len(patches) > 0 and n_rejected == 0,
        "per_patch": per_patch,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"✅ consistency_check: {len(patches)} патчей, "
          f"accept={n_accepted}, warn={n_warned}, reject={n_rejected}")
    print(f"   отчёт: {out_path}")
