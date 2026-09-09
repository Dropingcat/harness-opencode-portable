"""Registry loader for Writer Core v0.3 linguistic registries (YAML)."""
from __future__ import annotations

import os
from typing import Any

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.dirname(_HERE)          # .../scripts
_REGISTRY_DIR = (
    os.environ.get("WRITER_LINGUISTICS_REGISTRY_DIR")
    or os.path.join(_scripts_dir, "writer_core_handoff", "linguistics")
)


def _load(name: str) -> dict[str, Any]:
    with open(os.path.join(_REGISTRY_DIR, name), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class Registries:
    def __init__(self) -> None:
        self.lexicon = _load("academic_ru_lexicon.yaml")["entries"]
        self.connectives = _load("connective_registry.yaml")["entries"]
        self.frames = _load("academic_frame_registry.yaml")["frames"]
        self.patterns = _load("rhetorical_pattern_registry.yaml")["patterns"]
        self.actions = _load("language_action_registry.yaml")["actions"]
        self.valency = _load("valency_registry.yaml")["entries"]

        # expression -> (class, epistemic_force, risk)
        self.expr_force: dict[str, dict[str, str]] = {
            e["expression"]: e for e in self.lexicon
        }
        # connective form -> relation
        self.connective_rel: dict[str, dict[str, Any]] = {
            c["form"]: c for c in self.connectives
        }

    @staticmethod
    def search(entry: str) -> tuple[str, str]:
        """First matching lexicon expression contained in entry."""
        for expr, info in Registries.expr_force.items():
            if expr in entry.lower():
                return expr, info["epistemic_force"]
        return "", ""


# shared singleton (immutable after init)
_registries: Registries | None = None


def get_registries() -> Registries:
    global _registries
    if _registries is None:
        _registries = Registries()
    return _registries