from __future__ import annotations

import unittest

from researcher_core.r0.ids import EntityId
from researcher_core.tribunal_inquiry import (
    ResponseGroundingItem,
    ResponseGroundingKind,
    ResponseGroundingState,
    characterize_response_grounding,
)


VISIBLE_REF = EntityId("EVD_01K4V3JQ9A7F5E2D8C6B0MNPQR")


class ResponseGroundingTests(unittest.TestCase):
    def test_empty_grounding_is_ungrounded(self) -> None:
        self.assertEqual(characterize_response_grounding(()), ResponseGroundingState.UNGROUNDED)

    def test_disclosed_evidence_is_evidence_grounded(self) -> None:
        item = ResponseGroundingItem(
            ResponseGroundingKind.DISCLOSED_EVIDENCE,
            "The answer uses disclosed evidence.",
            (VISIBLE_REF,),
        )

        self.assertEqual(characterize_response_grounding((item,)), ResponseGroundingState.DOCUMENTED)

    def test_model_prior_cannot_claim_a_ref(self) -> None:
        with self.assertRaisesRegex(ValueError, "MODEL_PRIOR"):
            ResponseGroundingItem(ResponseGroundingKind.MODEL_PRIOR, "Model prediction.", (VISIBLE_REF,))

    def test_model_prior_only_is_not_visible_grounding(self) -> None:
        item = ResponseGroundingItem(ResponseGroundingKind.MODEL_PRIOR, "Model prediction.")

        self.assertEqual(characterize_response_grounding((item,)), ResponseGroundingState.MODEL_PRIOR_ONLY)

    def test_evidence_and_model_prior_are_mixed(self) -> None:
        evidence = ResponseGroundingItem(
            ResponseGroundingKind.DISCLOSED_EVIDENCE,
            "Uses disclosed evidence.",
            (VISIBLE_REF,),
        )
        prior = ResponseGroundingItem(ResponseGroundingKind.MODEL_PRIOR, "Adds a model prediction.")

        self.assertEqual(characterize_response_grounding((evidence, prior)), ResponseGroundingState.MIXED)


if __name__ == "__main__":
    unittest.main()
