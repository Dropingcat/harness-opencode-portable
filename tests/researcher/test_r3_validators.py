"""Tests for R3 deterministic validators/builders
(src/researcher_core/r3_validators.py).

Covers: ValidationOutcome shape, the first four admission validators, the
remaining validators 5-11 (scope, edge, cycle, gap, conflict, structural risk,
recommendation gate), reviewer regression cases, and TypeError guards on None.
Uses stdlib unittest only; inputs are SimpleNamespace / EntityId snapshots.
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace

from researcher_core.r0.enums import ValidationResult, WriterEligibility
from researcher_core.r0.ids import EntityId
from researcher_core.r3_validators import (
    AtomicityValidator,
    ConflictBuilder,
    EdgeValidator,
    EvidenceAdmissionValidator,
    GapBuilder,
    GraphCycleValidator,
    NumericValidator,
    RecommendationGate,
    ScopeValidator,
    SourceAdmissionValidator,
    StructuralRiskAnalyzer,
    ValidationOutcome,
)

HASH64 = "a" * 64
HASH64_UP = "A" * 64
ID_STEM = "01J7K6Y5T4D3R2A1B0C9E8F7G"
SRC_ID = EntityId(f"SRC_{ID_STEM}6")
EVD_ID = EntityId(f"EVD_{ID_STEM}7")
CLM_ID = EntityId(f"CLM_{ID_STEM}1")
CLM2_ID = EntityId(f"CLM_{ID_STEM}2")
CLM3_ID = EntityId(f"CLM_{ID_STEM}3")
QTY_ID = EntityId(f"QTY_{ID_STEM}4")
REC_ID = EntityId(f"REC_{ID_STEM}5")
REC2_ID = EntityId(f"REC_{ID_STEM}8")
GAP_ID = EntityId(f"GAP_{ID_STEM}9")
GAP2_ID = EntityId(f"GAP_{ID_STEM}A")
CNF_ID = EntityId(f"CNF_{ID_STEM}B")
ASM_ID = EntityId(f"ASM_{ID_STEM}C")
DRV_ID = EntityId(f"DRV_{ID_STEM}D")


def make_source(**overrides: object) -> SimpleNamespace:
    data = {
        "title": "A valid paper title",
        "locator": "doi:10.1000/xyz",
        "source_type": "journal_article",
        "content_hash": HASH64,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_evidence(**overrides: object) -> SimpleNamespace:
    data = {
        "exact_text": "The catalyst converts CO2 at 300 C.",
        "locator": "p.12",
        "text_hash": HASH64,
        "source_id": SRC_ID,
        "is_title_only": False,
        "allow_title": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_claim(**overrides: object) -> SimpleNamespace:
    data = {
        "id": CLM_ID,
        "proposition": "Water boils at 100 C",
        "normalized_proposition": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_quantity(**overrides: object) -> SimpleNamespace:
    data = {
        "id": QTY_ID,
        "value": Decimal("100"),
        "unit": "degC",
        "measured_property": "boiling_point",
        "provenance_evidence_id": EVD_ID,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_scope_subject(**overrides: object) -> SimpleNamespace:
    data = {"scope_match": "MATCH"}
    data.update(overrides)
    return SimpleNamespace(**data)


def make_edge(**overrides: object) -> SimpleNamespace:
    data = {
        "source_id": EVD_ID,
        "target_id": CLM_ID,
        "relation": "SUPPORTS",
        "metadata": {"directness": "DIRECT", "scope_match": "MATCH"},
        "status": "VALID_IN_REPORT",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_derivation(**overrides: object) -> SimpleNamespace:
    data = {
        "id": DRV_ID,
        "output_claim_id": CLM2_ID,
        "output_quantities": (QTY_ID,),
        "states": {"arithmetic_status": "REPRODUCIBLE", "epistemic_status": "SUPPORTED"},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_gap_record(**overrides: object) -> SimpleNamespace:
    data = {
        "id": GAP_ID,
        "gap_type": "OTHER",
        "severity": "medium",
        "blocks": (),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_recommendation(**overrides: object) -> SimpleNamespace:
    data = {
        "id": REC_ID,
        "benefit_supported": True,
        "risk_claims_considered": True,
        "prerequisites_satisfied": True,
        "scope_match": "MATCH",
        "evidence_lineage_count": 2,
        "blocking_gap_ids": (),
        "unresolved_conflict_ids": (),
        "eligibility": WriterEligibility.ALLOWED,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class ValidationOutcomeTests(unittest.TestCase):
    def test_outcome_shape(self) -> None:
        outcome = ValidationOutcome(ValidationResult.PASS)
        self.assertIs(outcome.result, ValidationResult.PASS)
        self.assertEqual(outcome.reason_codes, ())
        self.assertEqual(outcome.findings, ())

    def test_outcome_enum_values(self) -> None:
        self.assertEqual(ValidationResult.PASS.value, "pass")
        self.assertEqual(ValidationResult.FAIL.value, "fail")
        self.assertEqual(ValidationResult.WARN.value, "warn")


class SourceAdmissionValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = SourceAdmissionValidator()

    def test_source_version(self) -> None:
        self.assertEqual(self.validator.version, "source-admission/1.1")

    def test_source_happy_path(self) -> None:
        outcome = self.validator.evaluate(make_source())
        self.assertIs(outcome.result, ValidationResult.PASS)
        self.assertEqual(outcome.reason_codes, ())

    def test_source_happy_path_uppercase_hash(self) -> None:
        outcome = self.validator.evaluate(make_source(content_hash=HASH64_UP))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_source_missing_hash_allowed(self) -> None:
        outcome = self.validator.evaluate(make_source(content_hash=None))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_source_empty_title(self) -> None:
        outcome = self.validator.evaluate(make_source(title=""))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("source:no_identity", outcome.reason_codes)

    def test_source_none_title(self) -> None:
        outcome = self.validator.evaluate(make_source(title=None))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("source:no_identity", outcome.reason_codes)

    def test_source_whitespace_identity_and_locator(self) -> None:
        outcome = self.validator.evaluate(make_source(title="   ", locator="   "))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("source:no_identity", outcome.reason_codes)
        self.assertIn("source:no_locator", outcome.reason_codes)

    def test_source_unknown_type(self) -> None:
        outcome = self.validator.evaluate(make_source(source_type="blog_post"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("source:unknown_type", outcome.reason_codes)

    def test_source_none_type(self) -> None:
        outcome = self.validator.evaluate(make_source(source_type=None))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("source:unknown_type", outcome.reason_codes)

    def test_source_bad_hash_short(self) -> None:
        outcome = self.validator.evaluate(make_source(content_hash="abc123"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("source:bad_hash", outcome.reason_codes)

    def test_source_bad_hash_63_chars(self) -> None:
        outcome = self.validator.evaluate(make_source(content_hash="a" * 63))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("source:bad_hash", outcome.reason_codes)

    def test_source_bad_hash_outside_hex(self) -> None:
        outcome = self.validator.evaluate(make_source(content_hash="g" * 64))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("source:bad_hash", outcome.reason_codes)

    def test_source_multiple_failures_accumulate(self) -> None:
        outcome = self.validator.evaluate(
            make_source(title="", locator="", source_type="nope", content_hash="zz")
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(
            sorted(outcome.reason_codes),
            ["source:bad_hash", "source:no_identity", "source:no_locator", "source:unknown_type"],
        )

    def test_source_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.validator.evaluate(None)

    def test_source_empty_object_fails_everything(self) -> None:
        outcome = self.validator.evaluate(SimpleNamespace())
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(
            sorted(outcome.reason_codes),
            ["source:no_identity", "source:no_locator", "source:unknown_type"],
        )


class EvidenceAdmissionValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = EvidenceAdmissionValidator()

    def test_evidence_version(self) -> None:
        self.assertEqual(self.validator.version, "evidence-admission/1.1")

    def test_evidence_happy_path(self) -> None:
        outcome = self.validator.evaluate(make_evidence())
        self.assertIs(outcome.result, ValidationResult.PASS)
        self.assertEqual(outcome.reason_codes, ())

    def test_evidence_empty_exact_text(self) -> None:
        outcome = self.validator.evaluate(make_evidence(exact_text=""))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:no_text", outcome.reason_codes)

    def test_evidence_whitespace_text(self) -> None:
        outcome = self.validator.evaluate(make_evidence(exact_text="   "))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:no_text", outcome.reason_codes)

    def test_evidence_empty_locator(self) -> None:
        outcome = self.validator.evaluate(make_evidence(locator=""))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:no_locator", outcome.reason_codes)

    def test_evidence_bad_hash(self) -> None:
        outcome = self.validator.evaluate(make_evidence(text_hash="deadbeef"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:bad_hash", outcome.reason_codes)

    def test_evidence_missing_hash(self) -> None:
        outcome = self.validator.evaluate(make_evidence(text_hash=None))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:bad_hash", outcome.reason_codes)

    def test_evidence_bad_source_namespace(self) -> None:
        outcome = self.validator.evaluate(make_evidence(source_id=EVD_ID))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:bad_source", outcome.reason_codes)

    def test_evidence_src_string_source_id(self) -> None:
        outcome = self.validator.evaluate(make_evidence(source_id=str(SRC_ID)))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_evidence_non_src_string_source_id(self) -> None:
        outcome = self.validator.evaluate(make_evidence(source_id=str(EVD_ID)))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:bad_source", outcome.reason_codes)

    def test_evidence_missing_source_id(self) -> None:
        outcome = self.validator.evaluate(make_evidence(source_id=None))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:bad_source", outcome.reason_codes)

    def test_evidence_title_only_fails(self) -> None:
        outcome = self.validator.evaluate(make_evidence(is_title_only=True))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:title_only", outcome.reason_codes)

    def test_evidence_title_only_allowed(self) -> None:
        outcome = self.validator.evaluate(make_evidence(is_title_only=True, allow_title=True))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_evidence_title_only_allow_title_string_is_rejected(self) -> None:
        outcome = self.validator.evaluate(make_evidence(is_title_only=True, allow_title="false"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("evidence:title_only", outcome.reason_codes)

    def test_evidence_multiple_failures_accumulate(self) -> None:
        outcome = self.validator.evaluate(make_evidence(exact_text="", locator="", text_hash="x", source_id=None))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(
            sorted(outcome.reason_codes),
            ["evidence:bad_hash", "evidence:bad_source", "evidence:no_locator", "evidence:no_text"],
        )

    def test_evidence_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.validator.evaluate(None)

    def test_evidence_empty_object_finds(self) -> None:
        outcome = self.validator.evaluate(SimpleNamespace())
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(
            sorted(outcome.reason_codes),
            ["evidence:bad_hash", "evidence:bad_source", "evidence:no_locator", "evidence:no_text"],
        )


class AtomicityValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = AtomicityValidator()

    def test_atomicity_version(self) -> None:
        self.assertEqual(self.validator.version, "atomicity/1.1")

    def test_atomicity_happy_path(self) -> None:
        outcome = self.validator.evaluate(make_claim())
        self.assertIs(outcome.result, ValidationResult.PASS)
        self.assertEqual(outcome.reason_codes, ())

    def test_atomicity_happy_path_russian(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="солнце встаёт на востоке"))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_atomicity_word_contains_marker_but_is_atomic(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="кислота сильная"))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_atomicity_english_word_contains_marker_but_is_atomic(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="standard pressure is stable"))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_atomicity_empty(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition=""))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(outcome.reason_codes, ("atomicity:empty",))

    def test_atomicity_none_proposition(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition=None))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(outcome.reason_codes, ("atomicity:empty",))

    def test_atomicity_rus_and(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="кошка и собака бегут"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_rus_takzhe(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="вода кипит, также он плавится"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_rus_odnako(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="реакция быстрая, однако опасная"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_rus_prichyom(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="метод точный, причём дешёвый"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_rus_krome_togo(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="план верен, кроме того он выполним"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_eng_and(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="water boils and metal expands"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_eng_also(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="rate increases, also pressure rises"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_eng_however(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="fast, however unstable"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_case_insensitive(self) -> None:
        outcome = self.validator.evaluate(make_claim(proposition="fast However unstable"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_normalized_proposition_used(self) -> None:
        outcome = self.validator.evaluate(
            make_claim(proposition="clean claim", normalized_proposition="clean claim and extra")
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_normalized_proposition_fallback(self) -> None:
        outcome = self.validator.evaluate(
            make_claim(proposition="signal decays and repeats", normalized_proposition="")
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("atomicity:suspect_composite", outcome.reason_codes)

    def test_atomicity_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.validator.evaluate(None)


class NumericValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = NumericValidator()

    def test_numeric_version(self) -> None:
        self.assertEqual(self.validator.version, "numeric/1.1")

    def test_numeric_happy_path(self) -> None:
        outcome = self.validator.evaluate(make_quantity())
        self.assertIs(outcome.result, ValidationResult.PASS)
        self.assertEqual(outcome.reason_codes, ())

    def test_numeric_happy_path_stdlib_decimal(self) -> None:
        outcome = self.validator.evaluate(make_quantity(value=Decimal("1.5e3")))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_numeric_bad_value_float(self) -> None:
        outcome = self.validator.evaluate(make_quantity(value=100.0))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:bad_value", outcome.reason_codes)

    def test_numeric_bad_value_int(self) -> None:
        outcome = self.validator.evaluate(make_quantity(value=100))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:bad_value", outcome.reason_codes)

    def test_numeric_bad_value_str(self) -> None:
        outcome = self.validator.evaluate(make_quantity(value="100"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:bad_value", outcome.reason_codes)

    def test_numeric_bad_value_none(self) -> None:
        outcome = self.validator.evaluate(make_quantity(value=None))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:bad_value", outcome.reason_codes)

    def test_numeric_no_unit(self) -> None:
        outcome = self.validator.evaluate(make_quantity(unit=""))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:no_unit", outcome.reason_codes)

    def test_numeric_no_property(self) -> None:
        outcome = self.validator.evaluate(make_quantity(measured_property=None))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:no_property", outcome.reason_codes)

    def test_numeric_negative_ratio(self) -> None:
        outcome = self.validator.evaluate(
            make_quantity(value=Decimal("-0.5"), measured_property="efficiency")
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:negative_ratio", outcome.reason_codes)

    def test_numeric_negative_ratio_accuracy(self) -> None:
        outcome = self.validator.evaluate(
            make_quantity(value=Decimal("-1"), measured_property="accuracy")
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:negative_ratio", outcome.reason_codes)

    def test_numeric_negative_non_ratio_allowed(self) -> None:
        outcome = self.validator.evaluate(
            make_quantity(value=Decimal("-273.15"), measured_property="temperature")
        )
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_numeric_zero_ratio_allowed(self) -> None:
        outcome = self.validator.evaluate(
            make_quantity(value=Decimal("0"), measured_property="rate")
        )
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_numeric_missing_provenance_warns(self) -> None:
        outcome = self.validator.evaluate(make_quantity(provenance_evidence_id=None))
        self.assertIs(outcome.result, ValidationResult.WARN)
        self.assertEqual(outcome.reason_codes, ("numeric:missing_provenance",))

    def test_numeric_bad_provenance_warns(self) -> None:
        outcome = self.validator.evaluate(make_quantity(provenance_evidence_id=SRC_ID))
        self.assertIs(outcome.result, ValidationResult.WARN)
        self.assertEqual(outcome.reason_codes, ("numeric:bad_provenance",))

    def test_numeric_nested_provenance_evidence_refs_passes(self) -> None:
        quantity = make_quantity(provenance_evidence_id=None, provenance={"evidence_refs": (EVD_ID,)})
        outcome = self.validator.evaluate(quantity)
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_numeric_multiple_failures_accumulate(self) -> None:
        outcome = self.validator.evaluate(make_quantity(value="x", unit="", measured_property=""))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(
            sorted(outcome.reason_codes),
            ["numeric:bad_value", "numeric:no_property", "numeric:no_unit"],
        )

    def test_numeric_negative_ratio_combined_failures(self) -> None:
        outcome = self.validator.evaluate(
            make_quantity(value=Decimal("-2"), unit="", measured_property="concentration")
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:negative_ratio", outcome.reason_codes)
        self.assertIn("numeric:no_unit", outcome.reason_codes)

    def test_numeric_whitespace_unit_rejected(self) -> None:
        """Regression: whitespace-only unit must not pass as a real unit."""
        outcome = self.validator.evaluate(
            make_quantity(value=Decimal("1"), unit="   ", measured_property="mass")
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:no_unit", outcome.reason_codes)

    def test_numeric_whitespace_ratio_property_rejected(self) -> None:
        """Regression: ' efficiency ' must normalize into _RATIO_PROPERTIES."""
        outcome = self.validator.evaluate(
            make_quantity(
                value=Decimal("-1"),
                unit="%",
                measured_property=" efficiency ",
                provenance_evidence_id=EVD_ID,
            )
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("numeric:negative_ratio", outcome.reason_codes)

    def test_numeric_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.validator.evaluate(None)


class ScopeValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ScopeValidator()

    def test_scope_version(self) -> None:
        self.assertEqual(self.validator.version, "scope/1.0")

    def test_scope_match_passes(self) -> None:
        outcome = self.validator.evaluate(make_scope_subject(scope_match="MATCH"))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_scope_metadata_match_passes(self) -> None:
        outcome = self.validator.evaluate(SimpleNamespace(metadata={"scope_match": "MATCH"}))
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_scope_partial_warns(self) -> None:
        outcome = self.validator.evaluate(make_scope_subject(scope_match="PARTIAL"))
        self.assertIs(outcome.result, ValidationResult.WARN)
        self.assertEqual(outcome.reason_codes, ("scope:partial",))

    def test_scope_unknown_warns(self) -> None:
        outcome = self.validator.evaluate(make_scope_subject(scope_match="UNKNOWN"))
        self.assertIs(outcome.result, ValidationResult.WARN)
        self.assertEqual(outcome.reason_codes, ("scope:unknown",))

    def test_scope_major_shift_fails(self) -> None:
        outcome = self.validator.evaluate(make_scope_subject(scope_match="MAJOR_SHIFT"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(outcome.reason_codes, ("scope:major_shift",))

    def test_scope_invalid_value_fails(self) -> None:
        outcome = self.validator.evaluate(make_scope_subject(scope_match="SIDEWAYS"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(outcome.reason_codes, ("scope:unknown_scope_match",))

    def test_scope_missing_value_fails(self) -> None:
        outcome = self.validator.evaluate(SimpleNamespace())
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(outcome.reason_codes, ("scope:no_scope_match",))

    def test_scope_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.validator.evaluate(None)


class EdgeValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = EdgeValidator()

    def test_edge_version(self) -> None:
        self.assertEqual(self.validator.version, "edge/1.0")

    def test_edge_support_happy_path(self) -> None:
        outcome = self.validator.evaluate(make_edge())
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_edge_quantifies_happy_path(self) -> None:
        outcome = self.validator.evaluate(
            make_edge(source_id=QTY_ID, target_id=CLM_ID, relation="QUANTIFIES", metadata={})
        )
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_edge_produced_valid_pairing_passes(self) -> None:
        outcome = self.validator.evaluate(
            make_edge(source_id=CLM_ID, target_id=REC_ID, relation="PRODUCED", metadata={})
        )
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_edge_produced_invalid_pairing_fails(self) -> None:
        outcome = self.validator.evaluate(
            make_edge(source_id=QTY_ID, target_id=SRC_ID, relation="PRODUCED", metadata={})
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("edge:unsupported_endpoints", outcome.reason_codes)

    def test_edge_partial_scope_warns(self) -> None:
        outcome = self.validator.evaluate(
            make_edge(metadata={"directness": "DIRECT", "scope_match": "PARTIAL"})
        )
        self.assertIs(outcome.result, ValidationResult.WARN)
        self.assertIn("edge:qualified_scope", outcome.reason_codes)

    def test_edge_missing_scope_fails(self) -> None:
        outcome = self.validator.evaluate(make_edge(metadata={"directness": "DIRECT"}))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("edge:bad_scope", outcome.reason_codes)

    def test_edge_missing_directness_fails(self) -> None:
        outcome = self.validator.evaluate(make_edge(metadata={"scope_match": "MATCH"}))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("edge:missing_directness", outcome.reason_codes)

    def test_edge_unknown_relation_fails(self) -> None:
        outcome = self.validator.evaluate(make_edge(relation="TELEPORTS"))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("edge:unknown_relation", outcome.reason_codes)

    def test_edge_self_loop_fails(self) -> None:
        outcome = self.validator.evaluate(make_edge(source_id=CLM_ID, target_id=CLM_ID))
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("edge:self_loop", outcome.reason_codes)

    def test_edge_unsupported_endpoints_fail(self) -> None:
        outcome = self.validator.evaluate(
            make_edge(source_id=CLM_ID, target_id=CLM2_ID, relation="QUANTIFIES", metadata={})
        )
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertIn("edge:unsupported_endpoints", outcome.reason_codes)

    def test_edge_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.validator.evaluate(None)


class GraphCycleValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = GraphCycleValidator()

    def test_graph_cycle_version(self) -> None:
        self.assertEqual(self.validator.version, "graph-cycle/1.0")

    def test_graph_cycle_acyclic_passes(self) -> None:
        graph = SimpleNamespace(
            edges=(
                make_edge(source_id=CLM_ID, target_id=CLM2_ID, relation="DEPENDS_ON", metadata={}),
                make_edge(source_id=CLM2_ID, target_id=CLM3_ID, relation="DERIVED_FROM", metadata={}),
            )
        )
        outcome = self.validator.evaluate(graph)
        self.assertIs(outcome.result, ValidationResult.PASS)

    def test_graph_cycle_detects_cycle(self) -> None:
        graph = SimpleNamespace(
            edges=(
                make_edge(source_id=CLM_ID, target_id=CLM2_ID, relation="DEPENDS_ON", metadata={}),
                make_edge(source_id=CLM2_ID, target_id=CLM_ID, relation="DEPENDS_ON", metadata={}),
            )
        )
        outcome = self.validator.evaluate(graph)
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(outcome.reason_codes, ("graph:cycle",))

    def test_graph_cycle_detects_cycle_under_relations_key(self) -> None:
        graph = SimpleNamespace(
            relations=(
                make_edge(source_id=CLM_ID, target_id=CLM2_ID, relation="DEPENDS_ON", metadata={}),
                make_edge(source_id=CLM2_ID, target_id=CLM_ID, relation="DEPENDS_ON", metadata={}),
            )
        )
        outcome = self.validator.evaluate(graph)
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(outcome.reason_codes, ("graph:cycle",))

    def test_graph_cycle_bad_edge_fails(self) -> None:
        graph = SimpleNamespace(edges=(make_edge(source_id=None, relation="DEPENDS_ON", metadata={}),))
        outcome = self.validator.evaluate(graph)
        self.assertIs(outcome.result, ValidationResult.FAIL)
        self.assertEqual(outcome.reason_codes, ("graph:bad_edge",))

    def test_graph_cycle_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.validator.evaluate(None)


class GapBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = GapBuilder()

    def test_gap_builder_version(self) -> None:
        self.assertEqual(self.builder.version, "gap-builder/1.0")

    def test_gap_builder_numeric_provenance_missing(self) -> None:
        snapshot = SimpleNamespace(quantities=(make_quantity(provenance_evidence_id=None),))
        gaps = self.builder.evaluate(snapshot)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].gap_type, "NUMERIC_PROVENANCE_MISSING")
        self.assertEqual(gaps[0].reason_codes, ("NUMERIC_PROVENANCE_MISSING",))

    def test_gap_builder_derivation_gaps(self) -> None:
        derivation = make_derivation(
            states={"arithmetic_status": "NON_CANONICAL_RANGE_TRANSFORM", "epistemic_status": "UNJUSTIFIED_ASSUMPTION"}
        )
        gaps = self.builder.evaluate(SimpleNamespace(derivations=(derivation,)))
        self.assertEqual({gap.gap_type for gap in gaps}, {"DERIVATION_NOT_REPRODUCIBLE", "UNSUPPORTED_ASSUMPTION"})

    def test_gap_builder_no_gaps(self) -> None:
        snapshot = SimpleNamespace(quantities=(make_quantity(),), derivations=(make_derivation(),))
        self.assertEqual(self.builder.evaluate(snapshot), ())

    def test_gap_builder_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.builder.evaluate(None)


class ConflictBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ConflictBuilder()

    def test_conflict_builder_version(self) -> None:
        self.assertEqual(self.builder.version, "conflict-builder/1.0")

    def test_conflict_builder_polarity_conflict(self) -> None:
        snapshot = SimpleNamespace(
            edges=(
                make_edge(source_id=EVD_ID, target_id=CLM_ID, relation="SUPPORTS"),
                make_edge(source_id=CLM2_ID, target_id=CLM_ID, relation="CONTRADICTS"),
            )
        )
        conflicts = self.builder.evaluate(snapshot)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, "EVIDENCE_POLARITY_CONFLICT")
        self.assertIn(str(CLM_ID), conflicts[0].blocks)

    def test_conflict_builder_polarity_conflict_under_relations_key(self) -> None:
        snapshot = SimpleNamespace(
            relations=(
                make_edge(source_id=EVD_ID, target_id=CLM_ID, relation="SUPPORTS"),
                make_edge(source_id=CLM2_ID, target_id=CLM_ID, relation="CONTRADICTS"),
            )
        )
        conflicts = self.builder.evaluate(snapshot)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, "EVIDENCE_POLARITY_CONFLICT")

    def test_conflict_builder_diagnostic_collapse(self) -> None:
        claim = make_claim(
            id=CLM2_ID,
            diagnostic_hypotheses=("drought", "root rot"),
            selected_hypothesis="drought",
        )
        conflicts = self.builder.evaluate(SimpleNamespace(claims=(claim,)))
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, "DIAGNOSTIC_COLLAPSE")

    def test_conflict_builder_no_conflicts(self) -> None:
        snapshot = SimpleNamespace(edges=(make_edge(source_id=EVD_ID, target_id=CLM_ID, relation="SUPPORTS"),))
        self.assertEqual(self.builder.evaluate(snapshot), ())

    def test_conflict_builder_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.builder.evaluate(None)


class StructuralRiskAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = StructuralRiskAnalyzer()

    def test_structural_risk_version(self) -> None:
        self.assertEqual(self.analyzer.version, "structural-risk/1.0")

    def test_structural_risk_pass_no_risks(self) -> None:
        snapshot = SimpleNamespace(
            edges=(make_edge(source_id=EVD_ID, target_id=CLM_ID, relation="SUPPORTS"),),
            gaps=(),
            recommendations=(make_recommendation(),),
        )
        report = self.analyzer.evaluate(snapshot)
        self.assertIs(report.result, ValidationResult.PASS)
        self.assertEqual(report.score, 1)
        self.assertEqual(report.reason_codes, ())

    def test_structural_risk_warns_on_unsupported_assumption(self) -> None:
        snapshot = SimpleNamespace(gaps=(make_gap_record(gap_type="UNSUPPORTED_ASSUMPTION"),))
        report = self.analyzer.evaluate(snapshot)
        self.assertIs(report.result, ValidationResult.WARN)
        self.assertIn("risk:unsupported_assumption", report.reason_codes)
        self.assertEqual(report.unsupported_assumption_count, 1)

    def test_structural_risk_relations_key_only(self) -> None:
        snapshot = SimpleNamespace(
            relations=(
                make_edge(source_id=CLM_ID, target_id=CLM2_ID, relation="DEPENDS_ON", metadata={}, status="WEAK"),
                make_edge(source_id=CLM_ID, target_id=CLM3_ID, relation="DEPENDS_ON", metadata={}, status="WEAK"),
            ),
            gaps=(),
            recommendations=(make_recommendation(),),
        )
        report = self.analyzer.evaluate(snapshot)
        self.assertEqual(report.fan_out, 2)
        self.assertEqual(report.weak_bridge_count, 2)
        self.assertIs(report.result, ValidationResult.WARN)

    def test_structural_risk_fails_on_blocked_recommendations(self) -> None:
        snapshot = SimpleNamespace(
            edges=(
                make_edge(source_id=CLM_ID, target_id=CLM2_ID, relation="DEPENDS_ON", metadata={}, status="WEAK"),
                make_edge(source_id=CLM_ID, target_id=CLM3_ID, relation="DEPENDS_ON", metadata={}, status="WEAK"),
                make_edge(source_id=CLM_ID, target_id=REC_ID, relation="DEPENDS_ON", metadata={}, status="WEAK"),
                make_edge(source_id=CLM_ID, target_id=REC2_ID, relation="DEPENDS_ON", metadata={}, status="WEAK"),
                make_edge(source_id=CLM_ID, target_id=QTY_ID, relation="DEPENDS_ON", metadata={}, status="WEAK"),
            ),
            gaps=(make_gap_record(gap_type="UNSUPPORTED_ASSUMPTION", blocks={"recommendations": (REC_ID,)}),),
            recommendations=(make_recommendation(id=REC2_ID, eligibility=WriterEligibility.FORBIDDEN_AS_RECOMMENDATION),),
        )
        report = self.analyzer.evaluate(snapshot)
        self.assertIs(report.result, ValidationResult.FAIL)
        self.assertIn("risk:high_fan_out", report.reason_codes)
        self.assertIn("risk:blocked_recommendations", report.reason_codes)
        self.assertEqual(report.fan_out, 5)
        self.assertEqual(report.blocked_recommendation_count, 2)

    def test_structural_risk_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.analyzer.evaluate(None)


class RecommendationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = RecommendationGate()

    def test_recommendation_gate_version(self) -> None:
        self.assertEqual(self.gate.version, "recommendation-gate/1.0")

    def test_recommendation_gate_allowed(self) -> None:
        decision = self.gate.evaluate(make_recommendation())
        self.assertIs(decision.eligibility, WriterEligibility.ALLOWED)
        self.assertEqual(decision.reason_codes, ())

    def test_recommendation_gate_partial_scope_is_qualified(self) -> None:
        decision = self.gate.evaluate(make_recommendation(scope_match="PARTIAL"))
        self.assertIs(decision.eligibility, WriterEligibility.QUALIFIED)
        self.assertIn("recommendation:qualified_scope", decision.reason_codes)

    def test_recommendation_gate_single_lineage_is_qualified(self) -> None:
        decision = self.gate.evaluate(make_recommendation(evidence_lineage_count=1))
        self.assertIs(decision.eligibility, WriterEligibility.QUALIFIED)
        self.assertIn("recommendation:single_lineage_support", decision.reason_codes)

    def test_recommendation_gate_blocking_gap_is_forbidden(self) -> None:
        decision = self.gate.evaluate(make_recommendation(blocking_gap_ids=(GAP_ID,)))
        self.assertIs(decision.eligibility, WriterEligibility.FORBIDDEN_AS_RECOMMENDATION)
        self.assertIn("recommendation:blocking_gap", decision.reason_codes)

    def test_recommendation_gate_unresolved_conflict_is_forbidden(self) -> None:
        decision = self.gate.evaluate(make_recommendation(unresolved_conflict_ids=(CNF_ID,)))
        self.assertIs(decision.eligibility, WriterEligibility.FORBIDDEN_AS_RECOMMENDATION)
        self.assertIn("recommendation:unresolved_conflict", decision.reason_codes)

    def test_recommendation_gate_missing_prerequisites_is_forbidden(self) -> None:
        decision = self.gate.evaluate(make_recommendation(prerequisites_satisfied=False))
        self.assertIs(decision.eligibility, WriterEligibility.FORBIDDEN_AS_RECOMMENDATION)
        self.assertIn("recommendation:prerequisites_unmet", decision.reason_codes)

    def test_recommendation_gate_unreviewed_risks_is_forbidden(self) -> None:
        decision = self.gate.evaluate(make_recommendation(risk_claims_considered=False))
        self.assertIs(decision.eligibility, WriterEligibility.FORBIDDEN_AS_RECOMMENDATION)
        self.assertIn("recommendation:risks_unreviewed", decision.reason_codes)

    def test_recommendation_gate_unknown_scope_match_is_forbidden(self) -> None:
        decision = self.gate.evaluate(make_recommendation(scope_match="SIDEWAYS"))
        self.assertIs(decision.eligibility, WriterEligibility.FORBIDDEN_AS_RECOMMENDATION)
        self.assertIn("recommendation:unknown_scope_match", decision.reason_codes)

    def test_recommendation_gate_zero_lineage_is_qualified(self) -> None:
        decision = self.gate.evaluate(make_recommendation(evidence_lineage_count=0))
        self.assertIs(decision.eligibility, WriterEligibility.QUALIFIED)
        self.assertIn("recommendation:no_lineage_support", decision.reason_codes)

    def test_recommendation_gate_scope_major_shift_is_forbidden(self) -> None:
        decision = self.gate.evaluate(make_recommendation(scope_match="MAJOR_SHIFT"))
        self.assertIs(decision.eligibility, WriterEligibility.FORBIDDEN_AS_RECOMMENDATION)
        self.assertIn("recommendation:scope_mismatch", decision.reason_codes)

    def test_recommendation_gate_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.gate.evaluate(None)


if __name__ == "__main__":
    unittest.main()
