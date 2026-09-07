from __future__ import annotations

import unittest

from researcher_core.r0.ids import EntityId


class ZeroRandom:
    def randrange(self, stop: int) -> int:
        return 0


class ZeroClock:
    def now_ms(self) -> int:
        return 0


class EntityIdTests(unittest.TestCase):
    def test_entity_id_exposes_namespace(self) -> None:
        entity_id = EntityId("CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")

        self.assertEqual(str(entity_id), "CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6")
        self.assertEqual(entity_id.namespace, "CLM")

    def test_entity_id_rejects_untyped_id(self) -> None:
        with self.assertRaises(ValueError):
            EntityId("C-POOR-002")

        with self.assertRaises(ValueError):
            EntityId("BAD_01J7K6Y5T4D3R2A1B0C9E8F7G6")

    def test_entity_id_new_uses_injected_sources(self) -> None:
        entity_id = EntityId.new("CLM", ZeroClock(), ZeroRandom())

        self.assertEqual(str(entity_id), "CLM_00000000000000000000000000")

        with self.assertRaises(ValueError):
            EntityId.new("BAD", ZeroClock(), ZeroRandom())

    def test_entity_id_new_rejects_raw_timestamp(self) -> None:
        with self.assertRaises(TypeError):
            EntityId.new("CLM", 0, ZeroRandom())


if __name__ == "__main__":
    unittest.main()
