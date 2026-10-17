"""execution_tracker.py — per-request state machine for P2 native requests.

States: NEW -> BOUND -> SUBMITTED -> WAITING -> COMPLETED | FAILED | TIMED_OUT | CANCELLED

Fail-closed semantics (never an implicit PASS):
  - the immutable `RequestSnapshot` enters via `bind(snapshot)` (BOUND);
  - queue admission (submit) is recorded but is NOT terminal — completion
    requires a correlated terminal assistant message with finish=='stop' and a
    model binding equal to the BOUND snapshot;
  - unknown/foreign message ids, mismatched model bindings, finish != 'stop'
    and late replies after a terminal state are all refused;
  - all transitions are atomic under a `threading.Lock`.
"""
from __future__ import annotations

import threading
from typing import Optional, Union

from opencode_transport import HostMessage, ModelRef, RequestSnapshot, Clock

# Legal singleton states.
NEW = "NEW"
BOUND = "BOUND"
SUBMITTED = "SUBMITTED"
WAITING = "WAITING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
TIMED_OUT = "TIMED_OUT"
CANCELLED = "CANCELLED"

_TERMINAL = frozenset({COMPLETED, FAILED, TIMED_OUT, CANCELLED})
_NON_TERMINAL = (NEW, BOUND, SUBMITTED, WAITING)  # strict order


class TrackerError(Exception):
    """Raised on any illegal/refused transition; state is left unchanged."""


def _models_equal(snapshot_model: ModelRef, message_model: ModelRef) -> bool:
    """Binding equality: providerID + id always; variant iff snapshot has one.

    A snapshot variant of None accepts any message variant. Fail-closed side:
    if the SNAPSHOT has a variant, the message MUST carry the exact same one.
    """
    if snapshot_model.providerID != message_model.providerID:
        return False
    if snapshot_model.id != message_model.id:
        return False
    if snapshot_model.variant is not None:
        return snapshot_model.variant == message_model.variant
    return True


class ExecutionTracker:
    """One tracker per request. All mutations are serialized through a single
    lock so transitions are atomic; reads return atomic state snapshots.
    """

    def __init__(self, snapshot=None, clock=None):
        self._snapshot = None  # bound via bind(); None until BOUND
        self._clock = clock if clock is not None else Clock()
        self._lock = threading.Lock()
        self._state = NEW
        self._submitted_admission = None
        self._terminal_message_id = None
        self._terminal_reason = None
        if snapshot is not None:
            # Pre-bound construction: the immutable snapshot is fixed at
            # creation and the tracker starts at BOUND.
            if not isinstance(snapshot, RequestSnapshot):
                raise TrackerError("tracker_snapshot_invalid")
            self._snapshot = snapshot
            self._state = BOUND

    # -- introspection -----------------------------------------------------

    def state(self) -> str:
        with self._lock:
            return self._state

    def snapshot(self) -> Optional[RequestSnapshot]:
        return self._snapshot

    def clock(self):
        """The injectable Clock used for deadline/now() decisions."""
        return self._clock

    def admission(self):
        """Admission payload recorded at submit(), or None. Read-only."""
        with self._lock:
            return self._submitted_admission

    def terminal_reason(self) -> Optional[str]:
        with self._lock:
            return self._terminal_reason

    def terminal_message_id(self) -> Optional[str]:
        with self._lock:
            return self._terminal_message_id

    def is_terminal(self) -> bool:
        with self._lock:
            return self._state in _TERMINAL

    # -- guarded transition helper -------------------------------------------

    def _transition(self, allowed_from, to, reason=None):
        """Atomic state change; raises TrackerError when not allowed."""
        with self._lock:
            allowed = {allowed_from} if isinstance(allowed_from, str) else set(allowed_from)
            if self._state not in allowed:
                raise TrackerError(
                    "tracker_transition_refused: from={} to={} reason={}".format(
                        self._state, to, reason or "not_allowed"))
            self._state = to
            self._terminal_reason = reason
            return self._state

    # -- public transitions ---------------------------------------------------

    def bind(self, snapshot):
        """NEW -> BOUND. Captures the immutable binding for correlation."""
        if not isinstance(snapshot, RequestSnapshot):
            raise TrackerError("bind_snapshot_invalid")
        with self._lock:
            if self._state != NEW:
                raise TrackerError("bind_refused: state={}".format(self._state))
            self._snapshot = snapshot
            self._state = BOUND
            return self._state

    def submit(self, admission):
        """BOUND -> SUBMITTED. Records the queue admission WITHOUT completing."""
        with self._lock:
            if self._state != BOUND or self._snapshot is None:
                raise TrackerError("submit_refused: state={}".format(self._state))
            self._submitted_admission = admission
            self._state = SUBMITTED
            return self._state

    def mark_waiting(self):
        """SUBMITTED -> WAITING (request dispatched to the fake/source)."""
        return self._transition(SUBMITTED, WAITING, reason=None)

    # -- terminal transitions ---------------------------------------------------

    def complete(self, message, reject_unknown=True):
        """WAITING -> COMPLETED only for a correlated terminal stop message.

        Correlation (all must hold, else TrackerError with state unchanged):
          - current state must be WAITING (late results refused: after any
            terminal state a later complete() always raises);
          - `message` must be a HostMessage;
          - finish must be 'stop';
          - when `request_hash` is present it must equal snapshot.input_sha256;
          - message.session_id must be the owned child session bound at BOUND;
          - model binding must equal the snapshot's binding.

        Correlated terminal-but-not-stop (finish in
        length/tool-calls/content-filter/error/unknown): never COMPLETED. With
        reject_unknown=True (default) the tracker goes FAILED; with False it
        STAYS WAITING. Either way it is an explicit refusal, not a PASS.
        """
        if not isinstance(message, HostMessage):
            raise TrackerError("complete_message_invalid")
        with self._lock:
            if self._state != WAITING:
                raise TrackerError(
                    "late_or_foreign_complete_refused: state={}".format(self._state))
            snapshot = self._snapshot
            if snapshot is None:
                raise TrackerError("complete_unbound_snapshot")
            owned_child = snapshot.request_id
            if message.session_id != owned_child:
                raise TrackerError("complete_foreign_session_refused")
            if (message.request_hash is not None
                    and message.request_hash != snapshot.input_sha256):
                raise TrackerError("complete_request_hash_mismatch")
            if not _models_equal(snapshot.model, message.model):
                raise TrackerError("complete_model_binding_mismatch")

            if message.finish == "stop":
                self._state = COMPLETED
                self._terminal_message_id = message.message_id
                self._terminal_reason = None
                return self._state

            # Correlated terminal message that is not finish=='stop'.
            if reject_unknown:
                self._state = FAILED
                self._terminal_message_id = message.message_id
                self._terminal_reason = "terminal_message_finish_not_stop:{}".format(
                    message.finish or "missing")
            return self._state

    def fail(self, reason):
        """Any non-terminal state -> FAILED (explicit refusal)."""
        if not isinstance(reason, str) or not reason:
            reason = "unspecified"
        return self._transition(_NON_TERMINAL, FAILED, reason=reason)

    def timeout(self):
        """Terminal: -> TIMED_OUT. A later complete() is refused (late result)."""
        return self._transition(_NON_TERMINAL, TIMED_OUT, reason="deadline_exceeded")

    def cancel(self):
        """Terminal: -> CANCELLED. A later complete() is refused."""
        return self._transition(_NON_TERMINAL, CANCELLED, reason="cancelled")

    # -- helpers ---------------------------------------------------------------

    def owned_session_id(self) -> Optional[str]:
        snapshot = self._snapshot
        if snapshot is None:
            return None
        return snapshot.request_id

    @property
    def model(self) -> Optional[ModelRef]:
        snapshot = self._snapshot
        return snapshot.model if snapshot is not None else None