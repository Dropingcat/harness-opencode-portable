# -*- coding: utf-8 -*-
"""Canonical public Writer CLI compatibility facade (WRITER-UNIFY-001 Phase 2).

This file is intentionally thin. It does not reimplement writer semantics.
It dispatches to the currently active entrypoints and preserves their
stdout/stderr and process exit codes.

Public surface:
  python scripts/writer/cli.py <writer-core-command> [...]
  python scripts/writer/cli.py draft-loop [...]
  python scripts/writer/cli.py citation-trace [...]
  python scripts/writer/cli.py verify-claims [...]
  python scripts/writer/cli.py research-adapt [...]
  python scripts/writer/cli.py release-check [...]

The old entrypoints remain supported until the legacy/archive phase.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

_HERE = Path(__file__).resolve()
_HARNESS_ROOT = _HERE.parents[2]

_CORE_COMMANDS = {
    "plan", "draftcheck", "live-cycle", "extract", "graphs", "annotate",
    "consolidate", "vectorsim", "dom", "review", "uncertainty", "register",
}

_SCRIPT_ENTRYPOINTS = {
    "verify-claims": _HARNESS_ROOT / "scripts" / "researcher" / "verify_claims.py",
}
_MODULE_ENTRYPOINTS = {
    "draft-loop": "scripts.writer.drafting.draft_loop",
    "citation-trace": "scripts.writer.review.citation_trace",
    "research-adapt": "scripts.writer.research.verify_claims_adapter",
    "release-check": "scripts.writer.release.gate",
    "object-select": "scripts.writer.planning.object_router",
    "reference-prepare": "scripts.writer.references.prepare",
    "validation-plan": "scripts.writer.research.validation_router",
    "research-dispatch": "scripts.writer.research.dispatch_plan",
    "change-ledger": "scripts.writer.provenance.change_ledger",
    "reference-fragments": "scripts.writer.references.fragments",
    "reference-select": "scripts.writer.references.select",
    "evidence-select": "scripts.writer.references.evidence_select",
    "reference-select-iterative": "scripts.writer.references.iterative_select",
    "evidence-span": "scripts.writer.sources.evidence_span",
    "source-catalog": "scripts.writer.sources.source_catalog",
    "search-memory": "scripts.writer.sources.search_memory",
    "library-search": "scripts.writer.sources.library_search",
    "library-ingest": "scripts.writer.sources.library_ingest",
    "source-update": "scripts.writer.sources.update",
    "draft-request": "scripts.writer.drafting.request",
    "dependency-graph": "scripts.writer.provenance.dependency_graph",
    "provenance-register": "scripts.writer.provenance.event_bridge",
    "document-card": "scripts.writer.library.card_cli",
    "fragment-graph": "scripts.writer.references.enrich",
    "writing-policy": "scripts.writer.composition.writing_policy",
    "style-instruction": "scripts.writer.composition.style_instruction",
    "draft-artifact": "scripts.writer.drafting.artifact",
    "writer-dispatch": "scripts.writer.drafting.agent_dispatch",
    "dom-patch": "scripts.writer.drafting.dom_patch",
    "repair-request": "scripts.writer.drafting.repair",
    "claim-state": "scripts.writer.provenance.state_cli",
    "invalidation-register": "scripts.writer.provenance.invalidation_event",
}
_CORE_MODULE = "scripts.writer.core.cli"


def _emit_error(command: str | None, message: str) -> int:
    print(json.dumps({
        "command": command,
        "error": message,
        "fail_closed": True,
        "facade": "scripts/writer/cli.py",
    }, ensure_ascii=False, indent=2))
    return 2


def _dispatch(path: Path, argv: Sequence[str]) -> int:
    if not path.is_file():
        return _emit_error(argv[0] if argv else None, f"entrypoint missing: {path}")
    try:
        completed = subprocess.run([sys.executable, str(path), *argv], check=False, cwd=str(_HARNESS_ROOT))
    except OSError as exc:
        return _emit_error(argv[0] if argv else None, f"{type(exc).__name__}: {exc}")
    return int(completed.returncode)


def _dispatch_module(module: str, argv: Sequence[str]) -> int:
    try:
        completed = subprocess.run([sys.executable, "-m", module, *argv], check=False, cwd=str(_HARNESS_ROOT))
    except OSError as exc:
        return _emit_error(argv[0] if argv else None, f"{type(exc).__name__}: {exc}")
    return int(completed.returncode)


def _print_help() -> int:
    core = " ".join(sorted(_CORE_COMMANDS))
    aliases = " ".join(sorted({*_SCRIPT_ENTRYPOINTS, *_MODULE_ENTRYPOINTS}))
    print(
        "Canonical Writer CLI compatibility facade\n\n"
        "Usage:\n"
        "  python scripts/writer/cli.py <command> [args...]\n\n"
        f"Writer-core commands:\n  {core}\n\n"
        f"Compatibility aliases:\n  {aliases}\n\n"
        "Old entrypoints remain active during migration."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        return _print_help()

    command, rest = args[0], args[1:]
    if command in _CORE_COMMANDS:
        return _dispatch_module(_CORE_MODULE, [command, *rest])
    if command in _MODULE_ENTRYPOINTS:
        return _dispatch_module(_MODULE_ENTRYPOINTS[command], rest)
    if command in _SCRIPT_ENTRYPOINTS:
        return _dispatch(_SCRIPT_ENTRYPOINTS[command], rest)
    return _emit_error(command, f"unknown command: {command}")


if __name__ == "__main__":
    raise SystemExit(main())
