# -*- coding: utf-8 -*-
"""
damage_basket.py — КОРЗИНА УРОНА (скрипт-счётчик).

Аудитор НЕ считает урон сам. Он бросает техдолги в корзину (файл).
Скрипт (этот модуль) читает корзину, начисляет урон (severity -> очки),
и при достижении ПОРОГА (по умолчанию 100) вызывает скрипт сна.

Изоляция: корзина — единственный канал между аудитором и остальными.
Оркестратор/аудитор не имеют общего контекста; только файл корзины.
"""
from __future__ import annotations

import json
import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .durable_json import StoreCorruption, read_json, update_json, storage_identity
except ImportError:
    from durable_json import StoreCorruption, read_json, update_json, storage_identity

_DEFAULT_BASKET = Path(os.environ.get(
    'HARNESS_DAMAGE_BASKET', str(Path(__file__).parent.parent.parent / '.damage_basket')))


class DamageEntry:
    """Запись урона в корзине."""

    __slots__ = ("entry_id", "rule_id", "engine", "severity", "message",
                 "target", "damage_points", "timestamp", "auditor_id")

    def __init__(self, rule_id: str, engine: str, severity: str, message: str,
                 target: str = "", auditor_id: str = "external") -> None:
        self.entry_id = str(uuid.uuid4())[:8]
        self.rule_id = rule_id
        self.engine = engine
        self.severity = severity
        self.message = message
        self.target = target
        # CRITICAL = 25, WARNING = 5, LOW = 1 (настраиваемо)
        self.damage_points = {"CRITICAL": 25, "WARNING": 5, "LOW": 1}.get(severity, 1)
        self.timestamp = datetime.now().isoformat()
        self.auditor_id = auditor_id

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}

    @classmethod
    def from_dict(cls, data):
        """Restore an event, never generate replacement identity or score."""
        if not isinstance(data, dict) or set(data) != set(cls.__slots__):
            raise StoreCorruption('invalid damage entry fields')
        for key in cls.__slots__:
            if key != 'damage_points' and not isinstance(data[key], str):
                raise StoreCorruption(f'invalid entry {key}')
        if not data['entry_id'] or not data['timestamp']:
            raise StoreCorruption('missing entry identity/time')
        try:
            datetime.fromisoformat(data['timestamp'])
        except ValueError as exc:
            raise StoreCorruption('invalid entry timestamp') from exc
        expected = {'CRITICAL': 25, 'WARNING': 5, 'LOW': 1}.get(data['severity'], 1)
        if type(data['damage_points']) is not int or data['damage_points'] != expected:
            raise StoreCorruption('invalid stored damage score')
        entry = cls.__new__(cls)
        for key in cls.__slots__:
            setattr(entry, key, data[key])
        return entry


class BasketConflict(ValueError):
    """Event collision or invalid/conflicting captured view; nothing committed."""


def _threshold(value):
    if type(value) is not int or value <= 0:
        raise StoreCorruption('threshold must be a positive integer')


def _records(records):
    if not isinstance(records, list):
        raise StoreCorruption('entries must be a list')
    result = {}
    for record in records:
        entry = DamageEntry.from_dict(record)
        if entry.entry_id in result:
            raise StoreCorruption('duplicate entry ID')
        result[entry.entry_id] = record
    return result


def _validate(data):
    if not isinstance(data, dict):
        raise StoreCorruption('basket must be an object')
    versioned = 'schema_version' in data
    allowed = {'threshold', 'entries', 'saved_at'}
    if versioned:
        allowed |= {'schema_version', 'acknowledged'}
        if type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise StoreCorruption('unsupported basket version')
        if 'acknowledged' not in data:
            raise StoreCorruption('missing acknowledgement history')
    if set(data) - allowed or not {'threshold', 'entries'} <= set(data):
        raise StoreCorruption('invalid basket fields')
    if 'saved_at' in data and not isinstance(data['saved_at'], str):
        raise StoreCorruption('invalid saved_at')
    _threshold(data['threshold'])
    active = _records(data['entries'])
    history = data.get('acknowledged', [])
    if not isinstance(history, list):
        raise StoreCorruption('invalid acknowledgement history')
    seen = set(active)
    for item in history:
        if not isinstance(item, dict) or set(item) != {'entry', 'snapshot_hash'}:
            raise StoreCorruption('invalid acknowledgement record')
        entry = DamageEntry.from_dict(item['entry'])
        digest = item['snapshot_hash']
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise StoreCorruption('invalid snapshot reference')
        if entry.entry_id in seen:
            raise StoreCorruption('duplicate active/history ID')
        seen.add(entry.entry_id)


def _hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


class DamageBasket:
    """Корзина урона: аудитор бросает долги, скрипт считает урон."""

    def __init__(self, basket_dir: Optional[str] = None,
                 threshold: int = 100) -> None:
        self.dir = Path(basket_dir) if basket_dir else _DEFAULT_BASKET
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / 'basket.json'
        _threshold(threshold)
        self._initial_threshold = threshold
        self.lock_timeout = 5.0
        self._load()

    def _default(self):
        return {'threshold': self._initial_threshold, 'entries': []}

    def _load(self):
        self._state = read_json(self.file, self._default, _validate)
        return self._state

    @property
    def threshold(self):
        return self._load()['threshold']

    @property
    def entries(self):
        return [DamageEntry.from_dict(e) for e in self._load()['entries']]

    def _update(self, mutate):
        def apply(data):
            mutate(data)
            data['schema_version'] = 1
            data.setdefault('acknowledged', [])
            data['saved_at'] = datetime.now().isoformat()
        committed = update_json(self.file, self._default, _validate, apply,
                                timeout=self.lock_timeout)
        self._state = committed
        return sum(e['damage_points'] for e in committed['entries'])

    # ------------------------------------------------------ для аудитора
    def drop(self, entry: DamageEntry) -> int:
        """Аудитор бросает долг в корзину. Возвращает текущий суммарный урон."""
        return self.drop_many([entry])

    def drop_many(self, entries: List[DamageEntry]) -> int:
        records = [DamageEntry.from_dict(e.to_dict()).to_dict() for e in entries]
        def mutate(data):
            known = {e['entry_id']: e for e in data['entries']}
            known.update({h['entry']['entry_id']: h['entry'] for h in data.get('acknowledged', [])})
            for record in records:
                identity = record['entry_id']
                if identity in known:
                    if known[identity] != record:
                        raise BasketConflict(f'event payload collision: {identity}')
                else:
                    data['entries'].append(record)
                    known[identity] = record
        return self._update(mutate)

    # ------------------------------------------------------ для скрипта
    def total_damage(self) -> int:
        """Суммарный урон по всем записям."""
        return sum(e.damage_points for e in self.entries)

    def recent_damage(self, n: int = 10) -> List[DamageEntry]:
        return self.entries[-n:]

    def should_trigger_sleep(self) -> bool:
        """Урон достиг порога → вызвать скрипт сна."""
        capture = self.snapshot()
        return capture['total_damage'] >= capture['threshold']

    def trigger_sleep(self, orchestrator: str) -> Dict[str, Any]:
        """При достижении порога: формирует триггер сна (для SleepController)."""
        capture = self.snapshot()
        return {
            'trigger': 'DAMAGE_THRESHOLD',
            'orchestrator': orchestrator,
            'total_damage': capture['total_damage'],
            'threshold': capture['threshold'],
            'entries': capture['entries'],
            'triggered_at': datetime.now().isoformat(),
        }

    def cluster_by_rule(self) -> Dict[str, List[DamageEntry]]:
        """Группировка долгов по rule_id (для кластеризации при сне)."""
        clusters: Dict[str, List[DamageEntry]] = {}
        for e in self.entries:
            clusters.setdefault(e.rule_id, []).append(e)
        return clusters

    def snapshot(self):
        """One atomic-file view; hash binds contents, not repair authorization."""
        identity = os.path.normcase(str(storage_identity(self.file)))
        data = self._load()
        capture = {'snapshot_version': 1, 'storage_identity': identity,
                   'threshold': data['threshold'], 'entries': data['entries'],
                   'total_damage': sum(e['damage_points'] for e in data['entries'])}
        capture['hash'] = _hash(capture)
        return json.loads(json.dumps(capture, ensure_ascii=False))

    def _parse_capture(self, snapshot):
        """Shared capture shape, binding and integrity checks; independent copy."""
        try:
            capture = json.loads(json.dumps(snapshot, allow_nan=False))
            if not isinstance(capture, dict) or set(capture) != {
                    'snapshot_version', 'storage_identity', 'threshold', 'entries', 'total_damage', 'hash'}:
                raise ValueError('invalid snapshot fields')
            digest = capture.pop('hash')
            if type(capture['snapshot_version']) is not int or capture['snapshot_version'] != 1:
                raise ValueError('unsupported snapshot version')
            if capture['storage_identity'] != os.path.normcase(str(storage_identity(self.file))):
                raise ValueError('foreign snapshot')
            _threshold(capture['threshold'])
            captured = _records(capture['entries'])
            if type(capture['total_damage']) is not int or capture['total_damage'] != sum(e['damage_points'] for e in captured.values()):
                raise ValueError('invalid snapshot damage')
            if digest != _hash(capture):
                raise ValueError('snapshot hash mismatch')
        except (ValueError, TypeError, KeyError) as exc:
            raise BasketConflict(f'invalid capture: {exc}') from exc
        return capture, digest, captured

    @staticmethod
    def _check_captured(data, captured):
        active = {e['entry_id']: e for e in data['entries']}
        history = {h['entry']['entry_id']: h['entry'] for h in data.get('acknowledged', [])}
        for identity, record in captured.items():
            if active.get(identity, history.get(identity)) != record:
                raise BasketConflict(f'captured event missing or changed: {identity}')
        return active

    def validate_snapshot(self, snapshot):
        """Nonmutating current-view check, NOT future execution authorization.

        New IDs are allowed. No lease spans external execution; acknowledge
        must recheck against its own locked view before deleting anything.
        """
        capture, digest, captured = self._parse_capture(snapshot)
        self._check_captured(self._load(), captured)
        return dict(capture, hash=digest)

    def acknowledge(self, snapshot):
        """All-or-nothing removal of unchanged captured events, retaining evidence."""
        _, digest, captured = self._parse_capture(snapshot)

        def mutate(data):
            active = self._check_captured(data, captured)
            evidence = data.setdefault('acknowledged', [])
            for identity, record in captured.items():
                if identity in active:
                    evidence.append({'entry': record, 'snapshot_hash': digest})
            data['entries'] = [e for e in data['entries'] if e['entry_id'] not in captured]
        return self._update(mutate)

    def reset(self, snapshot=None):
        if snapshot is None:
            raise BasketConflict('reset requires an explicit captured snapshot')
        return self.acknowledge(snapshot)
