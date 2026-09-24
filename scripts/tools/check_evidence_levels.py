#!/usr/bin/env python3
"""check_evidence_levels.py — гейт TD-D8: соответствие compatibility/*.json шкале evidence levels.

Инварианты (fail-closed):
  I1  Каждая запись feature_probes — объект {level, evidence} ровно с этими ключами.
  I2  level ∈ keys(evidence_scale.levels) (канонический словарь уровней).
  I3  Устаревшие токены (LIVE_VERIFIED / NOT_LIVE_CERTIFIED / "verified against package types")
      отсутствуют в JSON целиком.
  I4  capability со level=LIVE_CERTIFIED ⊆ evidence_scale.allowed_live_certified.
  I5  Каждый LIVE_CERTIFIED имеет ≥1 evidence-ссылку на существующий файл репозитория;
      ссылки вида path#anchor проверяются по файлу.
  I6  semantic_status ∈ допустимых уровней; если NOT_CERTIFIED — ни одна LIVE-запись не
      называется semantic (согласованность: STRUCTURED_OUTPUT тоже не LIVE_CERTIFIED).
Выход: 0 = PASS, 1 = FAIL (перечислены нарушения).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_TOKENS = ("LIVE_VERIFIED", "NOT_LIVE_CERTIFIED", "verified against package types")
REQUIRED_KEYS = {"level", "evidence"}


def check(doc: dict, raw: str):
    errors = []
    # I3: устаревшие токены
    for tok in LEGACY_TOKENS:
        if tok in raw:
            errors.append(f"I3: устаревший токен в JSON: {tok!r}")

    scale = doc.get("evidence_scale", {})
    levels = set(scale.get("levels", {}))
    allowed_live = set(scale.get("allowed_live_certified", []))
    if not levels:
        errors.append("I2: evidence_scale.levels пуст или отсутствует")

    probes = doc.get("feature_probes", {})
    if not probes:
        errors.append("I1: feature_probes пуст или отсутствует")

    for name, rec in probes.items():
        # I1
        if not isinstance(rec, dict) or set(rec.keys()) != REQUIRED_KEYS:
            errors.append(f"I1: {name}: запись должна быть объектом {{level, evidence}}")
            continue
        level = rec["level"]
        ev = rec["evidence"]
        # I2
        if level not in levels:
            errors.append(f"I2: {name}: уровень {level!r} вне канонического набора {sorted(levels)}")
        if not isinstance(ev, list):
            errors.append(f"I1: {name}: evidence должен быть списком")
            continue
        # I5: ссылки на файлы существуют
        for ref in ev:
            fpath = ROOT / ref.split("#", 1)[0]
            if not fpath.is_file():
                errors.append(f"I5: {name}: evidence-файл не найден: {ref}")
        # I4 + I5 для LIVE
        if level == "LIVE_CERTIFIED":
            if name not in allowed_live:
                errors.append(f"I4: {name}: LIVE_CERTIFIED вне allowed_live_certified")
            if not ev:
                errors.append(f"I5: {name}: LIVE_CERTIFIED без evidence-ссылок")

    # I6
    sem = doc.get("semantic_status")
    if sem not in levels and levels:
        errors.append(f"I6: semantic_status {sem!r} вне канонического набора")
    if sem == "NOT_CERTIFIED" and probes.get("STRUCTURED_OUTPUT", {}).get("level") == "LIVE_CERTIFIED":
        errors.append("I6: semantic NOT_CERTIFIED против STRUCTURED_OUTPUT=LIVE_CERTIFIED")
    return errors


def main(paths=None):
    paths = [Path(p) for p in (paths or sorted((ROOT / "compatibility" / "opencode").glob("*.json")))]
    if not paths:
        print("GATE FAIL: нет compatibility-файлов")
        return 1
    total = 0
    for p in paths:
        raw = p.read_text(encoding="utf-8")
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"GATE FAIL [{p.name}]: невалидный JSON: {e}")
            return 1
        errs = check(doc, raw)
        if errs:
            total += len(errs)
            print(f"GATE FAIL [{p.name}]:")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"GATE PASS [{p.name}]: {len(doc['feature_probes'])} probes, уровни каноничны")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
