#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = "source_catalog/1.1"
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


def _db(path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("pragma journal_mode=WAL")
    connection.execute(
        """create table if not exists source_catalog(
          source_id text primary key, path text, sha256 text not null, media_type text,
          title text, authors_json text, year integer, doi text, language text, document_kind text,
          extractor_version text, metadata_json text, created_at text, updated_at text)"""
    )
    connection.execute(
        """create table if not exists source_versions(
          source_id text, sha256 text, path text, first_seen_at text, metadata_json text,
          primary key(source_id,sha256))"""
    )
    connection.execute("create index if not exists idx_source_sha on source_catalog(sha256)")
    connection.execute("create index if not exists idx_source_path on source_catalog(path)")
    return connection


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def upsert(db: str, source: dict[str, Any]) -> dict[str, Any]:
    source_id = str(source.get("source_id") or "")
    sha256 = str(source.get("sha256") or "")
    if not source_id or SHA256_PATTERN.fullmatch(sha256) is None:
        raise ValueError("source_id and sha256 required")

    now = _now()
    connection = _db(db)
    old = connection.execute(
        "select source_id,sha256,metadata_json from source_catalog where source_id=?",
        (source_id,),
    ).fetchone()
    old_sha256 = old[1] if old else None
    old_metadata = json.loads(old[2] or "{}") if old else {}
    metadata = json.dumps(source.get("metadata") or {}, ensure_ascii=False, sort_keys=True)
    connection.execute(
        "insert or ignore into source_versions(source_id,sha256,path,first_seen_at,metadata_json) values(?,?,?,?,?)",
        (source_id, sha256, source.get("path"), now, metadata),
    )
    connection.execute(
        """insert into source_catalog(source_id,path,sha256,media_type,title,authors_json,year,doi,language,document_kind,extractor_version,metadata_json,created_at,updated_at)
        values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        on conflict(source_id) do update set path=excluded.path,sha256=excluded.sha256,media_type=excluded.media_type,title=excluded.title,authors_json=excluded.authors_json,year=excluded.year,doi=excluded.doi,language=excluded.language,document_kind=excluded.document_kind,extractor_version=excluded.extractor_version,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
        (
            source_id,
            source.get("path"),
            sha256,
            source.get("media_type"),
            source.get("title"),
            json.dumps(source.get("authors") or [], ensure_ascii=False),
            source.get("year"),
            source.get("doi"),
            source.get("language"),
            source.get("document_kind"),
            source.get("extractor_version"),
            metadata,
            now if not old else None,
            now,
        ),
    )
    new_metadata = source.get("metadata") or {}
    old_normalized = old_metadata.get("normalized_text_hash")
    new_normalized = new_metadata.get("normalized_text_hash")
    byte_changed = bool(old_sha256 and old_sha256 != sha256)
    semantic_changed = byte_changed if not (old_normalized and new_normalized) else old_normalized != new_normalized
    connection.commit()
    connection.close()
    return {
        "ok": True,
        "schema": SCHEMA,
        "source_id": source_id,
        "change": "updated" if old else "added",
        "old_sha256": old_sha256,
        "sha256": sha256,
        "content_changed": byte_changed,
        "semantic_changed": semantic_changed,
        "change_class": "SEMANTIC" if semantic_changed else ("BYTE_ONLY" if byte_changed else "UNCHANGED"),
    }


def get(db: str, source_id: str) -> dict[str, Any] | None:
    connection = _db(db)
    connection.row_factory = sqlite3.Row
    row = connection.execute("select * from source_catalog where source_id=?", (source_id,)).fetchone()
    connection.close()
    if not row:
        return None
    result = dict(row)
    result["authors"] = json.loads(result.pop("authors_json") or "[]")
    result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
    return result


def by_path_or_sha(db: str, path: str | None, sha256: str | None) -> dict[str, Any] | None:
    connection = _db(db)
    connection.row_factory = sqlite3.Row
    row = None
    if sha256 and path:
        row = connection.execute(
            "select * from source_catalog where sha256=? and path=? order by updated_at desc limit 1",
            (sha256, path),
        ).fetchone()
    elif sha256:
        row = connection.execute(
            "select * from source_catalog where sha256=? order by updated_at desc limit 1", (sha256,)
        ).fetchone()
    elif path:
        row = connection.execute(
            "select * from source_catalog where path=? order by updated_at desc limit 1", (path,)
        ).fetchone()
    connection.close()
    if not row:
        return None
    result = dict(row)
    result["authors"] = json.loads(result.pop("authors_json") or "[]")
    result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
    return result


def versions(db: str, source_id: str) -> list[dict[str, Any]]:
    connection = _db(db)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "select * from source_versions where source_id=? order by first_seen_at", (source_id,)
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def list_sources(db: str) -> list[dict[str, Any]]:
    connection = _db(db)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "select source_id,path,sha256,media_type,title,year,doi,language,document_kind,updated_at from source_catalog order by source_id"
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    command = subparsers.add_parser("upsert")
    command.add_argument("json_file")
    command = subparsers.add_parser("get")
    command.add_argument("source_id")
    command = subparsers.add_parser("versions")
    command.add_argument("source_id")
    subparsers.add_parser("list")
    args = parser.parse_args()
    try:
        if args.cmd == "upsert":
            output = upsert(args.db, json.loads(Path(args.json_file).read_text(encoding="utf8")))
        elif args.cmd == "get":
            output = {"ok": True, "schema": SCHEMA, "source": get(args.db, args.source_id)}
        elif args.cmd == "versions":
            output = {"ok": True, "schema": SCHEMA, "versions": versions(args.db, args.source_id)}
        else:
            output = {"ok": True, "schema": SCHEMA, "sources": list_sources(args.db)}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "schema": SCHEMA, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
