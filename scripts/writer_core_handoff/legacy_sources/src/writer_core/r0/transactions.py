"""In-memory and SQLite UnitOfWork for writer-core R0.

Follows the same pattern as researcher_core.r0.transactions.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from writer_core.r0.events import EventEnvelope, _deep_freeze
from writer_core.r0.ids import EntityId


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    message_type: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.message_type:
            raise ValueError("message_type is required")
        object.__setattr__(self, "payload", _deep_freeze(self.payload))


class UnitOfWorkStateError(RuntimeError):
    """Raised when a transaction operation is used outside its lifecycle."""


class InMemoryUnitOfWork:
    """Atomic in-memory stand-in for SQLite-backed UnitOfWork."""

    def __init__(self) -> None:
        self.state: dict[EntityId, Mapping[str, Any]] = {}
        self.events: list = []
        self.outbox: list = []
        self.rejections: list = []
        self._active = False
        self._closed = False
        self._pending_state: dict = {}
        self._pending_events: list = []
        self._pending_outbox: list = []
        self._pending_rejections: list = []

    def __enter__(self) -> "InMemoryUnitOfWork":
        if self._active or self._closed:
            raise UnitOfWorkStateError("unit of work cannot be re-entered")
        self._active = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is not None:
            self.rollback()
            return False
        if self._active:
            self.rollback()
        return False

    def put_state(self, entity_id, row) -> None:
        self._require_active()
        self._pending_state[entity_id] = _deep_freeze(row)

    def append_event(self, event) -> None:
        self._require_active()
        self._pending_events.append(event)

    def enqueue_outbox(self, message) -> None:
        self._require_active()
        self._pending_outbox.append(message)

    def put_rejection(self, command_id, report) -> None:
        self._require_active()
        self._pending_rejections.append((command_id, report))

    def commit(self) -> None:
        self._require_active()
        self.state.update(self._pending_state)
        self.events.extend(self._pending_events)
        self.outbox.extend(self._pending_outbox)
        self.rejections.extend(self._pending_rejections)
        self._finish()

    def rollback(self) -> None:
        self._require_active()
        self._finish()

    def state_view(self):
        from types import MappingProxyType
        return MappingProxyType(self.state)

    def _finish(self) -> None:
        self._pending_state = {}
        self._pending_events = []
        self._pending_outbox = []
        self._pending_rejections = []
        self._active = False
        self._closed = True

    def _require_active(self) -> None:
        if not self._active:
            raise UnitOfWorkStateError("unit of work is not active")


def _to_jsonable(value):
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "namespace"):  # EntityId
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "meta"):
        try:
            meta = getattr(value, "meta")
            meta_id = getattr(meta, "id", None)
            return {"_type": type(value).__name__, "_id": str(meta_id) if meta_id else str(value)}
        except Exception:
            return str(value)
    try:
        import json
        json.dumps(value)
        return value
    except Exception:
        return str(value)


_SCHEMA_STATEMENTS = (
    "CREATE TABLE IF NOT EXISTS state (entity_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS outbox (message_id TEXT PRIMARY KEY, message_type TEXT NOT NULL, payload TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS rejections (id TEXT PRIMARY KEY, data TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS snapshots (snapshot_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
)


def init_sqlite_schema(conn) -> None:
    for stmt in [
        "CREATE TABLE IF NOT EXISTS state (entity_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS outbox (message_id TEXT PRIMARY KEY, message_type TEXT NOT NULL, payload TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS rejections (id TEXT PRIMARY KEY, data TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS snapshots (snapshot_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
    ]:
        conn.execute(stmt)
    conn.commit()


class SqliteUnitOfWork:
    """Prod SQLite implementation of UnitOfWorkPort."""

    def __init__(self, conn) -> None:
        self._conn = conn
        self._active = False
        self._closed = False
        self._conn.row_factory = sqlite3.Row
        for stmt in [
            "CREATE TABLE IF NOT EXISTS state (entity_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS outbox (message_id TEXT PRIMARY KEY, message_type TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS rejections (id TEXT PRIMARY KEY, data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS snapshots (snapshot_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
        ]:
            conn.execute(stmt)
        conn.commit()

    def __enter__(self):
        if self._active or self._closed:
            raise Exception("unit of work cannot be re-entered")
        self._active = True
        self._conn.execute("BEGIN")
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is not None:
            self.rollback()
            return False
        if self._active:
            self.rollback()
        return False

    def put_state(self, entity_id, row) -> None:
        self._require_active()
        jsonable = _to_jsonable(dict(row))
        data = json.dumps(jsonable, ensure_ascii=False, sort_keys=True)
        self._conn.execute(
            "INSERT OR REPLACE INTO state(entity_id, data) VALUES (?, ?)",
            (str(entity_id), data),
        )

    def append_event(self, event) -> None:
        self._require_active()
        payload = {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "aggregate_id": str(event.aggregate_id),
            "aggregate_revision": event.aggregate_revision,
            "run_id": str(event.run_id),
            "actor": event.actor,
            "timestamp": event.timestamp.isoformat(),
            "causation_id": str(event.causation_id),
            "correlation_id": str(event.correlation_id),
            "schema_version": event.schema_version,
            "reason_codes": [str(rc) for rc in event.reason_codes],
            "payload": _to_jsonable(dict(event.payload)),
        }
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self._conn.execute("INSERT INTO events(data) VALUES (?)", (data,))

    def put_rejection(self, command_id, report) -> None:
        self._require_active()
        try:
            issues = [
                {"code": str(issue.code), "message": str(issue.message)}
                for issue in getattr(report, "issues", [])
            ]
        except Exception:
            issues = [{"message": str(report)}]
        data = json.dumps(
            {"command_id": str(command_id), "issues": issues},
            ensure_ascii=False,
            sort_keys=True,
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO rejections(id, data) VALUES (?, ?)",
            (str(command_id), data),
        )

    def enqueue_outbox(self, message) -> None:
        self._require_active()
        payload = json.dumps(message.payload, ensure_ascii=False, sort_keys=True)
        message_id = f"{message.message_type}:{hash(payload) & 0x7FFFFFFF}"
        self._conn.execute(
            "INSERT OR REPLACE INTO outbox(message_id, message_type, payload) VALUES (?, ?, ?)",
            (message_id, message.message_type, payload),
        )

    def commit(self) -> None:
        self._require_active()
        self._conn.commit()
        self._finish()

    def rollback(self) -> None:
        self._require_active()
        self._conn.rollback()
        self._finish()

    def state_view(self):
        from types import MappingProxyType
        rows = self._conn.execute("SELECT entity_id, data FROM state").fetchall()
        result = {}
        for row in rows:
            result[row["entity_id"]] = json.loads(row["data"])
        return MappingProxyType(result)

    def events_view(self):
        rows = self._conn.execute("SELECT data FROM events ORDER BY seq").fetchall()
        return [json.loads(r["data"]) for r in rows]

    def outbox_view(self):
        rows = self._conn.execute("SELECT message_type, payload FROM outbox").fetchall()
        return [{"message_type": r["message_type"], "payload": json.loads(r["payload"])} for r in rows]

    def snapshots_view(self):
        rows = self._conn.execute("SELECT data FROM snapshots ORDER BY rowid").fetchall()
        return [json.loads(r["data"]) for r in rows]

    def _finish(self) -> None:
        self._active = False
        self._closed = True

    def _require_active(self) -> None:
        if not self._active:
            raise Exception("unit of work is not active")


class SqliteIdempotencyStore:
    """SQLite-backed idempotency store."""

    def __init__(self, conn) -> None:
        self._conn = conn
        for stmt in [
            "CREATE TABLE IF NOT EXISTS state (entity_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS outbox (message_id TEXT PRIMARY KEY, message_type TEXT NOT NULL, payload TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS rejections (id TEXT PRIMARY KEY, data TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS snapshots (snapshot_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
        ]:
            conn.execute(stmt)
        conn.commit()

    def replay_if_recorded(self, command):
        key = getattr(command, "idempotency_key", None)
        if not key:
            return None
        request_hash = command.request_hash()
        row = self._conn.execute(
            "SELECT request_hash, result FROM idempotency WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            return None
        return json.loads(row["result"])

    def record_or_replay(self, command, result):
        key = getattr(command, "idempotency_key", None)
        if not key:
            return result
        request_hash = command.request_hash()
        row = self._conn.execute(
            "SELECT request_hash, result FROM idempotency WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO idempotency(key, request_hash, result) VALUES (?, ?, ?)",
                (key, request_hash, json.dumps(result, ensure_ascii=False)),
            )
            self._conn.commit()
            return result
        if row["request_hash"] != request_hash:
            raise RuntimeError(f"idempotency conflict for key: {key}")
        return json.loads(row["result"])


def open_sqlite(path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    for stmt in [
        "CREATE TABLE IF NOT EXISTS state (entity_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS outbox (message_id TEXT PRIMARY KEY, message_type TEXT NOT NULL, payload TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS rejections (id TEXT PRIMARY KEY, data TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS snapshots (snapshot_id TEXT PRIMARY KEY, data TEXT NOT NULL)",
    ]:
        conn.execute(stmt)
    conn.commit()
    return conn