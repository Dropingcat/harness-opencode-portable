#!/usr/bin/env python3
"""Тесты config_loader: чтение writer_config.yaml, get() по точечному пути, llm_params()."""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import config_loader

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("  FAIL: " + msg)


def test_load_config_shape():
    cfg = config_loader.load_config()
    for section in ["llm", "temperature", "max_tokens", "growth",
                    "regression", "consistency", "budget", "meta_select", "state"]:
        check(section in cfg, "section " + section)
        check(isinstance(cfg[section], dict), "section " + section + " is dict")
    print("  test_load_config_shape: OK")


def test_get_dotted_path():
    check(config_loader.get("temperature.writer") == 0.3, "temperature.writer == 0.3")
    check(config_loader.get("temperature.critic") == 0.2, "temperature.critic == 0.2")
    check(config_loader.get("max_tokens.writer") == 2048, "max_tokens.writer == 2048")
    check(config_loader.get("growth.max_hops") == 3, "growth.max_hops == 3")
    check(config_loader.get("growth.max_nodes") == 15, "growth.max_nodes == 15")
    check(config_loader.get("budget.max_cost_rub") == 20.0, "budget.max_cost_rub == 20.0")
    check(config_loader.get("consistency.content_loss_threshold") == 0.3,
          "content_loss_threshold == 0.3")
    check(config_loader.get("consistency.hard_min_justification") == 10,
          "hard_min_justification == 10")
    check(config_loader.get("meta_select.min_score") == 1, "meta_select.min_score == 1")
    check(config_loader.get("regression.alpha") == 0.05, "regression.alpha == 0.05")
    check(config_loader.get("regression.conformal_fallback_ratio") == 0.75,
          "conformal_fallback_ratio == 0.75")
    print("  test_get_dotted_path: OK")


def test_get_default():
    check(config_loader.get("nonexistent.deep.path", "fallback") == "fallback", "default fallback")
    check(config_loader.get("temperature.unknown_role", None) is None, "unknown role -> None")
    print("  test_get_default: OK")


def test_llm_params():
    p = config_loader.llm_params("writer")
    check(isinstance(p, dict), "returns dict")
    check(set(["temperature", "max_tokens", "model"]).issubset(p.keys()),
          "has temperature/max_tokens/model")
    check(p["temperature"] == 0.3, "writer temp")
    check(p["max_tokens"] == 2048, "writer max_tokens")
    check(p["model"] == "deepseek-v4-flash", "default model")

    p2 = config_loader.llm_params("critic")
    check(p2["temperature"] == 0.2, "critic temp")
    check(p2["max_tokens"] == 1024, "critic max_tokens")

    p3 = config_loader.llm_params("reverify")
    check(p3["temperature"] == 0.0, "reverify temp (deterministic)")
    check(p3["max_tokens"] == 2048, "reverify max_tokens")
    print("  test_llm_params: OK")


def test_custom_path():
    tmp = SCRIPT_DIR / "_cfg_test_custom.yaml"
    tmp.write_text("custom:\n  deep:\n    value: 42\n", encoding="utf-8")
    cfg = config_loader.load_config(path=str(tmp))
    check(cfg.get("custom", {}).get("deep", {}).get("value") == 42, "custom yaml value == 42")
    tmp.unlink(missing_ok=True)
    print("  test_custom_path: OK")


if __name__ == "__main__":
    print("=== test_config_loader ===")
    test_load_config_shape()
    test_get_dotted_path()
    test_get_default()
    test_llm_params()
    test_custom_path()
    print("=== results: %d passed, %d failed ===" % (passed, failed))
    sys.exit(0 if failed == 0 else 1)
