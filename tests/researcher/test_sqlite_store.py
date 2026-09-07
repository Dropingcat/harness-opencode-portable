from __future__ import annotations

import unittest
from pathlib import Path

from datetime import datetime

from researcher_core.r0.events import EventEnvelope, ReasonCode
from researcher_core.r0.ids import EntityId
from researcher_core.r0.sqlite_store import SqliteUnitOfWork, open_sqlite
from researcher_core.r0.transactions import OutboxMessage

CREATED_AT = datetime.fromisoformat("2026-08-29T00:00:00+00:00")
RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")
EVENT_ID = EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6")
TXN_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")


def _make_event() -> EventEnvelope:
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
        payload={"claim": str(CLAIM_ID)},
    )


class SqliteStoreProdTests(unittest.TestCase):
    def test_commit_persists_state_and_events(self) -> None:
        conn = open_sqlite(":memory:")
        eid = CLAIM_ID
        event = _make_event()
        uow = SqliteUnitOfWork(conn)
        with uow:
            uow.put_state(eid, {"id": str(eid), "kind": "test"})
            uow.append_event(event)
            uow.enqueue_outbox(OutboxMessage(message_type="test", payload={"x": "1"}))
            uow.commit()
        self.assertIn(str(eid), uow.state_view())
        self.assertEqual(len(uow.events_view()), 1)
        self.assertEqual(len(uow.outbox_view()), 1)

    def test_rollback_discards_pending(self) -> None:
        conn = open_sqlite(":memory:")
        eid = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G7")
        uow = SqliteUnitOfWork(conn)
        with uow:
            uow.put_state(eid, {"id": str(eid)})
            uow.rollback()
        self.assertNotIn(str(eid), uow.state_view())
        self.assertEqual(len(uow.events_view()), 0)

    def test_reenter_fails_closed(self) -> None:
        conn = open_sqlite(":memory:")
        uow = SqliteUnitOfWork(conn)
        with uow:
            uow.commit()
        with self.assertRaises(Exception):
            with uow:
                pass  # debt-scan: ignore-line -- test re-enter must fail

    def test_exception_triggers_rollback(self) -> None:
        conn = open_sqlite(":memory:")
        eid = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G8")
        try:
            with SqliteUnitOfWork(conn) as uow:
                uow.put_state(eid, {"id": str(eid)})
                raise ValueError("boom")
        except ValueError:
            pass  # debt-scan: ignore-line -- expected test exception
        # new uow should see no state
        check = SqliteUnitOfWork(conn)
        self.assertNotIn(str(eid), check.state_view())


if __name__ == "__main__":
    unittest.main()
