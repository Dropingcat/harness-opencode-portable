#!/usr/bin/env python3
"""merge_numeric.py — вливает результаты numeric_comparator в вердикты (Этап 5.1).

Детерминированный код. Соединяет выход numeric_comparator.py (numeric_result.json,
groups[].claim_id + group_status) с вердиктами факт-чекера (verdicts.json) по
claim_id и пишет verdicts_with_numeric.json, который затем читает post_processor.py.

Стратегия merge:
  - Детерминированный status из numeric_result имеет приоритет (решения — КОДОМ).
  - Если детерминированный status = no_data, а LLM вручную проставил status —
    сохраняем ручной (детерминированный ничего не знает).
  - Детали/объяснения LLM не теряются: они сохраняются в `llm_details`.
  - Вердикт без совпадения по claim_id остаётся без изменений (no_data).

Usage:
    python3 merge_numeric.py <verdicts.json> <numeric_result.json> <output.json>
"""
import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_verdicts(data):
    """Приводит вход к (list_verdicts, shape). Сохраняет форму для записи."""
    if isinstance(data, list):
        return data, "list"
    if isinstance(data, dict):
        if isinstance(data.get("verdicts"), list):
            return data["verdicts"], "verdicts"
        if isinstance(data.get("groups"), list):
            return data["groups"], "groups"
        if any(k in data for k in ("claim_id", "claim_text", "verdict")):
            return [data], "single"
    return [], "list"


def build_numeric_index(numeric_data):
    """Индекс по numeric_result: {("claim_id"|"original_index", str(key)): entry}.

    entry = {status, details, n_sources}. Запись для группы входит под каждым
    доступным ключом (claim_id и/или original_index), значения нормализованы в str
    для устойчивого матчинга int/str.
    """
    index = {}
    for group in numeric_data.get("groups", []):
        if not isinstance(group, dict):
            continue
        status = group.get("group_status")
        entry = {
            "status": status if isinstance(status, str) else "",
            "details": _group_details(group),
            "n_sources": group.get("n_sources"),
        }
        keys = []
        if group.get("claim_id") is not None:
            keys.append(("claim_id", str(group["claim_id"])))
        if group.get("original_index") is not None:
            keys.append(("original_index", str(group["original_index"])))
        if not keys:
            continue
        for kind, key in keys:
            index[(kind, key)] = entry
    return index


def _group_details(group):
    """Собирает детали: объяснения входящих в группу claims (внутри source-сравнений)."""
    status = group.get("group_status")
    claims = group.get("claims", []) or []
    seen = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        explanation = c.get("explanation")
        if explanation and str(explanation) not in seen:
            seen.append(str(explanation))
    if seen:
        return "; ".join(seen)
    return f"numeric_comparator: group_status={status}"


def lookup_numeric(index, verdict):
    """Ищет entry для вердикта по claim_id, затем по original_index."""
    for kind, val in (("claim_id", verdict.get("claim_id")),
                      ("original_index", verdict.get("original_index"))):
        if val is None:
            continue
        entry = index.get((kind, str(val)))
        if entry:
            return entry
    return None


def merge_numeric_into_verdict(verdict, numeric_entry):
    """Инжектит verdict["numeric_comparison"] = {status, details, source}.

    Приоритет: детерминированный status из numeric_result (решения — кодом).
    Если детерминированный status = no_data, а LLM вручную проставил status и
    details — они сохраняются (детерминированный ничего не знает). Детали LLM
    не теряются и при перезаписи: уезжают в `llm_details`.
    """
    existing = verdict.get("numeric_comparison")
    if not isinstance(existing, dict):
        existing = {}
    merged = dict(existing)

    det_status = numeric_entry["status"]
    det_details = numeric_entry["details"]
    if det_status and det_status != "no_data":
        merged["status"] = det_status
        if det_details:
            if merged.get("details") and merged["details"] != det_details:
                merged.setdefault("llm_details", merged["details"])
            merged["details"] = det_details
    elif not merged.get("status"):
        merged["status"] = det_status or "no_data"
        if det_details and not merged.get("details"):
            merged["details"] = det_details

    merged["source"] = "numeric_comparator"
    merged["n_sources"] = numeric_entry["n_sources"]

    verdict["numeric_comparison"] = merged


def write_output(data, verdicts, shape, output_path):
    if shape == "list":
        out = verdicts
    elif shape in ("verdicts", "groups"):
        out = dict(data)
        out[shape] = verdicts
    else:
        out = verdicts[0] if verdicts else data
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 merge_numeric.py <verdicts.json> <numeric_result.json> <output.json>",
              file=sys.stderr)
        sys.exit(1)
    verdicts_path, numeric_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        verdicts_data = load_json(verdicts_path)
        numeric_data = load_json(numeric_path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"ОШИБКА: не удалось прочитать входной JSON: {exc}", file=sys.stderr)
        sys.exit(2)

    verdicts, shape = normalize_verdicts(verdicts_data)
    if not isinstance(numeric_data, dict) or not isinstance(numeric_data.get("groups"), list):
        numeric_data = {"groups": []}

    index = build_numeric_index(numeric_data)
    if not index:
        print("⚠ numeric_result.json пуст (нет groups) — ничего не влито")
    else:
        print(f"  numeric_result: {len(numeric_data['groups'])} groups → индекс {len(index)} ключей")

    merged_count = 0
    skipped = 0
    for v in verdicts:
        if not isinstance(v, dict):
            skipped += 1
            continue
        entry = lookup_numeric(index, v)
        if entry:
            merge_numeric_into_verdict(v, entry)
            merged_count += 1
        else:
            skipped += 1

    write_output(verdicts_data, verdicts, shape, output_path)
    print(f"✅ Merge numeric: {merged_count} вердиктов получили numeric_comparison "
          f"({len(verdicts)} всего, {skipped} без изменений)")
    for v in verdicts:
        if isinstance(v, dict) and v.get("numeric_comparison", {}).get("status") in (
                "mismatch", "qualifier_mismatch", "dimension_mismatch"):
            print(f"  claim {v.get('claim_id')}: "
                  f"{v['numeric_comparison']['status']} (source=numeric_comparator)")


if __name__ == "__main__":
    main()