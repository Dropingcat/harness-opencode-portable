"""Deterministic JSON serialization for R0 contract values."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from researcher_core.r0.events import ReasonCode
from researcher_core.r0.ids import EntityId


def canonical_json(obj: Any) -> str:
    """Return stable compact JSON for dataclasses, enums, ids, and datetimes."""

    return json.dumps(
        _to_jsonable(obj),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, EntityId | ReasonCode):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return obj.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(obj, Decimal):
        return str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {field.name: _to_jsonable(getattr(obj, field.name)) for field in fields(obj) if field.repr}
    if isinstance(obj, MappingProxyType):
        return _jsonable_mapping(obj)
    if isinstance(obj, dict):
        return _jsonable_mapping(obj)
    if isinstance(obj, tuple | list):
        return [_to_jsonable(value) for value in obj]
    return obj


def _jsonable_mapping(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in obj.items():
        if not isinstance(key, str):
            raise TypeError("canonical JSON mapping keys must be strings")
        if key in result:
            raise ValueError(f"duplicate mapping key after normalization: {key!r}")
        result[key] = _to_jsonable(value)
    return result
