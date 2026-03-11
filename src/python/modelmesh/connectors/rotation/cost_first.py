"""Cost-first rotation policy connector.

Bundles the three rotation policy components (deactivation, recovery,
selection) into a single connector that favours the cheapest model.
Selection scores models by negative total cost so the least expensive
candidate always wins.

Connector ID: ``modelmesh.cost-first.v1``
"""
from __future__ import annotations

from dataclasses import dataclass
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
    "CostFirstConfig",
    "CostFirstPolicy",
]


@dataclass
class CostFirstConfig(BaseRotationConfig):
    """Configuration for the cost-first rotation policy.

    Inherits all settings from BaseRotationConfig, including
    ``failure_threshold``, ``cooldown_seconds``, ``error_rate_threshold``,
    ``request_limit``, ``token_limit``, ``budget_limit``, and
    ``model_priority``.
    """

    pass


# ── Deactivation ────────────────────────────────────────────────────────


class CostFirstDeactivationPolicy(BaseDeactivationPolicy):
    """Threshold-based deactivation with budget-limit enforcement.

    Extends the base deactivation policy with explicit budget-limit
    awareness.  When a model's cumulative cost reaches the configured
    ``budget_limit`` it is deactivated with reason
    :attr:`DeactivationReason.BUDGET_EXCEEDED`.
    """

    def __init__(self, config: CostFirstConfig) -> None:
        super().__init__(config)

    def get_reason(self, state: ModelState) -> Optional[DeactivationReason]:
        """Return the first matching deactivation reason, or None.

        Checks base thresholds first, then applies budget-limit
        enforcement.
        """
        return super().get_reason(state)


# ── Selection ───────────────────────────────────────────────────────────


class CostFirstSelectionStrategy(BaseSelectionStrategy):
    """Selection strategy that picks the cheapest model.

    Scores each candidate as ``-total_cost`` so the model with the
    lowest accumulated cost receives the highest score and is selected
    first.
    """

    def __init__(self, config: CostFirstConfig) -> None:
        super().__init__(config)

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        """Score a candidate by negative total cost.

        Lower total cost produces a higher (less negative) score,
        ensuring the cheapest model is preferred.
        """
        return -state.total_cost


# ── Policy bundle ───────────────────────────────────────────────────────


class CostFirstPolicy:
    """Cost-first rotation policy bundle.

    Combines deactivation, recovery, and selection into a single
    connector that always routes to the cheapest available model.

    Connector ID: ``modelmesh.cost-first.v1``

    The three component policies are:

    - **Deactivation**: Threshold-based with budget-limit enforcement.
      Deactivates a model when its failure count, error rate, or
      cumulative cost exceeds configured limits.
    - **Recovery**: Cooldown-based.  Reactivates a standby model after
      the configured cooldown period has elapsed.
    - **Selection**: Cost-first.  Picks the model with the lowest
      total cost so far.

    Usage::

        policy = CostFirstPolicy(CostFirstConfig(
            budget_limit=10.0,
        ))
        selected = policy.selection.select(candidates, request)
    """

    CONNECTOR_ID: str = "modelmesh.cost-first.v1"

    def __init__(self, config: CostFirstConfig | None = None) -> None:
        if config is None:
            config = CostFirstConfig()
        self._config = config
        self._deactivation = CostFirstDeactivationPolicy(config)
        self._recovery = BaseRecoveryPolicy(config)
        self._selection = CostFirstSelectionStrategy(config)

    @property
    def deactivation(self) -> CostFirstDeactivationPolicy:
        """Return the deactivation policy component.

        Evaluates whether an active model should be moved to standby
        based on failure count, error rate, and budget limits.
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
    def selection(self) -> CostFirstSelectionStrategy:
        """Return the selection strategy component.

        Chooses the cheapest active model for a given request.
        """
        return self._selection
