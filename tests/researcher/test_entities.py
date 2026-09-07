from __future__ import annotations

import unittest
from datetime import datetime
from decimal import Decimal

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import Claim, ClaimProposal, EntityMeta, Quantity, QuantityProposal
from researcher_core.r0.enums import ClaimStatus
from researcher_core.r0.ids import EntityId
from researcher_core.r0.serialization import canonical_json


CREATED_AT = datetime.fromisoformat("2026-08-29T00:00:00+00:00")
RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")
QTY_ID = EntityId("QTY_01J7K6Y5T4D3R2A1B0C9E8F7G6")
SCOPE_ID = EntityId("QST_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OPR_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="bubble")


def meta(entity_id: EntityId) -> EntityMeta:
    return EntityMeta(
        id=entity_id,
        schema_version="r0-entity/0.1",
        revision=1,
        run_id=RUN_ID,
        created_at=CREATED_AT,
        created_by=ACTOR,
    )


class EntityBubbleTests(unittest.TestCase):
    def test_claim_proposal_scope_is_snapshot_immutable(self) -> None:
        tags: list[str] = []
        proposal = ClaimProposal(
            temp_id="tmp-claim-1",
            proposition="Yield increased by 12%.",
            proposed_type="numeric",
            proposed_scope={"tags": tags},
            source_span_ref=None,
            extraction_run_id=OPR_ID,
        )

        tags.append("late")

        self.assertEqual(proposal.proposed_scope["tags"], ())

    def test_quantity_proposal_requires_decimal(self) -> None:
        with self.assertRaises(TypeError):
            QuantityProposal(
                temp_id="tmp-qty-1",
                value="12",  # type: ignore[arg-type]
                unit="%",
                measured_property="yield increase",
                source_span_ref=None,
                extraction_run_id=OPR_ID,
            )

    def test_claim_rejects_authoritative_links_inside_record(self) -> None:
        with self.assertRaises(ValueError):
            Claim(
                meta=meta(CLAIM_ID),
                proposition="Derived claim.",
                normalized_proposition="derived claim.",
                claim_type="inference",
                scope_id=SCOPE_ID,
                status=ClaimStatus.OPEN,
                attributes={"derived_from": ["CLM_other"]},
            )

    def test_claim_and_quantity_are_canonical_json_serializable(self) -> None:
        claim = Claim(
            meta=meta(CLAIM_ID),
            proposition="Yield increased by 12%.",
            normalized_proposition="yield increased by 12%.",
            claim_type="numeric",
            scope_id=SCOPE_ID,
            status=ClaimStatus.OPEN,
            attributes={"source": "fixture"},
        )
        quantity = Quantity(
            meta=meta(QTY_ID),
            value=Decimal("12"),
            unit="%",
            measured_property="yield increase",
            scope_id=SCOPE_ID,
        )

        rendered_claim = canonical_json(claim)
        rendered_quantity = canonical_json(quantity)

        self.assertIn('"status":"open"', rendered_claim)
        self.assertIn('"value":"12"', rendered_quantity)

    def test_entity_meta_rejects_naive_datetime(self) -> None:
        with self.assertRaises(ValueError):
            EntityMeta(
                id=CLAIM_ID,
                schema_version="r0-entity/0.1",
                revision=1,
                run_id=RUN_ID,
                created_at=datetime(2026, 1, 1),  # debt-scan: ignore-line -- bubble test literal.
                created_by=ACTOR,
            )


if __name__ == "__main__":
    unittest.main()
