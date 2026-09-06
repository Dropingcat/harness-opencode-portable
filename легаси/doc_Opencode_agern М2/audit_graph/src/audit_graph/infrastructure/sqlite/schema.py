from __future__ import annotations

import sqlite3


CLAIMS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL
)
""".strip()


EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
)
""".strip()


def install_schema(connection: sqlite3.Connection) -> None:
    connection.execute(CLAIMS_TABLE_SQL)
    connection.execute(EVENTS_TABLE_SQL)
    connection.commit()
