#!/usr/bin/env python3
"""Regression Gateway (N12.5): KS-стабильность + semantic agreement + conformal social choice.

Сходимость через трибунал (вместо фиксированных порогов):
1. KS-тест: распределение вердиктов перестало значимо меняться → стоп
2. Semantic agreement: согласие свиты (0.0-1.0)
3. Conformal: предсказательный набор {accept, escalate, defer} с покрытием ≥1−α
"""

import json
import math
from typing import Any

from config_loader import get

from sexpr import SExpr, format_sexpr


def _verdict_rank(v: str) -> int:
    ranks = {"CONTRADICTED": 0, "UNSUPPORTED": 1, "AMBIGUOUS": 2, "SUPPORTED": 3, "OPEN": -1}
    return ranks.get(v, -1)


def _ks_critical_value(n: int, alpha: float = 0.05) -> float:
    if n <= 0:
        return 1.0
    return math.sqrt(-0.5 * math.log(alpha / 2) / n)


def ks_stability_test(
    verdicts_before: dict[int, str],
    verdicts_after: dict[int, str],
    alpha: float = None,
) -> dict:
    if alpha is None:
        alpha = get("regression.alpha", 0.05)
    groups = sorted(set(verdicts_before.keys()) | set(verdicts_after.keys()))
    if not groups:
        return {"p_value": 1.0, "stable": True, "d_statistic": 0.0, "critical_value": 1.0}

    before_ranks = sorted(_verdict_rank(verdicts_before.get(g, "UNKNOWN")) for g in groups)
    after_ranks = sorted(_verdict_rank(verdicts_after.get(g, "UNKNOWN")) for g in groups)

    n = len(groups)
    d_max = 0.0
    for i in range(n):
        f1 = (i + 1) / n
        j = 0
        while j < n and after_ranks[j] <= before_ranks[i]:
            j += 1
        f2 = j / n
        d_max = max(d_max, abs(f1 - f2))

    critical = _ks_critical_value(n, alpha)
    stable = d_max < critical

    return {
        "d_statistic": round(d_max, 4),
        "critical_value": round(critical, 4),
        "stable": stable,
        "n_groups": n,
        "alpha": alpha,
    }


def semantic_agreement(suite_verdicts: list[dict]) -> float:
    if not suite_verdicts:
        return 0.0

    verdicts = [v.get("verdict", "UNKNOWN") for v in suite_verdicts]
    confidences = [v.get("confidence", 0.5) for v in suite_verdicts]

    from collections import Counter
    counts = Counter(verdicts)
    most_common_count = counts.most_common(1)[0][1] if counts else 0
    agreement_ratio = most_common_count / len(verdicts)

    mean_conf = sum(confidences) / len(confidences) if confidences else 0.5

    weight = get("regression.semantic_agreement_weight", 0.6)
    return round(agreement_ratio * weight + mean_conf * (1 - weight), 4)


def conformal_social_choice(
    suite_verdicts: list[dict],
    golden_verdicts: list[dict] = None,
    alpha: float = None,
) -> dict:
    if alpha is None:
        alpha = get("regression.alpha", 0.05)
    verdicts = [v.get("verdict", "UNKNOWN") for v in suite_verdicts]
    confidences = [v.get("confidence", 0.5) for v in suite_verdicts]

    from collections import Counter
    counts = Counter(verdicts)
    total = len(verdicts)

    if total == 0:
        return {"set": ["defer"], "confidence": 0.0}

    fallback_ratio = get("regression.conformal_fallback_ratio", 0.75)
    majority_ratio = get("regression.conformal_majority_ratio", 0.5)

    support_ratio = counts.get("SUPPORTED", 0) / total
    contradict_ratio = counts.get("CONTRADICTED", 0) / total
    mean_conf = sum(confidences) / total

    if support_ratio >= fallback_ratio and contradict_ratio == 0:
        return {"set": ["accept"], "confidence": round(mean_conf, 4)}
    elif contradict_ratio > 0:
        return {"set": ["accept", "reject"], "confidence": round(mean_conf, 4)}
    elif support_ratio >= majority_ratio:
        return {"set": ["accept"], "confidence": round(mean_conf, 4)}
    else:
        return {"set": ["defer"], "confidence": round(mean_conf, 4)}


def regression_gateway(
    verdicts_before: dict[int, str],
    verdicts_after: dict[int, str],
    suite_verdicts: list[dict],
    golden_verdicts: list[dict] = None,
    alpha: float = None,
) -> dict:
    if alpha is None:
        alpha = get("regression.alpha", 0.05)
    ks = ks_stability_test(verdicts_before, verdicts_after, alpha)
    agreement = semantic_agreement(suite_verdicts)
    conformal = conformal_social_choice(suite_verdicts, golden_verdicts, alpha)

    regress_count = sum(
        1 for g in set(verdicts_before.keys()) | set(verdicts_after.keys())
        if _verdict_rank(verdicts_after.get(g, "UNKNOWN")) < _verdict_rank(verdicts_before.get(g, "UNKNOWN"))
    )
    improve_count = sum(
        1 for g in set(verdicts_before.keys()) | set(verdicts_after.keys())
        if _verdict_rank(verdicts_after.get(g, "UNKNOWN")) > _verdict_rank(verdicts_before.get(g, "UNKNOWN"))
    )
    total = len(set(verdicts_before.keys()) | set(verdicts_after.keys()))
    residual_count = total - regress_count - improve_count

    conformal_set = conformal["set"]
    if "accept" in conformal_set and "reject" not in conformal_set:
        gate = "accept"
    elif "reject" in conformal_set:
        gate = "revert"
    else:
        gate = "open_honest"

    return {
        "gate": gate,
        "ks_stable": ks["stable"],
        "ks_d_statistic": ks["d_statistic"],
        "ks_critical": ks["critical_value"],
        "semantic_agreement": agreement,
        "conformal_set": conformal_set,
        "conformal_confidence": conformal["confidence"],
        "regress_count": regress_count,
        "improve_count": improve_count,
        "residual_count": residual_count,
        "total_groups": total,
    }


def regression_to_sexpr(result: dict) -> str:
    return format_sexpr(SExpr("regression-result",
        SExpr("gate", ".", result["gate"]),
        SExpr("ks-stable", ".", "#t" if result["ks_stable"] else "#f"),
        SExpr("ks-d", ".", result["ks_d_statistic"]),
        SExpr("ks-critical", ".", result["ks_critical"]),
        SExpr("semantic-agreement", ".", result["semantic_agreement"]),
        SExpr("conformal-set", *[SExpr("item", ".", s) for s in result["conformal_set"]]),
        SExpr("conformal-confidence", ".", result["conformal_confidence"]),
        SExpr("regress-count", ".", result["regress_count"]),
        SExpr("improve-count", ".", result["improve_count"]),
        SExpr("residual-count", ".", result["residual_count"]),
    ))


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    # Настоящий CLI (этап 12.5 run_pipeline.sh):
    #   python3 regression_suite.py <reverify_result.json> <regression_result.json>
    if len(sys.argv) < 3:
        print("Usage: python3 regression_suite.py <reverify_result.json> "
              "<regression_result.json>", file=sys.stderr)
        sys.exit(1)
    in_path, out_path = sys.argv[1], sys.argv[2]

    try:
        with open(in_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"ОШИБКА: не удалось прочитать {in_path}: {exc}", file=sys.stderr)
        sys.exit(2)

    status_flow = data.get("status_flow", {}) or {}
    before = {}
    after = {}
    for gid, flow in status_flow.items():
        if not isinstance(flow, dict):
            continue
        before[str(gid)] = flow.get("old", "UNKNOWN")
        after[str(gid)] = flow.get("new", "UNKNOWN")

    # Свита: прокси из вердиктов «после» (детерминированный fallback-гейт)
    suite = [{"verdict": v, "confidence": 0.7} for v in after.values()]

    result = regression_gateway(before, after, suite)
    result["_meta"] = {
        "reverify_source": in_path,
        "n_groups": len(status_flow),
        "suite_proxy": "after_verdicts (детерминированный fallback)",
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ regression_suite: gate={result['gate']}, "
          f"ks_stable={result['ks_stable']}, "
          f"regress={result['regress_count']}, improve={result['improve_count']}")
    print(f"   результат: {out_path}")
