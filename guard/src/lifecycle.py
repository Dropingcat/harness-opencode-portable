"""lifecycle.py — per-request orchestration: deadline, admission, polling,
interrupt and cleanup, all delegating the state machine to ExecutionTracker.

Component layer only: `cleanup()` records intent and returns a descriptor; it
NEVER invokes the host. The future R2 host canary executes the described
action; no network/subprocess happens here.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from execution_tracker import (
    ExecutionTracker,
    TrackerError,
    NEW, BOUND,
    COMPLETED, FAILED, TIMED_OUT, CANCELLED,
)

_TERMINAL = frozenset({COMPLETED, FAILED, TIMED_OUT, CANCELLED})
_DEFAULT_POLL_INTERVAL = 0.05


class LifecycleError(Exception):
    """Raised on illegal lifecycle usage (programmer error), never out of
    band from cleanup()."""


class RequestLifecycle:
    """Binds a tracker and a shared deadline.

    `deadline` is the monotonic instant (seconds on the same clock as the
    tracker's Clock) at which the request must be settled; exceeding it while
    waiting triggers `request_timeout()` and returns TIMED_OUT.
    """

    def __init__(self, tracker, deadline: float):
        if not isinstance(tracker, ExecutionTracker):
            raise LifecycleError("lifecycle_tracker_invalid")
        if not isinstance(deadline, (int, float)) or deadline <= 0:
            raise LifecycleError("lifecycle_deadline_invalid")
        self._tracker = tracker
        self._deadline = float(deadline)
        self._cleanup_intents = []  # kind, id, action-descriptor pairs

    # -- state/deadline accessors ----------------------------------------------

    def state(self) -> str:
        return self._tracker.state()

    def deadline(self) -> float:
        return self._deadline

    # -- progression -------------------------------------------------------------

    def begin(self, snapshot=None) -> str:
        """NEW -> BOUND. Returns 'BOUND' or the current stage if already past it.

        `snapshot` (optional RequestSnapshot) is used only for the NEW->BOUND
        transition; a pre-bound tracker ignores it and returns its stage.
        """
        current = self._tracker.state()
        if current == NEW:
            bound = snapshot if snapshot is not None else self._tracker.snapshot()
            if bound is None:
                raise LifecycleError("begin_without_snapshot")
            self._tracker.bind(bound)
            return BOUND
        # Already bound or beyond: return the current stage unchanged.
        return current

    def admit(self, admission) -> str:
        """BOUND -> SUBMITTED. Records queue admission (NOT terminal)."""
        return self._tracker.submit(admission)

    def _stamp(self, message):
        """Attach provenance to a host message: owned child session id and the
        request hash, so the tracker can correlate without trusting the fake.
        Only the fields that exist on HostMessage are set; malformed input
        fails closed inside the tracker itself."""
        from opencode_transport import HostMessage  # local, no circular import
        if not isinstance(message, HostMessage):
            raise LifecycleError("wait_poll_invalid_message")
        owned = self._tracker.owned_session_id()
        snapshot = self._tracker.snapshot()
        if owned is None or snapshot is None:
            raise LifecycleError("wait_unbound_tracker")
        # Message must carry a message id and the owned session id; we enrich
        # only request_hash / session_id if the fake omitted them.
        msg_kwargs = {
            "kind": message.kind,
            "session_id": message.session_id if message.session_id else owned,
            "message_id": message.message_id,
            "model": message.model,
            "finish": message.finish,
            "request_hash": message.request_hash if message.request_hash is not None
            else snapshot.input_sha256,
        }
        return HostMessage(**msg_kwargs)

    def wait_for_terminal(self, poll: Callable[[], object],
                          poll_interval: float = _DEFAULT_POLL_INTERVAL,
                          max_wait: Optional[float] = None) -> str:
        """Poll `poll()` until the tracker is terminal.

        - `poll()` returns a HostMessage (or None when nothing is available).
        - Each non-None result is offered to tracker.complete().
        - A tracker-level refusal (TrackerError) is NOT swallowed: it is
          surfaced as an explicit FAILED transition (fail-closed), except
          'late/foreign' refusals which may be filtered by reject_unknown;
          this policy keeps the loop from converting refusals into PASSes.
        - Returns COMPLETED / FAILED / TIMED_OUT / CANCELLED.
        - When `max_wait` is given and exceeded from call start -> timeout.
        """
        if not callable(poll):
            raise LifecycleError("wait_poll_not_callable")
        if poll_interval is None or poll_interval <= 0:
            poll_interval = _DEFAULT_POLL_INTERVAL
        now = self._tracker.clock().now
        start = now()
        while True:
            state = self._tracker.state()
            if state in _TERMINAL:
                return state
            if max_wait is not None and (now() - start) >= max_wait:
                return self.request_timeout()
            if now() >= self._deadline:
                return self.request_timeout()
            try:
                item = poll()
            except Exception:
                # Poll itself failed: fail-closed, never a PASS.
                return self._tracker.fail("poll_error")
            if item is not None:
                try:
                    message = self._stamp(item)
                except (LifecycleError, TrackerError):
                    return self._tracker.fail("poll_message_invalid")
                try:
                    self._tracker.complete(message)
                except TrackerError as exc:
                    # A refusal (foreign/mismatched/late) is a failure signal;
                    # convert it into the FAILED state unless the tracker is
                    # already terminal (a terminal refusal leaves it unchanged
                    # and the loop will naturally finish).
                    if not self._tracker.is_terminal():
                        self._tracker.fail("complete_refused:{}".format(str(exc)))
            time.sleep(poll_interval)

    # -- interrupts --------------------------------------------------------------

    def request_timeout(self) -> str:
        """Timeout the request (terminal TIMED_OUT); late results are refused."""
        return self._tracker.timeout()

    def request_cancel(self) -> str:
        """Cancel the request (terminal CANCELLED); late results are refused."""
        return self._tracker.cancel()

    def request_finish(self) -> str:
        """Finish the request; returns the new state."""
        current = self._tracker.state()
        if current in _TERMINAL:
            return current
        # Not terminal: explicit refusal, not a PASS.
        return self._tracker.fail("lifecycle_finish_not_terminal")

    # -- cleanup (records intent only) ---------------------------------------------

    def cleanup(self, owned_session_id: str) -> dict:
        """Record cleanup intent for an owed child; returns a descriptor dict.

        Fail-closed cleanup contract:
          - cleanup is only ever recorded for the OWED child session (the one
            bound in the tracker); a parent id is rejected explicitly.
          - a non-owned id is recorded as a warning and the descriptor carries
            `action='none'`; cleanup is never invoked for a parent.
          - the descriptor NEVER forces the host; executing it is the R2 host
            canary's job. This method never raises out of band.
        """
        snapshot = self._tracker.snapshot()
        owned = snapshot.request_id if snapshot is not None else None
        if owned is None:
            # Unbound: cannot own anything; record warning, no action.
            descriptor = {
                "action": "none",
                "session_id": owned_session_id,
                "owned": None,
                "warning": "cleanup_unbound_tracker",
            }
            self._cleanup_intents.append(descriptor)
            return descriptor
        if owned_session_id != owned:
            descriptor = {
                "action": "none",
                "session_id": owned_session_id,
                "owned": owned,
                "warning": "cleanup_not_owned_ignored",
            }
            self._cleanup_intents.append(descriptor)
            return descriptor
        descriptor = {
            "action": "close_child_session",
            "session_id": owned_session_id,
            "owned": owned,
            "warning": None,
        }
        self._cleanup_intents.append(descriptor)
        return descriptor

    # -- observation ---------------------------------------------------------------

    def cleanup_intents(self):
        return list(self._cleanup_intents)