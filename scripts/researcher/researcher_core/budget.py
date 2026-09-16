"""Prod token/escalation budget for researcher runs.

All limits come from ``config/research_policy.yaml`` heuristics, never from
hardcoded literals. The module is dependency-free and fails closed when a
budget would be exceeded, saving LLM tokens before the call.
"""

from __future__ import annotations

from dataclasses import dataclass

from researcher_core.policy import Policy


_DECIMAL_ZERO = 0  # debt-scan: ignore-line -- budget zero, not heuristic
_BUDGET_HOPS_KEY = "research.escalation.max_hops"
_BUDGET_NODES_KEY = "research.escalation.max_nodes"
_BUDGET_TOKENS_KEY = "research.budget.max_tokens_per_run"


@dataclass(frozen=True, slots=True)
class TokenBudget:
    max_hops: int
    max_nodes: int
    max_tokens_per_run: int

    @classmethod
    def from_policy(cls, policy: Policy) -> TokenBudget:
        hops_heuristic = policy.heuristics.get(_BUDGET_HOPS_KEY)
        nodes_heuristic = policy.heuristics.get(_BUDGET_NODES_KEY)
        tokens_heuristic = policy.heuristics.get(_BUDGET_TOKENS_KEY)
        if hops_heuristic is None or nodes_heuristic is None or tokens_heuristic is None:
            raise KeyError("budget heuristics missing from policy")
        return cls(
            max_hops=int(hops_heuristic.value[0]),
            max_nodes=int(nodes_heuristic.value[0]),
            max_tokens_per_run=int(tokens_heuristic.value[0]),
        )


class BudgetExhausted(RuntimeError):
    """Raised when a hop/node/token budget would be exceeded."""


@dataclass(slots=True)
class TokenMeter:
    budget: TokenBudget
    hops_used: int = _DECIMAL_ZERO
    nodes_used: int = _DECIMAL_ZERO
    tokens_used: int = _DECIMAL_ZERO

    def check_hop(self) -> None:
        if self.hops_used >= self.budget.max_hops:
            raise BudgetExhausted(f"hop budget exhausted: {self.hops_used} >= {self.budget.max_hops}")

    def check_node(self, additional: int = 1) -> None:  # debt-scan: ignore-line -- default increment 1 is structural, not heuristic
        if self.nodes_used + additional > self.budget.max_nodes:
            raise BudgetExhausted(f"node budget exhausted: {self.nodes_used}+{additional} > {self.budget.max_nodes}")

    def check_tokens(self, additional: int) -> None:
        if self.tokens_used + additional > self.budget.max_tokens_per_run:
            raise BudgetExhausted(
                f"token budget exhausted: {self.tokens_used}+{additional} > {self.budget.max_tokens_per_run}"
            )

    def add_hop(self) -> None:
        self.check_hop()
        self.hops_used += 1

    def add_nodes(self, count: int) -> None:
        self.check_node(count)
        self.nodes_used += count

    def add_tokens(self, count: int) -> None:
        self.check_tokens(count)
        self.tokens_used += count

    @property
    def remaining_tokens(self) -> int:
        return self.budget.max_tokens_per_run - self.tokens_used

    @property
    def is_exhausted(self) -> bool:
        return (
            self.hops_used >= self.budget.max_hops
            or self.nodes_used >= self.budget.max_nodes
            or self.tokens_used >= self.budget.max_tokens_per_run
        )
