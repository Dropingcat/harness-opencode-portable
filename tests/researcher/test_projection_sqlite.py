from __future__ import annotations

import unittest

from researcher_core.r0.commands import ActorRef, CommandEnvelope
from researcher_core.r0.ids import EntityId
from researcher_core.r0.registry import make_numeric_dry_run_batch
from researcher_core.r0.sqlite_store import rebuild_state_from_sqlite
from researcher_core.runtime import build_sqlite_runtime


class ProjectionSqliteTests(unittest.TestCase):
    def test_sqlite_projector_rebuilds_same_as_registry(self) -> None:
        runtime = build_sqlite_runtime(":memory:")
        run_id = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        opr_id = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        txn_id = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        actor = ActorRef(actor_type="test", actor_id="proj-test")
        cmd = CommandEnvelope(
            command_id=opr_id,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=run_id,
            actor=actor,
            idempotency_key="proj-test-1",
            expected_revisions={},
            causation_id=None,
            correlation_id=txn_id,
            payload={"proposal_batch": make_numeric_dry_run_batch(opr_id)},
        )
        runtime.command_handler.execute(cmd)  # type: ignore[attr-defined]
        # In-memory state
        mem_state = runtime.command_handler.state_snapshot()  # type: ignore[attr-defined]
        # SQLite rebuilt state
        conn = getattr(runtime.command_handler, "_sqlite_conn", None)
        assert conn is not None
        sqlite_state = rebuild_state_from_sqlite(conn)
        self.assertEqual(set(mem_state.keys()), set(sqlite_state.keys()))
        # Compare one entity type
        for key in mem_state:
            self.assertEqual(str(mem_state[key].meta.id), str(sqlite_state[key].meta.id))

    def test_sqlite_projector_empty_on_no_events(self) -> None:
        from researcher_core.r0.sqlite_store import open_sqlite

        conn = open_sqlite(":memory:")
        state = rebuild_state_from_sqlite(conn)
        self.assertEqual(state, {})


if __name__ == "__main__":
    unittest.main()
