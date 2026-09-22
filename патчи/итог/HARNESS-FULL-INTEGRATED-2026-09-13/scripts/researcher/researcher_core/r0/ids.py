"""Typed identifier helpers for R0."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*_[0-9A-HJKMNP-TV-Z]{26}$")
ALLOWED_PREFIXES = frozenset({"RUN", "QST", "CLP", "CLM", "QTY", "SRC", "EVD", "EDG", "SCP", "DRV", "ASM", "REC", "GAP", "CNF", "EVT", "TXN", "SNP", "OPR", "RRQ", "RCD", "RMP", "RDM", "DCS", "PIT", "RPT", "RTL", "RCH", "RRS", "KDP", "DIA", "RIT", "TEP", "DLG", "TER", "EAP", "EAR", "AIM", "SRP", "SLR", "RAP", "RAS", "UPR", "RWF", "IQC", "IQT", "ARG", "ARL", "AGP", "DDC", "ADC", "DQC", "RPB", "TEX", "PER"})
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LENGTH = 26  # debt-scan: ignore-line -- ULID wire format length, not policy heuristic.
_RANDOM_PART_LENGTH = 16  # debt-scan: ignore-line -- ULID randomness length, not policy heuristic.


class RandomSource(Protocol):
    def randrange(self, stop: int) -> int: ...


class Clock(Protocol):
    def now_ms(self) -> int: ...


@dataclass(frozen=True, slots=True)
class EntityIdFactory:
    """Injectable ID factory port implementation for runtime wiring."""

    clock: Clock
    random_source: RandomSource

    def new(self, prefix: str) -> "EntityId":
        return EntityId.new(prefix, self.clock, self.random_source)


@dataclass(frozen=True, slots=True)
class EntityId:
    """Immutable R0 entity id, e.g. ``CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6``."""

    value: str

    def __post_init__(self) -> None:
        if not _ID_RE.match(self.value):
            raise ValueError(f"invalid entity id: {self.value!r}")
        if self.namespace not in ALLOWED_PREFIXES:
            raise ValueError(f"unsupported entity id prefix: {self.namespace!r}")

    @property
    def namespace(self) -> str:
        return self.value.split("_", maxsplit=1)[0]

    @classmethod
    def new(cls, prefix: str, clock: Clock, random_source: RandomSource) -> "EntityId":
        """Create a deterministic-testable ULID-like id from injected time/random."""

        if not re.match(r"^[A-Z][A-Z0-9]*$", prefix):
            raise ValueError(f"invalid id prefix: {prefix!r}")
        if prefix not in ALLOWED_PREFIXES:
            raise ValueError(f"unsupported id prefix: {prefix!r}")
        now_ms = getattr(clock, "now_ms", None)
        if not callable(now_ms):
            raise TypeError("clock must provide now_ms()")
        timestamp_ms = now_ms()
        if timestamp_ms < 0:
            raise ValueError("timestamp_ms must be non-negative")

        encoded_time = _encode_base32(timestamp_ms).rjust(_ULID_LENGTH - _RANDOM_PART_LENGTH, "0")
        encoded_random = "".join(_ALPHABET[random_source.randrange(len(_ALPHABET))] for _ in range(_RANDOM_PART_LENGTH))
        return cls(f"{prefix}_{encoded_time}{encoded_random}")

    def __str__(self) -> str:
        return self.value


def _encode_base32(value: int) -> str:
    if value == 0:
        return "0"
    chars: list[str] = []
    base = len(_ALPHABET)
    while value:
        value, remainder = divmod(value, base)
        chars.append(_ALPHABET[remainder])
    return "".join(reversed(chars))
