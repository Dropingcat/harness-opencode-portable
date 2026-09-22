#!/usr/bin/env python3
"""circularity.py — детектор циркулярности (инкапсулированный модуль).

Определяет происхождение источника относительно проверяемого claim:
  - origin="external": содержание НЕ происходит из проверяемого документа;
  - origin="document_derived": источник — цитата/пересказ строк документа
    (самоподтверждение текстом).

Механика (детерминированная, кодом):
  1. Если found_via == "in_text_reconstruction" — документный по построению.
  2. Перекрытие нормализованного текста источника и claim (Jaccard по
     токенам + покрытие биграммами, >= OVERLAP_THRESHOLD (0.6) → document_derived).
  3. Если источник дословно содержит claim (или наоборот) → document_derived.
  4. Если передан document_text и текст источника является пересказом строк
     документа (покрытие фрагментов) → document_derived.

Модуль самодостаточен и тестируется отдельно (test_circularity.py).

CLI:
  python3 circularity.py "<source_text>" "<claim_text>" [--document doc.txt] [--found-via local_corpus]
"""
import argparse
import re
import sys
from pathlib import Path

OVERLAP_THRESHOLD = 0.6          # >= → document_derived (проектное значение, калибруется)
DOC_LINE_COVERAGE = 0.4          # доля биграмм источника, найденных в документе


def normalize(text):
    """Нижний регистр, схлопывание пробелов, удаление пунктуации."""
    if not text:
        return ""
    t = str(text).lower()
    t = re.sub(r"[^a-zа-яё0-9\s-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tokenize(text):
    return [t for t in normalize(text).split(" ") if t]


def token_jaccard(a, b):
    """Jaccard по множествам токенов (нормализованных)."""
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def bigrams(tokens):
    return set(zip(tokens[:-1], tokens[1:]))


def phrase_coverage(short, long):
    """Доля биграмм short, встречающихся в long (покрытие подстрок)."""
    ts, tl = tokenize(short), tokenize(long)
    if len(ts) < 2 or len(tl) < 2:
        return 0.0
    bs = bigrams(ts)
    bl = bigrams(tl)
    if not bs:
        return 0.0
    return len(bs & bl) / len(bs)


def doc_line_coverage(source_text, doc_text):
    """Максимальная доля биграмм источника, найденных в ОДНОЙ строке документа.

    Покрытие по отдельным строкам, а не по всему документу: внешний источник с
    общими техническими фразами не получит высокое покрытие по одной строке,
    а пересказ строки документа — получит (строка-первоисточник концентрирует
    те же биграммы).
    """
    if not doc_text:
        return 0.0
    best = 0.0
    for line in doc_text.splitlines():
        c = phrase_coverage(source_text, line)
        best = max(best, c)
    return best


def detect_origin(source_text, claim_text, doc_text=None, found_via=None):
    """Определяет origin и overlap источника относительно claim.

    Возвращает dict: {origin, jaccard, claim_coverage, source_coverage,
    doc_coverage, reason, markers}.
    """
    markers = []
    if found_via == "in_text_reconstruction":
        return {
            "origin": "document_derived",
            "jaccard": 0.0,
            "claim_coverage": 0.0,
            "source_coverage": 0.0,
            "doc_coverage": 0.0,
            "reason": "источник восстановлен из внутритекстовых ссылок (in_text_reconstruction)",
            "markers": ["in_text_reconstruction"],
        }

    src = normalize(source_text or "")
    clm = normalize(claim_text or "")

    jac = token_jaccard(src, clm)
    claim_in_source = phrase_coverage(clm, src)   # насколько claim покрыт источником
    source_in_claim = phrase_coverage(src, clm)   # насколько источник покрыт claim
    doc_cov = doc_line_coverage(src, doc_text) if doc_text else 0.0

    overlap = max(jac, claim_in_source, source_in_claim)

    if clm and clm in src:
        markers.append("claim_is_substring_of_source")
        overlap = 1.0
        reason = "claim дословно входит в текст источника"
    elif src and src in clm:
        markers.append("source_is_substring_of_claim")
        overlap = 1.0
        reason = "текст источника дословно входит в claim"
    elif overlap >= OVERLAP_THRESHOLD:
        markers.append("overlap_ge_threshold")
        reason = f"перекрытие источника и claim {overlap:.2f} >= {OVERLAP_THRESHOLD}"
    elif doc_text and doc_cov >= DOC_LINE_COVERAGE:
        markers.append("source_paraphrases_document")
        overlap = max(overlap, doc_cov)
        reason = (f"текст источника — пересказ документа (покрытие {doc_cov:.2f} "
                  f">= {DOC_LINE_COVERAGE})")
    else:
        markers.append("external")
        reason = "перекрытие ниже порога — источник внешний"

    origin = "document_derived" if overlap >= OVERLAP_THRESHOLD else "external"
    return {
        "origin": origin,
        "jaccard": round(jac, 3),
        "claim_coverage": round(claim_in_source, 3),
        "source_coverage": round(source_in_claim, 3),
        "doc_coverage": round(doc_cov, 3),
        "overlap": round(overlap, 3),
        "reason": reason,
        "markers": markers,
    }


def annotate_source(source, claim_text, doc_text=None):
    """Добавляет origin/overlap в запись источника (мутабельно) и возвращает её."""
    text = source.get("excerpt") or source.get("text") or source.get("title") or ""
    res = detect_origin(text, claim_text, doc_text, source.get("found_via"))
    source["origin"] = res["origin"]
    source["overlap"] = res.get("overlap", 0.0)
    source["_circularity"] = res
    if res["origin"] == "document_derived":
        source.setdefault("caveats", []).append(
            {"severity": "critical", "text": f"circular_source: {res['reason']}"}
        )
    return source


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source_text", help="текст источника (или файл @path)")
    ap.add_argument("claim_text", help="текст claim")
    ap.add_argument("--document", help="путь к документу (для проверки пересказа)")
    ap.add_argument("--found-via", default=None,
                    choices=["local_corpus", "openalex", "arxiv", "web_search",
                             "scibot", "in_text_reconstruction"])
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args()

    src = args.source_text
    if src.startswith("@") and Path(src[1:]).is_file():
        src = Path(src[1:]).read_text(encoding="utf-8")
    doc = None
    if args.document and Path(args.document).is_file():
        doc = Path(args.document).read_text(encoding="utf-8")

    res = detect_origin(src, args.claim_text, doc, args.found_via)
    if args.as_json:
        print(__import__("json").dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"origin: {res['origin']}")
        print(f"jaccard: {res['jaccard']} | claim_coverage: {res['claim_coverage']} "
              f"| source_coverage: {res['source_coverage']} | doc_coverage: {res['doc_coverage']}")
        print(f"reason: {res['reason']}")
        print(f"markers: {res['markers']}")


if __name__ == "__main__":
    main()