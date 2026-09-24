#!/usr/bin/env python3
"""check_legacy_transport.py — гейт TD-D6/AG-D6 (issue #18).

Фиксация «semantic launcher leakage»: все модули mcp/, запускающие прямой
`opencode run` (legacy CLI transport), обязаны быть объявлены в каноническом
реестре docs/LEGACY_TRANSPORT_REGISTRY.json и нести машинно-читаемый токен
транспорта `opencode_cli_legacy`. Миграция на plugin semantic.execute — только
после live-сертификации P5 (NEXT_PHASE_PLAN.md); до неё реестр закрывает путь
для «молчаливой» протечки нового legacy-модуля.

Инварианты (fail-closed):
  I1  Реестр существует, парсится, schema == legacy_transport_registry/1.0,
      canonical_transport_token == "opencode_cli_legacy", modules непустой,
      id уникальны.
  I2  Каждая запись имеет непустые поля id, transport, declaration, rationale,
      owner; transport == каноническому токену.
  I3  Каждый объявленный модуль существует и содержит декларацию токена
      (строка вида `<NAME> = "opencode_cli_legacy"` для поля declaration)
      и сам токен.
  I4  Полнота дерева: каждый .py в mcp/launchers/ и mcp/coder_router_server.py,
      использующий legacy-вызов (`"run", "--pure"` / `from _runner import`),
      объявлен в реестре — запрет тихого добавления new leakage без фиксации.
  I5  related_debt — только известные ID тезисов формата TD-* / AG-* и т.п.;
      каждая запись связана с TD-D6 или AG-D6.
  I6  Раздел TD-D6 в TECH_DEBT_AGENTS.md помечен ЗАКРЫТО (реестр не врёт).

Выход: 0 = PASS, 1 = FAIL (со списком нарушений).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "LEGACY_TRANSPORT_REGISTRY.json"
DEBT_LEDGER = ROOT / "TECH_DEBT_AGENTS.md"

CANONICAL_TOKEN = "opencode_cli_legacy"
SCHEMA = "legacy_transport_registry/1.0"
REQUIRED_FIELDS = ("id", "transport", "declaration", "rationale", "owner")
DEBT_ID_RE = re.compile(r"^(TD|AG|CD|WR|RS|PL)-[A-Z]?\d+$")
# Признаки прямого legacy-вызова opencode run внутри модуля.
LEGACY_USAGE_RE = re.compile(r'"run",\s*"--pure"|from\s+_runner\s+import')


def load_registry(path: Path) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    if not path.is_file():
        return None, [f"I1: реестр отсутствует: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, [f"I1: реестр не парсится: {e}"]
    if data.get("schema") != SCHEMA:
        errors.append(f"I1: неверная schema: {data.get('schema')!r}")
    if data.get("canonical_transport_token") != CANONICAL_TOKEN:
        errors.append(
            f"I1: canonical_transport_token != {CANONICAL_TOKEN!r}: {data.get('canonical_transport_token')!r}"
        )
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
    seen_ids: set[str] = set()

    for m in data.get("modules", []):
        mid = str(m.get("id", "<no-id>"))
        seen_ids.add(mid)

        # I2: обязательные поля + канонический transport
        for f in REQUIRED_FIELDS:
            v = m.get(f)
            if not isinstance(v, str) or not v.strip():
                errors.append(f"I2: {mid}: поле {f!r} отсутствует или пусто")
        if m.get("transport") not in (None, "", CANONICAL_TOKEN) and m.get("transport"):
            errors.append(
                f"I2: {mid}: transport={m.get('transport')!r} != каноническому {CANONICAL_TOKEN!r}"
            )

        decl = m.get("declaration")
        # I3: файл существует, содержит токен и декларацию
        fp = ROOT / mid
        if not fp.is_file():
            errors.append(f"I3: {mid}: модуль отсутствует в дереве")
            continue
        src = fp.read_text(encoding="utf-8")
        if CANONICAL_TOKEN not in src:
            errors.append(f"I3: {mid}: нет токена {CANONICAL_TOKEN!r} в исходнике")
        if isinstance(decl, str) and decl.strip():
            decl_re = re.compile(
                rf"^{re.escape(decl)}\s*=\s*[\"']{re.escape(CANONICAL_TOKEN)}[\"']", re.M
            )
            if not decl_re.search(src):
                errors.append(
                    f"I3: {mid}: декларация {decl} = \"{CANONICAL_TOKEN}\" не найдена в файле"
                )

        # I5: related_debt — валидные ID и обязательная связь с TD-D6/AG-D6
        rel = m.get("related_debt", [])
        if not isinstance(rel, list):
            errors.append(f"I5: {mid}: related_debt не список")
            rel = []
        bad = [r for r in rel if not DEBT_ID_RE.match(str(r))]
        if bad:
            errors.append(f"I5: {mid}: недопустимые ID в related_debt: {bad}")
        if not ({"TD-D6", "AG-D6"} & set(map(str, rel))):
            errors.append(f"I5: {mid}: related_debt не связан с TD-D6/AG-D6")

    # I4: полнота — ни один legacy-модуль не обязан остаться необъявленным
    candidates = sorted(set((ROOT / "mcp" / "launchers").glob("*.py")))
    router = ROOT / "mcp" / "coder_router_server.py"
    if router.is_file():
        candidates.append(router)
    for cp in candidates:
        rel_path = cp.relative_to(ROOT).as_posix()
        src = cp.read_text(encoding="utf-8")
        uses_legacy = bool(LEGACY_USAGE_RE.search(src)) or (
            rel_path == "mcp/coder_router_server.py" and CANONICAL_TOKEN in src
        )
        if uses_legacy and rel_path not in seen_ids:
            errors.append(
                f"I4: модуль {rel_path} использует legacy `opencode run`, но не объявлен в реестре"
            )
    # Обратная сторона I4: объявленный несуществующий usage (запись-фантом)
    for mid in seen_ids:
        fp = ROOT / mid
        if fp.is_file():
            src = fp.read_text(encoding="utf-8")
            if CANONICAL_TOKEN not in src:
                errors.append(f"I4: запись реестра {mid} не содержит канонический токен (фантом)")

    # I6: раздел TD-D6 помечен ЗАКРЫТО
    if DEBT_LEDGER.is_file():
        text = DEBT_LEDGER.read_text(encoding="utf-8")
        sec = re.search(r"### TD-D6.*?(?=\n### |\Z)", text, re.S)
        if not sec:
            errors.append("I6: раздел TD-D6 не найден в TECH_DEBT_AGENTS.md")
        elif "ЗАКРЫТО" not in sec.group(0):
            errors.append("I6: раздел TD-D6 не помечен ЗАКРЫТО при существующем реестре")
    else:
        errors.append("I6: TECH_DEBT_AGENTS.md отсутствует")

    return errors


def main() -> int:
    data, errors = load_registry(REGISTRY)
    if data is None:
        print("FAIL:")
        print("\n".join(f"  - {e}" for e in errors))
        return 1
    errors += check(data)
    if errors:
        print("FAIL:")
        print("\n".join(f"  - {e}" for e in errors))
        return 1
    n = len(data.get("modules", []))
    print(f"PASS: legacy-транспорт зафиксирован: {n} модулей, токен {CANONICAL_TOKEN!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
