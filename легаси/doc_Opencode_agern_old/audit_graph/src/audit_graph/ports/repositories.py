from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from audit_graph.application.transactions import TransactionManager
from audit_graph.domain.entities import Claim
from audit_graph.domain.events import DomainEvent
from audit_graph.domain.ids import ClaimId, TaskId


@runtime_checkable
class ClaimRepository(Protocol):
    def get(self, claim_id: ClaimId) -> Claim:
        ...

    def upsert(self, claim: Claim) -> None:
        ...

    def list_by_task(self, task_id: TaskId | str) -> Iterable[Claim]:
        ...


@runtime_checkable
class EventRepository(Protocol):
    def append(self, event: DomainEvent) -> None:
        ...

    def list_for_claim(self, claim_id: ClaimId) -> Iterable[DomainEvent]:
        ...


@runtime_checkable
class UnitOfWorkFactory(Protocol):
    def __call__(self) -> TransactionManager:
        ...
