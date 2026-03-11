"""Priority-selection rotation policy connector.

Routes requests to models in a strict static order defined by a
priority list. The first available (active) model in the list always
wins. Falls back to lowest error rate when no prioritised model is
active.

Connector ID: ``modelmesh.priority-selection.v1``
"""
from __future__ import annotations

from dataclasses import dataclass

from modelmesh.cdk.base_rotation import (
    BaseDeactivationPolicy,
    BaseRecoveryPolicy,
    BaseRotationConfig,
    BaseSelectionStrategy,
)
from modelmesh.interfaces.provider import CompletionRequest
from modelmesh.interfaces.rotation import ModelState

__all__ = [
    "PrioritySelectionConfig",
    "PrioritySelectionPolicy",
]


@dataclass
class PrioritySelectionConfig(BaseRotationConfig):
    """Configuration for the priority-selection rotation policy.

    Attributes:
        model_priority: Ordered list of model IDs.  The first active
            model in this list is always selected.
    """
    pass


class PrioritySelectionStrategy(BaseSelectionStrategy):
    """Strict priority-list selection.

    Scores prioritised models with descending weights (1000+)
    so the first active model in the priority list always wins.
    Non-prioritised models score as ``1.0 - error_rate``.
    """

    def __init__(self, config: PrioritySelectionConfig) -> None:
        super().__init__(config)

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        """Score by position in the priority list."""
        prio = self._config.model_priority
        if state.model_id in prio:
            idx = prio.index(state.model_id)
            return 1000.0 + (len(prio) - idx)

        pprio = self._config.provider_priority
        pid = state.provider_id
        if pid and pid in pprio:
            idx = pprio.index(pid)
            return 500.0 + (len(pprio) - idx)

        return 1.0 - state.error_rate


class PrioritySelectionPolicy:
    """Priority-selection rotation policy bundle.

    Always routes to the highest-priority active model, with
    threshold-based deactivation and cooldown-based recovery.

    Connector ID: ``modelmesh.priority-selection.v1``
    """

    CONNECTOR_ID: str = "modelmesh.priority-selection.v1"

    def __init__(self, config: PrioritySelectionConfig | None = None) -> None:
        if config is None:
            config = PrioritySelectionConfig()
        self._config = config
        self._deactivation = BaseDeactivationPolicy(config)
        self._recovery = BaseRecoveryPolicy(config)
        self._selection = PrioritySelectionStrategy(config)

    @property
    def deactivation(self) -> BaseDeactivationPolicy:
        return self._deactivation

    @property
    def recovery(self) -> BaseRecoveryPolicy:
        return self._recovery

    @property
    def selection(self) -> PrioritySelectionStrategy:
        return self._selection
