#!/usr/bin/env python3
"""Actual pinned Graphify MCP reader, with no assistant/global auto-install."""
from knowledge_pilot.runtime import configure

configure()

from graphify.serve import _main

if __name__ == "__main__":
    _main()
