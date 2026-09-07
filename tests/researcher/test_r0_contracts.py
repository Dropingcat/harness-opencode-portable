from __future__ import annotations

import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from researcher_core.r0.enums import AdmissionStatus, ClaimKind, ClaimStatus, CommitPolicy, ValidationOutcome
from researcher_core.policy import load_bootstrap_policy
from researcher_core.r0.events import EventEnvelope, ReasonCode, ReasonCodeRegistry
from researcher_core.r0.ids import EntityId
from researcher_core.r0.serialization import canonical_json


CREATED_AT = datetime.fromisoformat("2026-08-29T00:00:00+00:00")


class R0ContractTests(unittest.TestCase):
    def test_unknown_enum_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ClaimKind("unknown")

    def test_r0_documented_enums_are_present(self) -> None:
        self.assertEqual(ClaimStatus.OPEN.value, "open")
        self.assertEqual(AdmissionStatus.CANDIDATE.value, "candidate")
        self.assertEqual(AdmissionStatus.NEEDS_REVIEW.value, "needs_review")
        self.assertEqual(ValidationOutcome.WARN.value, "warn")
        self.assertEqual(CommitPolicy.ALL_OR_NOTHING.value, "all_or_nothing")

    def test_unknown_reason_code_rejected(self) -> None:
        registry = ReasonCodeRegistry(load_bootstrap_policy(Path.cwd()).reason_codes)

        with self.assertRaises(ValueError):
            registry.validate(ReasonCode("MADE_UP_REASON"))

        registry.validate(ReasonCode("CLAIM_EVIDENCE_UPDATED"))

    def test_event_rejects_unknown_type(self) -> None:
        with self.assertRaises(ValueError):
            EventEnvelope(
                event_id=EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                event_type="TYPO_EVENT",
                aggregate_id=EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                aggregate_revision=1,
                run_id=EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                actor="validator",
                timestamp=CREATED_AT,
                causation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                correlation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                schema_version="r0-event/0.1",
                reason_codes=(),
                payload={},
            )

    def test_event_registry_rejects_unknown_reason_code(self) -> None:
        registry = ReasonCodeRegistry(load_bootstrap_policy(Path.cwd()).reason_codes)

        with self.assertRaises(ValueError):
            EventEnvelope(
                event_id=EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                event_type="VALIDATION_RECORDED",
                aggregate_id=EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                aggregate_revision=1,
                run_id=EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                actor="validator",
                timestamp=CREATED_AT,
                causation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                correlation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                schema_version="r0-event/0.1",
                reason_codes=(ReasonCode("MADE_UP_REASON"),),
                payload={},
                reason_registry=registry,
            )

    def test_status_changed_event_requires_reason_code(self) -> None:
        with self.assertRaises(ValueError):
            EventEnvelope(
                event_id=EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                event_type="CLAIM_STATE_CHANGED",
                aggregate_id=EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                aggregate_revision=1,
                run_id=EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                actor="validator",
                timestamp=CREATED_AT,
                causation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                correlation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                schema_version="r0-event/0.1",
                reason_codes=(),
                payload={},
            )

    def test_state_changed_alias_requires_reason_code(self) -> None:
        event = EventEnvelope(
            event_id=EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            event_type="CLAIM_STATE_CHANGED",
            aggregate_id=EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            aggregate_revision=1,
            run_id=EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            actor="validator",
            timestamp=CREATED_AT,
            causation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            correlation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            schema_version="r0-event/0.1",
            reason_codes=(ReasonCode("CLAIM_EVIDENCE_UPDATED"),),
            payload={},
        )

        self.assertEqual(event.event_type, "CLAIM_STATE_CHANGED")

    def test_canonical_json_is_stable(self) -> None:
        left = {"b": [ClaimKind.OBSERVATIONAL, {"z": EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")}], "a": 1}
        right = {"a": 1, "b": [ClaimKind.OBSERVATIONAL, {"z": EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")}]} 

        self.assertEqual(canonical_json(left), canonical_json(right))

    def test_canonical_json_rejects_non_string_mapping_keys(self) -> None:
        with self.assertRaises(TypeError):
            canonical_json({1: "a", "1": "b"})

    def test_event_payload_is_deep_frozen(self) -> None:
        nested: list[str] = []
        event = EventEnvelope(
            event_id=EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            event_type="CLAIM_STATUS_CHANGED",
            aggregate_id=EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            aggregate_revision=1,
            run_id=EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            actor="validator",
            timestamp=CREATED_AT,
            causation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            correlation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            schema_version="r0-event/0.1",
            reason_codes=(ReasonCode("CLAIM_EVIDENCE_UPDATED"),),
            payload={"nested": nested},
        )
        before = canonical_json(event)
        nested.append("mutation")
        self.assertEqual(canonical_json(event), before)
        self.assertIsInstance(event.payload["nested"], tuple)

    def test_entity_id_serialized_as_string(self) -> None:
        event = EventEnvelope(
            event_id=EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            event_type="CLAIM_STATUS_CHANGED",
            aggregate_id=EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            aggregate_revision=1,
            run_id=EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            actor="validator",
            timestamp=CREATED_AT,
            causation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            correlation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
            schema_version="r0-event/0.1",
            reason_codes=(ReasonCode("CLAIM_EVIDENCE_UPDATED"),),
            payload={"claim": EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")},
        )

        rendered = canonical_json(event)

        self.assertIn('"event_id":"EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6"', rendered)
        self.assertIn('"aggregate_id":"CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"', rendered)
        self.assertIn('"claim":"CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"', rendered)

    def test_decimal_serialized_as_string(self) -> None:
        self.assertEqual(canonical_json({"x": Decimal("1.20")}), '{"x":"1.20"}')

    def test_naive_datetime_rejected(self) -> None:
        with self.assertRaises(ValueError):
            canonical_json({"t": datetime(2026, 1, 1, 0, 0)})  # debt-scan: ignore-line -- test literal for naive datetime rejection.

    def test_status_changed_event_requires_causation_id(self) -> None:
        with self.assertRaises(TypeError):
            EventEnvelope(
                event_id=EntityId("EVT_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                event_type="CLAIM_STATUS_CHANGED",
                aggregate_id=EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                aggregate_revision=1,
                run_id=EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                actor="validator",
                timestamp=CREATED_AT,
                causation_id=None,  # type: ignore[arg-type]
                correlation_id=EntityId("TXN_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                schema_version="r0-event/0.1",
                reason_codes=(ReasonCode("CLAIM_EVIDENCE_UPDATED"),),
                payload={},
            )


if __name__ == "__main__":
    unittest.main()
