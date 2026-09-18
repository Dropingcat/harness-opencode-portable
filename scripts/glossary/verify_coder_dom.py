#!/usr/bin/env python3
"""Verify-gate for coder_dom.yaml (schema drift / staleness detection).

Re-generates coder_dom.yaml from current code and exits non-zero if the file on
disk differs (i.e. code changed but the DOM was not updated). Intended as a
pre-commit / CI hook. Universal: only stdlib + the glossary modules.

Usage:
    python scripts/glossary/verify_coder_dom.py --root <root> [--fix]
    --fix: write the regenerated file (used by the generator itself); without
           --fix it only compares and returns 1 on mismatch.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import coder_dom_build as cdb


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify coder_dom.yaml is in sync with code.")
    ap.add_argument("--root", default=r"E:\Documents\Документы\doc_Opencode_agern-new")
    ap.add_argument("--out", default=None, help="path to coder_dom.yaml (default <root>/docs/glossary/coder_dom.yaml)")
    ap.add_argument("--fix", action="store_true", help="write the regenerated file (generator mode)")
    args = ap.parse_args(argv)

    root = Path(args.root)
    out = Path(args.out) if args.out else root / "docs/glossary/coder_dom.yaml"

    data = cdb.build_coder_dom(root)
    try:
        import yaml
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=True)
    except ImportError:
        text = cdb._fallback_yaml(data)

    if args.fix:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}: fingerprint={data['fingerprint'][:24]}")
        return 0

    if not out.is_file():
        print(f"MISSING {out} — run: python scripts/glossary/coder_dom_build.py --root {root}", file=sys.stderr)
        return 1

    current = out.read_text(encoding="utf-8")
    if current == text:
        print(f"OK {out}: in sync (fingerprint={data['fingerprint'][:24]})")
        return 0

    print(
        f"STALE {out}: code changed but coder_dom.yaml not regenerated.\n"
        f"  run: python scripts/glossary/coder_dom_build.py --root {root}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())