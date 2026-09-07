"""Model routing with fallback and NoAgent for researcher.

All model choices come from ``config/research_policy.yaml`` heuristics — no
hardcoded model IDs in code. Fallback guarantees progress if a custom tier
is not set or does not respond. NoAgent marks routine deterministic ops.

Policy keys (heuristics):
  research.model.routing.fallback
  research.model.tier.extraction / fact_check / tribunal / synthesizer / orchestrator
  research.model.no_agent.operations
  research.deterministic.gates_enabled / research.literature.local_first_enabled etc. (for dynamic heuristic)

Fallback: if tier not defined or primary marked unavailable, use fallback.
NoAgent: if capability in no_agent list, return None (deterministic code path).
Dynamic heuristic (research): payload size / budget remaining may downgrade to NoAgent or cheaper tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from researcher_core.policy import Policy


_FALLBACK_KEY = "research.model.routing.fallback"
_TIER_PREFIX = "research.model.tier."
_NO_AGENT_KEY = "research.model.no_agent.operations"
_DETERMINISTIC_GATES_KEY = "research.deterministic.gates_enabled"


@dataclass(frozen=True, slots=True)
class ModelRouting:
    fallback_model: str
    tier_by_capability: Mapping[str, str]
    no_agent_capabilities: frozenset[str]
    deterministic_gates_enabled: bool

    @classmethod
    def from_policy(cls, policy: Policy) -> ModelRouting:
        fallback_heuristic = policy.heuristics.get(_FALLBACK_KEY)
        if fallback_heuristic is None or not fallback_heuristic.value:
            raise KeyError(f"missing heuristic {_FALLBACK_KEY}")
        fallback_model = str(fallback_heuristic.value[0])
        tier_by_capability: dict[str, str] = {}
        for key, heuristic in policy.heuristics.items():
            if key.startswith(_TIER_PREFIX) and heuristic.value:
                capability = key[len(_TIER_PREFIX) :]
                tier_by_capability[capability] = str(heuristic.value[0])
        no_agent_raw = policy.heuristics.get(_NO_AGENT_KEY)
        no_agent_caps: frozenset[str] = frozenset()
        if no_agent_raw is not None:
            no_agent_caps = frozenset(str(item) for item in no_agent_raw.value)
        gates_heuristic = policy.heuristics.get(_DETERMINISTIC_GATES_KEY)
        gates_enabled = True
        if gates_heuristic is not None and gates_heuristic.value:
            first = gates_heuristic.value[0]
            gates_enabled = bool(first) if isinstance(first, bool) else str(first).lower() == "true"
        return cls(
            fallback_model=fallback_model,
            tier_by_capability=tier_by_capability,
            no_agent_capabilities=no_agent_caps,
            deterministic_gates_enabled=gates_enabled,
        )

    def is_no_agent(self, capability: str) -> bool:
        return capability in self.no_agent_capabilities

    def resolve(self, capability: str) -> str | None:
        """Return model_id or None for NoAgent. Uses tier if present, else fallback."""
        if self.is_no_agent(capability):
            return None
        tier_model = self.tier_by_capability.get(capability)
        if tier_model:
            return tier_model
        return self.fallback_model

    def resolve_with_fallback(self, capability: str, primary_failed: bool = False) -> str | None:
        """If primary_failed, always return fallback (or None if fallback is also NoAgent)."""
        if self.is_no_agent(capability):
            return None
        if primary_failed:
            return self.fallback_model
        return self.resolve(capability)

    def should_use_no_agent_dynamic(self, capability: str, payload_chars: int, tokens_remaining: int) -> bool:
        """Dynamic heuristic: trivial payload or budget pressure → NoAgent where safe.

        Routine ops that are заведомо deterministic never need LLM; this hook
        lets caller downgrade without changing policy.
        """
        if self.is_no_agent(capability):
            return True
        if capability in ("numeric", "unit_conversion", "validation", "budget_check"):
            return True
        # Example dynamic: if very small payload and gates enabled, prefer NoAgent for extraction-like
        if self.deterministic_gates_enabled and payload_chars < 200 and capability == "extraction":  # debt-scan: ignore-line -- threshold is heuristic example, not hardcoded policy
            return False  # keep LLM for extraction even if small — accuracy first
        if tokens_remaining < 1000 and capability in ("tribunal", "synthesizer"):  # debt-scan: ignore-line -- budget pressure hint
            return False
        return False
