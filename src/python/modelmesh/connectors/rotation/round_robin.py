"""Round-robin rotation policy connector.

Distributes requests evenly across all active models by cycling
through them in order. Each call to ``select`` advances an internal
index so that no single model is favoured.

Connector ID: ``modelmesh.round-robin.v1``
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from modelmesh.cdk.base_rotation import (
    BaseDeactivationPolicy,
    BaseRecoveryPolicy,
    BaseRotationConfig,
)
from modelmesh.interfaces.provider import CompletionRequest
from modelmesh.interfaces.rotation import (
    ModelState,
    SelectionStrategy,
)

__all__ = ["RoundRobinConfig", "RoundRobinPolicy"]


@dataclass
class RoundRobinConfig(BaseRotationConfig):
    """Configuration for the round-robin rotation policy."""
    pass


class _RoundRobinSelection(SelectionStrategy):
    """Cycle through active models in order."""

    def __init__(self) -> None:
        self._index: int = 0

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
        self._index = self._index % len(active)
        selected = active[self._index]
        self._index = (self._index + 1) % len(active)
        return selected

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        return 1.0 - state.error_rate


class RoundRobinPolicy:
    """Round-robin rotation policy bundle.

    Distributes requests evenly across active models in a cyclic
    fashion while using standard threshold-based deactivation and
    cooldown-based recovery.

    Connector ID: ``modelmesh.round-robin.v1``
    """

    CONNECTOR_ID: str = "modelmesh.round-robin.v1"

    def __init__(self, config: RoundRobinConfig | None = None) -> None:
        if config is None:
            config = RoundRobinConfig()
        self._config = config
        self._deactivation = BaseDeactivationPolicy(config)
        self._recovery = BaseRecoveryPolicy(config)
        self._selection = _RoundRobinSelection()

    @property
    def deactivation(self) -> BaseDeactivationPolicy:
        return self._deactivation

    @property
    def recovery(self) -> BaseRecoveryPolicy:
        return self._recovery

    @property
    def selection(self) -> _RoundRobinSelection:
        return self._selection
