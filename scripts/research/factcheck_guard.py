#!/usr/bin/env python3
"""factcheck_guard.py — страховка выдачи факт-чекера (P0).

Проблема (trace): LLM факт-чекера иногда возвращает не-JSON; вердикт падает в
`verdicts.json` как UNSUPPORTED conf=0.1 + critical caveat "LLM error: ...".
Post_processor трактует это как критичное свидетельство → cap confidence →
UNSUPPORTED → OPEN/аларм. Тезисы ломаются артефактом сбоя выдачи, а не анализом.

Фикс: retry-цикл в run_pipeline.sh + этот guard:
  - validate_verdicts: схема + маркеры LLM-сбоя (broken records);
  - mark_parse_fail: LLM-сбой превращается в ЯВНЫЙ маркер `llm_parse_fail` и
    reason "LLM_PARSE_FAIL: ..." БЕЗ critical caveat — не валидируется как
    свидетельство (пост-процессор не капает confidence и не триггерит трибунал).

Использование:
    python3 factcheck_guard.py <verdicts.json>                # валидация (rc 0/1)
    python3 factcheck_guard.py <verdicts.json> --mark-parse-fail --out OUT.json
"""
import json
import re
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path

# Маркеры сбоя выдачи LLM, которые НЕ являются свидетельством о тезисе.
_LLM_ERROR_PATTERNS = (
    r"LLM error",
    r"Expecting value",
    r"Invalid JSON",
    r"JSONDecodeError",
    r"control character",
    r"non-JSON",
)
_LLM_ERROR_RE = re.compile("|".join(_LLM_ERROR_PATTERNS), re.IGNORECASE)

_ALLOWED_VERDICTS = {"SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "AMBIGUOUS", "OPEN"}

# Кол-во попыток факт-чекера, после которых выполняется mark_parse_fail.
MAX_RETRIES_DEFAULT = 3


def is_llm_error_text(text):
    """True, если текст содержит маркер LLM-сбоя парсинга."""
    if not text:
        return False
    return bool(_LLM_ERROR_RE.search(str(text)))


def record_is_broken(record):
    """True, если вердикт — артефакт сбоя выдачи LLM, а не анализ.

    Признаки: LLM-маркер в reason/caveats/или критичная caveat с таким текстом.
    """
    if not isinstance(record, dict):
        return True
    if is_llm_error_text(record.get("reason")):
        return True
    caveats = record.get("caveats") or []
    if isinstance(caveats, list):
        for c in caveats:
            text = c.get("text", "") if isinstance(c, dict) else str(c)
            if is_llm_error_text(text):
                return True
    return False


def validate_verdicts(data):
    """Проверяет verdicts.json на пригодность для последующих этапов.

    Возвращает (ok: bool, problems: list[str]).
    Проблемы: не-dict запись, отсутствие ключей claim_id/claim_text/verdict/
    confidence, недопустимый вердикт, или LLM-маркер сбоя (broken record).
    """
    problems = []
    items = data
    if isinstance(data, dict):
        items = data.get("verdicts", [data]) or []
    if not isinstance(items, list):
        items = [items]

    for i, rec in enumerate(items):
        if not isinstance(rec, dict):
            problems.append(f"Item {i}: не-словарь ({type(rec).__name__})")
            continue
        for key in ("claim_id", "claim_text", "verdict", "confidence"):
            if key not in rec:
                problems.append(f"Item {i}: отсутствует ключ `{key}`")
        verdict = rec.get("verdict")
        if verdict is not None and str(verdict).upper() not in _ALLOWED_VERDICTS:
            problems.append(f"Item {i}: недопустимый вердикт `{verdict}`")
        if record_is_broken(rec):
            problems.append(
                f"Item {i} (claim {rec.get('claim_id')}): LLM-сбой парсинга "
                f"('LLM error' в reason/caveats)"
            )
    return not problems, problems


def mark_parse_fail(data):
    """Санитизирует LLM-сбой: явный маркер без critical caveat.

    Для каждой broken-записи:
      - verdict остаётся UNSUPPORTED, confidence 0.1 (нейтрально, не как сбой);
      - критичная caveat "LLM error" удаляется (НЕ свидетельство);
      - добавляется info-caveat "LLM_PARSE_FAIL: ..." и флаг `llm_parse_fail: True`;
      - reason = "LLM_PARSE_FAIL: <исходный текст сбоя>".

    Возвращает (fixed_list, report_dict).
    """
    items = data
    if isinstance(data, dict):
        items = data.get("verdicts", [data]) or []
    if not isinstance(items, list):
        items = [items]

    fixed = []
    report = {"total": len(items), "fixed": 0, "broken_ids": []}
    for rec in items:
        if isinstance(rec, dict) and record_is_broken(rec):
            rec = dict(rec)
            rec["llm_parse_fail"] = True
            rec["verdict"] = "UNSUPPORTED"
            rec["confidence"] = 0.1
            reason = rec.get("reason", "LLM error: не-JSON ответ")
            rec["reason"] = f"LLM_PARSE_FAIL: {reason}"
            caveats = rec.get("caveats") or []
            kept = []
            if not isinstance(caveats, list):
                caveats = []
            for c in caveats:
                text = c.get("text", "") if isinstance(c, dict) else str(c)
                if is_llm_error_text(text):
                    continue  # НЕ оставляем LLM-сбой как критичное свидетельство
                kept.append(c)
            kept.append({"severity": "info", "text": "LLM_PARSE_FAIL: LLM не вернул валидный JSON"})
            rec["caveats"] = kept
            report["fixed"] += 1
            report["broken_ids"].append(rec.get("claim_id"))
        fixed.append(rec)
    return fixed, report


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 factcheck_guard.py <verdicts.json> "
              "[--mark-parse-fail] [--out OUT.json]", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    mark = "--mark-parse-fail" in sys.argv
    out_path = None
    if "--out" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--out") + 1])

    try:
        data = _load_json(path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"ОШИБКА: не удалось прочитать {path}: {exc}", file=sys.stderr)
        sys.exit(2)

    ok, problems = validate_verdicts(data)

    if mark:
        fixed, report = mark_parse_fail(data)
        dest = out_path or path
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(fixed, f, ensure_ascii=False, indent=2)
        print(f"✅ factcheck_guard: помечено LLM_PARSE_FAIL: {report['fixed']}"
              f" из {report['total']} → {dest}")
        sys.exit(0)

    if not ok:
        for p in problems:
            print(f"⚠️ factcheck_guard: {p}", file=sys.stderr)
        print(f"❌ factcheck_guard: {len(problems)} проблем — факт-чекер требует retry", file=sys.stderr)
        sys.exit(1)
    print("✅ factcheck_guard: выдача факт-чекера валидна (0 LLM-сбоев)")
    sys.exit(0)


if __name__ == "__main__":
    main()