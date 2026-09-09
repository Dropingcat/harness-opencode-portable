"""Smoke tests for writer-core R0."""

import unittest
from decimal import Decimal

from writer_core.r0.ids import EntityId, EntityIdFactory
from writer_core.r0.enums import (
    WriterUnitType,
    WriterUnitStatus,
    ObjectKind,
    WriterEligibility,
    ValidationResult,
)
from writer_core.r0.entities import (
    EntityMeta,
    WriterUnitProposal,
    WriterUnit,
    WriterDocument,
    WriterTransaction,
    WriterSnapshot,
    WriterEvent,
    FORBIDDEN_UNIT_LINK_KEYS,
)
from writer_core.r0.events import _deep_freeze, ReasonCodeRegistry, EventEnvelope
from writer_core.r0.transactions import InMemoryUnitOfWork, SqliteUnitOfWork, open_sqlite
from writer_core.r0.validation import ValidationReport, ValidationResult as VR
from writer_core.r0.registry import InMemoryWriterRegistry, SequenceClock, CycleRandom, EntityIdFactory


class TestIds(unittest.TestCase):
    def setUp(self):
        self.clock = SequenceClock()
        self.rand = CycleRandom()
        self.factory = EntityIdFactory(clock=self.clock, random_source=self.rand)

    def test_new_id(self):
        eid = self.factory.new("WUT")
        self.assertEqual(eid.namespace, "WUT")
        self.assertEqual(len(eid.value.split("_")[1]), 26)

    def test_all_prefixes(self):
        for pfx in ("WUT", "DOC", "TXN", "SNP", "EVT", "OPR"):
            eid = self.factory.new(pfx)
            self.assertEqual(eid.namespace, pfx)

    def test_invalid_prefix(self):
        with self.assertRaises(ValueError):
            self.factory.new("XXX")


class TestEnums(unittest.TestCase):
    def test_unit_types(self):
        self.assertEqual(WriterUnitType.PARAGRAPH.value, "paragraph")
        self.assertEqual(WriterUnitType.OBJECT.value, "object")

    def test_statuses(self):
        self.assertEqual(WriterUnitStatus.DRAFT.value, "draft")
        self.assertEqual(WriterUnitStatus.APPROVED.value, "approved")

    def test_object_kinds(self):
        self.assertIn("number", {k.value for k in ObjectKind})
        self.assertIn("formula", {k.value for k in ObjectKind})
        self.assertIn("citation", {k.value for k in ObjectKind})

    def test_validation_result(self):
        self.assertEqual(ValidationResult.PASS.value, "pass")
        self.assertEqual(ValidationResult.WARN.value, "warn")


class TestEntities(unittest.TestCase):
    def setUp(self):
        self.clock = SequenceClock()
        self.rand = CycleRandom()
        self.factory = EntityIdFactory(clock=self.clock, random_source=self.rand)

    def _mk_meta(self, prefix: str) -> EntityMeta:
        return EntityMeta(
            id=self.factory.new(prefix),
            schema_version="1.0",
            revision=1,
            run_id=self.factory.new("RUN"),
            created_at=self._now(),
            created_by="test",
        )

    def _now(self):
        from datetime import datetime, UTC
        return datetime.now(UTC)

    def test_writer_unit_proposal(self):
        prop = WriterUnitProposal(
            temp_id="tmp1",
            unit_type=WriterUnitType.PARAGRAPH,
            text="Test paragraph",
            extraction_run_id=self.factory.new("OPR"),
        )
        self.assertEqual(prop.unit_type, WriterUnitType.PARAGRAPH)

    def test_writer_unit_paragraph(self):
        meta = self._mk_meta("WUT")
        unit = WriterUnit(
            meta=meta,
            unit_type=WriterUnitType.PARAGRAPH,
            text="Test paragraph text",
        )
        self.assertEqual(unit.unit_type, WriterUnitType.PARAGRAPH)
        self.assertEqual(unit.status, WriterUnitStatus.DRAFT)

    def test_writer_unit_object_number(self):
        meta = self._mk_meta("WUT")
        unit = WriterUnit(
            meta=meta,
            unit_type=WriterUnitType.OBJECT,
            text="",
            object_payload={"kind": "number", "value": "1.5", "unit": "mm", "dimension": "length"},
        )
        self.assertEqual(unit.object_payload["kind"], "number")

    def test_writer_document(self):
        meta = EntityMeta(
            id=self.factory.new("DOC"),
            schema_version="1.0",
            revision=1,
            run_id=self.factory.new("RUN"),
            created_at=self._now(),
            created_by="test",
        )
        doc = WriterDocument(
            meta=meta,
            title="Test Dissertation",
            genre="dissertation",
            spec_vak="05.13.18",
        )
        self.assertEqual(doc.title, "Test Dissertation")
        self.assertEqual(doc.genre, "dissertation")


class TestTransactions(unittest.TestCase):
    def test_in_memory_uow(self):
        uow = InMemoryUnitOfWork()
        with uow:
            from writer_core.r0.registry import EntityIdFactory, SequenceClock, CycleRandom
            clock = SequenceClock()
            rand = CycleRandom()
            factory = EntityIdFactory(clock=clock, random_source=rand)
            uow.put_state(factory.new("WUT"), {"text": "test"})
            uow.commit()
        view = uow.state_view()
        self.assertEqual(len(view), 1)

    def test_sqlite_uow(self):
        conn = open_sqlite(":memory:")
        uow = SqliteUnitOfWork(conn)
        from writer_core.r0.registry import EntityIdFactory, SequenceClock, CycleRandom
        clock = SequenceClock()
        rand = CycleRandom()
        factory = EntityIdFactory(clock=clock, random_source=rand)
        with uow:
            uow.put_state(factory.new("WUT"), {"text": "sqlite test"})
            uow.commit()
        view = uow.state_view()
        self.assertEqual(len(view), 1)
        conn.close()


class TestValidation(unittest.TestCase):
    def test_validation_report(self):
        from writer_core.r0.enums import ValidationResult
        r = ValidationReport(result=ValidationResult.PASS)
        self.assertEqual(r.result, ValidationResult.PASS)


class TestRegistry(unittest.TestCase):
    def test_in_memory_registry(self):
        clock = SequenceClock()
        rand = CycleRandom()
        reg = InMemoryWriterRegistry(clock, rand)
        doc_id = reg.create_document("Test", "dissertation")
        self.assertEqual(doc_id.namespace, "DOC")


if __name__ == "__main__":
    unittest.main()