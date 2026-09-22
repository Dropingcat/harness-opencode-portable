#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim for WRITER-UNIFY-001 Phase 5.

Canonical implementation: :mod:`scripts.writer.drafting.draft_loop`.
This path remains callable until P6 reference migration and P8 archive criteria.
"""
from __future__ import annotations

try:
    from scripts.writer.drafting import draft_loop as _impl
except ModuleNotFoundError:  # direct execution from scripts/writer/
    from drafting import draft_loop as _impl  # type: ignore

main = _impl.main


def __getattr__(name: str):
    return getattr(_impl, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_impl)))


if __name__ == "__main__":
    raise SystemExit(main())
