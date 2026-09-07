"""Tests for R1 entity contracts (src/researcher_core/r1_entities.py).

Covers: construction of all 7 R1 entities, id-namespace validation, required
field validation, enum type guards, mapping/tuple snapshotting, and frozen
immutability. Uses stdlib unittest only.
"""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from types import MappingProxyType

from researcher_core.r0.enums import (
    AdmissionStatus,
    ClaimStatus,
    ConflictState,
    DerivationState,
    GapState,
    WriterEligibility,
)
from researcher_core.r0.ids import EntityId
from researcher_core.r1_entities import (
    Assumption,
    Conflict,
    Derivation,
    EdgeProposal,
    Gap,
    Recommendation,
    Scope,
)


BODY = "01J7K6Y5T4D3R2A1B0C9E8F7G6"
THREE_BLOCKS = 3  # debt-scan: ignore-line -- expected fixture block count
EDGE_CONFIDENCE = 0.9  # debt-scan: ignore-line -- expected metadata fixture value
LATE_TAG = 7  # debt-scan: ignore-line -- mutation sentinel for snapshot immutability

SCP_ID = EntityId(f"SCP_{BODY}")
DRV_ID = EntityId(f"DRV_{BODY}")
ASM_ID = EntityId(f"ASM_{BODY}")
REC_ID = EntityId(f"REC_{BODY}")
GAP_ID = EntityId(f"GAP_{BODY}")
CNF_ID = EntityId(f"CNF_{BODY}")
CLM_1 = EntityId(f"CLM_{BODY}")
CLM_2 = EntityId(f"CLM_01J7K6Y5T4D3R2A1B0C9E8F7G5")
EVD_1 = EntityId(f"EVD_{BODY}")
EVD_2 = EntityId(f"EVD_01J7K6Y5T4D3R2A1B0C9E8F7G5")
QTY_ID = EntityId(f"QTY_{BODY}")

ULID_26 = "0123456789ABCDEFGHJKMNPQRT"


def cid(prefix: str) -> EntityId:
    return EntityId(f"{prefix}_{BODY}")


class ScopeTests(unittest.TestCase):
    def test_scope_happy_path(self) -> None:
        scope = Scope(id=SCP_ID, domain="heterogeneous catalysis")
        self.assertEqual(scope.id, SCP_ID)
        self.assertEqual(scope.domain, "heterogeneous catalysis")
        self.assertEqual(scope.dimensions, {})

    def test_scope_dimensions_snapshot_immutable(self) -> None:
        tags: list[str] = []
        scope = Scope(id=SCP_ID, domain="catalysis", dimensions={"tags": tags, "nested": {"x": [1]}})
        tags.append("late")
        self.assertEqual(scope.dimensions["tags"], ())
        self.assertIsInstance(scope.dimensions, MappingProxyType)
        self.assertEqual(scope.dimensions["nested"]["x"], (1,))

    def test_scope_rejects_wrong_namespace(self) -> None:
        with self.assertRaises(ValueError):
            Scope(id=cid("CLM"), domain="catalysis")

    def test_scope_rejects_empty_domain(self) -> None:
        with self.assertRaises(ValueError):
            Scope(id=SCP_ID, domain="")

    def test_scope_frozen(self) -> None:
        scope = Scope(id=SCP_ID, domain="catalysis")
        with self.assertRaises(FrozenInstanceError):
            scope.domain = "other"  # type: ignore[misc]


class DerivationTests(unittest.TestCase):
    def test_derivation_happy_path(self) -> None:
        deriv = Derivation(
            id=DRV_ID,
            output_claim_id=CLM_1,
            input_claim_ids=(CLM_2,),
            operation="avg",
            formula="(a+b)/2",
            status=DerivationState.DERIVED_REPRODUCIBLE,
        )
        self.assertEqual(deriv.operation, "avg")
        self.assertEqual(deriv.formula, "(a+b)/2")
        self.assertEqual(deriv.status, DerivationState.DERIVED_REPRODUCIBLE)

    def test_derivation_accepts_none_formula(self) -> None:
        deriv = Derivation(
            id=DRV_ID,
            output_claim_id=CLM_1,
            input_claim_ids=(CLM_2,),
            operation="log",
            formula=None,
            status=DerivationState.NOT_DERIVED,
        )
        self.assertIsNone(deriv.formula)

    def test_derivation_normalizes_input_tuple(self) -> None:
        deriv = Derivation(
            id=DRV_ID,
            output_claim_id=CLM_1,
            input_claim_ids=[CLM_2, CLM_1],
            operation="sum",
            formula=None,
            status=DerivationState.NOT_DERIVED,
        )
        self.assertIsInstance(deriv.input_claim_ids, tuple)

    def test_derivation_rejects_own_namespace_wrong(self) -> None:
        with self.assertRaises(ValueError):
            Derivation(
                id=cid("CLM"),
                output_claim_id=CLM_1,
                input_claim_ids=(CLM_2,),
                operation="sum",
                formula=None,
                status=DerivationState.NOT_DERIVED,
            )

    def test_derivation_rejects_output_claim_non_clm(self) -> None:
        with self.assertRaises(ValueError):
            Derivation(
                id=DRV_ID,
                output_claim_id=QTY_ID,
                input_claim_ids=(CLM_2,),
                operation="sum",
                formula=None,
                status=DerivationState.NOT_DERIVED,
            )

    def test_derivation_rejects_empty_inputs(self) -> None:
        with self.assertRaises(ValueError):
            Derivation(
                id=DRV_ID,
                output_claim_id=CLM_1,
                input_claim_ids=(),
                operation="sum",
                formula=None,
                status=DerivationState.NOT_DERIVED,
            )

    def test_derivation_rejects_input_non_clm(self) -> None:
        with self.assertRaises(ValueError):
            Derivation(
                id=DRV_ID,
                output_claim_id=CLM_1,
                input_claim_ids=(EVD_1,),
                operation="sum",
                formula=None,
                status=DerivationState.NOT_DERIVED,
            )

    def test_derivation_rejects_empty_operation(self) -> None:
        with self.assertRaises(ValueError):
            Derivation(
                id=DRV_ID,
                output_claim_id=CLM_1,
                input_claim_ids=(CLM_2,),
                operation="",
                formula=None,
                status=DerivationState.NOT_DERIVED,
            )

    def test_derivation_rejects_empty_formula_string(self) -> None:
        with self.assertRaises(ValueError):
            Derivation(
                id=DRV_ID,
                output_claim_id=CLM_1,
                input_claim_ids=(CLM_2,),
                operation="sum",
                formula="",
                status=DerivationState.NOT_DERIVED,
            )

    def test_derivation_rejects_string_status(self) -> None:
        with self.assertRaises(TypeError):
            Derivation(
                id=DRV_ID,
                output_claim_id=CLM_1,
                input_claim_ids=(CLM_2,),
                operation="sum",
                formula=None,
                status="derived_reproducible",  # type: ignore[arg-type]
            )

    def test_derivation_frozen(self) -> None:
        deriv = Derivation(
            id=DRV_ID,
            output_claim_id=CLM_1,
            input_claim_ids=(CLM_2,),
            operation="sum",
            formula=None,
            status=DerivationState.NOT_DERIVED,
        )
        with self.assertRaises(FrozenInstanceError):
            deriv.operation = "other"  # type: ignore[misc]


class AssumptionTests(unittest.TestCase):
    def test_assumption_happy_path(self) -> None:
        assumption = Assumption(
            id=ASM_ID,
            proposition="Catalyst is stable at 400C",
            claim_id=CLM_1,
            status=AdmissionStatus.CANDIDATE,
        )
        self.assertEqual(assumption.claim_id, CLM_1)
        self.assertEqual(assumption.status, AdmissionStatus.CANDIDATE)

    def test_assumption_accepts_none_claim(self) -> None:
        assumption = Assumption(
            id=ASM_ID,
            proposition="Free-floating assumption",
            claim_id=None,
            status=AdmissionStatus.PROPOSED,
        )
        self.assertIsNone(assumption.claim_id)

    def test_assumption_rejects_wrong_namespace(self) -> None:
        with self.assertRaises(ValueError):
            Assumption(
                id=cid("DRV"),
                proposition="x",
                claim_id=None,
                status=AdmissionStatus.CANDIDATE,
            )

    def test_assumption_rejects_empty_proposition(self) -> None:
        with self.assertRaises(ValueError):
            Assumption(
                id=ASM_ID,
                proposition="",
                claim_id=None,
                status=AdmissionStatus.CANDIDATE,
            )

    def test_assumption_rejects_claim_non_clm(self) -> None:
        with self.assertRaises(ValueError):
            Assumption(
                id=ASM_ID,
                proposition="x",
                claim_id=QTY_ID,
                status=AdmissionStatus.CANDIDATE,
            )

    def test_assumption_rejects_string_status(self) -> None:
        with self.assertRaises(TypeError):
            Assumption(
                id=ASM_ID,
                proposition="x",
                claim_id=None,
                status="candidate",  # type: ignore[arg-type]
            )

    def test_assumption_frozen(self) -> None:
        assumption = Assumption(
            id=ASM_ID,
            proposition="x",
            claim_id=None,
            status=AdmissionStatus.CANDIDATE,
        )
        with self.assertRaises(FrozenInstanceError):
            assumption.proposition = "y"  # type: ignore[misc]


class RecommendationTests(unittest.TestCase):
    def test_recommendation_happy_path(self) -> None:
        rec = Recommendation(
            id=REC_ID,
            proposition="Use Pd/C at 1 mol%",
            target_claim_ids=(CLM_1, CLM_2),
            status=ClaimStatus.SUPPORTED,
            eligibility=WriterEligibility.ALLOWED,
        )
        self.assertEqual(rec.status, ClaimStatus.SUPPORTED)
        self.assertEqual(rec.eligibility, WriterEligibility.ALLOWED)

    def test_recommendation_accepts_none_status(self) -> None:
        rec = Recommendation(
            id=REC_ID,
            proposition="TBD",
            target_claim_ids=(CLM_1,),
            status=None,
            eligibility=WriterEligibility.QUALIFIED,
        )
        self.assertIsNone(rec.status)

    def test_recommendation_normalizes_targets(self) -> None:
        rec = Recommendation(
            id=REC_ID,
            proposition="TBD",
            target_claim_ids=[CLM_1, CLM_2],
            status=None,
            eligibility=WriterEligibility.ALLOWED,
        )
        self.assertIsInstance(rec.target_claim_ids, tuple)

    def test_recommendation_rejects_wrong_namespace(self) -> None:
        with self.assertRaises(ValueError):
            Recommendation(
                id=cid("GAP"),
                proposition="x",
                target_claim_ids=(),
                status=None,
                eligibility=WriterEligibility.ALLOWED,
            )

    def test_recommendation_rejects_empty_proposition(self) -> None:
        with self.assertRaises(ValueError):
            Recommendation(
                id=REC_ID,
                proposition="",
                target_claim_ids=(),
                status=None,
                eligibility=WriterEligibility.ALLOWED,
            )

    def test_recommendation_rejects_target_non_clm(self) -> None:
        with self.assertRaises(ValueError):
            Recommendation(
                id=REC_ID,
                proposition="x",
                target_claim_ids=(QTY_ID,),
                status=None,
                eligibility=WriterEligibility.ALLOWED,
            )

    def test_recommendation_rejects_string_status(self) -> None:
        with self.assertRaises(TypeError):
            Recommendation(
                id=REC_ID,
                proposition="x",
                target_claim_ids=(),
                status="supported",  # type: ignore[arg-type]
                eligibility=WriterEligibility.ALLOWED,
            )

    def test_recommendation_rejects_string_eligibility(self) -> None:
        with self.assertRaises(TypeError):
            Recommendation(
                id=REC_ID,
                proposition="x",
                target_claim_ids=(),
                status=None,
                eligibility="allowed",  # type: ignore[arg-type]
            )

    def test_recommendation_frozen(self) -> None:
        rec = Recommendation(
            id=REC_ID,
            proposition="x",
            target_claim_ids=(),
            status=None,
            eligibility=WriterEligibility.ALLOWED,
        )
        with self.assertRaises(FrozenInstanceError):
            rec.proposition = "y"  # type: ignore[misc]


class GapTests(unittest.TestCase):
    def test_gap_happy_path(self) -> None:
        gap = Gap(
            id=GAP_ID,
            gap_type="missing_evidence",
            target_claim_ids=(CLM_1,),
            severity="blocking",
            blocks=(REC_ID, CLM_2),
            resolution_requirements=("SRC for claim CLM_1",),
            status=GapState.OPEN_BLOCKING_GAPS,
        )
        self.assertEqual(gap.gap_type, "missing_evidence")
        self.assertEqual(gap.blocks, (REC_ID, CLM_2))

    def test_gap_accepts_rec_gap_clm_blocks(self) -> None:
        gap = Gap(
            id=GAP_ID,
            gap_type="chain",
            target_claim_ids=(CLM_1,),
            severity="nonblocking",
            blocks=(REC_ID, GAP_ID, CLM_1),
            resolution_requirements=(),
            status=GapState.OPEN_NONBLOCKING_GAPS,
        )
        self.assertEqual(len(gap.blocks), THREE_BLOCKS)

    def test_gap_normalizes_tuples(self) -> None:
        gap = Gap(
            id=GAP_ID,
            gap_type="chain",
            target_claim_ids=[CLM_1],
            severity="minor",
            blocks=[CLM_2],
            resolution_requirements=["do x"],
            status=GapState.NO_OPEN_GAPS,
        )
        self.assertIsInstance(gap.target_claim_ids, tuple)
        self.assertIsInstance(gap.blocks, tuple)
        self.assertIsInstance(gap.resolution_requirements, tuple)

    def test_gap_rejects_wrong_namespace(self) -> None:
        with self.assertRaises(ValueError):
            Gap(
                id=cid("SCP"),
                gap_type="x",
                target_claim_ids=(CLM_1,),
                severity="s",
                blocks=(),
                resolution_requirements=(),
                status=GapState.NO_OPEN_GAPS,
            )

    def test_gap_rejects_empty_gap_type(self) -> None:
        with self.assertRaises(ValueError):
            Gap(
                id=GAP_ID,
                gap_type="",
                target_claim_ids=(CLM_1,),
                severity="s",
                blocks=(),
                resolution_requirements=(),
                status=GapState.NO_OPEN_GAPS,
            )

    def test_gap_rejects_empty_targets(self) -> None:
        with self.assertRaises(ValueError):
            Gap(
                id=GAP_ID,
                gap_type="x",
                target_claim_ids=(),
                severity="s",
                blocks=(),
                resolution_requirements=(),
                status=GapState.NO_OPEN_GAPS,
            )

    def test_gap_rejects_target_non_clm(self) -> None:
        with self.assertRaises(ValueError):
            Gap(
                id=GAP_ID,
                gap_type="x",
                target_claim_ids=(EVD_1,),
                severity="s",
                blocks=(),
                resolution_requirements=(),
                status=GapState.NO_OPEN_GAPS,
            )

    def test_gap_rejects_empty_severity(self) -> None:
        with self.assertRaises(ValueError):
            Gap(
                id=GAP_ID,
                gap_type="x",
                target_claim_ids=(CLM_1,),
                severity="",
                blocks=(),
                resolution_requirements=(),
                status=GapState.NO_OPEN_GAPS,
            )

    def test_gap_rejects_invalid_block_prefix(self) -> None:
        with self.assertRaises(ValueError):
            Gap(
                id=GAP_ID,
                gap_type="x",
                target_claim_ids=(CLM_1,),
                severity="s",
                blocks=(QTY_ID,),
                resolution_requirements=(),
                status=GapState.NO_OPEN_GAPS,
            )

    def test_gap_rejects_string_status(self) -> None:
        with self.assertRaises(TypeError):
            Gap(
                id=GAP_ID,
                gap_type="x",
                target_claim_ids=(CLM_1,),
                severity="s",
                blocks=(),
                resolution_requirements=(),
                status="no_open_gaps",  # type: ignore[arg-type]
            )

    def test_gap_frozen(self) -> None:
        gap = Gap(
            id=GAP_ID,
            gap_type="x",
            target_claim_ids=(CLM_1,),
            severity="s",
            blocks=(),
            resolution_requirements=(),
            status=GapState.NO_OPEN_GAPS,
        )
        with self.assertRaises(FrozenInstanceError):
            gap.severity = "other"  # type: ignore[misc]


class ConflictTests(unittest.TestCase):
    def test_conflict_happy_path(self) -> None:
        conflict = Conflict(
            id=CNF_ID,
            member_claim_ids=(CLM_1, CLM_2),
            member_evidence_ids=(EVD_1, EVD_2),
            conflict_type="contradiction",
            status=ConflictState.CONFLICT_UNRESOLVED,
        )
        self.assertEqual(conflict.conflict_type, "contradiction")
        self.assertEqual(conflict.status, ConflictState.CONFLICT_UNRESOLVED)

    def test_conflict_accepts_empty_evidence(self) -> None:
        conflict = Conflict(
            id=CNF_ID,
            member_claim_ids=(CLM_1,),
            member_evidence_ids=(),
            conflict_type="contradiction",
            status=ConflictState.CONFLICT_MEMBER,
        )
        self.assertEqual(conflict.member_evidence_ids, ())

    def test_conflict_normalizes_tuples(self) -> None:
        conflict = Conflict(
            id=CNF_ID,
            member_claim_ids=[CLM_1],
            member_evidence_ids=[EVD_1],
            conflict_type="contradiction",
            status=ConflictState.CONFLICT_MEMBER,
        )
        self.assertIsInstance(conflict.member_claim_ids, tuple)
        self.assertIsInstance(conflict.member_evidence_ids, tuple)

    def test_conflict_rejects_wrong_namespace(self) -> None:
        with self.assertRaises(ValueError):
            Conflict(
                id=cid("ASM"),
                member_claim_ids=(CLM_1,),
                member_evidence_ids=(),
                conflict_type="c",
                status=ConflictState.CONFLICT_MEMBER,
            )

    def test_conflict_rejects_empty_claims(self) -> None:
        with self.assertRaises(ValueError):
            Conflict(
                id=CNF_ID,
                member_claim_ids=(),
                member_evidence_ids=(),
                conflict_type="c",
                status=ConflictState.CONFLICT_MEMBER,
            )

    def test_conflict_rejects_claim_non_clm(self) -> None:
        with self.assertRaises(ValueError):
            Conflict(
                id=CNF_ID,
                member_claim_ids=(QTY_ID,),
                member_evidence_ids=(),
                conflict_type="c",
                status=ConflictState.CONFLICT_MEMBER,
            )

    def test_conflict_rejects_evidence_non_evd(self) -> None:
        with self.assertRaises(ValueError):
            Conflict(
                id=CNF_ID,
                member_claim_ids=(CLM_1,),
                member_evidence_ids=(CLM_2,),
                conflict_type="c",
                status=ConflictState.CONFLICT_MEMBER,
            )

    def test_conflict_rejects_empty_conflict_type(self) -> None:
        with self.assertRaises(ValueError):
            Conflict(
                id=CNF_ID,
                member_claim_ids=(CLM_1,),
                member_evidence_ids=(),
                conflict_type="",
                status=ConflictState.CONFLICT_MEMBER,
            )

    def test_conflict_rejects_string_status(self) -> None:
        with self.assertRaises(TypeError):
            Conflict(
                id=CNF_ID,
                member_claim_ids=(CLM_1,),
                member_evidence_ids=(),
                conflict_type="c",
                status="conflict_member",  # type: ignore[arg-type]
            )

    def test_conflict_frozen(self) -> None:
        conflict = Conflict(
            id=CNF_ID,
            member_claim_ids=(CLM_1,),
            member_evidence_ids=(),
            conflict_type="c",
            status=ConflictState.CONFLICT_MEMBER,
        )
        with self.assertRaises(FrozenInstanceError):
            conflict.conflict_type = "other"  # type: ignore[misc]


class EdgeProposalTests(unittest.TestCase):
    def test_edge_proposal_happy_path(self) -> None:
        edge = EdgeProposal(
            temp_id="tmp-edge-1",
            source_entity=CLM_1,
            target_entity=CLM_2,
            proposed_relation_type="supports",
        )
        self.assertEqual(edge.temp_id, "tmp-edge-1")
        self.assertEqual(edge.proposed_metadata, {})

    def test_edge_proposal_accepts_any_entity_kinds(self) -> None:
        edge = EdgeProposal(
            temp_id="tmp-edge-2",
            source_entity=SCP_ID,
            target_entity=REC_ID,
            proposed_relation_type="in_scope",
            proposed_metadata={"confidence": EDGE_CONFIDENCE},
        )
        self.assertEqual(edge.proposed_metadata["confidence"], EDGE_CONFIDENCE)

    def test_edge_proposal_metadata_snapshot_immutable(self) -> None:
        vals: list[int] = []
        edge = EdgeProposal(
            temp_id="tmp-edge-3",
            source_entity=CLM_1,
            target_entity=EVD_1,
            proposed_relation_type="supports",
            proposed_metadata={"tags": vals},
        )
        vals.append(LATE_TAG)
        self.assertEqual(edge.proposed_metadata["tags"], ())
        self.assertIsInstance(edge.proposed_metadata, MappingProxyType)

    def test_edge_proposal_rejects_empty_temp_id(self) -> None:
        with self.assertRaises(ValueError):
            EdgeProposal(
                temp_id="",
                source_entity=CLM_1,
                target_entity=CLM_2,
                proposed_relation_type="supports",
            )

    def test_edge_proposal_rejects_non_entity_source(self) -> None:
        with self.assertRaises(TypeError):
            EdgeProposal(
                temp_id="tmp-edge-4",
                source_entity="CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6",  # type: ignore[arg-type]
                target_entity=CLM_2,
                proposed_relation_type="supports",
            )

    def test_edge_proposal_rejects_non_entity_target(self) -> None:
        with self.assertRaises(TypeError):
            EdgeProposal(
                temp_id="tmp-edge-5",
                source_entity=CLM_1,
                target_entity=None,  # type: ignore[arg-type]
                proposed_relation_type="supports",
            )

    def test_edge_proposal_rejects_empty_relation_type(self) -> None:
        with self.assertRaises(ValueError):
            EdgeProposal(
                temp_id="tmp-edge-6",
                source_entity=CLM_1,
                target_entity=CLM_2,
                proposed_relation_type="",
            )

    def test_edge_proposal_frozen(self) -> None:
        edge = EdgeProposal(
            temp_id="tmp-edge-7",
            source_entity=CLM_1,
            target_entity=CLM_2,
            proposed_relation_type="supports",
        )
        with self.assertRaises(FrozenInstanceError):
            edge.temp_id = "other"  # type: ignore[misc]


class EntityIdGuardTests(unittest.TestCase):
    """EntityId itself validates the ULID shape before entity constructors run."""

    def test_entity_id_rejects_malformed_body(self) -> None:
        with self.assertRaises(ValueError):
            EntityId("SCP_short")

    def test_entity_id_rejects_unregistered_prefix(self) -> None:
        with self.assertRaises(ValueError):
            EntityId(f"ZZZ_{ULID_26}")

    def test_new_r1_prefixes_registered(self) -> None:
        for prefix in ("SCP", "DRV", "ASM", "REC", "GAP", "CNF"):
            entity_id = EntityId(f"{prefix}_{ULID_26}")
            self.assertEqual(entity_id.namespace, prefix)


if __name__ == "__main__":
    unittest.main()
