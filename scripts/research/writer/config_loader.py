#!/usr/bin/env python3
"""Единый загрузчик конфига блока «Писатель» (writer_config.yaml).

Предоставляет:
  - load_config(path=None) -> dict   — прочитать + закэшировать
  - get('temperature.writer', default) — доступ по точечному пути
  - llm_params(role) -> dict         — {temperature, max_tokens, model} для роли
"""

import os
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_CONFIG_PATH = SCRIPT_DIR / "writer_config.yaml"

_CONFIG = None
_CONFIG_PATH = None


def load_config(path=None) -> dict:
    """Прочитать writer_config.yaml. Результат кэшируется.

    Если передан явный path — принудительно перечитывает файл с этого пути.
    """
    global _CONFIG, _CONFIG_PATH
    if path is not None:
        _CONFIG_PATH = Path(path)
        _CONFIG = None
    if _CONFIG is None:
        cfg_path = _CONFIG_PATH or _DEFAULT_CONFIG_PATH
        if yaml is None:
            raise RuntimeError("PyYAML is required to load writer_config.yaml")
        with open(cfg_path, encoding="utf-8") as f:
            _CONFIG = yaml.safe_load(f) or {}
    return _CONFIG


def get(path, default=None):
    """Достать параметр по точечному пути (например 'temperature.writer')."""
    cfg = load_config()
    node = cfg
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default
    return node


def llm_params(role):
    """Параметры LLM-вызова ({temperature, max_tokens, model}) для роли.

    model: берётся из llm.models.<role> (если задан), иначе llm.default_model.
    fallback_model — запасная модель для retry-путей.
    """
    cfg = load_config()
    llm = cfg.get("llm", {})
    temps = cfg.get("temperature", {})
    toks = cfg.get("max_tokens", {})
    models = llm.get("models", {})

    return {
        "temperature": temps.get(role, 0.3),
        "max_tokens": toks.get(role, 2048),
        "model": models.get(role, llm.get("default_model", "deepseek-v4-flash")),
        "fallback_model": llm.get("fallback_model", "deepseek-v4-pro"),
    }


if __name__ == "__main__":
    cfg = load_config()
    print("config keys:", list(cfg.keys()))
    print("writer temp:", get("temperature.writer"))
    print("writer params:", llm_params("writer"))
    print("missing:", get("nonexistent.deep", "fallback-value"))
