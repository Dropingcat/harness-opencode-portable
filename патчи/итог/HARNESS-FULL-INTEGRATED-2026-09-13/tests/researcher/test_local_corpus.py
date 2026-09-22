from __future__ import annotations

import unittest
from pathlib import Path

from researcher_core.capsules import CapsuleRequest, InMemoryCapabilityRegistry
from researcher_core.local_corpus import LocalCorpusCapsule
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.ids import EntityId


RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OPR_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="local-corpus")
INDEX_PATH = Path("tests/fixtures/literature_index_sample.jsonl")
SEARCH_LIMIT = 3  # debt-scan: ignore-line -- test fixture limit


class LocalCorpusCapsuleTests(unittest.TestCase):
    def test_search_local_hits(self) -> None:
        capsule = LocalCorpusCapsule(INDEX_PATH)
        request = CapsuleRequest(OPR_ID, RUN_ID, "literature.search_local", ACTOR, {"query": "Scherrer steel", "limit": SEARCH_LIMIT})
        observation = capsule.run(request)
        hits = observation.payload["hits"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["name"], "doc1.pdf")

    def test_sources_local_ranked(self) -> None:
        capsule = LocalCorpusCapsule(INDEX_PATH)
        request = CapsuleRequest(OPR_ID, RUN_ID, "literature.sources_local", ACTOR, {"topics": ["method", "steel"], "limit": SEARCH_LIMIT})
        observation = capsule.run(request)
        sources = observation.payload["sources"]
        self.assertEqual(sources[0]["name"], "doc1.pdf")

    def test_registry_registers_local_corpus_capsule(self) -> None:
        registry = InMemoryCapabilityRegistry()
        capsule = LocalCorpusCapsule(INDEX_PATH)
        registry.register(capsule)
        self.assertIs(registry.provider_for("literature.search_local"), capsule)


if __name__ == "__main__":
    unittest.main()
