"""Base rotation policy implementation.

Implements the three rotation policy sub-interfaces --
:class:`~modelmesh.interfaces.rotation.DeactivationPolicy`,
:class:`~modelmesh.interfaces.rotation.RecoveryPolicy`, and
:class:`~modelmesh.interfaces.rotation.SelectionStrategy` -- with
threshold-based defaults: deactivate on consecutive failure count or
error rate, recover after a cooldown period, and select by lowest
error rate.
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
    "BaseRotationConfig",
    "BaseDeactivationPolicy",
    "BaseRecoveryPolicy",
    "BaseSelectionStrategy",
    "BaseRotationPolicy",
]


@dataclass
class BaseRotationConfig:
    """Configuration shared by all base rotation policy components."""

    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    error_rate_threshold: float = 0.5
    request_limit: Optional[int] = None
    token_limit: Optional[int] = None
    budget_limit: Optional[float] = None
    model_priority: list[str] = field(default_factory=list)
    provider_priority: list[str] = field(default_factory=list)


# ── Deactivation ────────────────────────────────────────────────────────


class BaseDeactivationPolicy(DeactivationPolicy):
    """Threshold-based model deactivation.

    Deactivates a model when its consecutive failure count reaches the
    configured threshold, its error rate exceeds the configured maximum,
    or a quota / budget limit is exceeded.
    """

    def __init__(self, config: BaseRotationConfig) -> None:
        self._config = config

    def should_deactivate(self, state: ModelState) -> bool:
        """Return True if the model should be moved to standby."""
        return self.get_reason(state) is not None

    def get_reason(self, state: ModelState) -> Optional[DeactivationReason]:
        """Return the first matching deactivation reason, or None.

        Evaluation order:
        1. Consecutive failure count >= failure_threshold
        2. Error rate >= error_rate_threshold
        3. Request limit exceeded (total_requests)
        4. Token limit exceeded (total_tokens)
        5. Budget limit exceeded (total_cost)
        """
        if state.failure_count >= self._config.failure_threshold:
            return DeactivationReason.ERROR_THRESHOLD

        if state.error_rate >= self._config.error_rate_threshold:
            return DeactivationReason.ERROR_THRESHOLD

        if (
            self._config.request_limit is not None
            and state.total_requests >= self._config.request_limit
        ):
            return DeactivationReason.REQUEST_LIMIT

        if (
            self._config.token_limit is not None
            and state.total_tokens >= self._config.token_limit
        ):
            return DeactivationReason.TOKEN_LIMIT

        if (
            self._config.budget_limit is not None
            and state.total_cost >= self._config.budget_limit
        ):
            return DeactivationReason.BUDGET_EXCEEDED

        return None


# ── Recovery ────────────────────────────────────────────────────────────


class BaseRecoveryPolicy(RecoveryPolicy):
    """Cooldown-based model recovery.

    Recovers a standby model once the configured cooldown period has
    elapsed since deactivation.
    """

    def __init__(self, config: BaseRotationConfig) -> None:
        self._config = config

    def should_recover(self, state: ModelState) -> bool:
        """Return True if cooldown has expired and the model can be reactivated.

        A model is eligible for recovery when ``cooldown_until`` is
        ``None`` (no cooldown set) or the current time has passed the
        cooldown deadline.
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


# ── Selection ───────────────────────────────────────────────────────────


class BaseSelectionStrategy(SelectionStrategy):
    """Stick-until-failure selection with priority-list support.

    Picks the first active model from the priority list (if configured),
    falling back to the candidate with the lowest error rate.
    """

    def __init__(self, config: BaseRotationConfig) -> None:
        self._config = config

    def select(
        self,
        candidates: list[ModelState],
        request: CompletionRequest,
    ) -> Optional[ModelState]:
        """Choose the best model from active candidates for the request.

        Returns ``None`` if no suitable candidate is available.
        """
        if not candidates:
            return None

        return max(candidates, key=lambda c: self.score(c, request))

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        """Score a single candidate for ranking purposes.

        Priority-listed models receive scores 1000+ (higher for earlier
        position).  Non-priority models are scored as ``1.0 - error_rate``.
        """
        if state.model_id in self._config.model_priority:
            idx = self._config.model_priority.index(state.model_id)
            return 1000.0 + (len(self._config.model_priority) - idx)

        # Check provider priority list
        provider_id = state.provider_id
        if provider_id and provider_id in self._config.provider_priority:
            idx = self._config.provider_priority.index(provider_id)
            return 500.0 + (len(self._config.provider_priority) - idx)

        # Fallback: lowest error rate wins
        return 1.0 - state.error_rate


# ── Combined Policy ──────────────────────────────────────────────────


class BaseRotationPolicy(DeactivationPolicy, RecoveryPolicy, SelectionStrategy):
    """Combined rotation policy implementing all three sub-interfaces.

    Provides threshold-based deactivation, cooldown-based recovery, and
    priority-list selection with error-rate fallback in a single class.
    Subclasses override individual methods to implement custom logic
    without replacing the entire policy.

    This is the recommended base class when a single object should own
    all rotation decisions.  For finer-grained composition, use the
    individual :class:`BaseDeactivationPolicy`,
    :class:`BaseRecoveryPolicy`, and :class:`BaseSelectionStrategy`
    classes instead.
    """

    def __init__(self, config: BaseRotationConfig) -> None:
        self._config = config

    # ── Deactivation ────────────────────────────────────────────────

    def should_deactivate(self, state: ModelState) -> bool:
        """Return True if the model should be moved to standby.

        Checks failure count, error rate, request limit, token limit,
        and budget limit in that order.
        """
        return self.get_reason(state) is not None

    def get_reason(self, state: ModelState) -> Optional[DeactivationReason]:
        """Return the first matching deactivation reason, or None.

        Evaluation order:
        1. Consecutive failure count >= failure_threshold
        2. Error rate >= error_rate_threshold
        3. Request limit exceeded (total_requests)
        4. Token limit exceeded (total_tokens)
        5. Budget limit exceeded (total_cost)
        """
        if state.failure_count >= self._config.failure_threshold:
            return DeactivationReason.ERROR_THRESHOLD

        if state.error_rate >= self._config.error_rate_threshold:
            return DeactivationReason.ERROR_THRESHOLD

        if (
            self._config.request_limit is not None
            and state.total_requests >= self._config.request_limit
        ):
            return DeactivationReason.REQUEST_LIMIT

        if (
            self._config.token_limit is not None
            and state.total_tokens >= self._config.token_limit
        ):
            return DeactivationReason.TOKEN_LIMIT

        if (
            self._config.budget_limit is not None
            and state.total_cost >= self._config.budget_limit
        ):
            return DeactivationReason.BUDGET_EXCEEDED

        return None

    # ── Recovery ────────────────────────────────────────────────────

    def should_recover(self, state: ModelState) -> bool:
        """Return True if cooldown has expired and the model can be reactivated."""
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

    # ── Selection ───────────────────────────────────────────────────

    def select(
        self,
        candidates: list[ModelState],
        request: CompletionRequest,
    ) -> Optional[ModelState]:
        """Choose the best model from active candidates for the request.

        Returns ``None`` if no suitable candidate is available.
        """
        if not candidates:
            return None

        return max(candidates, key=lambda c: self.score(c, request))

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        """Score a single candidate for ranking purposes.

        Priority-listed models receive scores 1000+ (higher for earlier
        position).  Provider-priority models receive scores 500+.
        Non-priority models are scored as ``1.0 - error_rate``.
        """
        if state.model_id in self._config.model_priority:
            idx = self._config.model_priority.index(state.model_id)
            return 1000.0 + (len(self._config.model_priority) - idx)

        # Check provider priority list
        provider_id = state.provider_id
        if provider_id and provider_id in self._config.provider_priority:
            idx = self._config.provider_priority.index(provider_id)
            return 500.0 + (len(self._config.provider_priority) - idx)

        # Fallback: lowest error rate wins
        return 1.0 - state.error_rate

    def _selection_reason(self, state: ModelState) -> str:
        """Return a human-readable reason for why a candidate was selected."""
        if state.model_id in self._config.model_priority:
            return "model_priority"
        provider_id = state.provider_id
        if provider_id and provider_id in self._config.provider_priority:
            return "provider_priority"
        return "lowest_error_rate"
