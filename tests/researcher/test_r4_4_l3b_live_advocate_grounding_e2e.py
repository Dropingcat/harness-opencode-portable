from __future__ import annotations

import unittest

from researcher_core.tribunal_advocate import (
    AdvocateOutcome,
    AdvocateWorkerDraft,
    TribunalAdvocateError,
    compile_advocate_defense_contract,
    compile_advocate_disclosure,
    decide_advocate_activation,
    materialize_advocate_draft,
)
from researcher_core.tribunal_inquiry import ResponseGroundingItem, ResponseGroundingKind
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack
from tests.researcher import test_r4_4_advocate_branching_e2e as advocate_fixture


class LiveAdvocateGroundingE2E(unittest.TestCase):
    def test_prior_only_defense_cannot_materialize_defends(self) -> None:
        fixture = advocate_fixture.AdvocateBranchingE2E(methodName="test_defense_outcome_adds_defends_and_reply_edges")
        fixture.setUp()
        _, root, _, challenge, _, sibling, attack, _, graph = fixture.fixture_graph()
        arguments = {item.meta.id: item for item in (root, challenge, sibling)}
        activation = decide_advocate_activation(
            graph=graph,
            arguments=arguments,
            challenge_relation=attack,
            composition_policy=fixture.policy,
        )
        disclosure = compile_advocate_disclosure(
            activation=activation,
            graph=graph,
            arguments=arguments,
            id_factory=fixture.ids,
            actor=fixture.actor,
            created_at=fixture.t,
        )
        instruction = compile_role_instruction_pack(
            role_id="advocate",
            variant=RoleVariantKind.DEFENSE,
            handbook=fixture.handbook,
            policy=fixture.policy,
        )
        contract = compile_advocate_defense_contract(
            activation=activation,
            disclosure=disclosure,
            composition_policy=fixture.policy,
            instruction=instruction,
            id_factory=fixture.ids,
            actor=fixture.actor,
            created_at=fixture.t,
        )
        draft = AdvocateWorkerDraft(
            outcome=AdvocateOutcome.DEFEND,
            summary="The target may remain defensible.",
            justification="This statement relies only on model prior.",
            cited_target_refs=(fixture.claim,),
            grounding_items=(ResponseGroundingItem(ResponseGroundingKind.MODEL_PRIOR, "Model prediction."),),
        )

        with self.assertRaisesRegex(TribunalAdvocateError, "cannot DEFEND"):
            materialize_advocate_draft(
                contract=contract,
                disclosure=disclosure,
                draft=draft,
                id_factory=fixture.ids,
                actor=fixture.actor,
                created_at=fixture.t,
            )


if __name__ == "__main__":
    unittest.main()
