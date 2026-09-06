from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable


@runtime_checkable
class TransactionManager(Protocol):
    def __enter__(self) -> "TransactionManager":
        ...

    def __exit__(self, exc_type, exc, tb) -> bool | None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


class NoOpTransaction(AbstractContextManager["NoOpTransaction"]):
    def __enter__(self) -> "NoOpTransaction":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool | None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None
