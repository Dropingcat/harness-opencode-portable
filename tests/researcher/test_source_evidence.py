from __future__ import annotations

import unittest
from datetime import datetime

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta, EvidenceSpan, Source
from researcher_core.r0.ids import EntityId
from researcher_core.r0.serialization import canonical_json


CREATED_AT = datetime.fromisoformat("2026-08-29T00:00:00+00:00")
RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
SOURCE_ID = EntityId("SRC_01J7K6Y5T4D3R2A1B0C9E8F7G6")
EVIDENCE_ID = EntityId("EVD_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="source-evidence-bubble")


def meta(entity_id: EntityId) -> EntityMeta:
    return EntityMeta(
        id=entity_id,
        schema_version="r0-entity/0.1",
        revision=1,
        run_id=RUN_ID,
        created_at=CREATED_AT,
        created_by=ACTOR,
    )


class SourceEvidenceBubbleTests(unittest.TestCase):
    def test_source_and_evidence_are_distinct_entities(self) -> None:
        source = Source(meta=meta(SOURCE_ID), source_type="local_document", title="Fixture document", locator="fixture://doc1", content_hash="sha256:source")
        evidence = EvidenceSpan(meta=meta(EVIDENCE_ID), source_id=SOURCE_ID, exact_text="The measured indicator increased by 12%.", locator="line:1", text_hash="sha256:evidence")

        self.assertEqual(source.meta.id.namespace, "SRC")
        self.assertEqual(evidence.meta.id.namespace, "EVD")
        self.assertEqual(evidence.source_id, source.meta.id)
        self.assertIn('"source_id":"SRC_', canonical_json(evidence))

    def test_evidence_requires_source_id_not_claim_id(self) -> None:
        with self.assertRaises(ValueError):
            EvidenceSpan(
                meta=meta(EVIDENCE_ID),
                source_id=EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6"),
                exact_text="Text",
                locator="line:1",
                text_hash="sha256:evidence",
            )


if __name__ == "__main__":
    unittest.main()
