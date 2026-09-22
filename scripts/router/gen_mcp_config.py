#!/usr/bin/env python3
"""gen_mcp_config.py — генератор .opencode/.mcp.json из mcp_registry.json.

TD-154: проброс harness MCP-серверов (academic_search, searxng_search, doc_extract,
coder_router) в opencode как stdio-серверов. Генерирует .opencode/.mcp.json
детерминированно, чтобы субагенты (source-fetcher и др.) видели tools
(arxiv_search/openalex_search/searxng_search/extract_document/coder_run).

Usage:
  python gen_mcp_config.py [--root <harness-root>] [--python <python-exe>] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def default_python() -> str:
    """Python с mcp-библиотекой: venv harness, иначе системный."""
    candidates = [
        os.environ.get("PYTHON"),
        str(Path(sys.executable)),
    ]
    for c in candidates:
        if c:
            return c
    return sys.executable


def gen(root: Path, python_exe: str, dry_run: bool) -> int:
    registry_path = root / "config" / "mcp_registry.json"
    if not registry_path.exists():
        print(f"ERROR: нет {registry_path}", file=sys.stderr)
        return 2
    reg = json.loads(registry_path.read_text(encoding="utf-8"))
    servers = reg.get("servers", {})

    # политика: какие MCP включены в opencode (все, чьи entrypoint существуют)
    mcp_servers = {}
    enabled = []
    for name, cfg in servers.items():
        ep = root / cfg.get("entrypoint", "")
        if not ep.exists():
            print(f"  SKIP {name}: entrypoint {cfg.get('entrypoint')} не найден")
            continue
        if not cfg.get("tools"):
            print(f"  SKIP {name}: нет tools в реестре")
            continue
        mcp_servers[name] = {
            "command": python_exe,
            "args": [str(ep)],
            "env": {"PYTHONIOENCODING": "utf-8"},
        }
        enabled.append(name)

    config = {
        "_meta": {
            "generatedBy": "harness gen_mcp_config.py",
            "version": 1,
            "generatedAt": "",
            "note": "Авто-сгенерировано из config/mcp_registry.json. Не править вручную.",
        },
        "mcpServers": mcp_servers,
    }
    # сохранить метаданные
    from datetime import datetime, timezone
    config["_meta"]["generatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    out = root / ".opencode" / ".mcp.json"
    if dry_run:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        print(f"\n[DRY] Будет записано в {out}")
        return 0

    # бэкап существующего
    if out.exists():
        bak = out.with_suffix(".mcp.json.bak")
        shutil.copy2(out, bak)
        print(f"  бэкап: {out.name} -> {bak.name}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {out} — подключено MCP-серверов: {len(mcp_servers)}")
    for n in enabled:
        tools = servers[n].get("tools", [])
        print(f"  {n}: {tools}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Генератор .opencode/.mcp.json из mcp_registry (TD-154)")
    ap.add_argument("--root", default=None)
    ap.add_argument("--python", default=None, help="python с mcp-библиотекой")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = Path(args.root) if args.root else Path(__file__).resolve().parents[2]
    py = args.python or default_python()
    return gen(root, py, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())