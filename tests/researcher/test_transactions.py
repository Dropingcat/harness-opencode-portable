from __future__ import annotations

import unittest
from datetime import datetime

from researcher_core.r0.events import EventEnvelope, ReasonCode
from researcher_core.r0.ids import EntityId
from researcher_core.r0.transactions import InMemoryUnitOfWork, OutboxMessage, UnitOfWorkStateError


CREATED_AT = datetime.fromisoformat("2026-08-29T00:00:00+00:00")
RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")
EVENT_ID = EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6")
TXN_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")


def make_event() -> EventEnvelope:
    return EventEnvelope(
        event_id=EVENT_ID,
        event_type="CLAIM_ADMITTED",
        aggregate_id=CLAIM_ID,
        aggregate_revision=1,
        run_id=RUN_ID,
        actor="registry",
        timestamp=CREATED_AT,
        causation_id=TXN_ID,
        correlation_id=TXN_ID,
        schema_version="r0-event/0.1",
        reason_codes=(ReasonCode("CLAIM_EVIDENCE_UPDATED"),),
        payload={"claim": CLAIM_ID},
    )


class TransactionBubbleTests(unittest.TestCase):
    def test_commit_makes_state_events_and_outbox_visible_atomically(self) -> None:
        uow = InMemoryUnitOfWork()

        with uow:
            uow.put_state(CLAIM_ID, {"status": "open"})
            uow.append_event(make_event())
            uow.enqueue_outbox(OutboxMessage("projector.update", {"claim": CLAIM_ID}))
            uow.commit()

        self.assertEqual(uow.state[CLAIM_ID]["status"], "open")
        self.assertEqual(len(uow.events), 1)
        self.assertEqual(len(uow.outbox), 1)

    def test_exception_rolls_back_all_pending_writes(self) -> None:
        uow = InMemoryUnitOfWork()

        with self.assertRaises(RuntimeError):
            with uow:
                uow.put_state(CLAIM_ID, {"status": "open"})
                uow.append_event(make_event())
                raise RuntimeError("injected crash")

        self.assertEqual(uow.state, {})
        self.assertEqual(uow.events, [])
        self.assertEqual(uow.outbox, [])

    def test_context_exit_without_commit_rolls_back(self) -> None:
        uow = InMemoryUnitOfWork()

        with uow:
            uow.put_state(CLAIM_ID, {"status": "open"})

        self.assertEqual(uow.state, {})

    def test_writes_outside_active_transaction_are_rejected(self) -> None:
        uow = InMemoryUnitOfWork()

        with self.assertRaises(UnitOfWorkStateError):
            uow.put_state(CLAIM_ID, {"status": "open"})


if __name__ == "__main__":
    unittest.main()
