"""C1-C3 adapter: PDF -> canonical_document (schema conformant).

Детерминированный, без LLM. НЕ использует font-size эвристики как primary signal.
Опирается на reading order блоков pymupdf + типизацию по контексту.
Выход: документ, соответствующий schemas/canonical_document.schema.yaml.
Позже этот адаптер заменится на GROBID/Docling-адаптер с тем же форматом.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

import pymupdf  # fitz


@dataclass
class CanonicalBlock:
    block_id: str
    block_type: str
    text: str
    page: int
    bbox: list[float] = field(default_factory=list)
    level: int | None = None
    parent: str | None = None


@dataclass
class CanonicalDocument:
    doc_id: str
    source_path: str
    parser: str = "pymupdf_adapter"
    parser_version: str = "0.1"
    language: str = "ru"
    metadata: dict = field(default_factory=dict)
    blocks: list[CanonicalBlock] = field(default_factory=list)
    sentences: list[dict] = field(default_factory=list)


# ---------- block typing heuristic (context, NOT font size) ----------

_CAPS_HEADING_RE = re.compile(r"^[А-ЯЁA-Z][А-ЯЁA-Z0-9\s\-]{4,}$")
_HEADING_NUM_RE = re.compile(r"^\d{1,2}(\.\d{1,2}){0,2}\s+[А-ЯЁA-ZА-яа-я]")
_SECTION_NAMES = ("введение", "общая характеристика", "содержание работы", "заключение",
                  "список литературы", "выводы", "глава", "аннотация", "references",
                  "introduction", "conclusion", "abstract", "acknowledgements", "appendix")
_REF_HEADER_RE = re.compile(r"^(список использованных|литература|библиографический)", re.I)


def _is_section_word(t: str) -> bool:
    """Заголовок, если текст — одно секционное слово/короткое имя (отдельным словом)."""
    low = t.lower().rstrip("….:")
    if low in _SECTION_NAMES:
        return True
    # "ВВЕДЕНИЕ", "ЗАКЛЮЧЕНИЕ", "1 СОВРЕМЕННОЕ СОСТОЯНИЕ..."
    # но НЕ "Введение в стали..." (это абзац)
    first_word = low.split()[0] if low.split() else ""
    return first_word in _SECTION_NAMES and len(low.split()) == 1


def _looks_like_heading(text: str) -> bool:
    """Определить заголовок по содержимому (не font-size)."""
    t = text.strip()
    if not t or len(t) > 120:
        return False
    # никогда заголовок, если это физическая величина с единицей (формула/значение)
    if re.search(r"(МДж/м2|МПа|ГПа|мкм|мм\b|°С|%|кН|Н/мм2)", t):
        return False
    # одно секционное слово / короткое имя (ВВЕДЕНИЕ, ЗАКЛЮЧЕНИЕ)
    if _is_section_word(t):
        return True
    # "1 СОВРЕМЕННОЕ СОСТОЯНИЕ ВОПРОСА" / "1.1 Название" / "ГЛАВА 2 ..."
    if _CAPS_HEADING_RE.match(t):
        return True
    if _HEADING_NUM_RE.match(t):
        return True
    return False


def classify_block(text: str, first_line: str = "") -> str:
    """Типизация блока по содержанию (контентный классификатор, не layout)."""
    t = first_line.strip() if first_line else text.strip()
    if len(t) < 3:
        return "footer" if not t else "paragraph"
    if _looks_like_heading(t):
        return "heading"
    low = t.lower()
    if re.match(r"^(таблица|рис\.|рисунок|figure|table)\s*[\d.]", low):
        return "caption"
    if re.match(r"^\(?\d+\)?\.?\s*$", t):
        return "list"
    return "paragraph"


# ---------- block ordering (reading order) ----------

def extract_blocks_reading_order(path: Path) -> list[CanonicalBlock]:
    """Блоки в порядке чтения: top-to-bottom, left-to-right по bbox."""
    doc = pymupdf.open(str(path))
    blocks: list[CanonicalBlock] = []
    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        d = page.get_text("dict")
        page_blocks = []
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue  # images skip
            text = "".join(
                span.get("text", "")
                for line in b.get("lines", [])
                for span in line.get("spans", [])
            ).strip()
            if not text:
                continue
            bbox = list(b["bbox"])
            first = ""
            if b.get("lines"):
                first = "".join(s.get("text", "") for s in b["lines"][0].get("spans", [])).strip()
            page_blocks.append((bbox[1], bbox[0], bbox, text, first))  # y, x, ...
        page_blocks.sort(key=lambda r: (r[0], r[1]))
        for yi, xi, bbox, text, first in page_blocks:
            btype = classify_block(text, first)
            level = None
            if btype == "heading":
                m = re.match(r"^(\d+(?:\.\d+){0,3})", text.strip())
                if m:
                    level = m.group(1).count(".") + 1
                else:
                    level = 1
            blocks.append(CanonicalBlock(
                block_id=f"BLK_{len(blocks):05d}",
                block_type=btype,
                text=text,
                page=page_idx,
                bbox=bbox,
                level=level,
            ))
    doc.close()

    # Post-process: demote false headings that are continuation lines of previous
    # paragraph (no vertical gap above them on the same page, and previous block
    # did not end with terminal punctuation AND is long).
    for i in range(1, len(blocks)):
        prev = blocks[i - 1]
        cur = blocks[i]
        if cur.block_type != "heading":
            continue
        # TOC: "3.5 Выводы по третьей главе" followed by dot leaders "... 68"
        if re.search(r"[….]{4,}\s*\d{1,3}$", cur.text) or re.search(r"\.{2,}\s*\d{1,3}$", cur.text):
            cur.block_type = "toc_item"
            cur.level = None
            continue
        # Title page (page 0) CAPS names/authors are not structural headings
        if cur.page == 0 and cur.level == 1 and not _is_section_word(cur.text):
            cur.block_type = "paragraph"
            cur.level = None
            continue
        # Заголовок с прилипшим текстом: "ВВЕДЕНИЕ Общая характеристика..." -> split
        # Если предыдущий блок не абзац (start of section) и внутри есть точка, отделяющая
        # заголовок от текста — обрезаем до заголовка.
        m = re.match(r"^((?:[А-ЯЁA-Z0-9\s]{4,})(?:\d+(?:\.\d+){0,3})?)\s{1,3}([А-ЯЁ][а-яё].{40,})", cur.text.strip())
        if m and _looks_like_heading(m.group(1)):
            cur.text = m.group(1).strip()
        same_page = prev.page == cur.page
        if not same_page:
            continue
        cur_height = cur.bbox[3] - cur.bbox[1] if cur.bbox else 12.0
        gap = cur.bbox[1] - prev.bbox[3]  # top - bottom
        prev_text = prev.text.strip()
        prev_short = len(prev_text) < 200
        prev_no_terminal = not re.search(r"[.;!?…]\s*$", prev_text)
        # If previous block is short (likely a heading) -> keep cur as heading.
        if prev_short:
            continue
        # Previous is a long paragraph. If it doesn't end with terminal punctuation
        # and there is no large vertical gap, cur is a continuation, not a heading.
        if prev_no_terminal and gap < cur_height * 1.5:
            cur.block_type = "paragraph"
            cur.level = None
    return blocks


# ---------- canonical assembly ----------

def build_canonical(path: Path, doc_id: str) -> CanonicalDocument:
    blocks = extract_blocks_reading_order(path)
    doc = CanonicalDocument(
        doc_id=doc_id,
        source_path=str(path),
        metadata={"title": Path(path).stem, "pages": _page_count(path)},
    )
    doc.blocks = blocks
    # sentences per paragraph
    for bi, blk in enumerate(blocks):
        if blk.block_type in ("paragraph", "abstract", "heading", "caption"):
            for si, s in enumerate(_split_sentences(blk.text)):
                doc.sentences.append({"block_id": blk.block_id, "si": si, "s": s})
    return doc


# sentence splitter (ru academic conventions)
_SENT_END_RE = re.compile(r"(?<=[.;!?…])\s+(?=[А-ЯЁA-Z0-9«\"(])")


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return _SENT_END_RE.split(text)


def _page_count(path: Path) -> int:
    d = pymupdf.open(str(path))
    n = d.page_count
    d.close()
    return n


# ---------- canonical -> sqlite (для построения графов) ----------

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, path TEXT, title TEXT, parser TEXT, lang TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS blocks (
    block_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, block_type TEXT, text TEXT,
    page INTEGER, bbox TEXT, level INTEGER, parent TEXT,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS sentences (
    sentence_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, block_id TEXT,
    text TEXT, page INTEGER, si INTEGER,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS quantities (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL, block_id TEXT,
    raw TEXT, value_lower REAL, value_upper REAL, value_exact REAL, unit TEXT, dimension TEXT,
    sentence_id TEXT, si INTEGER
);
CREATE TABLE IF NOT EXISTS citations (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL, block_id TEXT,
    marker TEXT, context TEXT, ref_text TEXT
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def store_canonical(doc: CanonicalDocument, conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO documents(id, path, title, parser, lang) VALUES (?,?,?,?,?)",
        (doc.doc_id, doc.source_path, doc.metadata.get("title"), doc.parser, doc.language),
    )
    for blk in doc.blocks:
        conn.execute(
            "INSERT OR REPLACE INTO blocks(block_id, document_id, block_type, text, page, bbox, level, parent) VALUES (?,?,?,?,?,?,?,?)",
            (blk.block_id, doc.doc_id, blk.block_type, blk.text, blk.page,
             json.dumps(blk.bbox), blk.level, blk.parent),
        )
    for i, st in enumerate(doc.sentences):
        conn.execute(
            "INSERT OR REPLACE INTO sentences(sentence_id, document_id, block_id, text, page, si) VALUES (?,?,?,?,?,?)",
            (f"SEN_{doc.doc_id}_{i:06d}", doc.doc_id, st["block_id"], st["s"], -1, st["si"]),
        )
    conn.commit()


# ---------- main ----------

def run(path: Path, db_path: Path | None, doc_id: str) -> dict:
    doc = build_canonical(path, doc_id)
    if db_path is not None:
        conn = sqlite3.connect(str(db_path))
        init_db(conn)
        store_canonical(doc, conn)
        conn.close()
    return {
        "document_id": doc.doc_id,
        "blocks": len(doc.blocks),
        "sentences": len(doc.sentences),
        "headings": sum(1 for b in doc.blocks if b.block_type == "heading"),
        "title": doc.metadata.get("title"),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="C1-C3 adapter: PDF -> canonical_document")
    ap.add_argument("pdf")
    ap.add_argument("--db", default=None)
    ap.add_argument("--doc-id", default=None)
    a = ap.parse_args()
    did = a.doc_id or Path(a.pdf).stem.replace(" ", "_")[:40]
    r = run(Path(a.pdf), Path(a.db) if a.db else None, did)
    print(json.dumps(r, ensure_ascii=False, indent=2))