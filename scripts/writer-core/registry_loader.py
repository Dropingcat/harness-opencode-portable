"""Fail-closed loader for runtime-owned Writer Core linguistic registries."""
from __future__ import annotations

import os
from typing import Any

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_REGISTRY_DIR = os.path.join(_HERE, "linguistic_assets")

_SPECS: dict[str, tuple[str, str, frozenset[str]]] = {
    "academic_ru_lexicon.yaml": ("entries", "expression", frozenset({"expression", "class", "risk"})),
    "connective_registry.yaml": ("entries", "form", frozenset({"form", "relation"})),
    "academic_frame_registry.yaml": ("frames", "id", frozenset({"id", "requires", "slots"})),
    "rhetorical_pattern_registry.yaml": ("patterns", "id", frozenset({"id", "moves"})),
    "language_action_registry.yaml": ("actions", "id", frozenset({"id", "may_mutate", "must_preserve", "post_checks"})),
    "valency_registry.yaml": ("entries", "lemma", frozenset({"lemma", "argument", "preposition", "case"})),
}


def _load(name: str, registry_dir: str = _REGISTRY_DIR) -> dict[str, Any]:
    if name not in _SPECS:
        raise ValueError(f"unsupported linguistic registry: {name}")
    with open(os.path.join(registry_dir, name), encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or not isinstance(data.get("schema_version"), str):
        raise ValueError(f"{name}: root mapping and schema_version are required")
    collection, identity, required = _SPECS[name]
    entries = data.get(collection)
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{name}: {collection} must be a non-empty list")
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{name}: {collection}[{index}] must be a mapping")
        missing = required - entry.keys()
        if missing:
            raise ValueError(f"{name}: {collection}[{index}] missing {sorted(missing)}")
        key = str(entry[identity]).strip().casefold()
        if not key or key in seen:
            raise ValueError(f"{name}: blank or duplicate {identity}: {entry[identity]!r}")
        seen.add(key)
        if name == "academic_ru_lexicon.yaml" and not (
                entry.get("epistemic_force") or entry.get("expected_relation")):
            raise ValueError(f"{name}: entries[{index}] needs epistemic_force or expected_relation")
    return data


class Registries:
    def __init__(self, registry_dir: str = _REGISTRY_DIR) -> None:
        self.lexicon = _load("academic_ru_lexicon.yaml", registry_dir)["entries"]
        self.connectives = _load("connective_registry.yaml", registry_dir)["entries"]
        self.frames = _load("academic_frame_registry.yaml", registry_dir)["frames"]
        self.patterns = _load("rhetorical_pattern_registry.yaml", registry_dir)["patterns"]
        self.actions = _load("language_action_registry.yaml", registry_dir)["actions"]
        self.valency = _load("valency_registry.yaml", registry_dir)["entries"]

        # expression -> (class, epistemic_force, risk)
        self.expr_force: dict[str, dict[str, str]] = {
            e["expression"]: e for e in self.lexicon
        }
        # connective form -> relation
        self.connective_rel: dict[str, dict[str, Any]] = {
            c["form"]: c for c in self.connectives
        }

    def search(self, entry: str) -> tuple[str, str]:
        """First matching lexicon expression contained in entry."""
        for expr, info in self.expr_force.items():
            if expr in entry.lower():
                return expr, info.get("epistemic_force", "")
        return "", ""


# shared singleton (immutable after init)
_registries: Registries | None = None


def get_registries() -> Registries:
    global _registries
    if _registries is None:
        _registries = Registries()
    return _registries
