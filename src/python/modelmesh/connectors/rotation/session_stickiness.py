"""Session-stickiness rotation policy connector.

Hashes a session identifier from the request to deterministically
bind a user/session to a specific model. This ensures conversational
continuity across multiple requests while falling back to round-robin
when the sticky model is unavailable.

Connector ID: ``modelmesh.session-stickiness.v1``
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from modelmesh.cdk.base_rotation import (
    BaseDeactivationPolicy,
    BaseRecoveryPolicy,
    BaseRotationConfig,
    BaseSelectionStrategy,
)
from modelmesh.interfaces.provider import CompletionRequest
from modelmesh.interfaces.rotation import ModelState

__all__ = [
    "SessionStickinessConfig",
    "SessionStickinessPolicy",
]


@dataclass
class SessionStickinessConfig(BaseRotationConfig):
    """Configuration for the session-stickiness rotation policy.

    Attributes:
        session_header: Name of the metadata key in
            ``CompletionRequest`` used as the session identifier.
            Default is ``"session_id"``.
    """

    session_header: str = "session_id"


class SessionStickySelectionStrategy(BaseSelectionStrategy):
    """Hash-based session-to-model binding.

    Uses a consistent hash of the session identifier to pin a
    session to a specific model.  Falls back to lowest error rate
    when no session key is present or the hashed model is
    unavailable.
    """

    def __init__(self, config: SessionStickinessConfig) -> None:
        super().__init__(config)
        self._session_header = config.session_header

    def _extract_session_id(self, request: CompletionRequest) -> Optional[str]:
        """Extract session identifier from the request messages."""
        if not request.messages:
            return None
        # Check last message metadata for session_id
        last = request.messages[-1]
        if isinstance(last, dict):
            meta = last.get("metadata", {})
            if isinstance(meta, dict):
                sid = meta.get(self._session_header)
                if sid:
                    return str(sid)
            # Also check top-level for convenience
            sid = last.get(self._session_header)
            if sid:
                return str(sid)
        return None

    def select(
        self,
        candidates: list[ModelState],
        request: CompletionRequest,
    ) -> Optional[ModelState]:
        if not candidates:
            return None

        active = [c for c in candidates if c.status.value == "active"]
        if not active:
            return None

        session_id = self._extract_session_id(request)
        if session_id is None:
            # No session; fall back to base priority selection
            return max(active, key=lambda c: super(
                SessionStickySelectionStrategy, self
            ).score(c, request))

        # Consistent hash: pick model index deterministically
        h = int(hashlib.sha256(session_id.encode()).hexdigest(), 16)
        idx = h % len(active)
        return active[idx]

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        return 1.0 - state.error_rate


class SessionStickinessPolicy:
    """Session-stickiness rotation policy bundle.

    Binds sessions to models via consistent hashing, with threshold-
    based deactivation and cooldown-based recovery.

    Connector ID: ``modelmesh.session-stickiness.v1``
    """

    CONNECTOR_ID: str = "modelmesh.session-stickiness.v1"

    def __init__(self, config: SessionStickinessConfig | None = None) -> None:
        if config is None:
            config = SessionStickinessConfig()
        self._config = config
        self._deactivation = BaseDeactivationPolicy(config)
        self._recovery = BaseRecoveryPolicy(config)
        self._selection = SessionStickySelectionStrategy(config)

    @property
    def deactivation(self) -> BaseDeactivationPolicy:
        return self._deactivation

    @property
    def recovery(self) -> BaseRecoveryPolicy:
        return self._recovery

    @property
    def selection(self) -> SessionStickySelectionStrategy:
        return self._selection
