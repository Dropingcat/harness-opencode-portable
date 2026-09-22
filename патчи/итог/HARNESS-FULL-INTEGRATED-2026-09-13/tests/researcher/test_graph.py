from __future__ import annotations

import unittest
from datetime import datetime

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import Claim, EntityMeta
from researcher_core.r0.enums import ClaimStatus, EdgeKind
from researcher_core.r0.graph import GraphEdge, InMemoryGraphRepository
from researcher_core.r0.ids import EntityId
from researcher_core.r0.serialization import canonical_json


CREATED_AT = datetime.fromisoformat("2026-08-29T00:00:00+00:00")
RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
EDGE_ID = EntityId("EDG_01J7K6Y5T4D3R2A1B0C9E8F7G6")
CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OTHER_CLAIM_ID = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G7")
SCOPE_ID = EntityId("QST_01J7K6Y5T4D3R2A1B0C9E8F7G6")
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


class GraphBubbleTests(unittest.TestCase):
    def test_dependency_lives_as_edge_not_claim_attribute(self) -> None:
        claim = Claim(
            meta=meta(CLAIM_ID),
            proposition="Derived claim.",
            normalized_proposition="derived claim.",
            claim_type="inference",
            scope_id=SCOPE_ID,
            status=ClaimStatus.OPEN,
            attributes={},
        )
        edge = GraphEdge(
            meta=meta(EDGE_ID),
            source_id=CLAIM_ID,
            target_id=OTHER_CLAIM_ID,
            edge_kind=EdgeKind.DERIVED_FROM,
        )

        self.assertNotIn("derived_from", claim.attributes)
        self.assertIn('"edge_kind":"derived_from"', canonical_json(edge))

    def test_graph_edge_rejects_self_edge(self) -> None:
        with self.assertRaises(ValueError):
            GraphEdge(
                meta=meta(EDGE_ID),
                source_id=CLAIM_ID,
                target_id=CLAIM_ID,
                edge_kind=EdgeKind.DEPENDS_ON,
            )

    def test_graph_repository_rejects_duplicate_edge_id(self) -> None:
        edge = GraphEdge(
            meta=meta(EDGE_ID),
            source_id=CLAIM_ID,
            target_id=OTHER_CLAIM_ID,
            edge_kind=EdgeKind.SUPPORTS,
        )
        graph = InMemoryGraphRepository()

        graph.add_edge(edge)

        with self.assertRaises(ValueError):
            graph.add_edge(edge)

    def test_graph_edge_attributes_are_snapshot_immutable(self) -> None:
        nested: list[str] = []
        edge = GraphEdge(
            meta=meta(EDGE_ID),
            source_id=CLAIM_ID,
            target_id=OTHER_CLAIM_ID,
            edge_kind=EdgeKind.SUPPORTS,
            attributes={"spans": nested},
        )

        nested.append("late")

        self.assertEqual(edge.attributes["spans"], ())


if __name__ == "__main__":
    unittest.main()
