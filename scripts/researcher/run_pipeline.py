#!/usr/bin/env python3
"""Deterministic Researcher pipeline (code-controlled, no LLM agency).

Выполняет полный цикл верификации научного утверждения кодом:
  search (arxiv/openalex/searxng) -> relevance scoring (code) -> extract (top)
  -> verdict draft -> JSONL log of every action.

Контракты и границы задаёт КОД; агент/оркестратор ничего не решает на откуп.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mcp"))

import academic_search_server as acs  # noqa: E402
import searxng_search_server as sxs  # noqa: E402


RELEVANCE_KEYWORDS = [
    "lattice parameter", "lattice constant", "unit cell", "xrd", "diffraction",
    "solid solution", "ceria", "zirconia", "cerium", "zirconium", "vegard",
    "parameter de red", "параметр решётк", "твёрдый раствор",
]


class PipelineLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, action: str, result: str, note: str = "") -> None:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "action": action,
            "result": result,
            "note": note,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{rec['ts']}] {action}: {result} {note}")


def _relevance(text: str) -> int:
    """Deterministic relevance score (code, no LLM)."""
    t = (text or "").lower()
    return sum(1 for kw in RELEVANCE_KEYWORDS if kw.lower() in t)


def _dedup(records: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for r in records:
        key = (r.get("title") or "")[:80] + r.get("doi", "") + r.get("url", "")
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def run_pipeline(query: str, out_dir: Path, max_extract: int = 2) -> dict:
    logger = PipelineLogger(out_dir / "pipeline.log.jsonl")

    # 1. Search all three channels (code-controlled contracts)
    logger.log("search:arxiv", "", "start")
    arxiv = acs._arxiv_search(query, max_results=5)
    logger.log("search:arxiv", f"{len(arxiv)} hits")

    logger.log("search:openalex", "", "start")
    openalex = acs._openalex_search(query, per_page=6)
    logger.log("search:openalex", f"{len(openalex)} hits")

    logger.log("search:searxng", "", "start")
    searxng = sxs._search(query, limit=8)
    logger.log("search:searxng", f"{len(searxng)} hits")

    # 2. Normalize + score relevance (code)
    records: list[dict] = []
    for r in arxiv:
        blob = " ".join([r.get("title", ""), r.get("abstract", "")])
        records.append({"channel": "arxiv", "title": r["title"], "url": r.get("pdf_url", ""), "doi": "", "abstract": r.get("abstract", "")[:300], "relevance": _relevance(blob)})
    for r in openalex:
        blob = " ".join([r.get("title", ""), r.get("display_name", ""), str(r.get("year", ""))])
        records.append({"channel": "openalex", "title": r.get("title", ""), "url": "", "doi": r.get("doi", ""), "abstract": "", "relevance": _relevance(blob)})
    for r in searxng:
        blob = " ".join([r.get("title", ""), r.get("snippet", "")])
        records.append({"channel": "searxng", "title": r.get("title", ""), "url": r.get("url", ""), "doi": "", "abstract": r.get("snippet", "")[:300], "relevance": _relevance(blob)})

    records = _dedup(records)
    records.sort(key=lambda x: x["relevance"], reverse=True)
    logger.log("dedup+rank", f"{len(records)} unique, top relevance={records[0]['relevance'] if records else 0}")

    # 3. Extract top candidates (code-selected); fetch URL -> temp file -> extract
    extracts: list[dict] = []
    top = [r for r in records if r["relevance"] > 0 and r.get("url")][:max_extract]
    logger.log("extract:select", f"{len(top)} candidates with url", "")
    import tempfile
    import urllib.request as _ur

    for r in top:
        try:
            from doc_extract_server import _extract_html
            tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
            req = _ur.Request(r["url"], headers={"User-Agent": "hermes-pipeline/1.0"})
            with _ur.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            tmp.write(html)
            tmp.close()
            text = _extract_html(tmp.name)[:600]
            extracts.append({"source": r["url"], "title": r["title"], "excerpt": text, "status": "extracted"})
            logger.log("extract", f"OK {r['url'][:60]}", f"chars={len(text)}")
            os.unlink(tmp.name)
        except Exception as e:  # noqa: BLE001
            extracts.append({"source": r["url"], "title": r["title"], "excerpt": "", "status": f"FAIL:{type(e).__name__}"})
            logger.log("extract", f"FAIL {r['url'][:60]}", str(e)[:120])

    # 4. Draft verdict (code rules, no LLM)
    has_strong = any(r["relevance"] >= 2 for r in records)
    has_extract = any(e["status"] == "extracted" and e["excerpt"] for e in extracts)
    verdict = "OPEN"
    if not records:
        verdict = "UNSUPPORTED"
    elif has_strong and has_extract:
        verdict = "PARTIALLY_SUPPORTED"
    elif has_strong:
        verdict = "OPEN"  # relevant sources exist, need manual/LLM read
    logger.log("verdict", verdict, f"strong={has_strong} extract={has_extract}")

    artifact = {
        "schema": "researcher-pipeline-deterministic/1.0",
        "date": time.strftime("%Y-%m-%d"),
        "query": query,
        "channels": {"arxiv": len(arxiv), "openalex": len(openalex), "searxng": len(searxng)},
        "total_unique": len(records),
        "top_candidates": [{"channel": r["channel"], "title": r["title"][:90], "relevance": r["relevance"], "url": r.get("url", ""), "doi": r.get("doi", "")} for r in records[:6]],
        "extracts": extracts,
        "verdict": verdict,
        "verdict_basis": f"strong_relevant={has_strong}, extract_ok={has_extract}",
    }
    (out_dir / "pipeline_result.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.log("artifact", f"saved {out_dir.name}/pipeline_result.json")
    return artifact


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="cerium zirconium oxide solid solution lattice parameter XRD")
    ap.add_argument("--out", default=str(ROOT / "run" / "researcher_deterministic_20260917"))
    args = ap.parse_args()
    art = run_pipeline(args.query, Path(args.out))
    print(json.dumps({k: art[k] for k in ("channels", "total_unique", "verdict")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())