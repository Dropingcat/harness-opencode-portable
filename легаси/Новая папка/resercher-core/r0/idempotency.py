"""R0 idempotency record helpers for command replay bubble tests."""

from __future__ import annotations

from dataclasses import dataclass

from researcher_core.r0.commands import CommandEnvelope, CommandResult


@dataclass(frozen=True, slots=True)
class IdempotencyConflict(RuntimeError):
    idempotency_key: str

    def __str__(self) -> str:
        return f"idempotency key reused with a different request hash: {self.idempotency_key}"


class InMemoryIdempotencyStore:
    """Small deterministic stand-in for the future SQLite idempotency table."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, CommandResult]] = {}

    def replay_if_recorded(self, command: CommandEnvelope) -> CommandResult | None:
        request_hash = command.request_hash()
        existing = self._records.get(command.idempotency_key)
        if existing is None:
            return None
        existing_hash, existing_result = existing
        if existing_hash != request_hash:
            return None
        return CommandResult(
            command_id=existing_result.command_id,
            accepted_ids=existing_result.accepted_ids,
            event_ids=existing_result.event_ids,
            new_revisions=existing_result.new_revisions,
            replayed=True,
        )

    def record_or_replay(self, command: CommandEnvelope, result: CommandResult) -> CommandResult:
        request_hash = command.request_hash()
        existing = self._records.get(command.idempotency_key)
        if existing is None:
            self._records[command.idempotency_key] = (request_hash, result)
            return result
        existing_hash, existing_result = existing
        if existing_hash != request_hash:
            raise IdempotencyConflict(command.idempotency_key)
        return CommandResult(
            command_id=existing_result.command_id,
            accepted_ids=existing_result.accepted_ids,
            event_ids=existing_result.event_ids,
            new_revisions=existing_result.new_revisions,
            replayed=True,
        )
