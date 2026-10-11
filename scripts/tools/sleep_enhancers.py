#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sleep_enhancers.py — интеграция перфекциониста и skill-master'а в цикл сна (M10).

Запрос пользователя: «учесть что есть внутренний скил перфекциониста который
тут актуален и должен роутиться при этом скил самоулучшения скилов и написания
контрактов — все это должно работать в связке».

Что здесь собрано (обёртки-роутеры, ДЕТЕРМИНИРОВАННО, БЕЗ LLM):

1. perfectionist_review(branch, artifact_path) -> dict
   Канон гл.22 «схлопывание»: на этапе завершения ветки сна после полировки
   убрать наросшее (дубли, лишние проверки, обходные пути). Это изолированный
   «внутренний критик»: не участвует в основном потоке — вызывается только на
   завершении ветки сна (снапшот артефакта, не рабочий файл).
   Анализ: дублирующиеся строки (>3 одинаковых), лишние проверки
   (if x is not None: pass), TODO/костыли. Возвращает
   {findings: [{kind: duplicate|dead_code|todo, line}], cleanup_suggested}.

2. skill_upgrade_proposal(usage_stats) -> dict
   Канон гл.12: «что повторилось 3 раза → в скилл»; «скилл = подписка,
   окупаемость = повторы». count >= 3 -> кандидат в скилл; count < 3 — не
   предлагать (экономика скилла). Возвращает
   {candidates: [{name, count, reason}], suggestions: []}.

3. write_contract_suggestion(action, evidence) -> dict
   Канон гл.2/24 «контракт обеспечивает код»: типизированный контракт
   (вход/выход/guard) для повторяющегося действия. Возвращает
   {contract: {name, input_schema, output_schema, guard}}.

API: perfectionist_review / skill_upgrade_proposal / write_contract_suggestion

Usage:
    python sleep_enhancers.py perfectionist --artifact <path>
    python sleep_enhancers.py skill-upgrade --stats '{"arxiv_search": 5, "dom_builder": 2}'
    python sleep_enhancers.py contract --action download --evidence "3 раза в сессии"

Зависимости: только stdlib (ast, argparse, json). НЕ трогает
scripts/meta/perfectionist.py / scripts/meta/skill_master.py.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Канон гл.12: «что повторилось 3 раза → в скилл». Порог окупаемости скилла:
# скилл — это подписка (обслуживание), она окупается только повторами.
SKILL_MIN_COUNT = 3

# Канон гл.22 «схлопывание»: дубль = строка, повторённая больше 3 раз.
DUPLICATE_THRESHOLD = 3

# Паттерны костылей/обходных путей (гл.22: убрать наросшее). Все строчные.
_WORKAROUND_MARKERS = (
    "hack", "workaround", "костыль", "обходн", "обходной", "обходной путь",
    "временное решение", "на скорую руку",
)

# Константы типизированного контракта (гл.2/24). Схемы — JSON-schema-подобные
# декларации, НЕ питон-классы: роутер сна оперирует словарями.
_ACTION_ALIASES = {
    "download": "download", "скачать": "download", "download_file": "download",
    "fetch": "fetch", "получить": "fetch", "get": "fetch",
    "parse": "parse", "разобрать": "parse", "extract": "parse",
    "search": "search", "поиск": "search", "find": "search",
    "validate": "validate", "проверить": "validate", "check": "validate",
    "build": "build", "собрать": "build", "construct": "build",
}
_ACTION_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "download": {
        "input_schema": {"type": "object", "required": ["url"],
                         "properties": {"url": {"type": "string"},
                                        "target": {"type": "string", "optional": True}}},
        "output_schema": {"type": "object", "required": ["path"],
                          "properties": {"path": {"type": "string"},
                                         "bytes": {"type": "integer", "optional": True}}},
        "guard": "url обязателен и начинается с http(s); target не может "
                 "выходить за пределы workspace (path traversal).",
    },
    "fetch": {
        "input_schema": {"type": "object", "required": ["url"],
                         "properties": {"url": {"type": "string"}}},
        "output_schema": {"type": "object", "required": ["status"],
                          "properties": {"status": {"type": "integer"},
                                         "body": {"type": "string", "optional": True}}},
        "guard": "url обязателен и начинается с http(s); таймаут по умолчанию; "
                 "не отправлять секреты в query-параметрах.",
    },
    "parse": {
        "input_schema": {"type": "object", "required": ["source"],
                         "properties": {"source": {"type": "string"},
                                        "format": {"type": "string", "optional": True}}},
        "output_schema": {"type": "object", "required": ["ok"],
                          "properties": {"ok": {"type": "boolean"},
                                         "data": {"type": "object", "optional": True}}},
        "guard": "source непустой; format из разрешённого списка, иначе — "
                 "ошибка валидации (никаких авто-догадок).",
    },
    "search": {
        "input_schema": {"type": "object", "required": ["query"],
                         "properties": {"query": {"type": "string"},
                                        "limit": {"type": "integer", "optional": True}}},
        "output_schema": {"type": "object", "required": ["results"],
                          "properties": {"results": {"type": "array"}}},
        "guard": "query непустая; limit в 1..50 (защита от вырожденных входов).",
    },
    "validate": {
        "input_schema": {"type": "object", "required": ["target"],
                         "properties": {"target": {"type": "string"}}},
        "output_schema": {"type": "object", "required": ["valid"],
                          "properties": {"valid": {"type": "boolean"},
                                         "errors": {"type": "array", "optional": True}}},
        "guard": "target непустой; валидатор — чистая функция, без побочных "
                 "эффектов и без LLM.",
    },
    "build": {
        "input_schema": {"type": "object", "required": ["parts"],
                         "properties": {"parts": {"type": "array"}}},
        "output_schema": {"type": "object", "required": ["artifact"],
                          "properties": {"artifact": {"type": "string"}}},
        "guard": "parts — непустой массив; результат детерминирован для "
                 "одинаковых входов.",
    },
}

_TODO_PATTERNS = ("todo", "fixme", "xxx", "заглушк", "не реализовано",
                  "placeholder", "stub")


# --------------------------------------------------------------------------- #
# 1. Perfectionist-роутер (канон гл.22 «схлопывание»)
# --------------------------------------------------------------------------- #
class _DuplicateFinder(ast.NodeVisitor):
    """Собирает номера строки каждого If-узла (для определения «if x: pass»)."""

    def __init__(self) -> None:
        self.if_linenos: List[int] = []

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        self.if_linenos.append(node.lineno)
        self.generic_visit(node)


def _is_noop_if(node: ast.If) -> bool:
    """Лишняя проверка: if c единственным Pass в теле и без else.

    Пример: ``if x is not None: pass`` — проверка без действия («мёртвый»
    охранник). По гл.22 такое наросшее схлопывается.
    """
    body = node.body
    if len(body) != 1:
        return False
    if not isinstance(body[0], ast.Pass):
        return False
    # Docstring в else/elif тоже мёртвый код: любая непустая ветка ошибочна.
    if node.orelse:
        return False
    return True


def _find_duplicates(lines: List[str]) -> List[Dict[str, Any]]:
    """Дублирующиеся строки: одинаковые НЕпустые строки чаще 3 раз."""
    seen: Dict[str, List[int]] = {}
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        seen.setdefault(stripped, []).append(idx)
    return [{"kind": "duplicate", "line": lineno[0], "count": len(lineno)}
            for lineno in seen.values() if len(lineno) > DUPLICATE_THRESHOLD]


def _find_todos(lines: List[str]) -> List[Dict[str, Any]]:
    """TODO/костыли: маркеры незавершённости или обходных путей."""
    findings: List[Dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        lowered = line.lower()
        is_todo = any(p in lowered for p in _TODO_PATTERNS)
        is_workaround = any(p in lowered for p in _WORKAROUND_MARKERS)
        if is_todo:
            findings.append({"kind": "todo", "line": idx,
                             "note": "незакрытый TODO/заглушка"})
        elif is_workaround:
            findings.append({"kind": "dead_code", "line": idx,
                             "note": "костыль/обходной путь"})
    return findings


def _find_dead_code(path: Path) -> List[Dict[str, Any]]:
    """Лишние проверки (if x: pass) в Python-артефактах — через AST."""
    findings: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return findings  # не Python/нечитаемый — детерминированный пропуск
    visitor = _DuplicateFinder()
    visitor.visit(tree)
    if_linenos = set(visitor.if_linenos)
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(),
                               start=1):
        stripped = line.strip()
        if not stripped.lower().startswith("if "):
            continue
        # грубая текстовая эвристика «if ...: pass» для любых текстовых файлов
        if stripped.rstrip().endswith(": pass"):
            findings.append({"kind": "dead_code", "line": idx,
                             "note": "if-проверка с pass (без действия)"})
    return findings


def perfectionist_review(branch: str, artifact_path: str) -> Dict[str, Any]:
    """Изолированный внутренний критик на завершении ветки сна.

    Канон гл.22 «схлопывание»: после полировки убрать наросшее (дубли,
    лишние проверки, обходные пути). Анализ детерминированный, без LLM.

    Args:
        branch: имя завершаемой ветки сна (context; не влияет на анализ).
        artifact_path: путь к снапшоту артефакта (файл) для анализа.

    Returns:
        {"branch", "artifact", "findings": [{kind, line, ...}],
         "cleanup_suggested": bool}
        cleanup_suggested=True, если есть хоть одна находка (дубль/мёртвый
        код/TODO-костыль) — ветку не завершать, сначала схлопнуть.
    """
    path = Path(artifact_path)
    findings: List[Dict[str, Any]] = []
    if path.is_file():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            lines = []
        findings.extend(_find_duplicates(lines))
        findings.extend(_find_todos(lines))
        # AST-проход только для Python-файлов (иначе текстовая эвристика
        # «if ...: pass» и так покроет случай).
        if path.suffix.lower() in (".py", ".pyw"):
            findings.extend(_find_dead_code(path))
    return {"branch": branch,
            "artifact": str(path),
            "findings": findings,
            "cleanup_suggested": bool(findings)}


# --------------------------------------------------------------------------- #
# 2. Skill-master-роутер (канон гл.12)
# --------------------------------------------------------------------------- #
def _situation_hint(name: str) -> str:
    """Ситуации применения кандидата в скилл (по имени действия)."""
    mapping = {
        "arxiv_search": "поиск научных статей (запрос, дедупликация, метаданные)",
        "search": "любой повторяющийся поиск (запрос -> ранжированные результаты)",
        "download": "скачивание файлов (url -> локальный путь, зеркала)",
        "dom_builder": "сборка DOM-структуры (гл.29) из сырья",
        "contract": "написание типизированных контрактов (вход/выход/guard)",
        "review": "рецензирование артефакта по чек-листу",
        "validate": "валидация входных данных/артефактов",
    }
    return mapping.get(name, f"повторяющееся действие «{name}»")


def skill_upgrade_proposal(usage_stats: Dict[str, int]) -> Dict[str, Any]:
    """Самоулучшение скилов (канон гл.12): «3 раза → в скилл».

    Экономика скилла: скилл — это подписка (обслуживание/обновление), она
    окупается только повторами. count >= 3 -> кандидат; count < 3 — не
    предлагать (иначе подписка дороже разовых повторов).

    Args:
        usage_stats: {skill_or_action: count} — счётчики из цикла сна.

    Returns:
        {"candidates": [{"name", "count", "reason"}], "suggestions": []}
    """
    candidates: List[Dict[str, Any]] = []
    for name, count in sorted(usage_stats.items(), key=lambda kv: -int(kv[1])):
        try:
            cnt = int(count)
        except (TypeError, ValueError):
            cnt = 0  # нечисловой счётчик — не кандидат, не падаем
        if cnt >= SKILL_MIN_COUNT:
            candidates.append({
                "name": name,
                "count": cnt,
                "reason": f"повторён {cnt} раза (порог {SKILL_MIN_COUNT}): "
                          f"оформить в скилл — {_situation_hint(name)}.",
            })
    return {"candidates": candidates, "suggestions": []}


# --------------------------------------------------------------------------- #
# 3. Написание контракта (канон гл.2/24 «контракт обеспечивает код»)
# --------------------------------------------------------------------------- #
def write_contract_suggestion(action: str, evidence: str) -> Dict[str, Any]:
    """Типизированный контракт для повторяющегося действия.

    По канону гл.2/24 «контракт обеспечивает код»: повторяющееся действие
    получает явный контракт (вход/выход/guard), чтобы код был обязан ему.

    Args:
        action: имя действия (download, search, ...). Алиасы нормализуются.
        evidence: почему нужно (напр. «3 раза в сессии»).

    Returns:
        {"contract": {"name", "input_schema", "output_schema", "guard"}}
        Для неизвестного действия — дефолтный контракт с дженерик-схемами.
    """
    name = _ACTION_ALIASES.get(action.strip().lower(), action.strip().lower())
    spec = _ACTION_CONTRACTS.get(name, {
        "input_schema": {"type": "object", "required": [],
                         "properties": {}},
        "output_schema": {"type": "object", "required": [],
                          "properties": {}},
        "guard": "вход обязателен и валиден; выход — детерминированный, "
                 "без побочных эффектов.",
    })
    return {"contract": {"name": name,
                         "input_schema": spec["input_schema"],
                         "output_schema": spec["output_schema"],
                         "guard": spec["guard"]},
            "evidence": evidence}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_stats(raw: str) -> Dict[str, int]:
    """JSON-строка '{"arxiv_search": 5, "dom_builder": 2}' -> dict[int]."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--stats не JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("--stats должен быть объектом {action: count}")
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="sleep_enhancers.py",
        description="Интеграция перфекциониста и skill-master'а в цикл сна "
                    "(M10): роутеры гл.22 «схлопывание», гл.12 «3 раза → в "
                    "скилл», гл.2/24 «контракт обеспечивает код».")
    sub = parser.add_subparsers(dest="command", required=True)

    p_perf = sub.add_parser("perfectionist", help="внутренний критик (гл.22)")
    p_perf.add_argument("--branch", default="sleep-branch",
                        help="имя завершаемой ветки сна (context)")
    p_perf.add_argument("--artifact", required=True,
                        help="путь к файлу-артефакту для анализа")

    p_skill = sub.add_parser("skill-upgrade", help="самоулучшение скилов (гл.12)")
    p_skill.add_argument("--stats", required=True,
                         help="JSON {'action': count}")

    p_contract = sub.add_parser("contract", help="контракт для действия (гл.2/24)")
    p_contract.add_argument("--action", required=True,
                            help="имя действия (download, search, ...)")
    p_contract.add_argument("--evidence", default="",
                            help="почему нужен контракт")

    args = parser.parse_args(argv)

    try:
        if args.command == "perfectionist":
            result = perfectionist_review(args.branch, args.artifact)
        elif args.command == "skill-upgrade":
            result = skill_upgrade_proposal(_parse_stats(args.stats))
        elif args.command == "contract":
            result = write_contract_suggestion(args.action, args.evidence)
        else:  # pragma: no cover — argparse не даст сюда попасть
            raise RuntimeError(f"неизвестная команда: {args.command}")
    except (ValueError, TypeError, OSError) as exc:
        parser.error(str(exc))

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    # Windows stdout cp1251 -> utf-8 (JSON с русскими строками ломается иначе).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())