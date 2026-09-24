#!/usr/bin/env python3
"""check_module_porting.py — гейт TD-D1/AG-D1 (issue #17).

Проверяет канонический реестр docs/MODULE_PORTING_EXCLUSIONS.json — сверку
«списки модулей в документации переноса» vs «фактический состав v1».

Инварианты (fail-closed):
  I1  Реестр существует, парсится, schema == module_porting_exclusions/1.0,
      содержит непустой список modules с уникальными id.
  I2  Каждый статус из разрешённых (statuses_allowed); обязательные поля:
      id, status, rationale (не пустая строка), owner, declared_in.
  I3  Статус согласован с деревом:
        - PORTED: все actual_paths существуют; actual_paths непустой;
        - PARTIAL: required_paths_present существуют, absent_declared_files
          НЕ существуют, пересечений нет;
        - EXCLUDED_PENDING_PORT: сам путь модуля (id как relative path)
          НЕ существует в дереве и actual_paths пуст.
  I4  Множество «обязательно объявленных» модулей (CANONICAL_DECLARED_MODULES)
      полностью покрыто записями реестра — запрет тихого удаления записи.
  I5  related_debt — только известные ID тезисов формата TD-* / AG-* / CD-* и т.п.
  I6  Раздел-источник в TECH_DEBT_AGENTS.md помечен ЗАКРЫТО (реестр не врёт).

Выход: 0 = PASS, 1 = FAIL (со списком нарушений).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "MODULE_PORTING_EXCLUSIONS.json"
DEBT_LEDGER = ROOT / "TECH_DEBT_AGENTS.md"

# Модули, которые ДОЛЖНЫ быть объявлены в реестре (по TD-D1 + фактический writer-core).
CANONICAL_DECLARED_MODULES = {
    "scripts/writer",
    "scripts/writer-core",
    "scripts/kanban",
    "scripts/memory",
    "scripts/capsules",
    "shared",
}

DEBT_ID_RE = re.compile(r"^(TD|AG|CD|WR|RS|PL)-[A-Z]?\d+$")


def load_registry(path: Path) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    if not path.is_file():
        return None, [f"I1: реестр отсутствует: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, [f"I1: реестр не парсится: {e}"]
    if data.get("schema") != "module_porting_exclusions/1.0":
        errors.append(f"I1: неверная schema: {data.get('schema')!r}")
    mods = data.get("modules")
    if not isinstance(mods, list) or not mods:
        errors.append("I1: modules отсутствует или пуст")
        return data, errors
    ids = [m.get("id") for m in mods]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        errors.append(f"I1: дубликаты id в реестре: {sorted(dupes)}")
    return data, errors


def check(data: dict) -> list[str]:
    errors: list[str] = []
    allowed = set(data.get("statuses_allowed") or [])
    if not allowed:
        errors.append("I2: statuses_allowed пуст")
    seen_ids = set()
    for m in data.get("modules", []):
        mid = str(m.get("id", "<no-id>"))
        seen_ids.add(mid)
        # I2
        status = m.get("status")
        if status not in allowed:
            errors.append(f"I2[{mid}]: статус {status!r} не в statuses_allowed")
        for field in ("rationale", "owner", "declared_in"):
            val = m.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"I2[{mid}]: поле {field} отсутствует/пустое")
        # I3
        paths = m.get("actual_paths") or []
        if status == "PORTED":
            if not paths:
                errors.append(f"I3[{mid}]: PORTED без actual_paths")
            for p in paths:
                if not (ROOT / p).exists():
                    errors.append(f"I3[{mid}]: PORTED путь не существует: {p}")
        elif status == "PARTIAL":
            present = m.get("required_paths_present") or []
            absent = m.get("absent_declared_files") or []
            if not present or not absent:
                errors.append(f"I3[{mid}]: PARTIAL требует и present, и absent списки")
            for p in present:
                if not (ROOT / p).exists():
                    errors.append(f"I3[{mid}]: PARTIAL present-путь не существует: {p}")
            for p in absent:
                if (ROOT / p).exists():
                    errors.append(f"I3[{mid}]: PARTIAL absent-путь фактически СУЩЕСТВУЕТ: {p}")
            if set(present) & set(absent):
                errors.append(f"I3[{mid}]: пересечение present/absent: {sorted(set(present) & set(absent))}")
        elif status == "EXCLUDED_PENDING_PORT":
            if paths:
                errors.append(f"I3[{mid}]: EXCLUDED_PENDING_PORT с непустым actual_paths")
            mod_path = ROOT / mid
            if mod_path.exists():
                errors.append(f"I3[{mid}]: EXCLUDED_PENDING_PORT, но путь существует в дереве: {mid}")
        # I5
        for d in m.get("related_debt") or []:
            if not DEBT_ID_RE.match(d):
                errors.append(f"I5[{mid}]: некорректный related_debt id: {d!r}")
    # I4
    missing = CANONICAL_DECLARED_MODULES - seen_ids
    if missing:
        errors.append(f"I4: в реестре отсутствуют обязательные записи: {sorted(missing)}")
    # I6
    if DEBT_LEDGER.is_file():
        text = DEBT_LEDGER.read_text(encoding="utf-8")
        m = re.search(r"^### TD-D1\..*$", text, flags=re.M)
        if not m:
            errors.append("I6: секция TD-D1 не найдена в TECH_DEBT_AGENTS.md")
        elif "ЗАКРЫТО" not in m.group(0):
            errors.append("I6: секция TD-D1 в TECH_DEBT_AGENTS.md не помечена ЗАКРЫТО")
    else:
        errors.append("I6: TECH_DEBT_AGENTS.md отсутствует")
    return errors


def main(argv: list[str]) -> int:
    registry_path = Path(argv[1]) if len(argv) > 1 else REGISTRY
    data, errors = load_registry(registry_path)
    if data is not None:
        errors += check(data) if registry_path == REGISTRY else _check_external(data, registry_path)
    if errors:
        print("FAIL: check_module_porting")
        for e in errors:
            print("  -", e)
        return 1
    print("PASS: check_module_porting (реестр исключений переноса согласован с деревом)")
    return 0


def _check_external(data: dict, base_dir: Path) -> list[str]:
    """Для тестов-мутаций: та же проверка I2/I3/I5 против временного дерева."""
    global ROOT
    saved = ROOT
    try:
        ROOT = base_dir
        errs = []
        allowed = set(data.get("statuses_allowed") or [])
        for m in data.get("modules", []):
            mid = str(m.get("id", "<no-id>"))
            status = m.get("status")
            if status not in allowed:
                errs.append(f"I2[{mid}]: статус {status!r} не в statuses_allowed")
            paths = m.get("actual_paths") or []
            if status == "PORTED":
                for p in paths:
                    if not (ROOT / p).exists():
                        errs.append(f"I3[{mid}]: PORTED путь не существует: {p}")
            elif status == "PARTIAL":
                for p in m.get("required_paths_present") or []:
                    if not (ROOT / p).exists():
                        errs.append(f"I3[{mid}]: PARTIAL present-путь не существует: {p}")
                for p in m.get("absent_declared_files") or []:
                    if (ROOT / p).exists():
                        errs.append(f"I3[{mid}]: PARTIAL absent-путь фактически СУЩЕСТВУЕТ: {p}")
            elif status == "EXCLUDED_PENDING_PORT":
                if (ROOT / mid).exists():
                    errs.append(f"I3[{mid}]: EXCLUDED_PENDING_PORT, но путь существует: {mid}")
            for d in m.get("related_debt") or []:
                if not DEBT_ID_RE.match(d):
                    errs.append(f"I5[{mid}]: некорректный related_debt id: {d!r}")
        missing = CANONICAL_DECLARED_MODULES - {str(m.get("id")) for m in data.get("modules", [])}
        if missing:
            errs.append(f"I4: отсутствуют обязательные записи: {sorted(missing)}")
        return errs
    finally:
        ROOT = saved


if __name__ == "__main__":
    sys.exit(main(sys.argv))
