from __future__ import annotations

import unittest
from pathlib import Path

from researcher_core.model_routing import ModelRouting
from researcher_core.policy import load_policy

_PAYLOAD_TINY = 10  # debt-scan: ignore-line -- test payload chars
_PAYLOAD_SMALL = 100  # debt-scan: ignore-line -- test payload chars
_PAYLOAD_MEDIUM = 1000  # debt-scan: ignore-line -- test payload chars
_TOKENS_HIGH = 5000  # debt-scan: ignore-line -- test tokens remaining
_TOKENS_LOW = 500  # debt-scan: ignore-line -- test tokens remaining


class ModelRoutingProdTests(unittest.TestCase):
    def test_model_routing_resolves_with_fallback(self) -> None:
        policy = load_policy(Path.cwd())
        routing = ModelRouting.from_policy(policy)
        # tier present
        self.assertEqual(routing.resolve("extraction"), "gpt-5.5-mini")
        self.assertEqual(routing.resolve("tribunal"), "gpt-5.6-terra")
        # fallback when tier missing
        self.assertEqual(routing.resolve("unknown_capability"), routing.fallback_model)
        # primary_failed → fallback
        self.assertEqual(routing.resolve_with_fallback("extraction", primary_failed=True), routing.fallback_model)
        # NoAgent returns None
        self.assertIsNone(routing.resolve("numeric"))
        self.assertIsNone(routing.resolve("validation"))
        self.assertTrue(routing.is_no_agent("numeric"))
        self.assertFalse(routing.is_no_agent("extraction"))

    def test_no_agent_dynamic_heuristic_safe(self) -> None:
        policy = load_policy(Path.cwd())
        routing = ModelRouting.from_policy(policy)
        # deterministic routine → true via is_no_agent
        self.assertTrue(routing.should_use_no_agent_dynamic("numeric", _PAYLOAD_TINY, _TOKENS_HIGH))
        # extraction small payload should not auto-downgrade (accuracy first)
        self.assertFalse(routing.should_use_no_agent_dynamic("extraction", _PAYLOAD_SMALL, _TOKENS_HIGH))
        # budget pressure should not force NoAgent for tribunal (keep quality)
        self.assertFalse(routing.should_use_no_agent_dynamic("tribunal", _PAYLOAD_MEDIUM, _TOKENS_LOW))

    def test_deterministic_gates_flag(self) -> None:
        policy = load_policy(Path.cwd())
        routing = ModelRouting.from_policy(policy)
        self.assertTrue(routing.deterministic_gates_enabled)


if __name__ == "__main__":
    unittest.main()
