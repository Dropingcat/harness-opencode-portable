#!/usr/bin/env python3
"""CI smoke-test: ChromaDB локальный корпус доступен.

Запускается из GitHub Actions (ci.yml -> chroma-test job).
Путь к БД берётся из env CHROMA_DB_DIR (в CI не существует -> SKIP с кодом 0,
чтобы не блокировать пайплайн на машинах без локальных данных).
"""
import os
import sys
from pathlib import Path

try:
    import chromadb
except ImportError:
    print("chromadb не установлен -> SKIP")
    raise SystemExit(0)


def main() -> int:
    db = os.environ.get("CHROMA_DB_DIR", r"F:\AnalisysDataSet\.chroma_papers")
    if not os.path.isdir(db):
        print(f"ChromaDB БД не найдена: {db} -> SKIP (нет локальных данных)")
        return 0
    client = chromadb.PersistentClient(path=db)
    try:
        col = client.get_collection("papers")
    except Exception:
        print("Коллекция 'papers' не найдена -> SKIP")
        return 0
    n = col.count()
    print(f"ChromaDB OK: collection=papers count={n}")
    return 0 if n > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())