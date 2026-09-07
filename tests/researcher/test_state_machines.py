from __future__ import annotations

import unittest
from datetime import datetime

from researcher_core.policy import load_bootstrap_policy
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import Claim, EntityMeta
from researcher_core.r0.enums import ClaimStatus
from researcher_core.r0.events import ReasonCode, ReasonCodeRegistry
from researcher_core.r0.ids import EntityId
from researcher_core.r0.serialization import canonical_json
from researcher_core.r0.state_machines import InvalidTransition, RevisionConflict, TransitionRequest, transition_claim_status


CREATED_AT = datetime.fromisoformat("2026-08-29T00:00:00+00:00")
RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")
EVENT_ID = EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6")
TXN_ID = EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
SCOPE_ID = EntityId("QST_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="state-machine-bubble")


def make_claim(status: ClaimStatus = ClaimStatus.OPEN, revision: int = 1) -> Claim:
    return Claim(
        meta=EntityMeta(
            id=CLAIM_ID,
            schema_version="r0-entity/0.1",
            revision=revision,
            run_id=RUN_ID,
            created_at=CREATED_AT,
            created_by=ACTOR,
        ),
        proposition="Measured indicator increased by 12%.",
        normalized_proposition="measured indicator increased by 12%.",
        claim_type="quantitative",
        scope_id=SCOPE_ID,
        status=status,
    )


class StateMachineBubbleTests(unittest.TestCase):
    def test_valid_transition_updates_status_revision_and_event(self) -> None:
        registry = ReasonCodeRegistry(load_bootstrap_policy(Path.cwd()).reason_codes)

        result = transition_claim_status(
            make_claim(),
            TransitionRequest(
                target_id=CLAIM_ID,
                expected_revision=1,
                requested_status=ClaimStatus.SUPPORTED,
                reason_codes=(ReasonCode("CLAIM_EVIDENCE_UPDATED"),),
            ),
            actor=ACTOR,
            event_id=EVENT_ID,
            causation_id=TXN_ID,
            correlation_id=TXN_ID,
            timestamp=CREATED_AT,
            reason_registry=registry,
        )

        self.assertEqual(result.claim.status, ClaimStatus.SUPPORTED)
        self.assertEqual(result.claim.meta.revision, 2)  # debt-scan: ignore-line -- one transition increments revision by one.
        self.assertEqual(result.event.event_type, "CLAIM_STATUS_CHANGED")
        self.assertIn('"to_status":"supported"', canonical_json(result.event))

    def test_transition_requires_reason_codes(self) -> None:
        with self.assertRaises(ValueError):
            TransitionRequest(
                target_id=CLAIM_ID,
                expected_revision=1,
                requested_status=ClaimStatus.SUPPORTED,
                reason_codes=(),
            )

    def test_transition_rejects_revision_conflict(self) -> None:
        with self.assertRaises(RevisionConflict):
            transition_claim_status(
                make_claim(revision=2),  # debt-scan: ignore-line -- conflict fixture current revision.
                TransitionRequest(
                    target_id=CLAIM_ID,
                    expected_revision=1,
                    requested_status=ClaimStatus.SUPPORTED,
                    reason_codes=(ReasonCode("CLAIM_EVIDENCE_UPDATED"),),
                ),
                actor=ACTOR,
                event_id=EVENT_ID,
                causation_id=TXN_ID,
                correlation_id=TXN_ID,
                timestamp=CREATED_AT,
            )

    def test_transition_rejects_invalid_path(self) -> None:
        with self.assertRaises(InvalidTransition):
            transition_claim_status(
                make_claim(status=ClaimStatus.REJECTED),
                TransitionRequest(
                    target_id=CLAIM_ID,
                    expected_revision=1,
                    requested_status=ClaimStatus.SUPPORTED,
                    reason_codes=(ReasonCode("CLAIM_EVIDENCE_UPDATED"),),
                ),
                actor=ACTOR,
                event_id=EVENT_ID,
                causation_id=TXN_ID,
                correlation_id=TXN_ID,
                timestamp=CREATED_AT,
            )

    def test_transition_registry_rejects_unknown_reason(self) -> None:
        registry = ReasonCodeRegistry(load_bootstrap_policy(Path.cwd()).reason_codes)

        with self.assertRaises(ValueError):
            transition_claim_status(
                make_claim(),
                TransitionRequest(
                    target_id=CLAIM_ID,
                    expected_revision=1,
                    requested_status=ClaimStatus.SUPPORTED,
                    reason_codes=(ReasonCode("MADE_UP_REASON"),),
                ),
                actor=ACTOR,
                event_id=EVENT_ID,
                causation_id=TXN_ID,
                correlation_id=TXN_ID,
                timestamp=CREATED_AT,
                reason_registry=registry,
            )


from pathlib import Path


if __name__ == "__main__":
    unittest.main()
