#!/usr/bin/env python3
"""verify_claims.py — детерминированная верификация writer DOM-claims через researcher_core.

Мост «писатель ↔ ресерчер»: берёт DOM YAML писателя (claims с text + evidence),
прогоняет каждый claim через детерминированное ядро researcher_core:
  - numeric:     если в claim/source есть числа → compare_numeric (с единицами/неопределённостью);
  - formula:     detect_formula + check_constant (Scherrer и др.);
  - guard:       scan_text (P0 инъекции) на тексте claim и source span;
  - qualifier:   extract_qualifier (уточняющие слова: примерно/не менее…).

Выход: JSON с per-claim verifier summary (verdict, confidence, numeric_comparison,
formula, guard), совместимый с полем DOM claims[].verification.

Режим --apply: пишет verification обратно в DOM YAML (append-only: не трогает
не-verification поля). По умолчанию — read-only (только отчёт).

Append-only правила для verification (курация защищена):
  1. verdict не даунгрейдится: если у claim уже есть verdict, отличный от OPEN
     (SUPPORTED/AMBIGUOUS/CONTRADICTED/UNSUPPORTED) — вычисленный НЕ пишется наверх;
     вердикт пересчитывается только если его нет или он OPEN.
     Вместе с вердиктом сохраняется и его confidence (не рассогласовывать пару).
  2. numeric_comparison не стирается: при уже существующем поле оно сохраняется
     как есть; заполняется только если поля нет.
  3. guard/formula/qualifier обновляются всегда (дешёвые, не конфликтуют с
     курацией), если вычислены.
Fail-closed: битый DOM/claim → JSON {"ok": false, "error": ...}, exit 2;
исключения наружу не пробрасываются.

Примеры:
  python verify_claims.py --dom <slug>-dom.yaml
  python verify_claims.py --dom <slug>-dom.yaml --apply
  python verify_claims.py --dom <slug>-dom.yaml --json
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# researcher_core
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from researcher_core.guard import scan_text
    from researcher_core.numeric import NumericComparisonStatus, NumericValue, compare_numeric
    from researcher_core.formulas import check_constant, detect_formula
    from researcher_core.qualifier import extract_qualifier
    RESEARCHER_OK = True
except Exception as exc:  # pragma: no cover
    RESEARCHER_OK = False
    _IMPORT_ERR = str(exc)


def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML required (pip install PyYAML)")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"DOM {path} top-level must be mapping")
    return data


def _extract_numbers(text: str) -> list[dict]:
    """Детерминированный мини-парсер чисел (value + unit) из текста claim/source."""
    import re
    out = []
    # диапазон "70-80 HV" / "0.5–0.7"
    m = re.search(r"(\d+[.,]?\d*)\s*[–—-]\s*(\d+[.,]?\d*)\s*([А-Яа-яёЁA-Za-z%°/µ²]+)", text)
    if m:
        try:
            lo = Decimal(m.group(1).replace(",", "."))
            hi = Decimal(m.group(2).replace(",", "."))
            out.append({"value": (lo + hi) / 2, "lower": lo, "upper": hi, "unit": m.group(3), "raw": m.group(0)})
            return out
        except InvalidOperation:
            pass
    # одиночное число + единица
    m = re.search(r"(\d+[.,]?\d*)\s*([А-Яа-яёЁA-Za-z%°µ²]+)", text)
    if m:
        try:
            out.append({"value": Decimal(m.group(1).replace(",", ".")), "unit": m.group(2), "raw": m.group(0)})
        except InvalidOperation:
            pass
    return out


def _normalize_unit(u: str | None) -> str | None:
    if not u:
        return None
    u = u.strip()
    # кириллические единицы → латиница (researcher_core.numeric реестр)
    if u in ("мг/м2ч", "мг/м²ч"):
        return "mg/m2h"
    if u in ("°С", "°C", "оС", "°с"):
        return "celsius"
    if u in ("МПа", "мпа", "МПа"):
        return "mpa"
    if u in ("ГПа", "гпа"):
        return "gpa"
    if u in ("МДж/м2", "МДж/м²"):
        return "MJ/m2"
    if u in ("мкм", "µm", "μm"):
        return "um"
    if u in ("мм",):
        return "mm"
    if u in ("см",):
        return "cm"
    if u in ("кг/га",):
        return "kg/ha"
    if u in ("г/м2", "г/м²"):
        return "g/m2"
    if u == "HV":
        return "hv"
    return u


def _verdict_label(status: str) -> str:
    m = {
        "MATCH": "SUPPORTED",
        "PARTIAL_MATCH": "SUPPORTED",
        "MISMATCH": "CONTRADICTED",
        "NOT_COMPARABLE": "AMBIGUOUS",
        "NO_DATA": "AMBIGUOUS",
        "FORMULA_CONFLICT": "CONTRADICTED",
    }
    return m.get(status, "AMBIGUOUS")


def _merge_verification(existing: dict | None, computed: dict) -> dict:
    """Append-only merge свежевычисленной verification с уже существующей.

    Курация защищена от перезаписи:
      1. verdict: вычисленный пишется ТОЛЬКО если текущего нет или он 'OPEN'.
         Пара (verdict, confidence) обновляется/сохраняется целиком, чтобы не
         рассогласовывать вердикт с его уверенностью.
      2. numeric_comparison: заполняется ТОЛЬКО если поля нет (не стирается).
      3. guard/formula/qualifier: обновляются всегда, если вычислены (не None).

    Прочие ключи existing (error, note, method, …) сохраняются как есть.
    """
    existing = existing if isinstance(existing, dict) else {}
    out = dict(existing)

    cur_verdict = existing.get("verdict")
    if cur_verdict is None or cur_verdict == "OPEN":
        out["verdict"] = computed.get("verdict")
        out["confidence"] = computed.get("confidence")

    if existing.get("numeric_comparison") is None:
        out["numeric_comparison"] = computed.get("numeric_comparison")

    for key in ("guard", "formula", "qualifier"):
        val = computed.get(key)
        if val is not None:
            out[key] = val

    return out


def verify_claim(claim: dict, source_text: str | None, policy: dict | None = None) -> dict:
    """Детерминированная верификация одного claim. Возвращает dict для DOM verification."""
    # CD-003: fail-closed guard на не-dict claim (None/str/int/list/...) — вернуть
    # вердикт-схему, не бросать AttributeError на claim.get('text').
    if not isinstance(claim, dict):
        return {"verdict": "OPEN", "confidence": 0.0, "numeric_comparison": None,
                "formula": None, "guard": None, "qualifier": None,
                "error": "claim must be a dict"}

    if not RESEARCHER_OK:
        return {"verdict": "AMBIGUOUS", "confidence": 0.0,
                "error": f"researcher_core import failed: {_IMPORT_ERR}"}

    text = claim.get("text", "")
    result: dict = {
        "verdict": "OPEN",
        "confidence": 0.0,
        "numeric_comparison": None,
        "formula": None,
        "guard": None,
        "qualifier": None,
    }

    # 1. Guard (инъекции)
    try:
        guard = scan_text(text, field="claim.text", provenance="internal", tool="read")
        result["guard"] = guard.verdict if hasattr(guard, "verdict") else None
        if result["guard"] == "FAIL":
            result["verdict"] = "AMBIGUOUS"
            result["confidence"] = 0.1
            return result
    except Exception:
        result["guard"] = "ERROR"

    # 2. Qualifier (примерно/не менее → снижает confidence)
    try:
        q = extract_qualifier(text)
        result["qualifier"] = q
    except Exception:
        pass

    # 3. Formula
    try:
        formula_name = detect_formula(text)
        if formula_name:
            constant = check_constant(formula_name, text)
            result["formula"] = {"name": formula_name, "constant_check": constant}
            if constant == "formula_conflict":
                result["verdict"] = "CONTRADICTED"
                result["confidence"] = 0.3
                return result
    except Exception:
        result["formula"] = "ERROR"

    # 4. Numeric: если есть число в claim и source
    claim_nums = _extract_numbers(text)
    source_nums = _extract_numbers(source_text or "") if source_text else []
    if claim_nums and source_nums:
        cn = claim_nums[0]
        sn = source_nums[0]
        try:
            def _make(nums):
                if nums.get("lower") is not None and nums.get("upper") is not None:
                    return NumericValue(unit=_normalize_unit(nums.get("unit")),
                                        lower=nums["lower"], upper=nums["upper"])
                return NumericValue(value=nums.get("value"), unit=_normalize_unit(nums.get("unit")))
            cv = _make(cn)
            sv = _make(sn)
            comp = compare_numeric(cv, sv)
            label = _verdict_label(comp.status.name if hasattr(comp.status, "name") else str(comp.status))
            result["verdict"] = label
            result["numeric_comparison"] = {
                "status": comp.status.name if hasattr(comp.status, "name") else str(comp.status),
                "claim": cn.get("raw"), "source": sn.get("raw"),
                "unit": _normalize_unit(cn.get("unit")),
            }
            result["confidence"] = 0.8 if label == "SUPPORTED" else 0.4
            return result
        except Exception as exc:
            result["numeric_comparison"] = {"error": str(exc)}

    # 5. Нет чисел → если есть evidence с source, ставим OPEN (фактический check — в r3/citation)
    if source_text:
        result["verdict"] = "OPEN" if not result.get("verdict") or result["verdict"] == "OPEN" else result["verdict"]
        result["confidence"] = max(result.get("confidence", 0.0), 0.3)

    return result


def main() -> int:
    ap = argparse.ArgumentParser(prog="verify_claims", description="Верификация writer DOM-claims через researcher_core")
    ap.add_argument("--dom", required=True, help="путь к DOM YAML писателя")
    ap.add_argument("--apply", action="store_true", help="записать verification обратно в DOM (append-only)")
    ap.add_argument("--json", action="store_true", help="вывод JSON")
    args = ap.parse_args()

    if not RESEARCHER_OK:
        print(json.dumps({"ok": False, "error": f"researcher_core import failed: {_IMPORT_ERR}"}, ensure_ascii=False))
        return 2

    try:
        dom = _load_yaml(Path(args.dom))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2

    try:
        sources = {str(s.get("id")): s for s in dom.get("sources", []) if isinstance(s, dict)}
        claims = dom.get("claims", [])
        if not isinstance(claims, list):
            raise ValueError(f"DOM {args.dom}: claims must be list")
        results = []
        for c in claims:
            if not isinstance(c, dict):
                raise ValueError(f"DOM {args.dom}: claim must be mapping, got {type(c).__name__}")
            cid = c.get("id")
            # source text: из первого evidence
            source_text = None
            ev = c.get("evidence") or []
            if isinstance(ev, list) and ev:
                sid = ev[0].get("source_id")
                src = sources.get(str(sid)) if sid else None
                if src:
                    source_text = src.get("text") or src.get("ref")
            v = verify_claim(c, source_text)
            results.append({"claim_id": cid, **v})
            if args.apply:
                # append-only: не даунгрейдить курированный verdict, не стирать
                # numeric_comparison (см. _merge_verification)
                c["verification"] = _merge_verification(c.get("verification"), v)

        if args.apply:
            with open(args.dom, "w", encoding="utf-8") as f:
                yaml.safe_dump(dom, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    out = {
        "ok": True,
        "dom": args.dom,
        "claims_verified": len(results),
        "results": results,
        "applied": args.apply,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())