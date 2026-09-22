"""Schema-backed policy loading for Researcher Core.

This is the production policy module. It parses ``config/research_policy.yaml``
with YAML, validates the full shape, and exposes an immutable ``Policy``
with a stable ``policy_hash``. The legacy ``BootstrapPolicy`` API is preserved
for debt-scanner compatibility but now delegates to the same schema.

Policy hash is computed from canonical JSON (sorted keys) of the loaded
mapping, ensuring artifact provenance without storing secrets.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml


_POLICY_HASH_PREFIX = "sha256:"  # debt-scan: ignore-line -- hash prefix, not heuristic
_REQUIRED_TOP_KEYS = ("schema_version", "policy_id", "policy_version", "reason_codes", "heuristics")
_REQUIRED_REASON_FIELDS = ("description", "owner", "tests")
_REQUIRED_HEURISTIC_FIELDS = (
    "value",
    "unit",
    "applies_to",
    "reason",
    "owner",
    "introduced_in",
    "review_after",
    "failure_if_wrong",
    "tests",
)


@dataclass(frozen=True, slots=True)
class BootstrapPolicy:
    debt_fail_on: str
    debt_excluded_files: frozenset[str]
    debt_excluded_dirs: frozenset[str]
    reason_codes: frozenset[str]


@dataclass(frozen=True, slots=True)
class ReasonCodeMeta:
    code: str
    description: str
    owner: str
    tests: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Heuristic:
    key: str
    value: tuple[Any, ...]
    unit: str
    applies_to: tuple[str, ...]
    reason: str
    owner: str
    introduced_in: str
    review_after: Mapping[str, Any]
    failure_if_wrong: tuple[str, ...]
    tests: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Policy:
    schema_version: str
    policy_id: str
    policy_version: str
    reason_codes: Mapping[str, ReasonCodeMeta]
    heuristics: Mapping[str, Heuristic]
    policy_hash: str
    source_path: Path

    @property
    def debt_fail_on(self) -> str:
        heuristic = self.heuristics.get("debt.scan.default_fail_on")
        if heuristic is None or not heuristic.value:
            raise KeyError("heuristic debt.scan.default_fail_on missing")
        first = heuristic.value[0]
        return str(first)

    @property
    def debt_excluded_files(self) -> frozenset[str]:
        heuristic = self.heuristics.get("debt.scan.excluded_files")
        if heuristic is None:
            return frozenset()
        return frozenset(str(item) for item in heuristic.value)

    @property
    def debt_excluded_dirs(self) -> frozenset[str]:
        heuristic = self.heuristics.get("debt.scan.excluded_dirs")
        if heuristic is None:
            return frozenset()
        return frozenset(str(item) for item in heuristic.value)


class PolicyConfigurationError(RuntimeError):
    """Raised when policy is missing or structurally invalid."""


def load_policy(root: Path) -> Policy:
    policy_path = root / "config" / "research_policy.yaml"
    if not policy_path.exists():
        raise PolicyConfigurationError(f"policy file not found: {policy_path}")
    text = policy_path.read_text(encoding="utf-8", errors="replace")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PolicyConfigurationError(f"policy YAML parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyConfigurationError("policy top-level must be a mapping")
    _validate_policy_dict(data)
    policy_hash = _compute_policy_hash(data)
    reason_codes = _parse_reason_codes(data["reason_codes"])
    heuristics = _parse_heuristics(data["heuristics"])
    return Policy(
        schema_version=str(data["schema_version"]),
        policy_id=str(data["policy_id"]),
        policy_version=str(data["policy_version"]),
        reason_codes=MappingProxyType(reason_codes),
        heuristics=MappingProxyType(heuristics),
        policy_hash=policy_hash,
        source_path=policy_path,
    )


def load_bootstrap_policy(root: Path) -> BootstrapPolicy:
    policy = load_policy(root)
    return BootstrapPolicy(
        debt_fail_on=policy.debt_fail_on,
        debt_excluded_files=policy.debt_excluded_files,
        debt_excluded_dirs=policy.debt_excluded_dirs,
        reason_codes=frozenset(policy.reason_codes.keys()),
    )


def lint_policy_text(text: str) -> None:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PolicyConfigurationError(f"policy YAML parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyConfigurationError("policy top-level must be a mapping")
    _validate_policy_dict(data)


def compute_policy_hash_for_text(text: str) -> str:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise PolicyConfigurationError("policy top-level must be a mapping")
    return _compute_policy_hash(data)


def _validate_policy_dict(data: dict[Any, Any]) -> None:
    for key in _REQUIRED_TOP_KEYS:
        if key not in data:
            raise PolicyConfigurationError(f"missing policy top-level key: {key}")
    if not isinstance(data["reason_codes"], dict) or not data["reason_codes"]:
        raise PolicyConfigurationError("policy reason_codes must be a non-empty mapping")
    if not isinstance(data["heuristics"], dict) or not data["heuristics"]:
        raise PolicyConfigurationError("policy heuristics must be a non-empty mapping")
    for code, meta in data["reason_codes"].items():
        if not isinstance(meta, dict):
            raise PolicyConfigurationError(f"reason code {code!r} must be a mapping")
        for field_name in _REQUIRED_REASON_FIELDS:
            if field_name not in meta:
                raise PolicyConfigurationError(f"reason code {code!r} missing field {field_name!r}")
        if not isinstance(meta["tests"], list) or not meta["tests"]:
            raise PolicyConfigurationError(f"reason code {code!r} tests must be a non-empty list")
    for key, heuristic in data["heuristics"].items():
        if not isinstance(heuristic, dict):
            raise PolicyConfigurationError(f"heuristic {key!r} must be a mapping")
        for field_name in _REQUIRED_HEURISTIC_FIELDS:
            if field_name not in heuristic:
                raise PolicyConfigurationError(f"heuristic {key!r} missing field {field_name!r}")
        if "value" not in heuristic or heuristic["value"] is None:
            raise PolicyConfigurationError(f"heuristic {key!r} value must be present")
        if not isinstance(heuristic["value"], list):
            raise PolicyConfigurationError(f"heuristic {key!r} value must be a list")
        for list_field in ("applies_to", "failure_if_wrong", "tests"):
            if not isinstance(heuristic[list_field], list):
                raise PolicyConfigurationError(f"heuristic {key!r} {list_field} must be a list")
        if not isinstance(heuristic["review_after"], dict):
            raise PolicyConfigurationError(f"heuristic {key!r} review_after must be a mapping")


def _parse_reason_codes(raw: dict[Any, Any]) -> dict[str, ReasonCodeMeta]:
    parsed: dict[str, ReasonCodeMeta] = {}
    for code, meta in raw.items():
        code_str = str(code)
        parsed[code_str] = ReasonCodeMeta(
            code=code_str,
            description=str(meta["description"]),
            owner=str(meta["owner"]),
            tests=tuple(str(item) for item in meta["tests"]),
        )
    return parsed


def _parse_heuristics(raw: dict[Any, Any]) -> dict[str, Heuristic]:
    parsed: dict[str, Heuristic] = {}
    for key, heuristic in raw.items():
        key_str = str(key)
        raw_value = heuristic["value"]
        value_tuple = tuple(raw_value) if isinstance(raw_value, list) else (raw_value,)
        parsed[key_str] = Heuristic(
            key=key_str,
            value=value_tuple,
            unit=str(heuristic["unit"]),
            applies_to=tuple(str(item) for item in heuristic["applies_to"]),
            reason=str(heuristic["reason"]),
            owner=str(heuristic["owner"]),
            introduced_in=str(heuristic["introduced_in"]),
            review_after=MappingProxyType(dict(heuristic["review_after"])),
            failure_if_wrong=tuple(str(item) for item in heuristic["failure_if_wrong"]),
            tests=tuple(str(item) for item in heuristic["tests"]),
        )
    return parsed


def _compute_policy_hash(data: dict[Any, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{_POLICY_HASH_PREFIX}{digest}"
