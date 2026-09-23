#!/usr/bin/env python3
"""Agent Registry — единый источник истины по ролям агентов harness (Фаза 0 TD-A1).

Загружает и валидирует:
  - agents/*.md            — исходники ролей (frontmatter OpenCode + тело-промпт);
  - config/agent_categories/<agent>.json — категории/bucket/capsule роли;
  - runtime/model_bindings.json — маппинг «агент → модель» (создаётся вручную,
    потребляется на Фазе 2 компилятором .opencode/agent/*.md).

Формат frontmatter (подтверждён аудитом 2026-09-24):
  name, description, mode (primary|subagent|all), steps, permission{...},
  опционально model, temperature.

Stdlib-only + PyYAML (уже в requirements-core.txt). Парсер frontmatter
собственный (детерминированный, без зависимостей на python-frontmatter).

Использование:
  python3 runtime/registry.py                 # сводка реестра
  python3 runtime/registry.py --validate      # strict-валидация (exit 1 при ошибках)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
CATEGORIES_DIR = ROOT / "config" / "agent_categories"
MODEL_BINDINGS_PATH = ROOT / "runtime" / "model_bindings.json"

VALID_MODES = {"primary", "subagent", "all"}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FM_BLOCK_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)


class FrontmatterError(ValueError):
    """Frontmatter отсутствует или синтаксически некорректен."""


@dataclass
class AgentRecord:
    """Каноническая запись роли агента в реестре."""

    name: str
    source: Path                      # agents/<name>.md
    description: str = ""
    mode: str = "subagent"
    steps: Optional[int] = None
    model: Optional[str] = None       # из frontmatter источника (если задан)
    temperature: Optional[float] = None
    permission: dict = field(default_factory=dict)
    extra_fm: dict = field(default_factory=dict)   # прочие поля frontmatter as-is
    body: str = ""                    # промпт роли (всё после frontmatter)
    categories: list = field(default_factory=list)
    default_bucket: Optional[str] = None
    capsule: Optional[str] = None
    bound_model: Optional[str] = None  # из runtime/model_bindings.json (приоритетнее frontmatter)

    @property
    def effective_model(self) -> Optional[str]:
        """Модель с учётом override из model_bindings (binding > frontmatter)."""
        return self.bound_model or self.model

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source": self.source.relative_to(ROOT).as_posix(),
            "description": self.description,
            "mode": self.mode,
            "steps": self.steps,
            "model": self.model,
            "effective_model": self.effective_model,
            "temperature": self.temperature,
            "permission": self.permission,
            "categories": self.categories,
            "default_bucket": self.default_bucket,
            "capsule": self.capsule,
        }


# ---------------------------------------------------------------- frontmatter

def split_frontmatter(text: str) -> tuple[dict, str]:
    """Разделить md-файл на (frontmatter-dict, body). Бросает FrontmatterError."""
    m = FM_BLOCK_RE.match(text)
    if not m:
        raise FrontmatterError("no YAML frontmatter block at file start")
    try:
        import yaml  # noqa: WPS433 — локальный импорт для точной ошибки
        raw = m.group(1)
        try:
            fm = yaml.safe_load(raw)
        except Exception:
            # Fallback: неэкранированные `: ` в unquoted-скалярах (например,
            # description с двоеточием посреди текста) — легально для парсера
            # OpenCode, но формальный YAML error. Повторяем с кавычками.
            fixed_lines = []
            for line in raw.splitlines():
                if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:\s+\S", line) \
                        and not re.match(r"^\S+:\s*$", line):
                    k, v = line.split(":", 1)
                    v = v.strip()
                    if v[0] not in "\"'|[{&>*!":
                        line = f'{k}: "{v.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"'
                fixed_lines.append(line)
            fm = yaml.safe_load("\n".join(fixed_lines))
    except ImportError as e:  # pragma: no cover
        raise FrontmatterError(f"PyYAML required: {e}")
    except Exception as e:  # yaml.YAMLError
        raise FrontmatterError(f"invalid frontmatter YAML: {e}")
    if not isinstance(fm, dict):
        raise FrontmatterError("frontmatter is not a mapping")
    return fm, text[m.end():]


def _as_int(v: Any, field_name: str) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        raise FrontmatterError(f"{field_name} must be an int, got {v!r}")


def _as_float(v: Any, field_name: str) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise FrontmatterError(f"{field_name} must be a number, got {v!r}")


KNOWN_FM_KEYS = {"name", "description", "mode", "steps", "permission",
                 "model", "temperature"}


def parse_agent_file(path: Path) -> AgentRecord:
    """Разобрать agents/<name>.md в AgentRecord (без строгой валидации)."""
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    known = {k: v for k, v in fm.items() if k in KNOWN_FM_KEYS}
    extra = {k: v for k, v in fm.items() if k not in KNOWN_FM_KEYS}
    perm = fm.get("permission")
    return AgentRecord(
        name=str(fm.get("name", path.stem)),
        source=path,
        description=str(fm.get("description", "")),
        mode=str(fm.get("mode", "subagent")),
        steps=_as_int(fm.get("steps"), "steps"),
        model=fm.get("model"),
        temperature=_as_float(fm.get("temperature"), "temperature"),
        permission=perm if isinstance(perm, dict) else {},
        extra_fm=extra,
        body=body.strip(),
    )


# ------------------------------------------------------------- category files

def _read_category_overlay(cats_dir: Path, name: str) -> dict:
    """Прочитать <cats_dir>/<name>.json; {} если нет."""
    p = cats_dir / f"{name}.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {
        "categories": data.get("categories", []),
        "default_bucket": data.get("default_bucket"),
        "capsule": data.get("capsule"),
    }


def _read_model_bindings(mb_path: Path) -> dict:
    """Прочитать model_bindings.json по пути; {} если файл ещё не создан."""
    if not mb_path.exists():
        return {}
    data = json.loads(mb_path.read_text(encoding="utf-8"))
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        raise ValueError("model_bindings.json: 'agents' must be an object")
    return {k: v for k, v in agents.items() if isinstance(v, dict)}


def load_category_overlay(name: str) -> dict:
    return _read_category_overlay(CATEGORIES_DIR, name)


def load_model_bindings() -> dict:
    return _read_model_bindings(MODEL_BINDINGS_PATH)


# -------------------------------------------------------------------- registry

class AgentRegistry:
    """Реестр всех ролей harness с cross-validation источников."""

    def __init__(self, records: dict[str, AgentRecord]):
        self.records = records  # name -> record
        self._root: Path = ROOT

    @classmethod
    def load(cls, root: Path = ROOT) -> "AgentRegistry":
        """Загрузить реестр из дерева (root инъекцируется в тестах)."""
        agents_dir = root / "agents"
        cats_dir = root / "config" / "agent_categories"
        mb_path = root / "runtime" / "model_bindings.json"
        bc_path = root / "config" / "bucket_contracts.json"
        bindings = _read_model_bindings(mb_path)
        records: dict[str, AgentRecord] = {}
        for path in sorted(agents_dir.glob("*.md")):
            rec = parse_agent_file(path)
            overlay = _read_category_overlay(cats_dir, rec.name)
            rec.categories = overlay.get("categories", [])
            rec.default_bucket = overlay.get("default_bucket")
            rec.capsule = overlay.get("capsule")
            b = bindings.get(rec.name, {})
            rec.bound_model = b.get("model")
            if rec.name in records:
                raise ValueError(f"duplicate agent name: {rec.name}")
            records[rec.name] = rec
        reg = cls(records)
        reg._root = root
        return reg

    def names(self) -> list[str]:
        return sorted(self.records)

    def by_mode(self, mode: str) -> list[AgentRecord]:
        return [r for r in self.records.values() if r.mode == mode]

    def runner_of(self, name: str) -> Optional[str]:
        """Имя primary-обёртки runner для субагента (<name>-runner), если есть."""
        cand = f"{name}-runner"
        return cand if cand in self.records else None

    # ---------------------------------------------------------------- validate

    def validate(self) -> list[str]:
        """Strict-валидация. Возвращает список ошибок ([] = OK)."""
        errors: list[str] = []
        root = self._root
        cats_dir = root / "config" / "agent_categories"
        cat_files = {p.stem for p in cats_dir.glob("*.json")} \
            if cats_dir.exists() else set()
        bindings = _read_model_bindings(root / "runtime" / "model_bindings.json")
        # канонические bucket'ы (config/bucket_contracts.json)
        buckets: set[str] = set()
        bc_path = root / "config" / "bucket_contracts.json"
        if bc_path.exists():
            buckets = set(json.loads(bc_path.read_text(encoding="utf-8"))
                          .get("buckets", {}))

        for fname, rec in sorted(((p.stem, r) for p, r in
                                  ((r.source, r) for r in self.records.values()))):
            pref = f"{fname}: "
            # имя файла == name во frontmatter
            if rec.name != fname:
                errors.append(pref + f"name '{rec.name}' != filename '{fname}'")
            # допустимое имя slugs
            if not NAME_RE.match(rec.name):
                errors.append(pref + f"invalid agent name '{rec.name}'")
            # обязательные поля
            if not rec.description.strip():
                errors.append(pref + "empty description")
            if rec.mode not in VALID_MODES:
                errors.append(pref + f"mode '{rec.mode}' not in {sorted(VALID_MODES)}")
            if rec.steps is not None and rec.steps <= 0:
                errors.append(pref + f"steps must be positive, got {rec.steps}")
            if not rec.body.strip():
                errors.append(pref + "empty prompt body")
            # overlay категорий должен существовать
            if rec.name not in cat_files:
                errors.append(pref + f"missing config/agent_categories/{rec.name}.json")
            # default_bucket должен быть каноническим
            if buckets and rec.default_bucket and rec.default_bucket not in buckets:
                errors.append(pref + f"default_bucket '{rec.default_bucket}' "
                                     f"not in bucket_contracts {sorted(buckets)}")

        # model_bindings: все ключи должны ссылаться на существующих агентов
        for bn in sorted(set(bindings) - set(self.records)):
            errors.append(f"model_bindings: unknown agent '{bn}'")
        # schema binding'ов
        for name, b in sorted(bindings.items()):
            if not b.get("model"):
                errors.append(f"model_bindings[{name}]: missing 'model'")
        return errors


# ------------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--validate", action="store_true",
                    help="strict-валидация реестра (exit 1 при ошибках)")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="дамп реестра в JSON (stdout)")
    args = ap.parse_args(argv)

    reg = AgentRegistry.load()

    if args.as_json:
        print(json.dumps({r["name"]: r for r in
                          (reg.records[n].to_dict() for n in reg.names())},
                         ensure_ascii=False, indent=2))
        return 0

    if args.validate:
        errors = reg.validate()
        if errors:
            print(f"REGISTRY INVALID ({len(errors)} errors):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        print(f"registry OK: {len(reg.records)} agents validated")
        return 0

    print(f"Agent registry: {len(reg.records)} roles")
    for mode in ("primary", "subagent", "all"):
        rs = reg.by_mode(mode)
        if rs:
            print(f"  {mode:9} ({len(rs)}): " +
                  ", ".join(sorted(r.name for r in rs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
