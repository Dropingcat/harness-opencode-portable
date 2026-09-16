"""Capsule and capability contracts.

Capsules are untrusted perimeter components. They can produce observations or
proposals, but they cannot mutate authoritative graph state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId


class SideEffectClass(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    IRREVERSIBLE_WRITE = "irreversible_write"


@dataclass(frozen=True, slots=True)
class CapsuleDescriptor:
    capsule_id: str
    version: str
    capabilities: tuple[str, ...]
    side_effect_class: SideEffectClass
    input_schema_version: str
    output_schema_version: str
    policy_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.capsule_id:
            raise ValueError("capsule_id is required")
        if not self.version:
            raise ValueError("version is required")
        if not self.capabilities:
            raise ValueError("at least one capability is required")
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise TypeError("side_effect_class must be SideEffectClass")
        if not self.input_schema_version or not self.output_schema_version:
            raise ValueError("input/output schema versions are required")
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "policy_keys", tuple(self.policy_keys))


@dataclass(frozen=True, slots=True)
class CapsuleRequest:
    request_id: EntityId
    run_id: EntityId
    capability: str
    actor: ActorRef
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.request_id.namespace != "OPR":
            raise ValueError("request_id must use OPR prefix")
        if self.run_id.namespace != "RUN":
            raise ValueError("run_id must use RUN prefix")
        if not self.capability:
            raise ValueError("capability is required")
        object.__setattr__(self, "payload", _deep_freeze(self.payload))


@dataclass(frozen=True, slots=True)
class CapsuleObservation:
    request_id: EntityId
    capsule_id: str
    capability: str
    output_schema_version: str
    payload: Mapping[str, Any]
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.request_id.namespace != "OPR":
            raise ValueError("request_id must use OPR prefix")
        if not self.capsule_id:
            raise ValueError("capsule_id is required")
        if not self.capability:
            raise ValueError("capability is required")
        if not self.output_schema_version:
            raise ValueError("output_schema_version is required")
        if not self.provenance:
            raise ValueError("provenance is required")
        object.__setattr__(self, "payload", _deep_freeze(self.payload))
        object.__setattr__(self, "provenance", _deep_freeze(self.provenance))


class Capsule(Protocol):
    descriptor: CapsuleDescriptor

    def run(self, request: CapsuleRequest) -> CapsuleObservation: ...


class InMemoryCapabilityRegistry:
    """Deterministic provider selection for bubble tests and early adapters."""

    def __init__(self) -> None:
        self._providers: dict[str, Capsule] = {}

    def register(self, capsule: Capsule) -> None:
        for capability in capsule.descriptor.capabilities:
            if capability in self._providers:
                raise ValueError(f"duplicate provider for capability: {capability}")
            self._providers[capability] = capsule

    def provider_for(self, capability: str) -> Capsule:
        try:
            return self._providers[capability]
        except KeyError as exc:
            raise LookupError(f"no provider for capability: {capability}") from exc

    def capabilities(self) -> Mapping[str, str]:
        return MappingProxyType({capability: provider.descriptor.capsule_id for capability, provider in self._providers.items()})


def assert_capsule_observation_is_untrusted(observation: CapsuleObservation) -> None:
    """Marker gate: capsule output is observation/proposal only, never state."""

    forbidden_keys = {"admitted", "authoritative", "commit", "state_write"}
    present = _find_forbidden_keys(observation.payload, forbidden_keys)
    if present:
        raise ValueError(f"capsule observation contains authority-like keys: {sorted(present)}")


def _find_forbidden_keys(value: object, forbidden_keys: set[str]) -> set[str]:
    if isinstance(value, Mapping):
        present = forbidden_keys.intersection(str(key) for key in value.keys())
        for nested in value.values():
            present.update(_find_forbidden_keys(nested, forbidden_keys))
        return present
    if isinstance(value, tuple | list):
        present: set[str] = set()
        for nested in value:
            present.update(_find_forbidden_keys(nested, forbidden_keys))
        return present
    return set()
