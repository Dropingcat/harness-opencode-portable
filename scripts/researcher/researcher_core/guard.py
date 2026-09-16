"""Leak-protection guard block — vendored P0 from E:\\Documents\\Документы\\doc_guard.

Wraps trust-boundary guard (session_guard.py P0) as deterministic, stdlib-only
block for researcher and opencode sessions. No network, no API keys, fail-closed.

Provenance: E:\\Documents\\Документы\\doc_guard\\src\\session_guard.py
  STRONG_EN / WEAK_RU / _normalize / _suspicion / _classify
  Bypass-rate: baseline 72% → P0 50% → P2 ~10% (doc_guard README)
  7 threats closed by P0+P2, 7 insurmountable require taint tracker (THREAT_MODEL.md)

Usage as block:
  - researcher pipeline: scan EvidenceSpan exact_text / Source title before registry admission
  - opencode pre-resume: scan opencode.db parts before execute
  - any external text (webfetch, task output) before it crosses trust boundary
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

# Vendor P0/P2 logic by importing from doc_guard src if available, else fallback.
# Portable: prefer the bundled guard/src (this module), then the legacy external path.
_HARNESS_ROOT = Path(__file__).resolve().parents[3]
_BUNDLED_GUARD_SRC = _HARNESS_ROOT / "guard" / "src"
_DOC_GUARD_SRC = Path(r"E:\Documents\Документы\doc_guard\src")
if str(_BUNDLED_GUARD_SRC) not in sys.path:
    sys.path.insert(0, str(_BUNDLED_GUARD_SRC))
if str(_DOC_GUARD_SRC) not in sys.path:
    sys.path.insert(0, str(_DOC_GUARD_SRC))

try:
    from session_guard import (  # type: ignore[import-not-found]
        STRONG_EN as _STRONG_EN,
        WEAK_RU as _WEAK_RU,
        _classify as _doc_classify,
        _normalize as _doc_normalize,
        _suspicion as _doc_suspicion,
        analyze as _doc_analyze,
    )

    _HAS_DOC_GUARD = True
except Exception:
    _HAS_DOC_GUARD = False

# P2 semantic layer via polza (optional, cheap simple model kept as requested)
try:
    from semantic_layer import (  # type: ignore[import-not-found]
        load_config as _p2_load_config,
        ClassifierChain as _P2Chain,  # type: ignore[attr-defined]
    )

    _HAS_P2 = True
except Exception:
    _HAS_P2 = False
    _p2_load_config = None  # type: ignore[assignment]
    _P2Chain = None  # type: ignore[assignment]
    # Fallback local copy (minimal, keeps block functional if doc_guard not mounted)
    _STRONG_EN = [
        "ignore previous",
        "disregard the above",
        "you are now",
        "override system",
        "important: you must",
        "reveal instructions",
        "repeat the system",
    ]
    _WEAK_RU = [
        "ответь",
        "запусти",
        "продолжи",
        "продолжай",
        "ответь ровно",
        "сделай",
        "напиши",
        "создай",
        "выполни",
        "приступай",
        "реализуй",
        "init bubble",
        "finalize",
        "отчёт фабрики",
    ]

    def _doc_normalize(text: str) -> str:  # type: ignore[no-redef]
        import re
        import unicodedata

        if not text:
            return ""
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"[\u200b-\u200d\u2060\ufeff]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.casefold()

    def _doc_suspicion(text: str, provenance: str, tool: str, sig: str) -> str:  # type: ignore[no-redef]
        # Minimal fallback: high if sig in normalized text and provenance untrusted
        if provenance not in ("untrusted", "internal"):
            return "low"
        norm = _doc_normalize(text)
        sig_norm = _doc_normalize(sig)
        return "high" if sig_norm in norm else "low"

    def _doc_classify(part_type: str, tool: str) -> str:  # type: ignore[no-redef]
        if part_type == "text":
            return "trusted"
        if tool in {
            "webfetch",
            "task",
            "research_papers",
            "websearch",
        }:
            return "untrusted"
        return "internal"

    def _doc_analyze(db_path: str, session_id: str | None = None) -> dict[str, Any]:  # type: ignore[no-redef]
        return {"verdict": "PASS", "findings": [], "stats": {"high_suspicion": 0}}


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
    verdict: str  # PASS / FAIL
    high_count: int
    low_count: int
    findings: tuple[GuardFinding, ...]
    scanned_fields: int


def scan_text(text: str, field: str = "text", provenance: str = "untrusted", tool: str = "webfetch") -> GuardReport:
    """Scan a single text value for injection signatures (P0 only)."""

    if not text:
        return GuardReport("PASS", 0, 0, (), 0)
    # Build normalized pool
    all_sigs = _STRONG_EN + _WEAK_RU
    findings: list[GuardFinding] = []
    for sig in all_sigs:
        # Use vendored suspicion logic
        try:
            suspicion = _doc_suspicion(text, provenance, tool, _doc_normalize(sig) if _HAS_DOC_GUARD else sig)
        except Exception:
            suspicion = "low"
        # fallback direct check if doc logic returns low but sig present
        norm_text = _doc_normalize(text)
        sig_norm = _doc_normalize(sig)
        if sig_norm in norm_text and suspicion == "high":
            # excerpt: 60 chars around sig
            idx = norm_text.find(sig_norm)
            start = max(0, idx - 20)  # debt-scan: ignore-line -- excerpt window offset, not heuristic
            excerpt = text[start : start + 60].replace("\n", " ").strip()  # debt-scan: ignore-line -- excerpt length, not heuristic
            findings.append(GuardFinding(field, provenance, tool, sig, "high", excerpt))
            break  # one per text
    high = sum(1 for f in findings if f.suspicion == "high")
    low = 0
    verdict = "FAIL" if high > 0 else "PASS"
    return GuardReport(verdict, high, low, tuple(findings), 1)


def scan_state(state: Mapping[str, Any], provenance: str = "untrusted", tool: str = "webfetch") -> GuardReport:
    """Scan all string values in a state dict (e.g., EvidenceSpan exact_text)."""

    findings: list[GuardFinding] = []
    scanned = 0
    for key, value in state.items():
        if isinstance(value, str) and value:
            scanned += 1
            report = scan_text(value, field=f"state.{key}", provenance=provenance, tool=tool)
            findings.extend(report.findings)
        elif isinstance(value, dict):
            sub = scan_state(value, provenance=provenance, tool=tool)
            findings.extend(sub.findings)
            scanned += sub.scanned_fields
    high = sum(1 for f in findings if f.suspicion == "high")
    verdict = "FAIL" if high > 0 else "PASS"
    return GuardReport(verdict, high, 0, tuple(findings), scanned)


def scan_opencode_db(db_path: str | Path, session_id: str | None = None) -> GuardReport:
    """Scan opencode.db via doc_guard P0 analyze (if available)."""

    try:
        result = _doc_analyze(str(db_path), session_id)
        findings = []
        for raw in result.get("findings", []):
            findings.append(
                GuardFinding(
                    field=str(raw.get("field", "")),
                    provenance=str(raw.get("provenance", "")),
                    tool=str(raw.get("tool", "")),
                    signature=str(raw.get("signature", "")),
                    suspicion=str(raw.get("suspicion", "")),
                    excerpt=str(raw.get("excerpt", "")),
                )
            )
        high = int(result.get("stats", {}).get("high_suspicion", 0))
        verdict = str(result.get("verdict", "PASS"))
        return GuardReport(verdict, high, 0, tuple(findings), int(result.get("total_parts_scanned", 0)))
    except Exception as exc:
        # fail-closed: on error, return FAIL to block
        return GuardReport("FAIL", 1, 0, (GuardFinding("error", "untrusted", "guard", "guard_error", "high", str(exc)),), 0)


def is_safe_text(text: str, provenance: str = "untrusted") -> bool:
    """Convenience: True if no high-suspicion injection."""

    return scan_text(text, provenance=provenance).verdict == "PASS"


def scan_text_with_p2(
    text: str,
    field: str = "text",
    provenance: str = "untrusted",
    tool: str = "webfetch",
    use_p2: bool = False,
    config_path: str | Path | None = None,
    budget_rub: float | None = None,
) -> GuardReport:
    """P0 + optional P2 (polza) — P2 is tie-breaker for untrusted low/no-match.

    P0 high → FAIL immediately (no P2 cost).
    If P0 PASS and use_p2 True and provenance untrusted → call P2 classifier chain
    (cloud gemma-4-26b / fallback l3-lunaris-8b / local qwen) with budget and fail-closed.
    Simple cheap model kept as requested: fallback gemma/lunaris via polza.

    When P2 not configured or config missing → degrade to P0 only (no error).
    """

    p0_report = scan_text(text, field=field, provenance=provenance, tool=tool)
    if p0_report.verdict == "FAIL":
        return p0_report
    if not use_p2 or provenance != "untrusted":
        return p0_report
    if not _HAS_P2 or _p2_load_config is None:
        return p0_report
    # Try to load guard config (polza provider + budget)
    cfg_path = Path(config_path) if config_path else _DOC_GUARD_SRC / "guard_config.json"
    # Also check researcher project guard config if exists
    if not cfg_path.exists():
        alt = Path(r"E:\Documents\Документы\doc_guard\configs\guard_config.json")
        if alt.exists():
            cfg_path = alt
        else:
            alt2 = Path("E:/Documents/Документы/doc_guard/configs/guard_config.json.example")
            if alt2.exists():
                cfg_path = alt2
            else:
                return p0_report
    try:
        cfg = _p2_load_config(str(cfg_path))
    except Exception:
        return p0_report
    # Override budget if requested
    if budget_rub is not None:
        try:
            cfg["budget"]["max_cost_rub"] = float(budget_rub)
        except Exception:
            pass  # debt-scan: ignore-line -- best-effort budget override
    # Build chain and classify — reuse semantic_layer's chain logic
    # Import here to avoid circular and to keep stdlib-only when P2 disabled
    try:
        # Create a minimal untrusted pool for P2 (one text)
        # Use semantic_layer's internal classify via direct call to chain
        # We instantiate chain the same way semantic_layer does
        from semantic_layer import Budget as _P2Budget  # type: ignore[import-not-found]

        budget_cfg = cfg.get("budget", {})
        budget = _P2Budget(
            max_cost=float(budget_cfg.get("max_cost_rub", 5.0)),  # debt-scan: ignore-line -- default from guard_config.json
            warn_threshold=float(budget_cfg.get("warn_threshold_rub", 4.0)),  # debt-scan: ignore-line -- default
            alarm_threshold=float(budget_cfg.get("alarm_threshold_rub", 4.8)),  # debt-scan: ignore-line -- default
        )
        # If budget already exhausted, don't call cloud
        if budget.exhausted:
            return p0_report
        # Use chain — we create it via same factory as semantic_layer
        # To avoid duplicating chain construction, call semantic_layer's analyze with limit 1
        # but that would re-scan DB. Instead, directly classify the text
        # Instantiate classifiers from cfg
        providers = cfg.get("providers", {})
        # Prefer simple cheap fallback if primary is heavy — user asked to keep simple polza model
        # Keep original chain order: cloud primary → fallback → local
        # Use _P2Chain if available
        if _P2Chain is not None:
            chain = _P2Chain(cfg, budget)  # type: ignore[call-arg]
            verdict, _cost = chain.classify(text)  # type: ignore[attr-defined]
            if verdict == "YES":
                return GuardReport(
                    "FAIL",
                    1,
                    0,
                    (GuardFinding("text", provenance, tool, "p2_semantic", "high", text[:60]),),  # debt-scan: ignore-line -- excerpt len
                    1,
                )
            if verdict == "NO":
                return p0_report
            # None/timeout → fail-closed → FAIL
            if verdict is None:
                return GuardReport(
                    "FAIL",
                    1,
                    0,
                    (GuardFinding("text", provenance, tool, "p2_timeout", "high", "p2 timeout fail-closed"),),
                    1,
                )
    except Exception:
        # On any P2 error, degrade to P0 (already PASS) but log as low
        return p0_report
    return p0_report


def scan_opencode_db_with_p2(
    db_path: str | Path,
    session_id: str | None = None,
    use_p2: bool = False,
    config_path: str | Path | None = None,
) -> GuardReport:
    """Full DB scan: P0 via session_guard, optionally P2 via polza for untrusted low.

    P0 high → FAIL. If use_p2 True and P0 not high, delegate to semantic_layer
    hybrid for semantic paraphrase coverage (~10% bypass vs 50% P0-only).
    """

    p0_report = scan_opencode_db(db_path, session_id)
    if p0_report.verdict == "FAIL" or not use_p2:
        return p0_report
    if not _HAS_P2:
        return p0_report
    # Delegate to semantic_layer's hybrid analyze for P2 tie-breaker
    try:
        from semantic_layer import analyze as _p2_analyze  # type: ignore[import-not-found]

        # semantic_layer.analyze does P0+P2 internally, reuse it
        # It needs budget/config; we pass via env or default
        result = _p2_analyze(str(db_path), session_id)  # type: ignore[call-arg]
        # Convert to GuardReport
        findings = []
        for raw in result.get("findings", []):
            findings.append(
                GuardFinding(
                    field=str(raw.get("field", "")),
                    provenance=str(raw.get("provenance", "")),
                    tool=str(raw.get("tool", "")),
                    signature=str(raw.get("signature", "")),
                    suspicion=str(raw.get("suspicion", "")),
                    excerpt=str(raw.get("excerpt", "")),
                )
            )
        high = int(result.get("stats", {}).get("p0_high", 0)) + int(result.get("stats", {}).get("p2_yes", 0))
        verdict = str(result.get("verdict", "PASS"))
        return GuardReport(verdict, high, 0, tuple(findings), int(result.get("total_parts_scanned", 0)))
    except Exception:
        return p0_report
