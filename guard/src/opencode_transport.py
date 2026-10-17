"""opencode_transport.py — provenance-typed DTOs for the P2 native transport.

Component layer only: pure stdlib, offline. No HTTP, no subprocess, no
credentials, no environment reads. DTO shapes mirror the managed OpenAPI 2.0.29
(`Session.Info`, `Model.Ref`, `Session.Message.Assistant`) from the R0 evidence.

Fail-closed decoders: missing/blank/mis-typed provenance fields raise
`TransportError`; there is NO silent coercion and NO implicit default model.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

# Version(s) of the managed OpenCode host the transport layer speaks to.
# Everything else is refused at decode time (fail-closed version gate).
KNOWN_HOST_VERSIONS = ("2.0.29",)

# Legal `finish` values for a terminal assistant message (OpenAPI enum).
_FINISH_VALUES = frozenset({"stop", "length", "tool-calls", "content-filter",
                            "error", "unknown"})


class TransportError(Exception):
    """Raised when host-provided provenance data is malformed or missing.

    Every raise is an explicit refusal (never an implicit PASS): a message
    that cannot be parsed cannot be correlated, and is therefore rejected.
    """


@dataclass(frozen=True)
class ModelRef:
    """Mirror of `Model.Ref`: required id + providerID, optional variant.

    Immutable and hashable; used as part of the adapter result-cache key and
    as the immutable model binding recorded at BOUND time.
    """

    providerID: str
    id: str
    variant: Optional[str] = None

    @classmethod
    def from_cli_json(cls, obj):
        """Strict decoder for a `Model.Ref`-shaped CLI JSON object.

        Raises TransportError on missing/blank `providerID`/`id` or on a
        non-str `variant`. No silent coercion: types must already be correct.
        """
        if not isinstance(obj, dict):
            raise TransportError("model_ref_not_object")
        provider = obj.get("providerID")
        model_id = obj.get("id")
        if not isinstance(provider, str) or not provider.strip():
            raise TransportError("model_ref_missing_provider")
        if not isinstance(model_id, str) or not model_id.strip():
            raise TransportError("model_ref_missing_id")
        variant = obj.get("variant")
        if variant is not None and (not isinstance(variant, str) or not variant.strip()):
            raise TransportError("model_ref_invalid_variant")
        return cls(providerID=provider, id=model_id, variant=variant)


@dataclass(frozen=True)
class ParentContext:
    """Trusted, host/transport-supplied parent session context.

    A parent identity is ONLY ever accepted as a structured context object
    created through `from_cli_json`/`validate`; a bare session-id string in a
    payload is rejected by construction (there is no string constructor).
    """

    parent_id: str
    workspace_dir: Optional[str] = None
    model: Optional[ModelRef] = None

    @classmethod
    def from_cli_json(cls, obj):
        """Strict decoder for a `Session.Info`-shaped CLI JSON object.

        - `id` must be a str starting with 'ses' (owned session namespace).
        - `model` is optional; absent -> model None (never coerced).
        - `location` (workspace/mount binding) is an optional str.
        """
        if not isinstance(obj, dict):
            raise TransportError("parent_context_not_object")
        parent_id = obj.get("id")
        if not isinstance(parent_id, str) or not parent_id.startswith("ses"):
            raise TransportError("parent_context_id_invalid")
        workspace_dir = obj.get("location")
        if workspace_dir is not None and (not isinstance(workspace_dir, str)
                                          or not workspace_dir.strip()):
            raise TransportError("parent_context_workspace_invalid")
        model = None
        raw_model = obj.get("model")
        if raw_model is not None:
            model = ModelRef.from_cli_json(raw_model)
        return cls(parent_id=parent_id, workspace_dir=workspace_dir, model=model)

    def validate(self):
        """Fail-closed structural check; returns self or raises TransportError."""
        if not isinstance(self.parent_id, str) or not self.parent_id.startswith("ses"):
            raise TransportError("parent_context_id_invalid")
        if self.workspace_dir is not None and (not isinstance(self.workspace_dir, str)
                                               or not self.workspace_dir.strip()):
            raise TransportError("parent_context_workspace_invalid")
        if self.model is not None and not isinstance(self.model, ModelRef):
            raise TransportError("parent_context_model_invalid")
        return self


@dataclass(frozen=True)
class RequestSnapshot:
    """Immutable binding taken at BOUND time.

    `model` is the exact `ModelRef` the request was admitted under; the
    execution tracker requires terminal replies to match it (variant rule
    included). `input_sha256` is the public hash of the classified input —
    never the input text itself.
    """

    request_id: str
    parent: ParentContext
    input_sha256: str
    model: ModelRef

    def __post_init__(self):
        if not isinstance(self.request_id, str) or not self.request_id:
            raise TransportError("snapshot_request_id_invalid")
        if not isinstance(self.parent, ParentContext):
            raise TransportError("snapshot_parent_invalid")
        if not isinstance(self.input_sha256, str) or not self.input_sha256:
            raise TransportError("snapshot_input_hash_invalid")
        if not isinstance(self.model, ModelRef):
            raise TransportError("snapshot_model_invalid")


@dataclass(frozen=True)
class HostMessage:
    """Provenance fields of a host assistant message (no content carried).

    Deliberately does NOT carry `content`/`agent`: authz-relevant correlation
    uses only ids, model binding, finish and the request hash, so classified
    text and prompts never leak into tracker state or alarm info.

    `request_hash` binds the message to the admitted request
    (== snapshot.input_sha256); the tracker refuses messages without a
    matching hash.
    """

    kind: str
    session_id: str
    message_id: str
    model: ModelRef
    finish: Optional[str] = None
    request_hash: Optional[str] = None

    def __post_init__(self):
        if self.kind != "assistant":
            raise TransportError("host_message_kind_invalid")
        if not isinstance(self.session_id, str) or not self.session_id:
            raise TransportError("host_message_session_invalid")
        if not isinstance(self.message_id, str) or not self.message_id:
            raise TransportError("host_message_id_invalid")
        if not isinstance(self.model, ModelRef):
            raise TransportError("host_message_model_invalid")
        if self.finish is not None and self.finish not in _FINISH_VALUES:
            raise TransportError("host_message_finish_invalid")
        if self.request_hash is not None and (not isinstance(self.request_hash, str)
                                              or not self.request_hash):
            raise TransportError("host_message_request_hash_invalid")

    @classmethod
    def from_cli_json(cls, obj):
        """Strict decoder for a `Session.Message.Assistant`-shaped CLI JSON.

        Expected envelope keys (no aliases, no coercion):
          kind        : must equal 'assistant'
          sessionID   : non-empty str
          id          : non-empty str (message id)
          model       : `Model.Ref`-shaped dict
          finish      : optional str in {'stop','length','tool-calls',
                        'content-filter','error','unknown'}
          requestHash : optional str

        Any other shape raises TransportError. `content` and `agent` from the
        host message are intentionally ignored (never carried).
        """
        if not isinstance(obj, dict):
            raise TransportError("assistant_message_not_object")
        if obj.get("kind") != "assistant":
            raise TransportError("assistant_message_kind_invalid")
        session_id = obj.get("sessionID")
        message_id = obj.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise TransportError("assistant_message_session_invalid")
        if not isinstance(message_id, str) or not message_id:
            raise TransportError("assistant_message_id_invalid")
        model = ModelRef.from_cli_json(obj.get("model"))
        finish = obj.get("finish")
        if finish is not None and finish not in _FINISH_VALUES:
            raise TransportError("assistant_message_finish_invalid")
        request_hash = obj.get("requestHash")
        if request_hash is not None and (not isinstance(request_hash, str)
                                         or not request_hash):
            raise TransportError("assistant_message_request_hash_invalid")
        return cls(kind="assistant", session_id=session_id, message_id=message_id,
                   model=model, finish=finish, request_hash=request_hash)


class Clock:
    """Monotonic clock, injectable for deterministic tests.

    `Clock()` uses `time.monotonic()`; a test may pass `now_fn` returning a
    scripted float. All deadline logic in tracker/lifecycle goes through this
    abstraction so timeouts are testable without sleeping.
    """

    def __init__(self, now_fn=None):
        self._now_fn = now_fn

    def now(self) -> float:
        if self._now_fn is not None:
            return float(self._now_fn())
        return time.monotonic()