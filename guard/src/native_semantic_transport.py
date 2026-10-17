"""native_semantic_transport.py — drop-in P2 chain over the native transport DTOs.

`NativeTransportChain(cfg, budget)` mirrors the `ClassifierChain` result schema
(verdict/votes/provider/cost/alarm_level/alarm_info) consumed by
`artifact_guard._p2_run`, but delegates every classify-vote to a deterministic
adapter result cache keyed by (sha256(chunk), model_ref) fed by a future host
invoke — never to Local/Cloud classifiers.

Fail-closed contract:
  - verdict is 'NO' ONLY when a correlated terminal assistant message with a
    matching model binding is present for the request; everything else (absent
    adapter, mismatched binding, foreign session, finish != 'stop', malformed
    message) is verdict None + alarm_level='CRITICAL' — an explicit refusal,
    never an implicit PASS.
  - parent/model absence returns the exact fail-closed alarm dict; no fallback
    chain, no global default, no env reads, no network, no subprocess.
"""
from __future__ import annotations

import hashlib
from typing import Callable, Optional

from opencode_transport import (
    HostMessage,
    ModelRef,
    ParentContext,
    RequestSnapshot,
    TransportError,
)

# Majority-vote constants mirroring semantic_layer.P2_VOTES (local copies:
# nothing is re-exported from semantic_layer per contract).
P2_VOTES = 3
_MAJORITY = (P2_VOTES + 1) // 2  # 2

# Neutral provider tag reported for native-classified (NO) results.
_NATIVE_PROVIDER = "native"

# Fail-closed provider tag (scanner requires provider != 'none' for NO; the
# alarm path uses 'none' exactly like semantic_layer._alarm).
_NONE_PROVIDER = "none"

# Callable shape: (input_sha256: str, chunk: str) -> HostMessage | None
AdapterChain = Callable[[str, str], Optional[HostMessage]]


def _sha256(data) -> str:
    """Local sha256 hex digest (contract: no re-export from semantic_layer)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _models_equal(snapshot_model: ModelRef, message_model: ModelRef) -> bool:
    """Binding equality: providerID + id always; variant iff snapshot has one."""
    if snapshot_model.providerID != message_model.providerID:
        return False
    if snapshot_model.id != message_model.id:
        return False
    if snapshot_model.variant is not None:
        return snapshot_model.variant == message_model.variant
    return True


class NativeAdapter:
    """Pure DTO-level adapter: one classify() -> scanner-schema dict.

    Owns a private deterministic result cache keyed by (sha256(chunk),
    snapshot.model). No content is ever stored or emitted; alarm_info carries
    only neutral reason codes.
    """

    def __init__(self, adapter_chain: Optional[AdapterChain] = None):
        self._adapter_chain = adapter_chain
        # key: (input_sha256, ModelRef) -> 'NO' | None  (deterministic vote)
        self._cache = {}

    # -- per-vote primitive ---------------------------------------------------

    def _vote(self, chunk: str, snapshot: RequestSnapshot):
        """One classify-vote: 'NO' or None (fail-closed). Never raises."""
        input_hash = _sha256(chunk)
        key = (input_hash, snapshot.model)
        if key in self._cache:
            return self._cache[key]
        vote = None
        if self._adapter_chain is not None:
            try:
                message = self._adapter_chain(input_hash, chunk)
            except Exception:
                message = None  # adapter failure == unavailable (fail-closed)
            vote = self._correlate(message, input_hash, snapshot)
        self._cache[key] = vote
        return vote

    def _correlate(self, message, input_hash: str, snapshot: RequestSnapshot):
        """NO only for a correlated terminal 'stop' message with matching
        binding. Everything else -> None (refusal). Never raises: malformed
        inputs are data, not control flow.
        """
        if message is None:
            return None
        if not isinstance(message, HostMessage):
            return None
        if message.request_hash is not None and message.request_hash != input_hash:
            return None
        if message.session_id != snapshot.request_id:  # owned child session
            return None
        if not _models_equal(snapshot.model, message.model):
            return None
        if message.finish != "stop":
            return None
        return "NO"

    # -- public API -------------------------------------------------------------

    def classify(self, chunk: str, snapshot: RequestSnapshot) -> dict:
        """Scanner-schema dict for one chunk. Fail-closed: NO only under full
        correlation; None verdict + alarm CRITICAL otherwise.

        Votes always sum to 3; NO requires no >= 2 (majority), mirroring
        semantic_layer majority semantics.
        """
        if not isinstance(snapshot, RequestSnapshot):
            return self._fail_closed("snapshot_invalid")
        if snapshot.model is None:
            return self._fail_closed("model_missing")
        if not isinstance(chunk, str):
            return self._fail_closed("chunk_invalid")

        n_no = 0
        n_timeout = 0
        for _ in range(P2_VOTES):
            if self._vote(chunk, snapshot) == "NO":
                n_no += 1
            else:
                n_timeout += 1
        votes = {"yes": 0, "no": n_no, "timeout": n_timeout}

        if n_no >= _MAJORITY:
            return {
                "verdict": "NO",
                "votes": votes,
                "provider": _NATIVE_PROVIDER,
                "cost": 0.0,
                "alarm_level": None,
                "alarm_info": None,
            }
        return self._fail_closed("no_correlated_terminal", votes=votes)

    @staticmethod
    def _fail_closed(reason: str, votes=None) -> dict:
        """Explicit refusal dict; neutral codes only, never chunk text, never
        credentials. Mirrors the shape of semantic_layer._alarm().
        """
        return {
            "verdict": None,
            "votes": votes,
            "provider": _NONE_PROVIDER,
            "cost": 0.0,
            "alarm_level": "CRITICAL",
            "alarm_info": {
                "message": "GUARD CRITICAL — OPEN TO ATTACKS (no classifier available)",
                "primary": "native_adapter_unavailable",
                "fallback": "offline",
                "residual_risk": "50% bypass (paraphrase/indirect)",
                "reason": reason,
            },
        }


class NativeTransportChain:
    """Drop-in P2 chain in the scanner schema; NO fallback to Local/Cloud.

    Constructs its own NativeAdapter (with the private cache) and a snapshot
    derived from a caller-supplied `parent` (ParentContext). Component tests
    inject `parent=` and optionally `adapter_chain=`; production wiring
    supplies the real host invoke later (HOST_NOT_TESTED by contract).
    """

    def __init__(self, cfg, budget, parent: Optional[ParentContext] = None,
                 adapter_chain: Optional[AdapterChain] = None):
        self.cfg = cfg
        self.budget = budget
        self._parent = parent
        self._adapter = NativeAdapter(adapter_chain=adapter_chain)

    # -- snapshot derivation ---------------------------------------------------

    def _snapshot_for(self, chunk: str):
        """Immutable binding per chunk: parent context validated, owned child
        session id derived deterministically (neutral 'ses_r1_*' for R1
        fixtures; a real host owns/creates the child in R2).
        """
        parent = self._parent
        if parent is None or not isinstance(parent, ParentContext):
            return None
        try:
            parent = parent.validate()
        except (TransportError, AttributeError):
            return None
        if parent.model is None:
            return None
        input_hash = _sha256(chunk)
        child_id = "ses_r1_" + input_hash[:16]
        return RequestSnapshot(request_id=child_id, parent=parent,
                               input_sha256=input_hash, model=parent.model)

    # -- P2 schema entrypoint ------------------------------------------------------

    def run(self, chunk: str) -> dict:
        """Classify `chunk` in the P2 schema. Fail-closed on any absence."""
        # Budget parity with ClassifierChain.run (always 0.0 in R1 component
        # layer — no paid calls are authorized).
        snapshot = self._snapshot_for(chunk)
        if snapshot is None:
            result = NativeAdapter._fail_closed("parent_or_model_missing")
            self.budget.add(result["cost"])
            return result
        result = self._adapter.classify(chunk, snapshot)
        self.budget.add(result["cost"])
        return result