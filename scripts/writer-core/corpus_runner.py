# -*- coding: utf-8 -*-
"""Corpus runner for Writer Core v0.3 — batch linguistic analysis of dissertation abstracts.

L3 semantic module. Pipeline per document:
    extract text (.docx via python-docx / .pdf via pymupdf / .md as-is)
        -> split sentences (t0_ru.split_sentences, razdel)
        -> per sentence: analyze_sentence + build_digest -> LinguisticDigest
        -> optional (use_llm=True): propose_variants (weak LLM) + RTT compare(source, variant)
        -> corpus-level aggregates: epistemic force, issues by type/category,
           top connectives, top force lexemes, numeric frequency
        -> JSON report written below WRITER_RUNS_DIR (utf-8)

Fail-closed: unreadable files are recorded in report["errors"] and never abort the run;
per-sentence exceptions are counted as sentence_errors and skipped.
LLM is OFF by default (cost budget): use_llm=True must be passed explicitly.
Runtime is bounded by a global sentence cap (see run_corpus docstring) to stay <60 s without LLM.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from typing import Any

_WC_ROOT = os.environ.get("WRITER_CORE_ROOT") or os.path.dirname(os.path.abspath(__file__))
for _p in (_WC_ROOT, os.path.join(_WC_ROOT, "v2_extractor")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from t0_ru import analyze_sentence, split_sentences  # noqa: E402
from digest_builder import build_digest  # noqa: E402

try:  # modern pymupdf name (no deprecation warning); fall back to legacy `fitz`
    import pymupdf as fitz  # type: ignore[no-redef]
except Exception:  # pragma: no cover
    import fitz  # type: ignore[no-redef]

try:
    import docx  # python-docx
except Exception:  # pragma: no cover
    docx = None  # type: ignore[assignment]

REPORT_PATH = os.path.join(os.environ.get("WRITER_RUNS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")), "corpus_report.json")

_SUPPORTED_EXT = {".docx", ".pdf", ".md"}

# issue-type substrings -> metric category (contract: модальность/причинность/скоуп/коннективы)
_ISSUE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "MODALITY": ("MODALITY",),
    "CAUSALITY": ("CAUSALITY", "CAUSAL"),
    "SCOPE": ("SCOPE",),
    "CONNECTIVE": ("CONNECTIVE",),
}


# ----------------------------------------------------------------------------- extraction

def extract_document(path: str) -> str:
    """Extract plain text from a document. Raises on unsupported/unreadable files.

    .docx -> paragraph texts joined by newline (python-docx)
    .pdf  -> page texts joined by newline (pymupdf)
    .doc  -> text via Word COM Content.Text (writer_core.doc_com), fail-closed
    .md   -> raw text, encoding auto-detected (utf-8 -> cp1251 -> cp866 -> replace)
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return _extract_docx(path)
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".doc":
        try:
            from writer_core.doc_com import extract_doc_text
            return extract_doc_text(path)
        except Exception as e:
            raise ValueError(f".doc извлечение не удалось: {e}") from e
    if ext == ".md":
        return _extract_md(path)
    raise ValueError(f"unsupported extension {ext!r}, supported: {sorted(_SUPPORTED_EXT)}")


def _extract_docx(path: str) -> str:
    if docx is None:
        raise RuntimeError("python-docx is not installed")
    d = docx.Document(path)
    return "\n".join(p.text for p in d.paragraphs)


def _extract_pdf(path: str) -> str:
    with fitz.open(path) as pdf:
        return "\n".join(page.get_text() for page in pdf)


def _extract_md(path: str) -> str:
    with open(path, "rb") as fh:
        data = fh.read()
    for enc in ("utf-8", "cp1251", "cp866"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# ----------------------------------------------------------------------------- metrics

def _categorize_issue(issue_type: str) -> list[str]:
    """Map an issue type string to metric categories (may be several)."""
    return [cat for cat, keys in _ISSUE_CATEGORIES.items() if any(k in issue_type for k in keys)]


def _top(counter: Counter[str], n: int = 10) -> list[list[str]]:
    """Counter -> [[item, count], ...] sorted desc, for JSON-safe output."""
    return [[k, int(v)] for k, v in counter.most_common(n)]


# ----------------------------------------------------------------------------- runner

def run_corpus(paths: list[str], max_sentences: int = 200, use_llm: bool = False,
               report_path: str | None = None) -> dict:
    """Run the full corpus pipeline over `paths`.

    Per document: extract text, split into sentences (razdel), process up to
    `max_sentences` sentences. Global sentence cap = max_sentences * len(paths),
    hard-ceilinged at 1500 — keeps an LLM-free run well under ~60 s.

    Returns the report dict and writes it as utf-8 JSON to `report_path`
    (default ``scripts/writer-core/runs/corpus_report.json``).
    """
    t_start = time.perf_counter()
    use_llm = bool(use_llm)
    if use_llm:
        from weak_llm import propose_variants  # local import: keep non-LLM runs clean
        from rtt_compare import compare as rtt_compare

    global_cap = max(200, min(max_sentences * max(1, len(paths)), 1500))

    report: dict[str, Any] = {
        "schema": "writer_core.corpus_report.v1",
        "meta": {
            "max_sentences_per_doc": int(max_sentences),
            "global_sentence_cap": global_cap,
            "use_llm": use_llm,
            "corpus_files": len(paths),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "documents": {},
        "errors": [],
        "sentences": {"total_processed": 0, "per_document": {}, "sentence_errors": 0},
        "metrics": {},
        "llm": {"enabled": False},
    }

    force_counter: Counter[str] = Counter()
    modality_counter: Counter[str] = Counter()
    issue_type_counter: Counter[str] = Counter()
    issue_cat_counter: Counter[str] = Counter()
    connective_counter: Counter[str] = Counter()
    force_lexeme_counter: Counter[str] = Counter()
    rtt_verdicts: Counter[str] = Counter()
    rtt_reasons: Counter[str] = Counter()

    sentences_with_issue = 0
    numbers_total = 0
    sentences_with_numbers = 0
    sentence_error_examples: list[str] = []
    llm_variant_count = 0
    llm_error_count = 0
    llm_records: list[dict[str, Any]] = []
    processed = 0

    for path in paths:
        key = os.path.normpath(path)
        rec: dict[str, Any] = {"format": os.path.splitext(path)[1].lower(), "status": "ok"}
        try:
            text = extract_document(path)
        except Exception as e:  # fail-closed: never abort the whole run
            rec["status"] = "error"
            rec["error"] = f"{type(e).__name__}: {e}"
            report["errors"].append({"path": key, "error": rec["error"]})
            report["documents"][key] = rec
            continue

        sentences = split_sentences(text)
        rec["text_chars"] = len(text)
        rec["sentences_total"] = len(sentences)
        rec["sentences_processed"] = 0

        for sent in sentences:
            if processed >= global_cap or rec["sentences_processed"] >= max_sentences:
                break
            processed += 1
            rec["sentences_processed"] += 1
            try:
                s = analyze_sentence(sent)
                digest = build_digest(sent)
            except Exception as e:  # per-sentence fail-closed
                report["sentences"]["sentence_errors"] += 1
                if len(sentence_error_examples) < 20:
                    sentence_error_examples.append(f"{type(e).__name__}: {e} | {sent[:120]}")
                continue

            force_counter[s.force] += 1
            modality_counter[digest.modality or "none"] += 1
            if s.force_expr:
                force_lexeme_counter[s.force_expr] += 1
            for c in s.connectives:
                connective_counter[c["form"]] += 1
            if s.numbers:
                numbers_total += len(s.numbers)
                sentences_with_numbers += 1
            if digest.ambiguities:
                sentences_with_issue += 1
                cats: set[str] = set()
                for iss in digest.ambiguities:
                    issue_type_counter[iss.type] += 1
                    cats.update(_categorize_issue(iss.type))
                for cat in cats:
                    issue_cat_counter[cat] += 1

            if use_llm:
                variants = propose_variants(sent)
                llm_variant_count += len(variants)
                vrecs: list[dict[str, Any]] = []
                for v in variants:
                    if v.get("intent") == "ERROR":
                        llm_error_count += 1
                        vrecs.append({"intent": "ERROR", "text": v["text"]})
                        continue
                    rr = rtt_compare(sent, v["text"])
                    rtt_verdicts[rr.verdict] += 1
                    for rc in rr.reason_codes:
                        rtt_reasons[rc.value] += 1
                    vrecs.append({"intent": v["intent"], "text": v["text"],
                                  "rtt_verdict": rr.verdict,
                                  "reason_codes": [rc.value for rc in rr.reason_codes]})
                llm_records.append({"sentence_index": processed, "variants": vrecs})

        report["documents"][key] = rec
        report["sentences"]["per_document"][key] = rec["sentences_processed"]
        if processed >= global_cap:
            break

    total = processed
    report["sentences"]["total_processed"] = total
    if sentence_error_examples:
        report["sentences"]["sentence_error_examples"] = sentence_error_examples

    report["metrics"] = {
        "epistemic_force_distribution": dict(force_counter),
        "modality_distribution": dict(modality_counter),
        "sentences_with_issues": sentences_with_issue,
        "issue_share_of_sentences": round(sentences_with_issue / total, 4) if total else 0.0,
        "issues_by_type": dict(issue_type_counter),
        "issues_by_category_share": {
            cat: round(issue_cat_counter[cat] / total, 4) if total else 0.0
            for cat in _ISSUE_CATEGORIES
        },
        "top_connectives": _top(connective_counter),
        "top_force_lexemes": _top(force_lexeme_counter),
        "numbers": {
            "total_mentions": numbers_total,
            "sentences_with_numbers": sentences_with_numbers,
            "mean_mentions_per_sentence": round(numbers_total / total, 3) if total else 0.0,
        },
    }

    if use_llm:
        report["llm"] = {
            "enabled": True,
            "variant_count": llm_variant_count,
            "llm_error_count": llm_error_count,
            "rtt_verdicts": dict(rtt_verdicts),
            "rtt_reasons": dict(rtt_reasons),
            "per_sentence": llm_records,
        }

    report["meta"]["run_elapsed_sec"] = round(time.perf_counter() - t_start, 2)
    report["meta"]["corpus_errors"] = len(report["errors"])

    out_path = report_path or REPORT_PATH
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    return report


# ----------------------------------------------------------------------------- cli

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Corpus run: dissertation abstracts -> linguistic report")
    ap.add_argument("patterns", nargs="+", help="glob pattern(s) for documents")
    ap.add_argument("--max", type=int, default=200, help="max sentences per document")
    ap.add_argument("--llm", action="store_true", help="enable weak-LLM variants + RTT compare")
    ap.add_argument("--out", default=REPORT_PATH, help="output JSON path")
    args = ap.parse_args()

    import glob as _glob

    found: list[str] = []
    for pat in args.patterns:
        found.extend(_glob.glob(pat))
    # dedupe, keep order
    seen: set[str] = set()
    unique = [p for p in found if not (p in seen or seen.add(p))]

    rep = run_corpus(unique, max_sentences=args.max, use_llm=args.llm, report_path=args.out)
    print(json.dumps({
        "files": len(unique),
        "errors": rep["meta"]["corpus_errors"],
        "sentences_processed": rep["sentences"]["total_processed"],
        "report": args.out,
        "elapsed_sec": rep["meta"]["run_elapsed_sec"],
    }, ensure_ascii=False, indent=2))
