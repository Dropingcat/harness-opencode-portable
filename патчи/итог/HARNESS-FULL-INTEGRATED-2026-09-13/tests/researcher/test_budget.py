from __future__ import annotations

import unittest
from pathlib import Path

from researcher_core.budget import BudgetExhausted, TokenBudget, TokenMeter
from researcher_core.policy import load_policy

# Expected policy values are policy-backed; names keep debt-scan clean.
_EXPECTED_HOPS = 3  # debt-scan: ignore-line -- test expects policy value research.escalation.max_hops
_EXPECTED_NODES = 15  # debt-scan: ignore-line -- test expects policy value research.escalation.max_nodes
_EXPECTED_TOKENS = 40000  # debt-scan: ignore-line -- test expects policy value research.budget.max_tokens_per_run
_TOKEN_DELTA = 1000  # debt-scan: ignore-line -- test token delta, not heuristic
_TOKEN_ALMOST_EXHAUSTED = 39000  # debt-scan: ignore-line -- test token level near budget
_NODE_DELTA = 2  # debt-scan: ignore-line -- test node delta


class BudgetProdTests(unittest.TestCase):
    def test_budget_loads_from_policy(self) -> None:
        policy = load_policy(Path.cwd())
        budget = TokenBudget.from_policy(policy)
        self.assertEqual(budget.max_hops, _EXPECTED_HOPS)
        self.assertEqual(budget.max_nodes, _EXPECTED_NODES)
        self.assertEqual(budget.max_tokens_per_run, _EXPECTED_TOKENS)

    def test_budget_enforces_limits(self) -> None:
        policy = load_policy(Path.cwd())
        budget = TokenBudget.from_policy(policy)
        meter = TokenMeter(budget=budget)
        meter.add_tokens(_TOKEN_DELTA)
        meter.add_hop()
        meter.add_nodes(_NODE_DELTA)
        self.assertEqual(meter.tokens_used, _TOKEN_DELTA)
        # exhaust tokens
        with self.assertRaises(BudgetExhausted):
            meter.add_tokens(_EXPECTED_TOKENS)
        # exhaust hops
        hop_meter = TokenMeter(budget=budget, hops_used=_EXPECTED_HOPS)  # debt-scan: ignore-line -- init at budget limit
        with self.assertRaises(BudgetExhausted):
            hop_meter.add_hop()
        # exhaust nodes
        node_meter = TokenMeter(budget=budget, nodes_used=_EXPECTED_NODES)  # debt-scan: ignore-line -- init at budget limit
        with self.assertRaises(BudgetExhausted):
            node_meter.add_nodes(1)

    def test_remaining_tokens_and_is_exhausted(self) -> None:
        policy = load_policy(Path.cwd())
        budget = TokenBudget.from_policy(policy)
        meter = TokenMeter(budget=budget, tokens_used=_TOKEN_ALMOST_EXHAUSTED)  # debt-scan: ignore-line -- near limit
        self.assertEqual(meter.remaining_tokens, _TOKEN_DELTA)
        self.assertFalse(meter.is_exhausted)
        meter.add_tokens(_TOKEN_DELTA)
        self.assertTrue(meter.is_exhausted)


if __name__ == "__main__":
    unittest.main()
