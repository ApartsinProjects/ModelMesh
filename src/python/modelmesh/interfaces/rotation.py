"""Rotation policy interfaces and associated data types.

Defines the three independently replaceable rotation policy components:
deactivation (when to move a model to standby), recovery (when to
reactivate a standby model), and selection (which active model to use
for a given request). Each component receives current model state and
makes decisions accordingly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from modelmesh.interfaces.provider import CompletionRequest


class ModelStatus(Enum):
    """Lifecycle status of a model within a pool."""

    ACTIVE = "active"
    STANDBY = "standby"


class DeactivationReason(Enum):
    """Reason a model was moved from active to standby.

    Recorded on :attr:`ModelState.deactivation_reason` when a model is
    deactivated so that recovery policies can apply reason-specific logic.
    """

    ERROR_THRESHOLD = "error_threshold"
    QUOTA_EXHAUSTED = "quota_exhausted"
    BUDGET_EXCEEDED = "budget_exceeded"
    TOKEN_LIMIT = "token_limit"
    REQUEST_LIMIT = "request_limit"
    MAINTENANCE_WINDOW = "maintenance_window"
    MANUAL = "manual"


class RecoveryTrigger(Enum):
    """Trigger that caused a standby model to return to active."""

    COOLDOWN_EXPIRED = "cooldown_expired"
    QUOTA_RESET = "quota_reset"
    PROBE_SUCCESS = "probe_success"
    MANUAL = "manual"
    STARTUP_PROBE = "startup_probe"


@dataclass
class ModelState:
    """Mutable operational state for a single model within a pool.

    Tracks health indicators, usage counters, and lifecycle metadata
    that rotation policies use to make deactivation, recovery, and
    selection decisions.
    """

    model_id: str
    status: ModelStatus = ModelStatus.ACTIVE
    failure_count: int = 0
    error_rate: float = 0.0
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    cooldown_until: Optional[float] = None
    deactivation_reason: Optional[DeactivationReason] = None
    last_failure_at: Optional[float] = None
    last_success_at: Optional[float] = None


class DeactivationPolicy(ABC):
    """Abstract interface for model deactivation decisions.

    Evaluates whether an active model should move to standby. Triggered
    after each request or on state change (quota exhausted, error
    threshold exceeded, maintenance window entered).
    """

    @abstractmethod
    def should_deactivate(self, state: ModelState) -> bool:
        """Return True if the model should be moved to standby."""
        ...

    @abstractmethod
    def get_reason(self, state: ModelState) -> Optional[DeactivationReason]:
        """Return the reason for deactivation, or None if not applicable."""
        ...


class RecoveryPolicy(ABC):
    """Abstract interface for model recovery decisions.

    Evaluates whether a standby model should return to active. Triggered
    on timer expiry, calendar event, probe result, or manual command.
    """

    @abstractmethod
    def should_recover(self, state: ModelState) -> bool:
        """Return True if the model should be reactivated."""
        ...

    @abstractmethod
    def get_recovery_schedule(self, state: ModelState) -> Optional[float]:
        """Return the timestamp when recovery should be attempted, or None."""
        ...


class SelectionStrategy(ABC):
    """Abstract interface for choosing a model from active candidates.

    Considers cost, latency, rate-limit headroom, session affinity, or
    custom scoring to pick the best model for a given request.
    """

    @abstractmethod
    def select(
        self,
        candidates: list[ModelState],
        request: CompletionRequest,
    ) -> Optional[ModelState]:
        """Choose the best model from active candidates for the request.

        Returns None if no suitable candidate is available.
        """
        ...

    @abstractmethod
    def score(self, state: ModelState, request: CompletionRequest) -> float:
        """Score a single candidate for ranking purposes.

        Higher scores indicate better suitability for the request.
        """
        ...


__all__ = [
    "ModelStatus",
    "DeactivationReason",
    "RecoveryTrigger",
    "ModelState",
    "DeactivationPolicy",
    "RecoveryPolicy",
    "SelectionStrategy",
]
