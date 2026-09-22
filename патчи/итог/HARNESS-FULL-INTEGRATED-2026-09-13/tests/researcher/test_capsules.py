from __future__ import annotations

import unittest

from researcher_core.capsules import (
    CapsuleDescriptor,
    CapsuleObservation,
    CapsuleRequest,
    InMemoryCapabilityRegistry,
    SideEffectClass,
    assert_capsule_observation_is_untrusted,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.ids import EntityId


RUN_ID = EntityId("RUN_01J7K6Y5T4D3R2A1B0C9E8F7G6")
OPR_ID = EntityId("OPR_01J7K6Y5T4D3R2A1B0C9E8F7G6")
ACTOR = ActorRef(actor_type="test", actor_id="capsule-bubble")


class EchoCapsule:
    descriptor = CapsuleDescriptor(
        capsule_id="capsule.echo",
        version="0.1.0",
        capabilities=("llm.extract_claims",),
        side_effect_class=SideEffectClass.READ_ONLY,
        input_schema_version="capsule-request/0.1",
        output_schema_version="capsule-observation/0.1",
        policy_keys=("capsule.echo.timeout",),
    )

    def run(self, request: CapsuleRequest) -> CapsuleObservation:
        return CapsuleObservation(
            request_id=request.request_id,
            capsule_id=self.descriptor.capsule_id,
            capability=request.capability,
            output_schema_version=self.descriptor.output_schema_version,
            payload={"proposal": request.payload},
            provenance={"capsule_version": self.descriptor.version},
        )


class CapsuleBubbleTests(unittest.TestCase):
    def test_registry_selects_capsule_by_capability(self) -> None:
        registry = InMemoryCapabilityRegistry()
        capsule = EchoCapsule()

        registry.register(capsule)

        self.assertIs(registry.provider_for("llm.extract_claims"), capsule)
        self.assertEqual(registry.capabilities()["llm.extract_claims"], "capsule.echo")

    def test_duplicate_capability_provider_is_rejected(self) -> None:
        registry = InMemoryCapabilityRegistry()
        registry.register(EchoCapsule())

        with self.assertRaises(ValueError):
            registry.register(EchoCapsule())

    def test_capsule_request_payload_is_snapshot_immutable(self) -> None:
        payload = {"items": []}
        request = CapsuleRequest(
            request_id=OPR_ID,
            run_id=RUN_ID,
            capability="llm.extract_claims",
            actor=ACTOR,
            payload=payload,
        )

        payload["items"].append("late")

        self.assertEqual(request.payload["items"], ())

    def test_capsule_observation_requires_provenance(self) -> None:
        with self.assertRaises(ValueError):
            CapsuleObservation(
                request_id=OPR_ID,
                capsule_id="capsule.bad",
                capability="llm.extract_claims",
                output_schema_version="capsule-observation/0.1",
                payload={},
                provenance={},
            )

    def test_capsule_observation_cannot_claim_authority(self) -> None:
        observation = CapsuleObservation(
            request_id=OPR_ID,
            capsule_id="capsule.bad",
            capability="llm.extract_claims",
            output_schema_version="capsule-observation/0.1",
            payload={"authoritative": True},
            provenance={"capsule_version": "0.1.0"},
        )

        with self.assertRaises(ValueError):
            assert_capsule_observation_is_untrusted(observation)

    def test_capsule_observation_cannot_claim_nested_authority(self) -> None:
        observation = CapsuleObservation(
            request_id=OPR_ID,
            capsule_id="capsule.bad",
            capability="llm.extract_claims",
            output_schema_version="capsule-observation/0.1",
            payload={"proposal": {"authoritative": True}},
            provenance={"capsule_version": "0.1.0"},
        )

        with self.assertRaises(ValueError):
            assert_capsule_observation_is_untrusted(observation)


if __name__ == "__main__":
    unittest.main()
