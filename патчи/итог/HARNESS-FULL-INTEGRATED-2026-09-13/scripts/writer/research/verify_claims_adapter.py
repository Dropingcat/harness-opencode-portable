# -*- coding: utf-8 -*-
"""Read-only adapter over scripts/researcher/verify_claims.py.

The Writer may consume Researcher verdicts but may not mutate Researcher
state or silently upgrade verdicts. The adapter therefore executes the
canonical researcher entrypoint *without* --apply, verifies the DOM hash did
not change, validates the controlled verdict vocabulary, and emits a bounded
Writer-facing envelope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RESEARCHER_ENTRYPOINT = ROOT / "scripts" / "researcher" / "verify_claims.py"
ALLOWED_VERDICTS = frozenset({"SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "AMBIGUOUS", "OPEN"})


class VerificationAdapterError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_json(stdout: str) -> dict[str, Any]:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise VerificationAdapterError(f"researcher returned non-JSON output: {exc}") from exc
    if not isinstance(data, dict):
        raise VerificationAdapterError("researcher output must be an object")
    return data


def adapt_verification(dom: str | Path, timeout_seconds: float = 60.0) -> dict[str, Any]:
    dom_path = Path(dom).resolve()
    if not dom_path.is_file():
        raise VerificationAdapterError(f"DOM missing: {dom_path}")
    if not RESEARCHER_ENTRYPOINT.is_file():
        raise VerificationAdapterError(f"researcher authority missing: {RESEARCHER_ENTRYPOINT}")

    before = _sha256(dom_path)
    try:
        cp = subprocess.run(
            [sys.executable, str(RESEARCHER_ENTRYPOINT), "--dom", str(dom_path), "--json"],
            cwd=str(ROOT), text=True, capture_output=True, timeout=timeout_seconds, check=False,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationAdapterError(f"researcher invocation failed: {type(exc).__name__}: {exc}") from exc
    after = _sha256(dom_path)
    if before != after:
        raise VerificationAdapterError("researcher read-only adapter detected DOM mutation")
    if cp.returncode != 0:
        raise VerificationAdapterError(
            f"researcher verification failed rc={cp.returncode}: {(cp.stderr or cp.stdout).strip()[:1000]}"
        )

    payload = _parse_json(cp.stdout)
    if payload.get("ok") is not True or payload.get("applied") not in (False, None):
        raise VerificationAdapterError("researcher output violates read-only verification contract")
    results = payload.get("results")
    if not isinstance(results, list):
        raise VerificationAdapterError("researcher results must be a list")

    normalized: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            raise VerificationAdapterError("researcher result item must be an object")
        verdict = str(item.get("verdict") or "OPEN").upper()
        if verdict not in ALLOWED_VERDICTS:
            raise VerificationAdapterError(f"unknown researcher verdict: {verdict}")
        normalized.append({
            "claim_id": item.get("claim_id"),
            "verdict": verdict,
            "evidence_verdict": str(item.get("evidence_verdict") or verdict).upper(),
            "verification_state": item.get("verification_state") or ("UNCHECKED" if verdict == "OPEN" else "VERIFIED"),
            "epistemic_state": item.get("epistemic_state") or ("UNKNOWN" if verdict == "OPEN" else None),
            "confidence": item.get("confidence"),
            "numeric_comparison": item.get("numeric_comparison"),
            "guard": item.get("guard"),
            "formula": item.get("formula"),
            "raw": item,
        })

    return {
        "schema": "writer.research_verification/1.0",
        "authority": "scripts/researcher/verify_claims.py",
        "dom": str(dom_path),
        "dom_sha256": before,
        "read_only": True,
        "claims_verified": len(normalized),
        "results": normalized,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="writer-research-adapter")
    ap.add_argument("--dom", required=True)
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args(argv)
    try:
        result = adapt_verification(args.dom, timeout_seconds=args.timeout)
    except VerificationAdapterError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "fail_closed": True}, ensure_ascii=False))
        return 2
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
