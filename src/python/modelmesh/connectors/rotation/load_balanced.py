"""Load-balanced rotation policy connector.

Distributes requests across models proportionally to their configured
weight, achieving weighted round-robin load balancing. Models with
higher weights receive proportionally more traffic.

Connector ID: ``modelmesh.load-balanced.v1``
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
    "LoadBalancedConfig",
    "LoadBalancedPolicy",
]


@dataclass
class LoadBalancedConfig(BaseRotationConfig):
    """Configuration for the load-balanced rotation policy.

    Attributes:
        model_weights: Per-model traffic weights. Higher weight means
            more traffic. Default weight is 1 for unlisted models.
    """

    model_weights: dict[str, float] = field(default_factory=dict)


class LoadBalancedSelectionStrategy(BaseSelectionStrategy):
    """Weighted round-robin selection.

    Selects the active model that is furthest below its expected
    traffic share, based on configured weights. This achieves
    proportional distribution over time.
    """

    def __init__(self, config: LoadBalancedConfig) -> None:
        super().__init__(config)
        self._lb_config = config

    def _weight(self, model_id: str) -> float:
        return self._lb_config.model_weights.get(model_id, 1.0)

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

        total_weight = sum(self._weight(c.model_id) for c in active)
        if total_weight <= 0:
            return active[0]

        total_reqs = sum(c.total_requests for c in active)
        if total_reqs == 0:
            # No history yet: pick highest weight
            return max(active, key=lambda c: self._weight(c.model_id))

        # Pick the model furthest below its expected share
        best = None
        best_deficit = float("-inf")
        for c in active:
            expected_share = self._weight(c.model_id) / total_weight
            actual_share = (
                c.total_requests / total_reqs if total_reqs > 0 else 0.0
            )
            deficit = expected_share - actual_share
            if deficit > best_deficit:
                best_deficit = deficit
                best = c
        return best

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        """Score by weight (higher weight = higher score)."""
        return self._weight(state.model_id)


class LoadBalancedPolicy:
    """Load-balanced rotation policy bundle.

    Distributes traffic proportionally to model weights, with
    threshold-based deactivation and cooldown-based recovery.

    Connector ID: ``modelmesh.load-balanced.v1``
    """

    CONNECTOR_ID: str = "modelmesh.load-balanced.v1"

    def __init__(self, config: LoadBalancedConfig | None = None) -> None:
        if config is None:
            config = LoadBalancedConfig()
        self._config = config
        self._deactivation = BaseDeactivationPolicy(config)
        self._recovery = BaseRecoveryPolicy(config)
        self._selection = LoadBalancedSelectionStrategy(config)

    @property
    def deactivation(self) -> BaseDeactivationPolicy:
        return self._deactivation

    @property
    def recovery(self) -> BaseRecoveryPolicy:
        return self._recovery

    @property
    def selection(self) -> LoadBalancedSelectionStrategy:
        return self._selection
