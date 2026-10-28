"""Shared test configuration - adds MCP server source dirs to sys.path.

Adapted for the portable harness layout:
  <harness_root>/mcp/paper-parser-mcp
  <harness_root>/mcp/academic-search-mcp
Tests live in <harness_root>/tests/paper-review.
"""
import sys
import os

# tests/paper-review -> harness root
_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(_root, "mcp", "academic-search-mcp"))
sys.path.insert(0, os.path.join(_root, "mcp", "paper-parser-mcp"))