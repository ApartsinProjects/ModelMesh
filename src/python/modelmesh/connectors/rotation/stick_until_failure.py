"""Stick-until-failure rotation policy connector.

Bundles the three base rotation policy components (deactivation,
recovery, selection) into a single connector with a unified
configuration. Uses the current model until it fails, then rotates
to the next candidate.

Connector ID: ``modelmesh.stick-until-failure.v1``
"""
from __future__ import annotations

from dataclasses import dataclass

from modelmesh.cdk.base_rotation import (
    BaseDeactivationPolicy,
    BaseRecoveryPolicy,
    BaseRotationConfig,
    BaseSelectionStrategy,
)

__all__ = [
    "StickUntilFailureConfig",
    "StickUntilFailurePolicy",
]


@dataclass
class StickUntilFailureConfig(BaseRotationConfig):
    """Configuration for the stick-until-failure rotation policy.

    Inherits all settings from BaseRotationConfig, including
    ``failure_threshold``, ``cooldown_seconds``, ``error_rate_threshold``,
    ``request_limit``, ``token_limit``, ``budget_limit``, and
    ``model_priority``.
    """

    pass


class StickUntilFailurePolicy:
    """Stick-until-failure rotation policy bundle.

    Combines the three rotation policy components -- deactivation,
    recovery, and selection -- into a single connector with unified
    configuration. The policy keeps using the current model until it
    fails (exceeds the failure threshold or error rate), then deactivates
    it and selects the next best candidate.

    Connector ID: ``modelmesh.stick-until-failure.v1``

    The three component policies are:

    - **Deactivation**: Threshold-based. Deactivates a model when its
      consecutive failure count or error rate exceeds the configured
      thresholds, or when quota/budget limits are exceeded.
    - **Recovery**: Cooldown-based. Reactivates a standby model after
      the configured cooldown period has elapsed.
    - **Selection**: Stick-until-failure with priority support. Picks
      the first model from the priority list, or falls back to the
      candidate with the lowest error rate.

    Usage::

        policy = StickUntilFailurePolicy(StickUntilFailureConfig(
            failure_threshold=3,
            cooldown_seconds=60.0,
        ))
        should_deactivate = policy.deactivation.should_deactivate(state)
        should_recover = policy.recovery.should_recover(state)
        selected = policy.selection.select(candidates, request)
    """

    CONNECTOR_ID: str = "modelmesh.stick-until-failure.v1"

    def __init__(self, config: StickUntilFailureConfig | None = None) -> None:
        if config is None:
            config = StickUntilFailureConfig()
        self._config = config
        self._deactivation = BaseDeactivationPolicy(config)
        self._recovery = BaseRecoveryPolicy(config)
        self._selection = BaseSelectionStrategy(config)

    @property
    def deactivation(self) -> BaseDeactivationPolicy:
        """Return the deactivation policy component.

        Evaluates whether an active model should be moved to standby
        based on failure count, error rate, and quota limits.
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
    def selection(self) -> BaseSelectionStrategy:
        """Return the selection strategy component.

        Chooses the best active model for a given request using
        priority list or lowest error rate.
        """
        return self._selection
