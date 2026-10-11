#!/usr/bin/env python3
"""sleep_report_check.py — JSON-schema валидация отчёта сна (W13-T2).

Проверяет отчёт сна, сгенерированный sleep_git.run (W13-формат):

    {
      "task": "<task_id>",
      "baseline_tag": "baseline/<task>/<ts>",
      "timestamp": "<iso>",
      "simulated": false,
      "branches": [
        {"name": "fix/A", "status": "ok | failed | conflict | keep | false_ready | merged | created",
         "commits": ["<sha>"], "diffstat": {"files": int, "insertions": int, "deletions": int},
         "changed_files": ["<path>"]}
      ],
      "merged": ["<branch>"],
      "conflicts": [
        {"branch": "fix/B", "target": "main", "files": ["<path>"],
         "reason": "merge-tree exit 1", "kept": true}
      ],
      "restored_to": "baseline/<task>/<ts>",
      "lessons": [{"branch": "fix/B", "lesson": "конфликт: <файлы>", "target": ".l2_memory"}]
    }

Валидный отчёт -> exit 0, невалидный -> exit 1 (с перечнем нарушений).

Канон гл.24 (детерминированная проверка): схема жёсткая, без свободных
полей верхнего уровня; каждый branches[i] проверяется по своей подсхеме.

Usage:
    python sleep_report_check.py --report <path> [--schema <path>]
    python sleep_report_check.py --stdin
    python sleep_report_check.py --sample   # напечатать валидный образец и выйти 0
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# Допустимые классы статусов ветки (W13-T4 проверка 2 — только эти).
BRANCH_STATUSES = ("ok", "failed", "conflict", "keep", "false_ready",
                   "merged", "created")

_TAG_RE = re.compile(r"^baseline/[^/]+/\d{8}-\d{6}-\d{6}$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")

# Каноническая JSON-schema отчёта сна (W13-T2; расширяема через --schema).
REPORT_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "sleep_report",
    "type": "object",
    "required": ["task", "baseline_tag", "timestamp", "simulated", "branches",
                 "merged", "conflicts", "restored_to"],
    "additionalProperties": False,
    "properties": {
        "task": {"type": "string", "minLength": 1},
        "baseline_tag": {"type": "string", "pattern": "^baseline/"},
        "timestamp": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T"},
        "simulated": {"type": "boolean", "const": False},
        "branches": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "status", "commits", "diffstat",
                             "changed_files"],
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "status": {"enum": list(BRANCH_STATUSES)},
                    "commits": {"type": "array",
                                "items": {"type": "string",
                                          "pattern": "^[0-9a-f]{7,40}$"}},
                    "diffstat": {
                        "type": "object",
                        "required": ["files", "insertions", "deletions"],
                        "additionalProperties": False,
                        "properties": {
                            "files": {"type": "integer", "minimum": 0},
                            "insertions": {"type": "integer", "minimum": 0},
                            "deletions": {"type": "integer", "minimum": 0},
                        },
                    },
                    "changed_files": {"type": "array",
                                      "items": {"type": "string"}},
                },
            },
        },
        "merged": {"type": "array", "items": {"type": "string"}},
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["branch", "target", "files", "reason", "kept"],
                "additionalProperties": False,
                "properties": {
                    "branch": {"type": "string", "minLength": 1},
                    "target": {"type": "string", "minLength": 1},
                    "files": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string", "minLength": 1},
                    "kept": {"type": "boolean", "const": True},
                },
            },
        },
        "restored_to": {"type": ["string", "null"]},
        "lessons": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["branch", "lesson", "target"],
                "additionalProperties": False,
                "properties": {
                    "branch": {"type": "string"},
                    "lesson": {"type": "string"},
                    "target": {"type": "string"},
                },
            },
        },
    },
}


def _flatten_errors(errors: Any) -> List[str]:
    out: List[str] = []
    for e in errors:
        where = ".".join(str(p) for p in e.absolute_path) or "(root)"
        out.append(f"{where}: {e.message}")
    return out


def validate_report(data: Any, schema: Optional[Dict[str, Any]] = None
                    ) -> List[str]:
    """Детерминированная валидация отчёта по схеме. Возвращает нарушения [].

    Невалидная структура верхнего уровня -> single violation.
    """
    if not isinstance(data, dict):
        return ["отчёт должен быть JSON-объектом"]
    try:
        import jsonschema  # доступен в .venv (проверено W13)
    except ImportError:
        return _validate_manual(data, schema or REPORT_SCHEMA)
    errors = list(jsonschema.Draft202012Validator(schema or REPORT_SCHEMA)
                  .iter_errors(data))
    return _flatten_errors(errors)


# ------------------------------------------------------- fallback без jsonschema
def _validate_manual(data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Лёгкий ручной валидатор (когда jsonschema недоступен).

    Покрывает обязательные поля и основные типы; не дублирует всю мощь
    схемы, но достаточен для exit-кода и человекочитаемых нарушений.
    """
    violations: List[str] = []
    for field in ("task", "baseline_tag", "timestamp", "simulated",
                  "branches", "merged", "conflicts", "restored_to"):
        if field not in data:
            violations.append(f"(root): отсутствует обязательное поле '{field}'")
    if "task" in data and not isinstance(data["task"], str):
        violations.append("task: должен быть строкой")
    if "baseline_tag" in data and not (
            isinstance(data["baseline_tag"], str)
            and data["baseline_tag"].startswith("baseline/")):
        violations.append("baseline_tag: должен быть 'baseline/...'")
    if "simulated" in data and data.get("simulated") is not False:
        violations.append("simulated: должен быть false")
    if "branches" in data and not isinstance(data["branches"], list):
        violations.append("branches: должен быть списком")
    else:
        for i, b in enumerate(data.get("branches", [])):
            if not isinstance(b, dict):
                violations.append(f"branches[{i}]: должен быть объектом")
                continue
            if "status" not in b or b["status"] not in BRANCH_STATUSES:
                violations.append(
                    f"branches[{i}].status: недопустимый класс "
                    f"'{b.get('status')}' (ожидался один из {BRANCH_STATUSES})")
            if "diffstat" not in b or not isinstance(b["diffstat"], dict):
                violations.append(f"branches[{i}].diffstat: обязателен")
            if "commits" not in b or not isinstance(b["commits"], list):
                violations.append(f"branches[{i}].commits: должен быть списком")
            if "changed_files" not in b or not isinstance(b["changed_files"], list):
                violations.append(f"branches[{i}].changed_files: должен быть списком")
    if "conflicts" in data and not isinstance(data["conflicts"], list):
        violations.append("conflicts: должен быть списком")
    if "restored_to" in data and data.get("restored_to") is not None \
            and not isinstance(data["restored_to"], str):
        violations.append("restored_to: строка или null")
    return violations


# ---------------------------------------------------------------------- CLI
def _cmd_check(args: argparse.Namespace) -> int:
    if args.stdin:
        raw = sys.stdin.read()
        source = "<stdin>"
    else:
        path = Path(args.report)
        if not path.exists():
            print(f"FAIL: отчёт не найден: {path}", file=sys.stderr)
            return 1
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"FAIL: не удалось прочитать отчёт: {exc}", file=sys.stderr)
            return 1
        source = str(path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"FAIL: отчёт не JSON ({source}): {exc}", file=sys.stderr)
        return 1
    schema = None
    if args.schema:
        try:
            schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL: не удалось прочитать схему --schema: {exc}",
                  file=sys.stderr)
            return 1
    violations = validate_report(data, schema)
    if violations:
        print(f"FAIL: отчёт сна невалиден ({source}):")
        for v in violations[:50]:
            print(f"  - {v}")
        more = len(violations) - 50
        if more > 0:
            print(f"  ... и ещё {more}")
        return 1
    print(f"PASS: отчёт сна валиден ({source})")
    return 0


def _cmd_sample(args: argparse.Namespace) -> int:  # noqa: ARG001 — CLI-совместимость
    print(json.dumps(_sample_report(), ensure_ascii=False, indent=2))
    return 0


def _sample_report() -> Dict[str, Any]:
    return {
        "task": "nightly",
        "baseline_tag": "baseline/nightly/20261010-023000-000000",
        "timestamp": "2026-10-10T02:30:00.000000+00:00",
        "simulated": False,
        "branches": [
            {"name": "fix/RULE_REL_01",
             "status": "merged",
             "commits": ["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"],
             "diffstat": {"files": 2, "insertions": 10, "deletions": 3},
             "changed_files": ["scripts/tools/x.py", "docs/x.md"]},
            {"name": "fix/RULE_CMP_01",
             "status": "conflict",
             "commits": ["b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b01"],
             "diffstat": {"files": 1, "insertions": 4, "deletions": 0},
             "changed_files": ["scripts/meta/y.py"]},
        ],
        "merged": ["fix/RULE_REL_01"],
        "conflicts": [
            {"branch": "fix/RULE_CMP_01", "target": "main",
             "files": ["scripts/meta/y.py"],
             "reason": "merge-tree exit 1", "kept": True},
        ],
        "restored_to": "baseline/nightly/20261010-023000-000000",
        "lessons": [
            {"branch": "fix/RULE_CMP_01",
             "lesson": "конфликт: scripts/meta/y.py",
             "target": ".l2_memory"},
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        prog="sleep_report_check.py",
        description="JSON-schema валидация отчёта сна (W13-T2). exit 0/1.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="проверить отчёт")
    p_check.add_argument("--report", default=None,
                         help="путь к отчёту сна (или --stdin)")
    p_check.add_argument("--stdin", action="store_true",
                         help="читать отчёт из stdin")
    p_check.add_argument("--schema", default=None,
                         help="путь к JSON-schema (по умолчанию встроенная)")
    p_check.set_defaults(fn=_cmd_check)

    p_sample = sub.add_parser("sample", help="напечатать валидный образец")
    p_sample.set_defaults(fn=_cmd_sample)

    args = parser.parse_args(argv)
    if args.cmd == "check" and not args.report and not args.stdin:
        parser.error("check: требуется --report <path> или --stdin")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())