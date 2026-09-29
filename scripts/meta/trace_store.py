# -*- coding: utf-8 -*-
"""
trace_store.py — V8 Trace & Provenance.

Детерминированный слой аудита: запись переходов состояния, экспериментов, ошибок.
Позволяет воспроизвести состояние S_t через replay дельт от S_0.

Контракты: TraceEntry, TransitionRecord, TraceStore.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TraceEntry:
    """Одна запись трассы (событие любой ветки V1-V8)."""

    __slots__ = ("entry_id", "timestamp", "source_branch", "event_type",
                 "payload", "related_state_version", "related_branch_id")

    def __init__(
        self,
        source_branch: str,
        event_type: str,
        payload: Dict[str, Any],
        related_state_version: Optional[str] = None,
        related_branch_id: Optional[str] = None,
    ) -> None:
        self.entry_id = str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
        self.source_branch = source_branch
        self.event_type = event_type
        self.payload = payload
        self.related_state_version = related_state_version
        self.related_branch_id = related_branch_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "source_branch": self.source_branch,
            "event_type": self.event_type,
            "payload": self.payload,
            "related_state_version": self.related_state_version,
            "related_branch_id": self.related_branch_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TraceEntry":
        e = cls(d["source_branch"], d["event_type"], d.get("payload", {}),
                d.get("related_state_version"), d.get("related_branch_id"))
        e.entry_id = d.get("entry_id", e.entry_id)
        e.timestamp = d.get("timestamp", e.timestamp)
        return e


class TransitionRecord:
    """Запись перехода S_t → S_{t+1} (для reconstruct_state)."""

    __slots__ = ("from_version", "to_version", "delta", "evidence",
                 "metrics_before", "metrics_after", "timestamp")

    def __init__(
        self,
        from_version: str,
        to_version: str,
        delta: Dict[str, Any],
        evidence: Optional[List[str]] = None,
        metrics_before: Optional[Dict[str, float]] = None,
        metrics_after: Optional[Dict[str, float]] = None,
    ) -> None:
        self.from_version = from_version
        self.to_version = to_version
        self.delta = delta
        self.evidence = evidence or []
        self.metrics_before = metrics_before or {}
        self.metrics_after = metrics_after or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "delta": self.delta,
            "evidence": self.evidence,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "timestamp": self.timestamp,
        }


def state_hash(snapshot: Dict[str, Any]) -> str:
    """SHA-256 подпись состояния (V8-TD-03)."""
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TraceStore:
    """Хранилище трасс + воспроизведение состояний.

    - append(entry): добавить событие.
    - record_transition(tr): зафиксировать переход S_t→S_{t+1}.
    - reconstruct_state(version_id): replay S_0 + Δ_1..Δ_n.
    - verify_transition(from_v, to_v): проверить S_{t-1}+Δ == S_t.
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else Path(__file__).parent / '_trace_store.json'
        self.entries: List[TraceEntry] = []
        self.transitions: List[TransitionRecord] = []
        self.state_snapshots: Dict[str, Any] = {}
        self._load()

    # --- снимки состояний (V8-TD-02 reconstruct_state) ---
    def save_snapshot(self, state: Any) -> None:
        """Сохранить снимок состояния (объект с version_id + to_dict)."""
        self.state_snapshots[state.version_id] = state.to_dict()
        self._save()

    def get_snapshot(self, version_id: str) -> Optional[Dict[str, Any]]:
        return self.state_snapshots.get(version_id)

    # --- запись ---
    def append(self, entry: TraceEntry) -> None:
        self.entries.append(entry)
        self._save()

    def record_transition(self, tr: TransitionRecord) -> None:
        self.transitions.append(tr)
        self.append(TraceEntry("V2", "state_transition", tr.to_dict(),
                               tr.from_version, None))

    # --- запросы ---
    def query_by_state(self, state_version: str) -> List[TraceEntry]:
        return [e for e in self.entries if e.related_state_version == state_version]

    def query_by_branch(self, branch_id: str) -> List[TraceEntry]:
        return [e for e in self.entries if e.related_branch_id == branch_id]

    # --- воспроизведение ---
    def reconstruct_state(self, initial_state: Optional[Dict[str, Any]] = None,
                          version_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Replay: S_0 + Δ_1 + ... + Δ_n = S_n.

        Если version_id есть в state_snapshots — вернуть его (быстрый путь).
        Иначе replay из initial_state через transitions.
        """
        if version_id and version_id in self.state_snapshots:
            return self.state_snapshots[version_id]
        if initial_state is None:
            # пытаемся найти начальное состояние из снимков
            if not self.state_snapshots:
                return None
            initial_state = min(self.state_snapshots.values(),
                                key=lambda s: s.get("timestamp", ""))
        state = json.loads(json.dumps(initial_state, ensure_ascii=False))
        for tr in sorted(self.transitions, key=lambda t: t.timestamp):
            if version_id and tr.to_version != version_id:
                continue
            state = self._apply_delta(state, tr.delta)
        return state

    def verify_transition(self, from_v: str, to_v: str,
                          initial_state: Dict[str, Any]) -> bool:
        """Проверка S_{t-1} + Δ == S_t."""
        s_before = self.reconstruct_state(initial_state, from_v)
        s_after = self.reconstruct_state(initial_state, to_v)
        tr = self._get_transition(from_v, to_v)
        if tr is None:
            return False
        expected = self._apply_delta(s_before, tr.delta)
        return expected == s_after

    # --- внутренние ---
    def _apply_delta(self, state: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        """Применение дельты: delta = {path: new_value}."""
        import copy
        s = copy.deepcopy(state)
        for path, new_val in delta.items():
            parts = path.split(".")
            node = s
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = new_val
        return s

    def _get_transition(self, from_v: str, to_v: str) -> Optional[TransitionRecord]:
        for tr in self.transitions:
            if tr.from_version == from_v and tr.to_version == to_v:
                return tr
        return None

    # --- персистентность ---
    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self.entries = [TraceEntry.from_dict(e) for e in data.get("entries", [])]
            self.transitions = [TransitionRecord(**t) for t in data.get("transitions", [])]
            self.state_snapshots = data.get("state_snapshots", {})
        except Exception:
            self.entries = []
            self.transitions = []
            self.state_snapshots = {}

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": [e.to_dict() for e in self.entries],
            "transitions": [t.to_dict() for t in self.transitions],
            "state_snapshots": self.state_snapshots,
        }
        self.storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # --- инструменты ---
    def export(self, out_path: str | Path) -> None:
        """Экспорт трассы для внешнего аудита (V8-TD-06)."""
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": [e.to_dict() for e in self.entries],
            "transitions": [t.to_dict() for t in self.transitions],
        }
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")