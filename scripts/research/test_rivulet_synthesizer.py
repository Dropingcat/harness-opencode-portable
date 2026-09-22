#!/usr/bin/env python3
"""test_rivulet_synthesizer.py — ручейковое тестирование synthesizer.py.

Проблема 13 (shape_mismatch): synthesizer падал на list-формате verdicts.json
(`data.get('verdicts')` на списке). Тест покрывает 3 уровня:

    Уровень 1 — форматы входа:   list (exp1) / dict / пустой list / битый JSON
    Уровень 2 — сценарии данных: SUPPORTED, смешанные, str claim_id,
                                 отсутствие verdict, нет LLM-ключа
    Уровень 3 — интеграция:      прогон на реальных артефактах exp1

Каждый тест логирует: вход → действие → выход → status. Сводка PASS/FAIL.

Pytest:      python3 -m pytest scripts/test_rivulet_synthesizer.py -v
Standalone:  python3 scripts/test_rivulet_synthesizer.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SYNTH = SCRIPTS / "synthesizer.py"
EXP1 = Path(__file__).resolve().parent / "testdata" / "exp1"

# Без ключей — LLM-часть падает мгновенно, идёт fallback «_LLM недоступен_»
NO_KEY_ENV = {**os.environ, "AITUNNEL_KEY": "", "OPENAI_API_KEY": ""}

PASSED: list[str] = []
FAILED: list[str] = []
SKIPPED: list[str] = []


def _log(status: str, name: str, detail: str) -> None:
    line = f"[{status}] {name}: {detail}"
    print(line)
    if status == "PASS":
        PASSED.append(line)
    elif status == "SKIP":
        SKIPPED.append(line)
    else:
        FAILED.append(line)


def run_synth(in_path: Path, out_path: Path, timeout: int = 60) -> tuple[int, str]:
    env = dict(NO_KEY_ENV)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(SYNTH), str(in_path), str(out_path)],
        capture_output=True, text=True, env=env, timeout=timeout, encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def write_verdicts(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def make_verdicts(n: int = 20, claim_id_fn=None) -> list[dict]:
    return [{
        "claim_id": claim_id_fn(i) if claim_id_fn else i + 1,
        "claim_text": f"Claim text number {i + 1} about nitriding and XRD.",
        "verdict": "SUPPORTED",
        "confidence": 0.9,
        "sources": [{"title": f"source-{i}", "type": "textbook", "trust": 0.9}],
        "caveats": [],
        "reason": "Confirmed by sources.",
        "numeric_comparison": {"status": "match", "score": 0.8},
    } for i in range(n)]


# ─────────────────────────── Уровень 1: форматы входа ───────────────────────────

def test_list_flat_verdicts(tmp_path: Path) -> None:
    name = "L1.1 list из 20 плоских вердиктов (exp1)"
    inp = tmp_path / "verdicts_list.json"
    out = tmp_path / "final_report.md"
    write_verdicts(inp, make_verdicts(20))
    rc, log = run_synth(inp, out)
    ok = rc == 0 and out.exists() and "## Детали по claims" in out.read_text(encoding="utf-8")
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, отчёт={out.exists()}")
    assert ok, f"{name}: rc={rc} log={log}"


def test_dict_verdicts_statistics(tmp_path: Path) -> None:
    name = "L1.2 dict {verdicts, statistics}"
    inp = tmp_path / "verdicts_dict.json"
    out = tmp_path / "final_report.md"
    payload = {
        "verdicts": make_verdicts(5),
        "statistics": {"total": 5, "supported": 5, "contradicted": 0,
                       "unsupported": 0, "ambiguous": 0},
    }
    write_verdicts(inp, payload)
    rc, log = run_synth(inp, out)
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    ok = rc == 0 and "Подтверждено: **5**" in text and "Всего claims: **5**" in text
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, отчёт={out.exists()}")
    assert ok, f"{name}: rc={rc} log={log}"


def test_empty_list(tmp_path: Path) -> None:
    name = "L1.3 пустой list []"
    inp = tmp_path / "verdicts_empty.json"
    out = tmp_path / "final_report.md"
    write_verdicts(inp, [])
    rc, log = run_synth(inp, out)
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    ok = rc == 0 and "Всего claims: **0**" in text and "Подтверждено: **0**" in text
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, отчёт={out.exists()}")
    assert ok, f"{name}: rc={rc} log={log}"


def test_broken_json(tmp_path: Path) -> None:
    name = "L1.4 битый JSON → понятная ошибка"
    inp = tmp_path / "verdicts_broken.json"
    inp.write_text("{not valid json!!!", encoding="utf-8")
    rc, log = run_synth(inp, tmp_path / "final_report.md")
    ok = rc != 0 and "валидным JSON" in log
    _log("PASS" if ok else "FAIL", name, f"rc={rc} (ожидался !=0), stderr={'валидным JSON' in log}")
    assert ok, f"{name}: rc={rc} log={log}"


def test_null_json(tmp_path: Path) -> None:
    name = "L1.5 JSON null → понятная ошибка"
    inp = tmp_path / "verdicts_null.json"
    inp.write_text("null", encoding="utf-8")
    rc, log = run_synth(inp, tmp_path / "final_report.md")
    ok = rc != 0 and "пуст (null)" in log
    _log("PASS" if ok else "FAIL", name, f"rc={rc} (ожидался !=0)")
    assert ok, f"{name}: rc={rc} log={log}"


# ─────────────────────────── Уровень 2: сценарии данных ───────────────────────────

def test_all_supported(tmp_path: Path) -> None:
    name = "L2.1 все SUPPORTED → сводка"
    inp = tmp_path / "v.json"
    out = tmp_path / "final_report.md"
    write_verdicts(inp, make_verdicts(7))
    rc, log = run_synth(inp, out)
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    ok = rc == 0 and "Подтверждено: **7**" in text and "Всего claims: **7**" in text
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, Подтверждено 7={'Подтверждено: **7**' in text}")
    assert ok, f"{name}: rc={rc} log={log}"


def test_mixed_verdicts(tmp_path: Path) -> None:
    name = "L2.2 смешанные вердикты → сводка"
    inp = tmp_path / "v.json"
    out = tmp_path / "final_report.md"
    verdicts = [
        {"claim_id": i + 1, "claim_text": f"c{i}", "verdict": v}
        for i, v in enumerate(["SUPPORTED"] * 2 + ["CONTRADICTED", "UNSUPPORTED",
                                                   "AMBIGUOUS", ""])
    ]
    write_verdicts(inp, verdicts)
    rc, log = run_synth(inp, out)
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    ok = (rc == 0
          and "Подтверждено: **2**" in text
          and "Опровергнуто: **1**" in text
          and "Требует проверки: **1**" in text
          and "Противоречиво: **1**" in text
          and "Всего claims: **6**" in text)
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, сводка корректна={ok}")
    assert ok, f"{name}: rc={rc} log={log} text={text[:500]}"


def test_str_claim_id(tmp_path: Path) -> None:
    name = "L2.3 строковый claim_id («claim-1»)"
    inp = tmp_path / "v.json"
    out = tmp_path / "final_report.md"
    write_verdicts(inp, make_verdicts(3, claim_id_fn=lambda i: f"claim-{i + 1}"))
    rc, log = run_synth(inp, out)
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    ok = rc == 0 and "### Claim claim-1" in text
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, заголовок={'### Claim claim-1' in text}")
    assert ok, f"{name}: rc={rc} log={log} text={text[:300]}"


def test_missing_verdict(tmp_path: Path) -> None:
    name = "L2.4 verdict отсутствует → ❓"
    inp = tmp_path / "v.json"
    out = tmp_path / "final_report.md"
    write_verdicts(inp, [{"claim_id": 1, "claim_text": "no verdict here"}])
    rc, log = run_synth(inp, out)
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    ok = rc == 0 and "❓" in text
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, ❓={'❓' in text}")
    assert ok, f"{name}: rc={rc} log={log} text={text[:300]}"


def test_llm_unavailable(tmp_path: Path) -> None:
    name = "L2.5 LLM недоступен (нет ключа) → fallback"
    inp = tmp_path / "v.json"
    out = tmp_path / "final_report.md"
    write_verdicts(inp, make_verdicts(2))
    rc, log = run_synth(inp, out)
    text = out.read_text(encoding="utf-8") if out.exists() else ""
    ok = rc == 0 and "_LLM недоступен" in text
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, fallback={'_LLM недоступен' in text}")
    assert ok, f"{name}: rc={rc} log={log}"


# ─────────────────────────── Уровень 3: интеграция ───────────────────────────

def test_integration_exp1_verdicts(tmp_path: Path) -> None:
    name = "L3.1 exp1 verdicts.json (list, реальный артефакт)"
    src = EXP1 / "verdicts.json"
    if not src.exists():
        _log("SKIP", name, "артефакт отсутствует")
        return
    rc, log = run_synth(src, tmp_path / "final_report.md")
    ok = rc == 0 and (tmp_path / "final_report.md").exists()
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, отчёт={ok}")
    assert ok, f"{name}: rc={rc} log={log}"


def test_integration_exp1_verdicts_processed(tmp_path: Path) -> None:
    name = "L3.2 exp1 verdicts_processed.json (list, с _post_processed)"
    src = EXP1 / "verdicts_processed.json"
    if not src.exists():
        _log("SKIP", name, "артефакт отсутствует")
        return
    rc, log = run_synth(src, tmp_path / "final_report.md")
    ok = rc == 0 and (tmp_path / "final_report.md").exists()
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, отчёт={ok}")
    assert ok, f"{name}: rc={rc} log={log}"


def test_integration_verdicts_with_numeric(tmp_path: Path) -> None:
    name = "L3.3 verdicts_with_numeric (если создан)"
    candidates = [
        EXP1 / "verdicts_with_numeric.json",
        Path("/tmp/rivulet-work/verdicts_with_numeric.json"),
    ]
    src = next((p for p in candidates if p.exists()), None)
    if src is None:
        _log("SKIP", name, "артефакт не создан")
        return
    rc, log = run_synth(src, tmp_path / "final_report.md")
    ok = rc == 0 and (tmp_path / "final_report.md").exists()
    _log("PASS" if ok else "FAIL", name, f"rc={rc}, отчёт={ok}")
    assert ok, f"{name}: rc={rc} log={log}"


# ─────────────────────────── сводка / standalone ───────────────────────────

def run_all(work: Path) -> None:
    tests = [
        ("L1.1", test_list_flat_verdicts), ("L1.2", test_dict_verdicts_statistics),
        ("L1.3", test_empty_list), ("L1.4", test_broken_json), ("L1.5", test_null_json),
        ("L2.1", test_all_supported), ("L2.2", test_mixed_verdicts),
        ("L2.3", test_str_claim_id), ("L2.4", test_missing_verdict),
        ("L2.5", test_llm_unavailable),
        ("L3.1", test_integration_exp1_verdicts),
        ("L3.2", test_integration_exp1_verdicts_processed),
        ("L3.3", test_integration_verdicts_with_numeric),
    ]
    for tag, fn in tests:
        case_dir = work / tag
        case_dir.mkdir(parents=True, exist_ok=True)
        try:
            fn(case_dir)
        except AssertionError:
            continue
    print("=" * 60)
    print(f"СВОДКА: PASS={len(PASSED)} FAIL={len(FAILED)} SKIP={len(SKIPPED)}")
    for line in FAILED:
        print("  ✗ " + line)
    print("=" * 60)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rivulet-synth-") as tmp:
        run_all(Path(tmp))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())