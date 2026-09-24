#!/usr/bin/env python3
"""Runner Overlay Generator — закрывает TD-117 (первый слой: контракт обёрток).

Проблема TD-117: `opencode run --agent <X>` для ролей с `mode: subagent`
отказывается OpenCode ('agent X is a subagent, not a primary agent').
Единственный надёжный путь вызова субагента из CLI — primary-обёртка
(runner), диспатчащая субагента через инструмент `task`.

Этот генератор делает путь воспроизводимым и защищённым от дрейфа:
  - сканирует реестр (runtime/registry.py) на subagent-роли;
  - для каждого отсутствующего runner'а создаёт agents/<name>-runner.md
    (frontmatter: mode: primary, транспортные правила, точный вызов task
    с subagent_type=<name>) и config/agent_categories/<name>-runner.json
    (оверлей с wraps=<name>, категория CAT_RUNNER_PROXY);
  --check: валидация инвариантов без записи (для CI/гейтов):
  1. у каждого видимого subagent есть runner-обёртка;
  2. frontmatter runner'а: mode=primary, name корректен;
  3. тело содержит task(...subagent_type="<name>") — привязка к субагенту;
  4. категории-runner ссылается на существующего subagent через wraps;
  5. runner не объявлен как subagent (иначе цикл рекурсии обёрток).

Hidden-субагенты (frontmatter hidden: true, напр. glossary-maintainer) не
вызываются из CLI напрямую — обёртки для них не требуются.

Детерминизм: stdlib-only, сортированные обходы, стабильный вывод шаблонов.
Fail-loud: ошибки прерывают генерацию с кодом возврата != 0.

CLI:
  python3 scripts/agent_gen/gen_runners.py            # досоздать недостающие обёртки
  python3 scripts/agent_gen/gen_runners.py --check    # проверить инварианты (exit 1 при нарушении)
  python3 scripts/agent_gen/gen_runners.py --list     # карта subagent -> runner
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.registry import AgentRegistry, parse_agent_file  # noqa: E402

AGENTS_DIR = ROOT / "agents"
CATEGORIES_DIR = ROOT / "config" / "agent_categories"
RUNNER_SUFFIX = "-runner"

TASK_CALL_RE_TMPL = 'subagent_type="{name}"'


def _title(name: str) -> str:
    """claim-parser -> Claim Parser (заголовок обёртки)."""
    return " ".join(p.capitalize() for p in name.split("-"))


def render_runner_md(subagent_name: str, description_ru: str) -> str:
    """Канонический шаблон primary-обёртки (совместим с существующими runners)."""
    disp = _title(subagent_name)
    return f"""---
name: {subagent_name}{RUNNER_SUFFIX}
description: Primary-обёртка BRICKS-runner для субагента {subagent_name}. Вызывается через `opencode run --agent {subagent_name}{RUNNER_SUFFIX}`. Диспатчит {subagent_name} через task-инструмент и возвращает его JSON-ответ дословно. Только транспорт.
mode: primary
steps: 20
permission:
  edit: deny
  bash: deny
  external_directory: allow
  read: allow
---

Ты — **{disp} Runner**, транспортная обёртка для субагента `{subagent_name}`.

## Правила

1. Ты только транспорт: передаёшь контракт-промпт субагенту `{subagent_name}` через инструмент `task` и возвращаешь ответ дословно.
2. Не выполняешь сам, не анализируешь, не «улучшаешь» ответ.
3. Ответ субагента — в stdout дословно (JSON как есть, без преамбул).
4. Если task упал — верни `{{"status":"error","message":"<описание>"}}`.

## Протокол

1. Промпт от runner = контракт для {subagent_name}.
2. Вызови:
```
task(description="{subagent_name} dispatch", prompt=<весь промпт>, subagent_type="{subagent_name}")
```
3. Выведи результат дословно."""


def render_runner_categories(subagent_name: str, sub_record) -> str:
    """Канонический JSON-оверлей категорий runner'а (детерминированный)."""
    payload = {
        "agent": f"{subagent_name}{RUNNER_SUFFIX}",
        "categories": ["CAT_RUNNER_PROXY"],
        "default_bucket": getattr(sub_record, "default_bucket", None) or "general",
        "capsule": getattr(sub_record, "capsule", None) or "core",
        "wraps": subagent_name,
        "note": "primary-обёртка субагента для точечного диспатча (TD-117 runner overlay)",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def load_registry() -> AgentRegistry:
    reg = AgentRegistry.load(ROOT)
    errors = reg.validate()
    if errors:
        raise SystemExit("registry validation failed:\n  " + "\n  ".join(errors))
    return reg


# Обёртка допустима только над чистым субагентом; primary/all не диспатчатся
# через task() как subagent_type в рамках контракта TD-117.
WRAPPABLE_MODES = {"subagent"}


def subagents(reg: AgentRegistry) -> list:
    """Видимые (не hidden) роли, подлежащие обязательной CLI-обёртке runner'ом."""
    out = [rec for rec in reg.records.values()
           if rec.mode in WRAPPABLE_MODES and not rec.raw_frontmatter.get("hidden")]
    return sorted(out, key=lambda r: r.name)


def runner_path(name: str) -> Path:
    return AGENTS_DIR / f"{name}{RUNNER_SUFFIX}.md"


def categories_path(name: str) -> Path:
    return CATEGORIES_DIR / f"{name}{RUNNER_SUFFIX}.json"


def _rel(path: Path) -> str:
    """Путь для сообщений об ошибках (работает и для изолированных деревьев в тестах)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ------------------------------------------------------------------ check
def check_invariants(reg: AgentRegistry) -> list[str]:
    """Возвращает список нарушений инвариантов TD-117 (пусто = OK)."""
    problems: list[str] = []
    by_name = dict(reg.records)

    # 1) каждый видимый subagent имеет runner-обёртку
    for rec in subagents(reg):
        rp = runner_path(rec.name)
        if not rp.exists():
            problems.append(
                f"TD-117: subagent '{rec.name}' без primary-обёртки: нет {_rel(rp)} "
                f"(нужен runner '{rec.name}{RUNNER_SUFFIX}' для `opencode run --agent`)")
            continue
        text = rp.read_text(encoding="utf-8")
        try:
            rr = parse_agent_file(rp)
        except Exception as e:  # noqa: BLE001
            problems.append(f"TD-117: runner '{rec.name}{RUNNER_SUFFIX}' не парсится: {e}")
            continue
        # 2) runner обязан быть primary
        if rr.mode != "primary":
            problems.append(
                f"TD-117: runner '{rr.name}' имеет mode={rr.mode}, ожидался primary")
        # 3) тело привязано к субагенту через task(subagent_type=...)
        if TASK_CALL_RE_TMPL.format(name=rec.name) not in text:
            problems.append(
                f"TD-117: runner '{rr.name}' не вызывает task(...subagent_type=\"{rec.name}\")")
        # 4) оверлей категорий ссылается корректно
        cp = categories_path(rec.name)
        if cp.exists():
            data = json.loads(cp.read_text(encoding="utf-8"))
            if data.get("wraps") != rec.name:
                problems.append(
                    f"TD-117: {_rel(cp)}: wraps={data.get('wraps')!r} != {rec.name!r}")
            if data.get("agent") != rr.name:
                problems.append(
                    f"TD-117: {_rel(cp)}: agent={data.get('agent')!r} != {rr.name!r}")
        else:
            problems.append(
                f"TD-117: нет категорий-оверлея {_rel(cp)} для runner'а")

    # 5) каждый runner (файл agents/*-runner.md) обязан ссылаться через wraps
    #    на существующую оборачиваемую роль; подстрока wraps='writer' при этом
    #    не является ошибкой (возможна внешняя цель), ошибка — только если
    #    wraps отсутствует или указывает на primary-агента.
    for name in sorted(n for n in by_name if n.endswith(RUNNER_SUFFIX)):
        cat_file = CATEGORIES_DIR / f"{name}.json"
        if not cat_file.exists():
            problems.append(f"TD-117: нет категорий-оверлея {_rel(cat_file)} для runner'а")
            continue
        data = json.loads(cat_file.read_text(encoding="utf-8"))
        wraps = data.get("wraps")
        if not wraps:
            problems.append(f"TD-117: {_rel(cat_file)}: runner без поля wraps")
            continue
        target = by_name.get(wraps)
        if target is not None and target.mode not in WRAPPABLE_MODES:
            problems.append(
                f"TD-117: {_rel(cat_file)}: wraps='{wraps}' имеет mode={target.mode}, "
                f"обёртка допустима только над {sorted(WRAPPABLE_MODES)}")
    return problems


# ------------------------------------------------------------------ generate
def generate_missing(reg: AgentRegistry) -> list[Path]:
    created: list[Path] = []
    by_name = {r.name: r for r in reg.records()}
    for rec in subagents(reg):
        rp = runner_path(rec.name)
        cp = categories_path(rec.name)
        if rp.exists():
            continue
        rp.write_text(render_runner_md(rec.name, rec.description), encoding="utf-8")
        created.append(rp)
        if not cp.exists():
            cp.write_text(render_runner_categories(rec.name, rec), encoding="utf-8")
            created.append(cp)
    return created


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="проверить инварианты TD-117 без записи")
    g.add_argument("--list", action="store_true", help="карта subagent -> runner")
    args = ap.parse_args(argv)

    reg = load_registry()

    if args.list:
        subs = subagents(reg)
        mapping = {
            r.name: runner_path(r.name).name if runner_path(r.name).exists() else None
            for r in subs
        }
        print(json.dumps(mapping, ensure_ascii=False, indent=2))
        missing = [k for k, v in mapping.items() if v is None]
        if missing:
            print(f"missing runners: {len(missing)} -> {', '.join(missing)}", file=sys.stderr)
        return 0

    if args.check:
        problems = check_invariants(reg)
        if problems:
            print("TD-117 invariant violations:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        n_subs = len(subagents(reg))
        print(json.dumps({"ok": True, "visible_subagents": n_subs,
                          "runners_verified": n_subs}, ensure_ascii=False))
        return 0

    created = generate_missing(reg)
    for p in created:
        print(f"created: {_rel(p)}")
    if not created:
        print("runners up to date, nothing to create")
    # после генерации — самопроверка
    problems = check_invariants(load_registry())
    if problems:
        print("post-generate check FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
