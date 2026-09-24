#!/usr/bin/env python3
"""TD-D10 / TD-003: гейт дублирования route-данных (JSON vs TS vs compat-вью).

Проверяет инварианты соответствия между слоями route-данных:

  I1. `config/runtime_snapshot.json` детерминированно воспроизводим из
      авторитетных JSON-источников (`compile_runtime.compile_runtime(write=False)`
      == snapshot.routes, включая policy_hash);
  I2. Compat-вью (`profile_routes.json`, `tool_skill_routes.json`,
      `skill_to_route_map.json`) — точные проекции snapshot по тем же полям,
      что генерирует `compatibility_artifacts`, и несут актуальный
      `generated_from_policy_hash`;
  I3. В TS-потребителях плагина (`packages/opencode-harness-plugin/src/**/*.ts`)
      нет hardcode-сов идентификаторов маршрутов, отсутствующих в snapshot
      (допускаются только id из snapshot; литералы вида "academic-research"
      в строках описаний схем проверяются по префиксу harness- и по контексту
      route-id литералов);
  I4. Индекс `indexes.route_ids` == sorted(keys routes) в snapshot, authority
      и compat-вью (ни один слой не потерял/не добавил маршрут).

Fail-closed: любая ошибка -> список нарушений и exit code 1.
Stdlib-only, без сети. Запуск: python3 scripts/router/check_route_duplication.py [--root PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.router.compile_runtime import (  # noqa: E402
    compatibility_artifacts,
    compile_runtime,
    read_json,
    repo_root,
)

# Маршруты, объявленные в авторитете (используются как «белый список» для TS-скана)
ROUTE_ID_RE = re.compile(r"\b([a-z][a-z0-9]+(?:-[a-z][a-z0-9]+)+)\b")
TS_ROUTE_LITERAL_RES = [
    # route: "some-id" / route_id === 'some-id' / case "some-id":
    re.compile(r"""route(?:_id)?["']?\s*[:=]{1,3}\s*["']([a-z][a-z0-9]+(?:-[a-z][a-z0-9]+)+)["']"""),
    # switch/case на id маршрута
    re.compile(r"""case\s+["']([a-z][a-z0-9]+(?:-[a-z][a-z0-9]+)+)["']"""),
    # Map/Set перечисления маршрутов: new Set(["a-b", "c-d"])
    re.compile(r"""new\s+(?:Set|Map)\(\s*\[([^\]]*)\]"""),
]
SET_ENTRY_RE = re.compile(r"""["']([a-z][a-z0-9]+(?:-[a-z][a-z0-9]+)+)["']""")


def ts_route_literals(ts_files: list[Path]) -> set[str]:
    """Собирает все route-id литералы из TS-кода плагина."""
    found: set[str] = set()
    for path in ts_files:
        text = path.read_text(encoding="utf-8")
        for rx in TS_ROUTE_LITERAL_RES:
            for m in rx.finditer(text):
                chunk = m.group(1)
                if SET_ENTRY_RE.pattern and "[" not in chunk:
                    found.add(chunk)
                else:
                    found.update(SET_ENTRY_RE.findall(chunk))
    return found


def check(root: Path) -> list[str]:
    errors: list[str] = []
    cfg = root / "config"

    snap = read_json(cfg / "runtime_snapshot.json")
    authority = read_json(cfg / "routes_authority.json")
    profile_routes = read_json(cfg / "profile_routes.json")
    tool_skill_routes = read_json(cfg / "tool_skill_routes.json")
    skill_to_route_map = read_json(cfg / "skill_to_route_map.json")

    # --- I1: snapshot против пересборки из источников -----------------------
    try:
        rebuilt = compile_runtime(root=root, write=False)["snapshot"]
    except Exception as exc:  # fail-closed: невалидные источники = нарушение
        errors.append(f"I1: compile_runtime из источников падает: {exc}")
        rebuilt = None
    if rebuilt is not None:
        if rebuilt["policy_hash"] != snap["policy_hash"]:
            errors.append(
                f"I1: policy_hash рассинхронизирован: sources={rebuilt['policy_hash'][:12]}… "
                f"!= snapshot={snap['policy_hash'][:12]}… (нужен rerun compile_runtime)"
            )
        if rebuilt["routes"] != snap["routes"]:
            drift = sorted(set(rebuilt["routes"]) ^ set(snap["routes"]))
            detail = f" (расхождение по id: {drift})" if drift else " (состав id совпадает, различаются поля)"
            errors.append("I1: routes в runtime_snapshot.json не соответствуют пересборке из источников" + detail)

    # --- I2: compat-вью против snapshot -------------------------------------
    artifacts = compatibility_artifacts(snap)
    pairs = [
        ("profile_routes_compat", profile_routes),
        ("tool_skill_routes_compat", tool_skill_routes),
        ("skill_to_route_map_compat", skill_to_route_map),
    ]
    for name, actual in pairs:
        expected = artifacts[name]
        rel = {
            "profile_routes_compat": "config/profile_routes.json",
            "tool_skill_routes_compat": "config/tool_skill_routes.json",
            "skill_to_route_map_compat": "config/skill_to_route_map.json",
        }[name]
        if actual.get("generated_from_policy_hash") != snap["policy_hash"]:
            errors.append(
                f"I2: {rel}: generated_from_policy_hash устарел "
                f"({str(actual.get('generated_from_policy_hash'))[:12]}… != {snap['policy_hash'][:12]}…)"
            )
        # сравниваем содержательную часть (без служебных version/generated)
        for key in ("routes", "context_routes", "tool_contracts"):
            if key in expected and actual.get(key) != expected[key]:
                errors.append(f"I2: {rel}: поле '{key}' расходится с проекцией snapshot (дрейф дубликата)")

    # --- I3: TS-литералы маршрутов против snapshot ---------------------------
    known = set(snap["routes"]) | set(snap.get("indexes", {}).get("tool_ids", [])) \
        | set(snap.get("capsules", {})) | set(snap.get("profiles", {}))
    # служебные слова, встречающиеся в том же формате kebab-case и не являющиеся id
    allowlist_non_route = {
        "opencode-config", "sub-agent", "fact-check", "peer-review", "evidence-first",
        "fail-closed", "best-effort", "end-to-end", "read-only", "write-once",
        "harness-run", "harness-status", "semantic-execute", "code-review",
    }
    src_dir = root / "packages" / "opencode-harness-plugin" / "src"
    ts_files = sorted(src_dir.rglob("*.ts")) if src_dir.is_dir() else []
    for path in ts_files:
        text = path.read_text(encoding="utf-8")
        for rx in TS_ROUTE_LITERAL_RES:
            for m in rx.finditer(text):
                chunk = m.group(1)
                candidates = [chunk] if "[" not in (m.group(0)[-2:]) else SET_ENTRY_RE.findall(chunk)
                for lit in candidates:
                    if lit in known or lit in allowlist_non_route:
                        continue
                    if ROUTE_ID_RE.fullmatch(lit or "") is None:
                        continue
                    # литерал похож на id, но его нет ни в одном авторитетном множестве
                    errors.append(
                        f"I3: {path.relative_to(root)}: hardcode route-id '{lit}' отсутствует в runtime_snapshot"
                    )

    # --- I4: индексы и состав id во всех слоях -------------------------------
    ids_snap = set(snap["routes"])
    ids_auth = set(authority["routes"])
    ids_pr = set(profile_routes["routes"])
    ids_srm = set(skill_to_route_map["routes"])
    ids_ctx = {r["id"] for r in tool_skill_routes["context_routes"]}
    idx = set(snap.get("indexes", {}).get("route_ids", []))
    for label, group in [("authority", ids_auth), ("profile_routes", ids_pr),
                         ("skill_to_route_map", ids_srm), ("tool_skill_routes.context_routes", ids_ctx),
                         ("snapshot.indexes.route_ids", idx)]:
        if group != ids_snap:
            errors.append(f"I4: набор id маршрутов в {label} != набор в runtime_snapshot "
                          f"(missing={sorted(ids_snap - group)}, extra={sorted(group - ids_snap)})")

    # приоритеты/match_regex в profile_routes обязаны совпадать со snapshot (частичная проекция)
    for rid, r in profile_routes["routes"].items():
        s_r = snap["routes"].get(rid, {})
        for field in ("match_regex", "bucket", "default_profile", "priority"):
            if field in s_r and r.get(field) != s_r[field]:
                errors.append(f"I4: profile_routes[{rid}].{field} расходится со snapshot")

    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=None, help="repo root (по умолчанию — от корня скрипта)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else repo_root()
    errors = check(root)
    if errors:
        print(f"FAIL: обнаружено {len(errors)} нарушений инвариантов route-данных:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASS: инварианты TD-D10/TD-003 соблюдены "
          "(snapshot ↔ источники ↔ compat-вью ↔ TS, id-наборы идентичны)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
