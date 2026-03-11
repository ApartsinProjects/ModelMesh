"""Latency-first rotation policy connector.

Bundles the three rotation policy components (deactivation, recovery,
selection) into a single connector that favours the fastest model.
Tracks a rolling window of latencies per model and selects the one
with the lowest average response time.

Connector ID: ``modelmesh.latency-first.v1``
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from modelmesh.cdk.base_rotation import (
    BaseDeactivationPolicy,
    BaseRecoveryPolicy,
    BaseRotationConfig,
    BaseSelectionStrategy,
)
from modelmesh.interfaces.provider import CompletionRequest
from modelmesh.interfaces.rotation import (
    DeactivationReason,
    ModelState,
)

__all__ = [
    "LatencyFirstConfig",
    "LatencyFirstPolicy",
]


@dataclass
class LatencyFirstConfig(BaseRotationConfig):
    """Configuration for the latency-first rotation policy.

    Extends BaseRotationConfig with latency-specific settings.

    Attributes:
        latency_window: Number of recent latencies to keep in the
            rolling window for each model.
        max_latency_ms: Maximum acceptable average latency in
            milliseconds.  Models exceeding this are deactivated.
    """

    latency_window: int = 50
    max_latency_ms: float = 10000.0


# ── Deactivation ────────────────────────────────────────────────────────


class LatencyFirstDeactivationPolicy(BaseDeactivationPolicy):
    """Threshold-based deactivation with max-latency enforcement.

    Extends the base deactivation policy to also deactivate a model
    whose average latency exceeds ``max_latency_ms``.
    """

    def __init__(
        self,
        config: LatencyFirstConfig,
        latency_tracker: dict[str, deque[float]],
    ) -> None:
        super().__init__(config)
        self._latency_config = config
        self._latency_tracker = latency_tracker

    def get_reason(self, state: ModelState) -> Optional[DeactivationReason]:
        """Return the first matching deactivation reason, or None.

        Checks base thresholds first, then verifies that the model's
        average latency is within the configured maximum.
        """
        reason = super().get_reason(state)
        if reason is not None:
            return reason

        # Check average latency against the configured maximum
        latencies = self._latency_tracker.get(state.model_id)
        if latencies and len(latencies) > 0:
            avg = sum(latencies) / len(latencies)
            if avg > self._latency_config.max_latency_ms:
                return DeactivationReason.ERROR_THRESHOLD

        return None


# ── Selection ───────────────────────────────────────────────────────────


class LatencyFirstSelectionStrategy(BaseSelectionStrategy):
    """Selection strategy that picks the fastest model.

    Scores each candidate as ``-average_latency_ms`` using a rolling
    window of recent latency observations.  The model with the lowest
    average latency receives the highest score.  Models with no recorded
    latencies receive a score of ``0.0`` (neutral).
    """

    def __init__(
        self,
        config: LatencyFirstConfig,
        latency_tracker: dict[str, deque[float]],
    ) -> None:
        super().__init__(config)
        self._latency_tracker = latency_tracker

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        """Score a candidate by negative average latency.

        Lower average latency produces a higher (less negative) score.
        Models without observations score ``0.0``.
        """
        latencies = self._latency_tracker.get(state.model_id)
        if not latencies:
            return 0.0
        avg = sum(latencies) / len(latencies)
        return -avg


# ── Policy bundle ───────────────────────────────────────────────────────


class LatencyFirstPolicy:
    """Latency-first rotation policy bundle.

    Combines deactivation, recovery, and selection into a single
    connector that always routes to the fastest available model based
    on a rolling window of observed latencies.

    Connector ID: ``modelmesh.latency-first.v1``

    The three component policies are:

    - **Deactivation**: Threshold-based with max-latency enforcement.
      Deactivates a model when its average latency exceeds
      ``max_latency_ms`` or base thresholds are breached.
    - **Recovery**: Cooldown-based.  Reactivates a standby model after
      the configured cooldown period has elapsed.
    - **Selection**: Latency-first.  Picks the model with the lowest
      average latency over a configurable rolling window.

    Call :meth:`record_latency` after each request to feed observed
    response times into the rolling window.

    Usage::

        policy = LatencyFirstPolicy(LatencyFirstConfig(
            latency_window=50,
            max_latency_ms=5000.0,
        ))
        policy.record_latency("openai.gpt-4o", 320.5)
        selected = policy.selection.select(candidates, request)
    """

    CONNECTOR_ID: str = "modelmesh.latency-first.v1"

    def __init__(self, config: LatencyFirstConfig | None = None) -> None:
        if config is None:
            config = LatencyFirstConfig()
        self._config = config
        self._latency_tracker: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=config.latency_window)
        )
        self._deactivation = LatencyFirstDeactivationPolicy(
            config, self._latency_tracker
        )
        self._recovery = BaseRecoveryPolicy(config)
        self._selection = LatencyFirstSelectionStrategy(
            config, self._latency_tracker
        )

    def record_latency(self, model_id: str, latency_ms: float) -> None:
        """Record an observed latency for a model.

        Appends the latency to the rolling window.  Old entries are
        automatically evicted when the window size is exceeded.
        """
        self._latency_tracker[model_id].append(latency_ms)

    @property
    def deactivation(self) -> LatencyFirstDeactivationPolicy:
        """Return the deactivation policy component.

        Evaluates whether an active model should be moved to standby
        based on failure count, error rate, and average latency.
        """
        return self._deactivation

    @property
    def recovery(self) -> BaseRecoveryPolicy:
        """Return the recovery policy component.

        Evaluates whether a standby model should be reactivated based
        on cooldown expiration.
        """
        return self._recovery

    @property
    def selection(self) -> LatencyFirstSelectionStrategy:
        """Return the selection strategy component.

        Chooses the fastest active model for a given request.
        """
        return self._selection
