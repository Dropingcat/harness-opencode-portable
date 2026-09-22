#!/usr/bin/env python3
"""gap_rules.py — gap vs опровергнуто + cap UNSUPPORTED+high-conf
(инкапсулированный модуль).

Различает три ситуации для gap-claim («заявленный пробел»):
  - внешние источники подтверждают «задача не решена / данных нет» → SUPPORTED(gap);
  - ничего не найдено ни в одном слое каскада                        → GAP-UNVERIFIED
    (≠ UNSUPPORTED: это НЕ «опровергнуто/необоснованно»);
  - внешний источник прямо утверждает обратное (решение существует)  → CONTRADICTED.

Защитное правило (закрывает пару UNSUPPORTED+confidence>0.6, verification-plan A.2.2):
  UNSUPPORTED + confidence > 0.6 → срезать confidence до 0.5 с пометкой
  _capped_by: unsupported_conf_contradiction.

Также: для gap-claims НЕ применять verdict_unsupported→problematic автоматом
(этот маркер ставит пост-процессор; см. integration в post_processor.py).

Модуль самодостаточен и тестируется отдельно (test_gap_rules.py).

CLI:
  python3 gap_rules.py --claim-class gap --verdict UNSUPPORTED --confidence 0.9
"""
import argparse
import json
import sys

CAP_CONFIDENCE = 0.5
CONTRADICTION_MARKERS = [
    "решена", "решено", "решен", "решён", "установлено", "установлена",
    "установлены", "известно", "описано", "показано", "доказано",
    "разработано", "разработан", "предложен", "предложено",
    "данные имеются", "данные получены", "исследовано", "не является пробелом",
    "является решённой", "является решенной", "решена задача",
]

GAP_SUPPORT_MARKERS = [
    "остаётся нерешённ", "остается нерешенн", "нерешённой задачей",
    "нерешенной задачей", "отсутствуют", "отсутствует", "отсутствие",
    "не изучен", "не изучено", "неизвестн", "нет данных", "данные отсутствуют",
    "требует дальнейших", "недостаточно", "пробел", "не хватает", "не решено",
    "не решена", "малоизучен", "открытым остаётся", "недостаточно изучено",
]


def cap_unsupported_high_conf(verdict, threshold=0.6, cap_value=CAP_CONFIDENCE):
    """UNSUPPORTED + confidence > threshold → cap до cap_value с пометкой.

    Возвращает (обновлённый_verdict, changed: bool).
    """
    if not isinstance(verdict, dict):
        return verdict, False
    if str(verdict.get("verdict", "")).upper() != "UNSUPPORTED":
        return verdict, False
    try:
        conf = float(verdict.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return verdict, False
    if conf > threshold:
        verdict["_original_confidence"] = conf
        verdict["confidence"] = cap_value
        verdict["_capped_by"] = "unsupported_conf_contradiction"
        return verdict, True
    return verdict, False


def is_gap_supported_by_source(source_text):
    """Внешний источник подтверждает пробел («задача не решена / нет данных»)."""
    low = (source_text or "").lower()
    return any(m in low for m in GAP_SUPPORT_MARKERS)


def is_gap_contradicted_by_source(source_text):
    """Внешний источник прямо утверждает, что пробел закрыт (решение есть)."""
    low = (source_text or "").lower()
    return any(m in low for m in CONTRADICTION_MARKERS)


def decide_gap_verdict(external_sources, gap_support_hits=0, gap_contradictions=0):
    """Принимает вердикт для gap-claim по внешним источникам.

    Входы: список внешних источников (origin=external, accepted).
    Возвращает {"verdict", "confidence", "reason", "gap_supported", "gap_contradicted"}.
    """
    if gap_contradictions > 0:
        return {
            "verdict": "CONTRADICTED",
            "confidence": 0.85,
            "reason": "внешний источник прямо указывает, что пробел закрыт",
            "gap_supported": False,
            "gap_contradicted": True,
        }
    if gap_support_hits >= 1:
        return {
            "verdict": "SUPPORTED",
            "confidence": min(0.9, 0.6 + 0.1 * gap_support_hits),
            "reason": "пробел подтверждён внешней литературой (обзоры/статьи)",
            "gap_supported": True,
            "gap_contradicted": False,
        }
    if external_sources:
        return {
            "verdict": "GAP-UNVERIFIED",
            "confidence": 0.4,
            "reason": "внешние источники найдены, но пробел не подтверждён и не опровергнут",
            "gap_supported": False,
            "gap_contradicted": False,
        }
    return {
        "verdict": "GAP-UNVERIFIED",
        "confidence": 0.3,
        "reason": "ни один слой каскада не дал внешних источников — пробел не "
                  "подтверждён и не опровергнут (НЕ UNSUPPORTED)",
        "gap_supported": False,
        "gap_contradicted": False,
    }


def apply_gap_policy(verdict, claim_class=None):
    """Применяет gap-политику к вердикту (для пост-процессора).

    - если claim_class == gap: UNSUPPORTED (низкая уверенность) → GAP-UNVERIFIED,
      не problematic; UNSUPPORTED с high-conf → cap (unsupported_conf_contradiction).
    - если claim_class != gap: применяется только cap-правило.
    Возвращает (обновлённый_verdict, changes: list[str]).
    """
    changes = []
    if not isinstance(verdict, dict):
        return verdict, changes
    if claim_class != "gap":
        _, capped = cap_unsupported_high_conf(verdict)
        if capped:
            changes.append("confidence capped (unsupported_conf_contradiction)")
        return verdict, changes

    current = str(verdict.get("verdict", "")).upper()
    # gap-claim: снимаем автомат problematic за UNSUPPORTED
    if current == "UNSUPPORTED":
        verdict.pop("problematic", None)
        verdict.pop("_problematic_reason", None)
        changes.append("gap-claim: verdict_unsupported→problematic не применяется")

    # UNSUPPORTED + high conf → cap
    _, capped = cap_unsupported_high_conf(verdict)
    if capped:
        changes.append("UNSUPPORTED + conf>0.6 → cap 0.5 (unsupported_conf_contradiction)")

    # низкая уверенность → GAP-UNVERIFIED (не «опровергнуто»)
    if current == "UNSUPPORTED":
        try:
            conf = float(verdict.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf < 0.6:
            verdict["_original_verdict"] = verdict.get("verdict")
            verdict["verdict"] = "GAP-UNVERIFIED"
            verdict["_verdict_changed_by"] = "gap_rule_gap_unverified"
            verdict["_gap_claim"] = True
            changes.append("UNSUPPORTED → GAP-UNVERIFIED (gap-claim, отсутствие данных ≠ опровержение)")

    if current == "SUPPORTED":
        verdict["_gap_claim"] = True
        verdict["gap_supported"] = True
        changes.append("gap-claim: SUPPORTED(gap)")

    return verdict, changes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--claim-class", default="framing",
                    choices=["gap", "attribute", "numeric", "framing"])
    ap.add_argument("--verdict", default="UNSUPPORTED")
    ap.add_argument("--confidence", type=float, default=0.3)
    ap.add_argument("--external-sources", default=0, type=int,
                    help="число принятых внешних источников")
    ap.add_argument("--gap-support", default=0, type=int)
    ap.add_argument("--gap-contradictions", default=0, type=int)
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args()

    verdict = {
        "claim_id": 0,
        "claim_text": "",
        "verdict": args.verdict,
        "confidence": args.confidence,
        "sources": [],
    }
    if args.claim_class == "gap":
        res = decide_gap_verdict(
            [{}] * args.external_sources,
            gap_support_hits=args.gap_support,
            gap_contradictions=args.gap_contradictions,
        )
        verdict["verdict"] = res["verdict"]
        verdict["confidence"] = res["confidence"]
        verdict["reason"] = res["reason"]
    verdict, changes = apply_gap_policy(verdict, args.claim_class)
    if args.as_json:
        print(json.dumps({"verdict": verdict, "changes": changes},
                         ensure_ascii=False, indent=2))
    else:
        print(f"claim_class: {args.claim_class}")
        print(f"verdict: {verdict.get('verdict')} (conf={verdict.get('confidence')})")
        print(f"changes: {changes}")


if __name__ == "__main__":
    main()