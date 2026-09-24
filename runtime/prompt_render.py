#!/usr/bin/env python3
"""Рендер динамических промптов агентов (TD-I1, Фаза 2 v1.1).

Канонические источники:
  - templates/agent_prompts/*.md          — шаблоны с плейсхолдерами {task},
    {workspace}, {route}, {capsules}, {skills}, {tools}, {memory_context},
    {contracts}, {agent_hint};
  - config/agent_prompt_bindings.json     — роль -> шаблон + правила подстановки;
  - runtime/model_bindings.json           — «роль -> модель» (для agent_hint).

Детерминизм: stdlib-only, неизвестные плейсхолдеры не подставляются (строгий
режим — ошибка), отсутствующие значения рендерятся как "n/a".

Использование:
  python3 runtime/prompt_render.py --agent researcher --task "..." [--route-id ...] [--profile ...]
  python3 runtime/prompt_render.py --validate   # строгая проверка биндингов
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "templates" / "agent_prompts"
BINDINGS_PATH = ROOT / "config" / "agent_prompt_bindings.json"
MODEL_BINDINGS_PATH = ROOT / "runtime" / "model_bindings.json"

PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
KNOWN_PLACEHOLDERS = {
    "task", "workspace", "route", "capsules", "skills", "tools",
    "memory_context", "contracts", "agent_hint", "agent", "model",
}


class PromptRenderError(ValueError):
    pass


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_bindings(path: Path = BINDINGS_PATH) -> dict:
    if not path.exists():
        raise PromptRenderError(f"missing bindings file: {path.relative_to(ROOT)}")
    data = _load_json(path)
    if data.get("schema") != "harness-agent-prompt-bindings/1.0":
        raise PromptRenderError("agent_prompt_bindings.json: unexpected schema")
    if not isinstance(data.get("bindings"), dict):
        raise PromptRenderError("agent_prompt_bindings.json: 'bindings' must be an object")
    return data


def load_templates(prompts_dir: Path = PROMPTS_DIR) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(prompts_dir.glob("*.md")):
        out[p.name] = p.read_text(encoding="utf-8")
    return out


def template_placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER_RE.findall(text))


def resolve_model(agent: str, root: Path = ROOT) -> Optional[str]:
    """Модель роли: binding > frontmatter источника > default_model."""
    mb_path = root / "runtime" / "model_bindings.json"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from runtime.registry import AgentRegistry  # noqa: PLC0415
        rec = AgentRegistry.load(root).records.get(agent)
        if rec is not None:
            return rec.effective_model if hasattr(rec, "effective_model") else (rec.bound_model or rec.model)
    except FileNotFoundError:
        pass
    if mb_path.exists():
        data = _load_json(mb_path)
        b = data.get("agents", {}).get(agent)
        if isinstance(b, dict) and b.get("model"):
            return str(b["model"])
        return data.get("default_model")
    return None


def render_prompt(template_text: str, values: dict[str, str], *, strict: bool = True) -> str:
    """Подставить {placeholder}'ы. Неизвестные ключи в значениях игнорируются;
    плейсхолдеры без значения -> 'n/a' (или ошибка в strict-режиме)."""

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key in values:
            return values[key]
        if strict:
            raise PromptRenderError(f"template placeholder '{key}' has no value")
        return "n/a"

    return PLACEHOLDER_RE.sub(sub, template_text)


def build_values(resolved: dict, *, task: str, workspace: str = "",
                 memory_context: str = "", contracts: str = "") -> dict[str, str]:
    """Собрать словарь подстановок из результата resolve_route.resolve()."""
    route_id = resolved.get("route_id", "")
    model = resolve_model(route_agent(resolved)) if route_agent(resolved) else None
    hint = resolved.get("agent_hint", "")
    agent = route_agent(resolved) or "n/a"
    return {
        "task": task.strip() or "n/a",
        "workspace": workspace.strip() or "n/a",
        "route": route_id or "n/a",
        "capsules": ", ".join(resolved.get("capsules", [])) or "n/a",
        "skills": ", ".join(resolved.get("skills", [])) or "n/a",
        "tools": ", ".join(resolved.get("tools", [])) or "n/a",
        "memory_context": memory_context.strip() or "(no memory context)",
        "contracts": contracts.strip() or "(none declared)",
        "agent_hint": hint or "(none)",
        "agent": agent,
        "model": model or "host-default",
    }


def route_agent(resolved: dict) -> Optional[str]:
    a = resolved.get("agent")
    return a if isinstance(a, str) and a else None


def agent_hint_for(resolved: dict, *, prompt_template: Optional[str] = None) -> dict:
    """agent_hint для harness_run (Фаза 1 критерий): {agent, model, prompt_template}."""
    agent = route_agent(resolved)
    if not agent:
        return {}
    return {
        "agent": f"@{agent}",
        "model": resolve_model(agent) or "host-default",
        "prompt_template": prompt_template or "n/a",
        "hint": resolved.get("agent_hint", ""),
    }


def select_template(bindings: dict, agent: str, route_id: str) -> tuple[str, dict]:
    """Правило выбора шаблона: routes-specific binding > role binding > default.
    Возвращает (имя файла шаблона, record binding'а)."""
    rules = bindings.get("rules", {})
    by_route = rules.get("by_route", {})
    by_role = rules.get("by_role", {})
    default = bindings.get("default_template")
    rec = by_route.get(route_id) or by_role.get(agent)
    if rec:
        return rec["template"], rec
    if default:
        return default, {"template": default}
    raise PromptRenderError(f"no prompt template for agent={agent!r} route={route_id!r}")


def render_for_route(task: str, resolved: dict, *, workspace: str = "",
                     memory_context: str = "", contracts: str = "",
                     root: Path = ROOT) -> tuple[str, str]:
    """Вернуть (rendered_prompt, template_name). Только для ok-роутинга."""
    bindings = load_bindings(root / "config" / "agent_prompt_bindings.json")
    templates = load_templates(root / "templates" / "agent_prompts")
    agent = route_agent(resolved)
    if not agent or not resolved.get("ok"):
        raise PromptRenderError("render_for_route requires an ok resolution with route.agent")
    template_name, _rec = select_template(bindings, agent, resolved.get("route_id", ""))
    if template_name not in templates:
        raise PromptRenderError(f"template not found: templates/agent_prompts/{template_name}")
    values = build_values(resolved, task=task, workspace=workspace,
                          memory_context=memory_context, contracts=contracts)
    return render_prompt(templates[template_name], values), template_name


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        bindings = load_bindings(root / "config" / "agent_prompt_bindings.json")
    except (PromptRenderError, json.JSONDecodeError) as e:
        return [f"agent_prompt_bindings: {e}"]
    try:
        templates = load_templates(root / "templates" / "agent_prompts")
    except OSError as e:
        return [f"templates: {e}"]
    # все шаблоны используют только известные плейсхолдеры
    for name, text in sorted(templates.items()):
        unknown = sorted(template_placeholders(text) - KNOWN_PLACEHOLDERS)
        if unknown:
            errors.append(f"template {name}: unknown placeholders {unknown}")
    # ссылки правил существуют
    rules = bindings.get("rules", {})
    refs: list[tuple[str, str]] = []
    for scope in ("by_route", "by_role"):
        for key, rec in sorted(rules.get(scope, {}).items()):
            t = rec.get("template")
            if not t:
                errors.append(f"rules.{scope}[{key}]: missing 'template'")
            else:
                refs.append((f"rules.{scope}[{key}]", t))
    if bindings.get("default_template"):
        refs.append(("default_template", bindings["default_template"]))
    for src, t in refs:
        if t not in templates:
            errors.append(f"{src}: template not found: templates/agent_prompts/{t}")
    # by_route ссылается на известные route'ы и by_role — на известных агентов
    snap_path = root / "config" / "runtime_snapshot.json"
    if snap_path.exists():
        route_ids = set(_load_json(snap_path).get("routes", {}))
        for key in sorted(rules.get("by_route", {})):
            if key not in route_ids:
                errors.append(f"rules.by_route: unknown route {key!r}")
    agents_dir = root / "agents"
    if agents_dir.is_dir():
        known = {p.stem for p in agents_dir.glob("*.md")}
        for key in sorted(rules.get("by_role", {})):
            if key not in known:
                errors.append(f"rules.by_role: unknown agent {key!r}")
    return sorted(errors)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--agent")
    ap.add_argument("--task", default="")
    ap.add_argument("--route-id")
    ap.add_argument("--profile")
    args = ap.parse_args(argv)

    if args.validate:
        errors = validate()
        if errors:
            print("PROMPT BINDINGS INVALID:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print("prompt bindings OK")
        return 0

    if not args.agent or not args.task:
        ap.error("--agent and --task are required for rendering")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from router.resolve_route import resolve  # noqa: PLC0415
    hints: dict[str, Any] = {}
    if args.route_id:
        hints["route_id"] = args.route_id
    if args.profile:
        hints["preferred_profile"] = args.profile
    if not hints:
        hints["route_id"] = next(
            (rid for rid, r in _load_json(ROOT / "config" / "runtime_snapshot.json")["routes"].items()
             if r.get("agent") == args.agent),
            None,
        )
    resolved = resolve(args.task, hints=hints)
    if not resolved.get("ok"):
        print(json.dumps(resolved, ensure_ascii=False), file=sys.stderr)
        return 2
    prompt, template = render_for_route(args.task, resolved)
    sys.stdout.write(prompt)
    print(f"\n<!-- template: {template} -->", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
