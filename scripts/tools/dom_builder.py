#!/usr/bin/env python3
"""dom_builder.py — детерминированный билдер research-DOM и артефактов.

Закрывает TD-143 (главный блок аудита): заменяет десятки ad-hoc скриптов
(build_dom.py, gen_claims.py, update_dom_local.py, build_citations_map.py,
update_dom_citations.py, fix_dom_p0p3.py, write_depth_to_dom.py, dom_nist_update.py,
build_cluster_report.py, check_dom_status.py), которыми агент вручную заполнял DOM.

Артефакты:
  ch1_dom.json          — DOM главы (sections[] → claims[] → citations/verified_sources)
  citations_map.json    — карта цитат ↔ первоисточники
  ch1_dom_report.md     — человеко-читаемый отчёт из DOM

Операции:
  update-claim   — обновить claim в DOM (citations/verified_sources/len) по claim_id
  sync-citations — синхронизировать citations в DOM из citations_map (по claim_id)
  report         — сгенерировать ch1_dom_report.md из DOM (цветовая кодировка)
  verify         — проверить целостность DOM (каждый claim имеет citations/verified_sources)
  stats          — статистика DOM (секции/клаймы/цитаты)

Usage:
  python dom_builder.py update-claim --dom ch1_dom.json --claim c0 --citations "[{}]" --sources "[{}]"
  python dom_builder.py sync-citations --dom ch1_dom.json --cmap citations_map.json
  python dom_builder.py report --dom ch1_dom.json [-o ch1_dom_report.md]
  python dom_builder.py verify --dom ch1_dom.json
  python dom_builder.py stats --dom ch1_dom.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_DOM = os.environ.get("RESEARCH_DOM", r"F:\1\_STRUCTURED\research_verification\ch1_dom.json")


def _load(p: str) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _save(p: str, data) -> None:
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _iter_claims(dom: dict):
    """Итерирует (section, claim) по всем claims в DOM."""
    for sec in dom.get("sections", []):
        for claim in sec.get("claims", []):
            yield sec, claim


def _find_claim(dom: dict, claim_id: str):
    for sec, claim in _iter_claims(dom):
        if str(claim.get("claim_id")) == claim_id:
            return sec, claim
    return None, None


def cmd_update_claim(args) -> int:
    dom = _load(args.dom)
    sec, claim = _find_claim(dom, args.claim)
    if claim is None:
        print(f"ERROR: claim {args.claim} не найден в DOM", file=sys.stderr)
        return 2
    if args.citations:
        claim["citations"] = json.loads(args.citations)
    if args.sources:
        claim["verified_sources"] = json.loads(args.sources)
    if args.text:
        claim["text"] = args.text
    claim["len"] = len(claim.get("text", ""))
    _save(args.dom, dom)
    n_cit = len(claim.get("citations", []))
    n_src = len(claim.get("verified_sources", []))
    print(f"OK: {args.claim} обновлён (citations={n_cit}, sources={n_src}, len={claim['len']})")
    return 0


def _claim_id_from_context(context: str):
    """claim_id из context-строки вида 'c13: ...' или 'c13 — ...'."""
    import re
    m = re.match(r"\s*(c\d+)\s*[:—\-–]", context or "")
    return m.group(1) if m else None


def cmd_sync_citations(args) -> int:
    """Синхронизировать citations в DOM из citations_map (по claim_id).

    citations_map entries привязаны к клаймам через `context` (формат 'c13: ...').
    """
    dom = _load(args.dom)
    cmap = _load(args.cmap)
    entries = {}
    for cit in cmap.get("citations", []):
        cid = cit.get("claim_id") or cit.get("claim") or _claim_id_from_context(cit.get("context"))
        if cid:
            entries.setdefault(str(cid), []).append(cit)
    updated = 0
    for _, claim in _iter_claims(dom):
        cid = str(claim.get("claim_id"))
        if cid in entries:
            claim["citations"] = entries[cid]
            updated += 1
    _save(args.dom, dom)
    print(f"OK: синхронизировано citations для {updated} клаймов")
    return 0


def cmd_report(args) -> int:
    dom = _load(args.dom)
    out = Path(args.o) if args.o else (Path(args.dom).parent / "ch1_dom_report.md")
    lines = []
    title = dom.get("title", "DOM")
    lines.append(f"# {title}\n")
    n_supported = n_open = n_unsupported = n_ambiguous = 0
    for sec in dom.get("sections", []):
        heading = sec.get("heading", "?")
        lines.append(f"## {heading}\n")
        for claim in sec.get("claims", []):
            cid = claim.get("claim_id", "?")
            text = claim.get("text", "")[:120]
            n_cit = len(claim.get("citations", []))
            n_src = len(claim.get("verified_sources", []))
            # статус: sources=0 -> OPEN, else по наличию
            status = "OPEN" if n_src == 0 else ("OK" if n_cit > 0 else "PARTIAL")
            if status == "OK":
                n_supported += 1
            elif status == "OPEN":
                n_open += 1
            elif status == "PARTIAL":
                n_ambiguous += 1
            else:
                n_unsupported += 1
            emoji = {"OK": "🟢", "PARTIAL": "🟡", "OPEN": "⚪"}.get(status, "🔴")
            lines.append(f"- {emoji} **{cid}** [{status}] (cit={n_cit}, src={n_src}) — {text}")
    lines.append(f"\n---\nСводка: OK={n_supported}, PARTIAL={n_ambiguous}, OPEN={n_open}, UNSUPPORTED={n_unsupported}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: отчёт записан: {out}")
    return 0


def cmd_verify(args) -> int:
    dom = _load(args.dom)
    problems = []
    n_claims = 0
    for sec, claim in _iter_claims(dom):
        n_claims += 1
        cid = claim.get("claim_id", "?")
        if "text" not in claim or not claim.get("text"):
            problems.append(f"{cid}: нет text")
        if "citations" not in claim:
            problems.append(f"{cid}: нет citations")
        if "verified_sources" not in claim:
            problems.append(f"{cid}: нет verified_sources")
    if problems:
        print(f"Проблем: {len(problems)} (из {n_claims} клаймов)")
        for p in problems[:15]:
            print(f"  - {p}")
        return 1
    print(f"OK: DOM целостен ({n_claims} клаймов, секций {len(dom.get('sections', []))})")
    return 0


def cmd_stats(args) -> int:
    dom = _load(args.dom)
    n_sec = len(dom.get("sections", []))
    n_claims = sum(1 for _, _ in _iter_claims(dom))
    n_cit = sum(len(c.get("citations", [])) for _, c in _iter_claims(dom))
    n_src = sum(len(c.get("verified_sources", [])) for _, c in _iter_claims(dom))
    n_open = sum(1 for _, c in _iter_claims(dom) if not c.get("verified_sources"))
    print(f"секций: {n_sec}")
    print(f"клаймов: {n_claims}")
    print(f"цитат: {n_cit}")
    print(f"источников (verified_sources): {n_src}")
    print(f"клаймов без источников (OPEN): {n_open}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Детерминированный билдер research-DOM (TD-143)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("update-claim")
    p.add_argument("--dom", default=DEFAULT_DOM)
    p.add_argument("--claim", required=True)
    p.add_argument("--citations", default=None, help="JSON list")
    p.add_argument("--sources", default=None, help="JSON list")
    p.add_argument("--text", default=None)
    p.set_defaults(fn=cmd_update_claim)

    p = sub.add_parser("sync-citations")
    p.add_argument("--dom", default=DEFAULT_DOM)
    p.add_argument("--cmap", required=True)
    p.set_defaults(fn=cmd_sync_citations)

    p = sub.add_parser("report")
    p.add_argument("--dom", default=DEFAULT_DOM)
    p.add_argument("-o", default=None)
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("verify")
    p.add_argument("--dom", default=DEFAULT_DOM)
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("stats")
    p.add_argument("--dom", default=DEFAULT_DOM)
    p.set_defaults(fn=cmd_stats)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())