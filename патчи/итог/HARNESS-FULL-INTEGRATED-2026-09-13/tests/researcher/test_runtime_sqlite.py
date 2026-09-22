from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from researcher_core.r0.commands import ActorRef, CommandEnvelope
from researcher_core.r0.ids import EntityId
from researcher_core.r0.registry import make_numeric_dry_run_batch
from researcher_core.runtime import build_in_memory_runtime, build_sqlite_runtime
from researcher_core.artifact import check_artifact_text


class RuntimeSqliteWiringTests(unittest.TestCase):
    def test_sqlite_runtime_admits_and_renders(self) -> None:
        runtime = build_sqlite_runtime(":memory:")
        run_id = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        opr_id = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        txn_id = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        actor = ActorRef(actor_type="test", actor_id="runtime-sqlite")
        cmd = CommandEnvelope(
            command_id=opr_id,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=run_id,
            actor=actor,
            idempotency_key="runtime-sqlite-1",
            expected_revisions={},
            causation_id=None,
            correlation_id=txn_id,
            payload={"proposal_batch": make_numeric_dry_run_batch(opr_id)},
        )
        result = runtime.command_handler.execute(cmd)
        self.assertTrue(result.accepted_ids)
        # build artifact via sqlite runtime builder
        from researcher_core.r0.projections import Snapshot

        # Use in-memory state via handler's state_snapshot
        state = runtime.command_handler.state_snapshot()  # type: ignore[attr-defined]
        snapshot = runtime.command_handler.snapshots[-1]  # type: ignore[attr-defined]
        artifact = runtime.artifact_builder.build(snapshot, state, "sqlite run")
        rendered = runtime.artifact_builder.render(artifact)
        self.assertEqual(check_artifact_text(rendered), [])
        projected = runtime.event_projector.rebuild_state(())
        self.assertEqual(set(projected.keys()), set(state.keys()))

    def test_sqlite_idempotency_replay_via_db(self) -> None:
        runtime = build_sqlite_runtime(":memory:")
        run_id = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        opr_id = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        txn_id = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        actor = ActorRef(actor_type="test", actor_id="runtime-sqlite-idem")
        batch = make_numeric_dry_run_batch(opr_id)
        cmd = CommandEnvelope(
            command_id=opr_id,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=run_id,
            actor=actor,
            idempotency_key="runtime-sqlite-idem-1",
            expected_revisions={},
            causation_id=None,
            correlation_id=txn_id,
            payload={"proposal_batch": batch},
        )
        first = runtime.command_handler.execute(cmd)
        second = runtime.command_handler.execute(cmd)
        self.assertTrue(first.accepted_ids)
        self.assertTrue(second.replayed)
        self.assertEqual(first.accepted_ids, second.accepted_ids)

    def test_sqlite_runtime_persists_across_file(self) -> None:
        db_path = Path("C:\\Temp\\opencode\\test_sqlite_runtime.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # clean previous
        for suffix in ("", "-wal", "-shm"):
            try:
                (Path(str(db_path) + suffix) if suffix else db_path).unlink(missing_ok=True)
            except Exception:
                pass  # debt-scan: ignore-line -- best-effort clean
        runtime = build_sqlite_runtime(db_path)
        run_id = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        opr_id = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        txn_id = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        actor = ActorRef(actor_type="test", actor_id="runtime-sqlite-file")
        cmd = CommandEnvelope(
            command_id=opr_id,
            command_type="ADMIT_PROPOSAL_BATCH",
            run_id=run_id,
            actor=actor,
            idempotency_key="runtime-sqlite-file-1",
            expected_revisions={},
            causation_id=None,
            correlation_id=txn_id,
            payload={"proposal_batch": make_numeric_dry_run_batch(opr_id)},
        )
        runtime.command_handler.execute(cmd)
        self.assertTrue(db_path.exists())
        self.assertGreater(db_path.stat().st_size, 0)
        conn = getattr(runtime.command_handler, "_sqlite_conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass  # debt-scan: ignore-line -- best-effort close
        for suffix in ("", "-wal", "-shm"):
            try:
                (Path(str(db_path) + suffix) if suffix else db_path).unlink(missing_ok=True)
            except Exception:
                pass  # debt-scan: ignore-line -- best-effort clean


if __name__ == "__main__":
    unittest.main()
