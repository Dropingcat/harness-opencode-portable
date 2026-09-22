#!/usr/bin/env python3
"""post_processor.py — детерминированная пост-обработка вердиктов.

Читает verdicts.json, применяет правила из rules.yaml, пишет verdicts_processed.json.
Решения принимаются КОДОМ, не LLM. LLM производит свидетельства (caveats, numbers),
код — решения (cap confidence, mark problematic, trigger tribunal).

Usage:
    python3 post_processor.py <verdicts.json> <rules.yaml> <verdicts_processed.json>
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import re
import yaml
from pathlib import Path


def load_rules(rules_path):
    with open(rules_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_verdicts(verdicts_path):
    with open(verdicts_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("verdicts", [data])


def count_caveats(verdict):
    caveats = verdict.get("caveats", [])
    if isinstance(caveats, list):
        critical = [c for c in caveats if isinstance(c, dict) and c.get("severity") == "critical"]
        warnings = [c for c in caveats if isinstance(c, dict) and c.get("severity") == "warning"]
        info = [c for c in caveats if isinstance(c, dict) and c.get("severity") == "info"]
        # строковые caveats: эвристика критичности по маркерам
        crit_markers = ("caveat", "contradict", "не подтвержден", "не подтверждён",
                        "без источника", "несоглас", "отсутствует источник",
                        "may differ", "unverified", "no source", "contradicts",
                        "риск", "проблема", "недостаточн", "неполн")
        for c in caveats:
            if isinstance(c, str):
                low = c.lower()
                if any(m in low for m in crit_markers):
                    critical.append(c)
                else:
                    info.append(c)
        return len(caveats), len(critical), len(warnings), len(info)
    return 0, 0, 0, 0


def match_tribunal_condition(condition, verdict, total, critical):
    """Вычисляет условие tribunal_rules (trigger_when/skip_when) из rules.yaml.

    Условия определяются КОДОМ (не LLM). Неизвестное условие → False.
    """
    if condition == "critical_caveat_count_gte_1":
        return critical >= 1
    if condition == "verdict_ambiguous_after_postprocess":
        return verdict.get("verdict") == "AMBIGUOUS"
    if condition == "verdict_contradicted":
        return verdict.get("verdict") == "CONTRADICTED"
    if condition == "no_caveats":
        return total == 0
    if condition == "confidence_gte_0.8_and_no_critical":
        try:
            confidence = float(verdict.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        return confidence >= 0.8 and critical == 0
    return False


def decide_tribunal(verdict, rules, total, critical, all_changes):
    """Решение о трибунале по tribunal_rules из rules.yaml.

    Читает trigger_when / skip_when (правила КОДОМ, не LLM):
      - skip_when имеет приоритет над trigger_when (снимает ранее поставленный флаг);
      - если trigger_when/skip_when в конфиге нет — legacy fallback (critical >= 1).
    """
    tribunal_rules = rules.get("tribunal_rules", {})
    trigger_when = tribunal_rules.get("trigger_when") or []
    skip_when = tribunal_rules.get("skip_when") or []

    if not trigger_when and not skip_when:
        if critical >= 1 and not verdict.get("trigger_tribunal"):
            verdict["trigger_tribunal"] = True
            verdict["_tribunal_reason"] = "critical_caveat_after_postprocess"
            all_changes.append("tribunal triggered (critical caveat in postprocess)")
        return

    matched_triggers = [t for t in trigger_when
                        if match_tribunal_condition(t, verdict, total, critical)]
    matched_skips = [s for s in skip_when
                     if match_tribunal_condition(s, verdict, total, critical)]

    if matched_skips:
        if verdict.pop("trigger_tribunal", False):
            all_changes.append("tribunal skipped (rules.yaml skip_when: "
                               + ", ".join(matched_skips) + ")")
        verdict.pop("_tribunal_reason", None)
    elif matched_triggers and not verdict.get("trigger_tribunal"):
        verdict["trigger_tribunal"] = True
        verdict["_tribunal_reason"] = "rules.yaml trigger_when: " + ", ".join(matched_triggers)
        all_changes.append("tribunal triggered (rules.yaml trigger_when: "
                           + ", ".join(matched_triggers) + ")")


def prevalidate_with_schemas(verdicts, warn=True):
    """Pydantic-предвалидация вердиктов (verdict_schemas.py) — WARNING, не блокирует.

    Подключение verdict_schemas как предвалидации: ошибки схемы логируются в stderr,
    но не останавливают пост-обработку (детерминированные правила работают дальше).
    """
    try:
        from verdict_schemas import validate_verdicts
    except ImportError as exc:
        print(f"⚠️ verdict_schemas недоступен ({exc}) — предвалидация пропущена",
              file=sys.stderr)
        return []
    errors = validate_verdicts(verdicts)
    if warn:
        for err in errors:
            print(f"⚠️ verdict_schemas предвалидация: {err}", file=sys.stderr)
    return errors


def _claim_has_numbers(verdict):
    """Есть ли в claim числа (по extract_numbers — источнику истины numeric_comparator).

    Если extract_numbers недоступен (нет соседнего модуля) — грубая проверка цифр.
    """
    text = verdict.get("claim_text", "") or ""
    try:
        from numeric_comparator import extract_numbers
        return bool(extract_numbers(text))
    except Exception:
        return bool(re.search(r"\d", text))


def check_numeric(verdict):
    nc = verdict.get("numeric_comparison")
    if not nc:
        # обратная совместимость: старые артефакты (SKILL.md <0.3) писали
        # `number_comparison`; нормализуем в канонический ключ `numeric_comparison`
        nc = verdict.get("number_comparison")
        if nc:
            verdict["numeric_comparison"] = nc
    if not nc:
        return None
    status = nc.get("status", "")
    if status == "mismatch":
        return "numeric_mismatch"
    if status == "partial_match":
        return "numeric_partial_match"
    if status == "qualifier_mismatch":
        return "qualifier_mismatch"
    if status == "dimension_mismatch":
        return "dimension_mismatch"
    if status == "no_numbers_in_claim":
        # в claim нет чисел (definition-claim) — НЕ демоушим (правило cap 0.7 не применяется)
        return None
    if status == "no_data":
        # различаем «в claim нет чисел» (не демоушим) и «числа есть, но не проверяемы»
        if not _claim_has_numbers(verdict):
            return None
        return "no_numeric_data"
    return None


def check_source_trust(verdict):
    sources = verdict.get("sources", [])
    if not sources:
        return None
    trust_values = []
    for s in sources:
        if isinstance(s, dict):
            t = s.get("trust", s.get("reliability", 0.5))
            trust_values.append(t)
    if trust_values and max(trust_values) < 0.6:
        return "low_trust_only"
    return None


def check_evidence_trust(verdict):
    """Проверяет trust из evidence[] (Evidence Contract, У2).

    Если evidence существует — использует его, иначе fallback на старый
    check_source_trust (обратная совместимость со старыми verdicts).
    """
    evidence = verdict.get("evidence")
    if evidence is not None:
        trust_values = []
        for e in evidence:
            if isinstance(e, dict):
                trust_values.append(e.get("trust", 0.5))
        if trust_values and max(trust_values) < 0.6:
            return "low_trust_only"
        return None
    return check_source_trust(verdict)


def _coerce_confidence(verdict):
    """Нормализует confidence в float. LLM может вернуть строку "0.95"; при
    непарсибельном значении — fallback на 1.0 (не демоушим без причины)."""
    raw = verdict.get("confidence", 1.0)
    if isinstance(raw, bool):
        verdict["confidence"] = 1.0 if raw else 0.0
        return
    if isinstance(raw, (int, float)):
        return
    try:
        verdict["confidence"] = float(raw)
    except (TypeError, ValueError):
        print(f"⚠ confidence не парсится ({raw!r}) → fallback 1.0 "
              f"(claim {verdict.get('claim_id')})", file=sys.stderr)
        verdict["confidence"] = 1.0


def apply_rule(verdict, rule_name, rule_config, rules):
    action = rule_config.get("action")
    reason = rule_config.get("reason", rule_name)
    changes = []

    if action == "cap_confidence":
        cap = rule_config.get("value", 0.6)
        original = verdict.get("confidence", 1.0)
        if original > cap:
            verdict["confidence"] = cap
            verdict["_capped_by"] = reason
            verdict["_original_confidence"] = original
            changes.append(f"confidence {original} → {cap} ({reason})")

    elif action == "set_verdict":
        new_verdict = rule_config.get("value", "UNSUPPORTED")
        old = verdict.get("verdict", "")
        if old != new_verdict:
            verdict["verdict"] = new_verdict
            verdict["_verdict_changed_by"] = reason
            verdict["_original_verdict"] = old
            changes.append(f"verdict {old} → {new_verdict} ({reason})")
        if "cap_confidence" in rule_config:
            cap = rule_config["cap_confidence"]
            original = verdict.get("confidence", 1.0)
            if original > cap:
                verdict["confidence"] = cap
                verdict["_capped_by"] = reason
                changes.append(f"confidence → {cap}")

    elif action == "mark_problematic":
        verdict["problematic"] = True
        verdict["_problematic_reason"] = reason
        changes.append(f"marked problematic ({reason})")

    elif action == "trigger_tribunal":
        verdict["trigger_tribunal"] = True
        verdict["_tribunal_reason"] = reason
        changes.append(f"tribunal triggered ({reason})")

    return changes


def post_process_verdict(verdict, rules):
    all_changes = []
    total, critical, warnings, info = count_caveats(verdict)
    _coerce_confidence(verdict)

    # Caveat rules
    caveat_rules = rules.get("caveat_rules", {})
    if critical >= 1:
        if "critical_caveat" in caveat_rules:
            all_changes += apply_rule(verdict, "critical_caveat", caveat_rules["critical_caveat"], rules)
        if "critical_caveat_count_gte_1" in caveat_rules:
            all_changes += apply_rule(verdict, "critical_caveat_count_gte_1", caveat_rules["critical_caveat_count_gte_1"], rules)
    if total >= 3 and "caveats_count_gte_3" in caveat_rules:
        all_changes += apply_rule(verdict, "caveats_count_gte_3", caveat_rules["caveats_count_gte_3"], rules)
    elif total >= 2 and "caveats_count_gte_2" in caveat_rules:
        all_changes += apply_rule(verdict, "caveats_count_gte_2", caveat_rules["caveats_count_gte_2"], rules)

    # Numeric rules
    numeric_key = check_numeric(verdict)
    if numeric_key and numeric_key in rules.get("numeric_rules", {}):
        all_changes += apply_rule(verdict, numeric_key, rules["numeric_rules"][numeric_key], rules)

    # Source trust rules
    trust_key = check_evidence_trust(verdict)
    if trust_key and trust_key in rules.get("source_trust", {}):
        if isinstance(rules["source_trust"][trust_key], dict):
            all_changes += apply_rule(verdict, trust_key, rules["source_trust"][trust_key], rules)

    # Verdict recalculation (after caveat caps)
    final_confidence = verdict.get("confidence", 1.0)
    final_verdict = verdict.get("verdict", "SUPPORTED")
    # Gap-claim (слой оценки content_verdict): GAP-UNVERIFIED — осознанное «нет данных»,
    # НЕ «опровергнуто» (verification-plan B.4). Не сворачиваем в UNSUPPORTED и не
    # маркируем problematic автоматом.
    _is_gap = str((verdict.get("content_verdict") or {}).get("claim_class", "")).lower() == "gap"
    recalc = rules.get("verdict_recalculation", {})
    if _is_gap and final_verdict == "GAP-UNVERIFIED":
        all_changes.append("gap-claim: GAP-UNVERIFIED сохранён (нет данных ≠ опровержение)")
        final_verdict = "GAP-UNVERIFIED"
    elif final_confidence < 0.6 and "confidence_lt_0.6" in recalc:
        all_changes += apply_rule(verdict, "confidence_lt_0.6", recalc["confidence_lt_0.6"], rules)
    elif 0.6 <= final_confidence < 0.8 and "confidence_0.6_to_0.8" in recalc:
        all_changes += apply_rule(verdict, "confidence_0.6_to_0.8", recalc["confidence_0.6_to_0.8"], rules)

    # Problematic rules (after caps and recalculation)
    problematic_rules = rules.get("problematic_rules", {})
    final_confidence = verdict.get("confidence", 1.0)
    final_verdict = verdict.get("verdict", "SUPPORTED")

    if final_verdict == "UNSUPPORTED" and "verdict_unsupported" in problematic_rules:
        all_changes += apply_rule(verdict, "verdict_unsupported", problematic_rules["verdict_unsupported"], rules)
    elif final_verdict == "AMBIGUOUS" and "verdict_ambiguous" in problematic_rules:
        all_changes += apply_rule(verdict, "verdict_ambiguous", problematic_rules["verdict_ambiguous"], rules)
    elif _is_gap and final_verdict == "GAP-UNVERIFIED":
        all_changes.append("gap-claim: verdict_unsupported→problematic не применяется (GAP-UNVERIFIED)")
    elif final_confidence < rules.get("thresholds", {}).get("problematic", 0.6):
        if "confidence_lt_0.6" in problematic_rules:
            all_changes += apply_rule(verdict, "confidence_lt_0.6", problematic_rules["confidence_lt_0.6"], rules)

    # Tribunal decision (rules.yaml: trigger_when / skip_when)
    decide_tribunal(verdict, rules, total, critical, all_changes)

    verdict["_post_processed"] = True
    verdict["_changes"] = all_changes
    verdict["_caveats_total"] = total
    verdict["_caveats_critical"] = critical
    return verdict


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 post_processor.py <verdicts.json> <rules.yaml> <verdicts_processed.json>", file=sys.stderr)
        sys.exit(1)
    verdicts_path, rules_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]
    rules = load_rules(rules_path)
    verdicts = load_verdicts(verdicts_path)
    prevalidate_with_schemas(verdicts)
    processed = []
    for v in verdicts:
        pv = post_process_verdict(v, rules)
        processed.append(pv)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)
    supported = sum(1 for v in processed if v.get("verdict") == "SUPPORTED")
    unsupported = sum(1 for v in processed if v.get("verdict") == "UNSUPPORTED")
    ambiguous = sum(1 for v in processed if v.get("verdict") == "AMBIGUOUS")
    problematic = sum(1 for v in processed if v.get("problematic"))
    tribunal = sum(1 for v in processed if v.get("trigger_tribunal"))
    capped = sum(1 for v in processed if v.get("_capped_by"))
    print(f"✅ Post-processed {len(processed)} verdicts:")
    print(f"  SUPPORTED: {supported} | UNSUPPORTED: {unsupported} | AMBIGUOUS: {ambiguous}")
    print(f"  Problematic: {problematic} | Tribunal triggered: {tribunal} | Confidence capped: {capped}")


if __name__ == "__main__":
    main()