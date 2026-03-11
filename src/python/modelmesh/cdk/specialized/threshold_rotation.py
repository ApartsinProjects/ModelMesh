"""Threshold-based rotation policy for the CDK.

Implements DeactivationPolicy, RecoveryPolicy, and SelectionStrategy
using configurable numeric thresholds. Deactivation checks failure
count, error rate, quota usage, budget, token limits, and request
limits. Recovery uses cooldown-based timing. Selection follows a
priority list with stick-until-failure fallback.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from modelmesh.interfaces.provider import CompletionRequest
from modelmesh.interfaces.rotation import (
    DeactivationPolicy,
    DeactivationReason,
    ModelState,
    ModelStatus,
    RecoveryPolicy,
    SelectionStrategy,
)

__all__ = [
    "ThresholdRotationConfig",
    "ThresholdRotationPolicy",
]


@dataclass
class ThresholdRotationConfig:
    """Configuration for threshold-based rotation policy.

    All threshold fields are optional. When set to ``None``, the
    corresponding check is disabled. This allows combining only the
    thresholds relevant to a particular deployment.
    """

    # Deactivation thresholds
    failure_count_threshold: Optional[int] = 3
    error_rate_threshold: Optional[float] = 0.5
    quota_threshold: Optional[int] = None
    budget_threshold: Optional[float] = None
    token_limit_threshold: Optional[int] = None
    request_limit_threshold: Optional[int] = None

    # Recovery settings
    cooldown_seconds: float = 60.0

    # Selection settings
    priority_list: list[str] = field(default_factory=list)
    stick_until_failure: bool = True


class ThresholdRotationPolicy(
    DeactivationPolicy, RecoveryPolicy, SelectionStrategy
):
    """Rotation policy driven by numeric thresholds.

    Combines all three rotation sub-interfaces in a single
    configuration-only class. Thresholds are checked against
    ``ModelState`` fields to decide deactivation; cooldown timing
    drives recovery; priority ordering and stick-until-failure
    logic control selection.

    Usage::

        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            failure_count_threshold=5,
            error_rate_threshold=0.3,
            cooldown_seconds=120.0,
            priority_list=["openai.gpt-4o", "anthropic.claude-3"],
        ))
    """

    def __init__(self, config: ThresholdRotationConfig) -> None:
        self._config = config
        self._last_selected: Optional[str] = None

    # -- DeactivationPolicy --------------------------------------------------

    def should_deactivate(self, state: ModelState) -> bool:
        """Return True if any configured threshold is exceeded."""
        return self.get_reason(state) is not None

    def get_reason(self, state: ModelState) -> Optional[DeactivationReason]:
        """Return the first matching deactivation reason, or None.

        Checks thresholds in the following order:
        1. Consecutive failure count
        2. Error rate
        3. Quota (total_requests as proxy)
        4. Budget (total_cost)
        5. Token limit (total_tokens)
        6. Request limit (total_requests)
        """
        if (
            self._config.failure_count_threshold is not None
            and state.failure_count >= self._config.failure_count_threshold
        ):
            return DeactivationReason.ERROR_THRESHOLD

        if (
            self._config.error_rate_threshold is not None
            and state.error_rate >= self._config.error_rate_threshold
        ):
            return DeactivationReason.ERROR_THRESHOLD

        if (
            self._config.quota_threshold is not None
            and state.total_requests >= self._config.quota_threshold
        ):
            return DeactivationReason.QUOTA_EXHAUSTED

        if (
            self._config.budget_threshold is not None
            and state.total_cost >= self._config.budget_threshold
        ):
            return DeactivationReason.BUDGET_EXCEEDED

        if (
            self._config.token_limit_threshold is not None
            and state.total_tokens >= self._config.token_limit_threshold
        ):
            return DeactivationReason.TOKEN_LIMIT

        if (
            self._config.request_limit_threshold is not None
            and state.total_requests >= self._config.request_limit_threshold
        ):
            return DeactivationReason.REQUEST_LIMIT

        return None

    # -- RecoveryPolicy ------------------------------------------------------

    def should_recover(self, state: ModelState) -> bool:
        """Return True if cooldown has expired and the model can reactivate.

        A model is eligible for recovery when:
        - It has no ``cooldown_until`` set, or
        - The current time is past the ``cooldown_until`` timestamp.
        """
        if state.cooldown_until is None:
            return True
        return time.time() >= state.cooldown_until

    def get_recovery_schedule(self, state: ModelState) -> Optional[float]:
        """Return the timestamp when recovery should be attempted.

        Returns ``now + cooldown_seconds`` for standby models, or
        ``None`` for active models.
        """
        if state.status != ModelStatus.STANDBY:
            return None
        return time.time() + self._config.cooldown_seconds

    # -- SelectionStrategy ---------------------------------------------------

    def select(
        self,
        candidates: list[ModelState],
        request: CompletionRequest,
    ) -> Optional[ModelState]:
        """Choose the best model from active candidates.

        Selection logic:
        1. If ``stick_until_failure`` is enabled and the last selected
           model is still in the candidate list, re-use it.
        2. Otherwise, choose the highest-scored candidate via ``score()``.

        Returns None if no suitable candidate is available.
        """
        if not candidates:
            return None

        # Stick-until-failure: prefer the last-selected model if available
        if self._config.stick_until_failure and self._last_selected:
            for candidate in candidates:
                if candidate.model_id == self._last_selected:
                    return candidate

        # Score-based selection
        best = max(candidates, key=lambda c: self.score(c, request))
        self._last_selected = best.model_id
        return best

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        """Score a candidate by priority position, then by lowest error rate.

        Priority-listed models receive scores 1000+ (higher for earlier
        position). Non-priority models are scored as ``1.0 - error_rate``.
        """
        if state.model_id in self._config.priority_list:
            idx = self._config.priority_list.index(state.model_id)
            return 1000.0 + (len(self._config.priority_list) - idx)

        return 1.0 - state.error_rate
