"""Bundled guard adapters. P0-only reports never certify combined protection."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

_HARNESS_ROOT = Path(__file__).resolve().parents[3]
_BUNDLED_GUARD_SRC = _HARNESS_ROOT / "guard" / "src"


def _bundled(name):
    # Resolve exact bundled files, not CWD, PYTHONPATH, or sys.modules aliases.
    spec = importlib.util.spec_from_file_location("_research_guard_" + name, _BUNDLED_GUARD_SRC / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    _p0 = _bundled("session_guard")
    _STRONG_EN, _WEAK_RU = _p0.STRONG_EN, _p0.WEAK_RU
    _doc_normalize, _doc_suspicion = _p0._normalize, _p0._suspicion
    _doc_classify, _doc_analyze = _p0._classify, _p0.analyze
    _HAS_DOC_GUARD = True
except Exception:
    _HAS_DOC_GUARD = False

try:
    _p2 = _bundled("semantic_layer")
    _p2_load_config, _P2Chain = _p2.load_config, _p2.ClassifierChain
    _HAS_P2 = True
except Exception:
    _HAS_P2 = False
    _p2_load_config = _P2Chain = None


@dataclass(frozen=True, slots=True)
class GuardFinding:
    field: str
    provenance: str
    tool: str
    signature: str
    suspicion: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class GuardReport:
    verdict: str
    high_count: int
    low_count: int
    findings: tuple[GuardFinding, ...]
    scanned_fields: int
    stage: str = "P0"
    coverage_complete: bool = False


def _error(stage="P0"):
    # Neither exception text nor untrusted provider output belongs in errors.
    return GuardReport("ERROR", 0, 0, (), 0, stage, False)


def scan_text(text: str, field: str = "text", provenance: str = "untrusted", tool: str = "webfetch") -> GuardReport:
    """Deterministic P0 only; unavailable P0 is an error, not a fallback PASS."""
    if not _HAS_DOC_GUARD or not isinstance(text, str):
        return _error()
    try:
        norm_text = _doc_normalize(text)
        for sig in _STRONG_EN + _WEAK_RU:
            normalized = _doc_normalize(sig)
            suspicion = _doc_suspicion(text, provenance, tool, normalized)
            if suspicion not in ("high", "low"):
                return _error()
            if normalized in norm_text and suspicion == "high":
                # Findings identify policy matches, not raw potentially secret text.
                finding = GuardFinding(field, provenance, tool, sig, "high", "signature detected")
                return GuardReport("FAIL", 1, 0, (finding,), 1, "P0", True)
        return GuardReport("PASS", 0, 0, (), int(bool(text)), "P0", True)
    except Exception:
        return _error()


def scan_state(state: Mapping[str, Any], provenance: str = "untrusted", tool: str = "webfetch") -> GuardReport:
    """Recursively scan dictionaries and arbitrarily nested lists, or block."""
    findings = []
    scanned = 0
    seen = set()

    def visit(value, field):
        nonlocal scanned
        if isinstance(value, str):
            report = scan_text(value, field, provenance, tool)
            if report.verdict not in ("PASS", "FAIL"):
                raise ValueError("scan unavailable")
            scanned += report.scanned_fields
            findings.extend(report.findings)
        elif isinstance(value, (dict, list)):
            if id(value) in seen:
                raise ValueError("cyclic state")
            seen.add(id(value))
            for key, item in (value.items() if isinstance(value, dict) else enumerate(value)):
                visit(item, f"{field}.{key}")
            seen.remove(id(value))

    if not _HAS_DOC_GUARD or not isinstance(state, (dict, list)):
        return _error()
    try:
        visit(state, "state")
        high = len(findings)
        return GuardReport("FAIL" if high else "PASS", high, 0, tuple(findings), scanned, "P0", True)
    except Exception:
        return _error()


def _db_report(result, stage):
    if not isinstance(result, dict) or result.get("verdict") not in ("PASS", "FAIL"):
        return _error(stage)
    if stage == "P0+P2":
        c = result.get("coverage")
        if not (isinstance(c, dict) and c.get("complete") is True
                and all(type(c.get(k)) is int and c[k] >= 0 for k in
                        ("total_parts", "covered_parts", "required_parts", "classified_parts"))
                and c["total_parts"] > 0 and c["total_parts"] == c["covered_parts"]
                and c["required_parts"] == c["classified_parts"]
                and c["required_parts"] <= c["total_parts"]):
            return _error(stage)
    stats = result.get("stats", {})
    high = int(stats.get("high_suspicion", 0)) if stage == "P0" else int(stats.get("p0_high", 0)) + int(stats.get("p2_yes", 0))
    verdict = "FAIL" if high or result["verdict"] == "FAIL" else "PASS"
    return GuardReport(verdict, high, 0, (), int(result.get("total_parts_scanned", 0)), stage, True)


def scan_opencode_db(db_path: str | Path, session_id: str | None = None) -> GuardReport:
    if not _HAS_DOC_GUARD:
        return _error()
    try:
        return _db_report(_doc_analyze(str(db_path), session_id), "P0")
    except Exception:
        return _error()


def is_safe_text(text: str, provenance: str = "untrusted") -> bool:
    return scan_text(text, provenance=provenance).verdict == "PASS"


def scan_text_with_p2(text: str, field: str = "text", provenance: str = "untrusted",
                      tool: str = "webfetch", use_p2: bool = False,
                      config_path: str | Path | None = None,
                      budget_rub: float | None = None) -> GuardReport:
    p0 = scan_text(text, field, provenance, tool)
    if p0.verdict != "PASS" or not use_p2:
        return p0
    if not _HAS_P2 or _p2_load_config is None or _P2Chain is None:
        return _error("P0+P2")
    try:
        # An explicit P2 request always classifies the entire bounded text.
        if not text or len(text) > _p2.P2_MAX_TEXT:
            return _error("P0+P2")
        path = config_path or _BUNDLED_GUARD_SRC.parent / "configs" / "guard_config.json"
        cfg = _p2_load_config(str(path))
        bc = cfg.get("budget", {})
        budget = _p2.Budget(float(budget_rub if budget_rub is not None else bc.get("max_cost_rub", 5.0)))
        result = _P2Chain(cfg, budget).run(text)
        if not isinstance(result, dict) or result.get("verdict") not in ("YES", "NO"):
            return _error("P0+P2")
        high = int(result["verdict"] == "YES")
        return GuardReport("FAIL" if high else "PASS", high, 0, (), 1, "P0+P2", True)
    except Exception:
        return _error("P0+P2")


def scan_opencode_db_with_p2(db_path: str | Path, session_id: str | None = None,
                            use_p2: bool = False, config_path: str | Path | None = None) -> GuardReport:
    p0 = scan_opencode_db(db_path, session_id)
    if p0.verdict != "PASS" or not use_p2:
        return p0
    if not _HAS_P2:
        return _error("P0+P2")
    try:
        path = config_path or _BUNDLED_GUARD_SRC.parent / "configs" / "guard_config.json"
        cfg = _p2_load_config(str(path))
        return _db_report(_p2.analyze(str(db_path), session_id, config=cfg), "P0+P2")
    except Exception:
        return _error("P0+P2")
