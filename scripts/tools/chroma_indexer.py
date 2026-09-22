#!/usr/bin/env python3
"""chroma_indexer.py — канонический индексер локального корпуса в ChromaDB.

Заменяет build_chroma.py и связанные ad-hoc скрипты (build_*.py индексации).
Фиксирует TD-104: батчинг <=5461, resume (пропуск уже индексированных),
лог прогресса, пути из env. Принцип: локальный корпус — ПЕРВЫЙ источник
поиска (TD-127/RS-025), до внешних API.

Usage:
    python chroma_indexer.py index [--base <corpus_dir>] [--db <chroma_dir>] [--collection papers] [--batch 2000]
    python chroma_indexer.py count [--db <chroma_dir>] [--collection papers]
    python chroma_indexer.py search --query "..." [--n 5] [--db <chroma_dir>] [--collection papers]
    python chroma_indexer.py reset [--db <chroma_dir>] [--collection papers]

Env: CHROMA_CORPUS_DIR, CHROMA_DB_DIR, CHROMA_COLLECTION, CHROMA_BATCH.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_BASE = os.environ.get("CHROMA_CORPUS_DIR", r"F:\AnalisysDataSet\02-Methods")
DEFAULT_DB = os.environ.get("CHROMA_DB_DIR", r"F:\AnalisysDataSet\.chroma_papers")
DEFAULT_COLLECTION = os.environ.get("CHROMA_COLLECTION", "papers")
DEFAULT_BATCH = int(os.environ.get("CHROMA_BATCH", "2000"))
MAX_BATCH = 5461  # chroma 1.5.9 лимит

# Python-окружения: chromadb есть не везде (TD-142). Если chromadb недоступен в
# текущем python — перевызвать себя через python, где он есть (системный hermes).
FALLBACK_PYTHONS = [
    r"C:\Users\Arhys\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe",
    "python",
]


def _ensure_chromadb() -> None:
    """Если chromadb недоступен — перевызвать скрипт через python с chromadb."""
    try:
        import chromadb  # noqa: F401
        return
    except ImportError:
        pass
    for py in FALLBACK_PYTHONS:
        try:
            import subprocess
            probe = subprocess.run([py, "-c", "import chromadb"], capture_output=True, timeout=15)
            if probe.returncode == 0:
                print(f"INFO: chromadb нет в текущем python, перезапуск через {py} (TD-142)", file=sys.stderr)
                subprocess.run([py, *sys.argv], env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                raise SystemExit(0)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    print("ERROR: chromadb не найден ни в одном python. pip install chromadb", file=sys.stderr)
    raise SystemExit(3)


def extract_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    lines = [l for l in text.split("\n") if l.strip() and not l.startswith("#") and not l.startswith("**")]
    return "\n".join(lines)


def _client(db: str):
    import chromadb
    return chromadb.PersistentClient(path=db)


def cmd_index(args) -> int:
    import chromadb
    base = Path(args.base)
    db = args.db
    col_name = args.collection
    batch = min(args.batch, MAX_BATCH)

    client = _client(db)
    try:
        col = client.get_collection(col_name)
        existing_ids = set(col.get()["ids"]) if col.count() else set()
        print(f"Существующая коллекция: {col.count()} чанков, resume={len(existing_ids)} ids")
    except Exception:
        from chromadb.utils import embedding_functions
        ef = embedding_functions.DefaultEmbeddingFunction()
        col = client.create_collection(col_name, embedding_function=ef)
        existing_ids = set()
        print("Коллекция создана")

    notes = [f for f in base.iterdir() if f.suffix.lower() == ".md"]
    print(f"Заметок: {len(notes)}")

    to_add = []
    for fn in sorted(notes):
        nid = fn.stem
        text = extract_text(fn)
        if len(text) < 30:
            continue
        chunks = re.split(r"### \u041c\u0435\u0442\u043e\u0434 \d+", text) or [text]
        for ci, ch in enumerate(chunks):
            ch = ch.strip()
            if len(ch) < 30:
                continue
            for si in range(0, len(ch), 1500):
                piece = ch[si:si + 1500]
                cid = f"{nid}__c{ci}__s{si // 1500}"
                if cid in existing_ids:
                    continue
                to_add.append({"id": cid, "text": piece, "file": fn.name})

    print(f"К добавлению: {len(to_add)} чанков (batch={batch})")
    for i in range(0, len(to_add), batch):
        b = to_add[i:i + batch]
        col.add(
            ids=[x["id"] for x in b],
            documents=[x["text"] for x in b],
            metadatas=[{"file": x["file"]} for x in b],
        )
        print(f"  batch {i // batch + 1}: {len(b)} чанков, всего {col.count()}")
    print(f"Готово. Всего чанков: {col.count()}")
    return 0


def cmd_count(args) -> int:
    client = _client(args.db)
    try:
        col = client.get_collection(args.collection)
        print(f"collection={args.collection}: {col.count()} чанков")
    except Exception as e:
        print(f"Коллекция не найдена: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_search(args) -> int:
    client = _client(args.db)
    try:
        col = client.get_collection(args.collection)
    except Exception as e:
        print(f"Коллекция не найдена: {e}", file=sys.stderr)
        return 1
    res = col.query(query_texts=[args.query], n_results=args.n)
    for i, (doc, meta, dist) in enumerate(zip(res["documents"][0], res["metadatas"][0], res["distances"][0])):
        print(f"[{i}] dist={dist:.3f} file={meta.get('file', '?')}")
        print(f"    {doc[:200]}")
        print()
    return 0


def cmd_reset(args) -> int:
    client = _client(args.db)
    try:
        client.delete_collection(args.collection)
        print(f"Коллекция {args.collection} удалена")
    except Exception as e:
        print(f"Не удалось удалить: {e}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    _ensure_chromadb()
    ap = argparse.ArgumentParser(description="Канонический индексер ChromaDB (TD-104/TD-127)")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--collection", default=DEFAULT_COLLECTION)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("index")
    p.add_argument("--base", default=DEFAULT_BASE)
    p.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("count")
    p.set_defaults(fn=cmd_count)

    p = sub.add_parser("search")
    p.add_argument("--query", required=True)
    p.add_argument("-n", type=int, default=5)
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("reset")
    p.set_defaults(fn=cmd_reset)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())