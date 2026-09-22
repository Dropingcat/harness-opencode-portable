#!/usr/bin/env python3
"""Статическая проверка границ доменов (У5).

Проверяет через ast (без runtime-импортов), что:
  1. writer-домен (resercher/scripts/writer/*.py, кроме test_*) НЕ импортирует
     verification-домен: никаких импортов, содержащих "claimeai",
     "projects/claimeai" или "verdict_schemas".
  2. verification-домен (claimeai-service/scripts/*.py) НЕ импортирует
     writer-домен: никаких импортов, содержащих "resercher".

Возвращает список нарушений; пустой список = границы чистые, тест проходит.
"""

import ast
from pathlib import Path

WRITER_DIR = Path(__file__).resolve().parent
VERIFIER_DIR = Path("/home/orangepi/projects/claimeai-service/scripts")

# Маркеры verification-домена, запрещённые в writer-импортах.
VERIFIER_MARKERS = ("claimeai", "projects/claimeai", "verdict_schemas")
# Маркер writer-домена, запрещённый в verifier-импортах.
WRITER_MARKER = "resercher"


def _collect_import_strings(path: Path) -> list[str]:
    """Возвращает строки всех import-операций из файла (без runtime-выполнения)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                if mod:
                    imports.append(f"{mod}.{alias.name}")
                else:
                    imports.append(alias.name)
    return imports


def _scan_dir(directory: Path, skip_prefix: str) -> list[tuple[Path, str]]:
    """Пройтись по *.py (кроме test_*) и вернуть (файл, импорт) пары."""
    pairs: list[tuple[Path, str]] = []
    if not directory.is_dir():
        return pairs
    for py in sorted(directory.glob("*.py")):
        if py.name.startswith(skip_prefix):
            continue
        for imp in _collect_import_strings(py):
            pairs.append((py, imp))
    return pairs


def check_writer_does_not_import_verifier() -> list[str]:
    """writer-модули не импортируют verification-домен."""
    violations: list[str] = []
    for path, imp in _scan_dir(WRITER_DIR, skip_prefix="test_"):
        lowered = imp.lower()
        if any(marker in lowered for marker in VERIFIER_MARKERS):
            violations.append(
                f"{path.name}: запрещённый импорт verification-домена: {imp!r}"
            )
    return violations


def check_verifier_does_not_import_writer() -> list[str]:
    """verification-модули не импортируют writer-домен."""
    violations: list[str] = []
    for path, imp in _scan_dir(VERIFIER_DIR, skip_prefix="test_"):
        lowered = imp.lower()
        if WRITER_MARKER in lowered:
            violations.append(
                f"{path.name}: запрещённый импорт writer-домена: {imp!r}"
            )
    return violations


def check_module_boundaries() -> list[str]:
    violations: list[str] = []
    violations.extend(check_writer_does_not_import_verifier())
    violations.extend(check_verifier_does_not_import_writer())
    return violations


def test_module_boundaries():
    violations = check_module_boundaries()
    assert violations == [], (
        "Нарушения границ доменов (verification / writer):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_writer_dir_exists():
    assert WRITER_DIR.is_dir(), f"writer-каталог не найден: {WRITER_DIR}"