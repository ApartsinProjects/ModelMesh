"""Rate-limit-aware rotation policy connector.

Selects the model with the most remaining quota headroom, enabling
optimal utilisation of free-tier allocations across multiple
providers. Tracks request and token counts against configurable limits
and favours models furthest from their ceiling.

Connector ID: ``modelmesh.rate-limit-aware.v1``
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
from modelmesh.interfaces.rotation import (
    DeactivationReason,
    ModelState,
)

__all__ = [
    "RateLimitAwareConfig",
    "RateLimitAwarePolicy",
]


@dataclass
class RateLimitAwareConfig(BaseRotationConfig):
    """Configuration for the rate-limit-aware rotation policy.

    Attributes:
        model_request_limits: Per-model request ceilings.
        model_token_limits: Per-model token ceilings.
    """

    model_request_limits: dict[str, int] = field(default_factory=dict)
    model_token_limits: dict[str, int] = field(default_factory=dict)


class RateLimitAwareDeactivationPolicy(BaseDeactivationPolicy):
    """Deactivation with per-model quota enforcement.

    Extends the base policy to deactivate models that have reached
    their individual request or token limit, even if the global
    limits are not yet reached.
    """

    def __init__(self, config: RateLimitAwareConfig) -> None:
        super().__init__(config)
        self._rl_config = config

    def get_reason(self, state: ModelState) -> Optional[DeactivationReason]:
        reason = super().get_reason(state)
        if reason is not None:
            return reason

        req_limit = self._rl_config.model_request_limits.get(state.model_id)
        if req_limit is not None and state.total_requests >= req_limit:
            return DeactivationReason.QUOTA_EXHAUSTED

        tok_limit = self._rl_config.model_token_limits.get(state.model_id)
        if tok_limit is not None and state.total_tokens >= tok_limit:
            return DeactivationReason.QUOTA_EXHAUSTED

        return None


class RateLimitAwareSelectionStrategy(BaseSelectionStrategy):
    """Selection strategy that prefers models with the most headroom.

    Scores each candidate by the fraction of its quota that remains
    unused. Models without configured limits receive a neutral score.
    """

    def __init__(self, config: RateLimitAwareConfig) -> None:
        super().__init__(config)
        self._rl_config = config

    def _headroom(self, state: ModelState) -> float:
        """Return remaining headroom as a fraction in [0, 1].

        Uses the minimum headroom across request and token limits.
        Returns 1.0 (full headroom) for models without limits.
        """
        fractions: list[float] = []

        req_limit = self._rl_config.model_request_limits.get(state.model_id)
        if req_limit is not None and req_limit > 0:
            fractions.append(max(0.0, 1.0 - state.total_requests / req_limit))

        tok_limit = self._rl_config.model_token_limits.get(state.model_id)
        if tok_limit is not None and tok_limit > 0:
            fractions.append(max(0.0, 1.0 - state.total_tokens / tok_limit))

        if not fractions:
            return 1.0
        return min(fractions)

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        """Score a candidate by remaining quota headroom.

        Models with more remaining quota score higher, encouraging
        even distribution of usage across rate-limited providers.
        """
        return self._headroom(state) * 100.0


class RateLimitAwarePolicy:
    """Rate-limit-aware rotation policy bundle.

    Routes to the model with the most remaining quota, with per-model
    quota deactivation and cooldown-based recovery.

    Connector ID: ``modelmesh.rate-limit-aware.v1``
    """

    CONNECTOR_ID: str = "modelmesh.rate-limit-aware.v1"

    def __init__(self, config: RateLimitAwareConfig | None = None) -> None:
        if config is None:
            config = RateLimitAwareConfig()
        self._config = config
        self._deactivation = RateLimitAwareDeactivationPolicy(config)
        self._recovery = BaseRecoveryPolicy(config)
        self._selection = RateLimitAwareSelectionStrategy(config)

    @property
    def deactivation(self) -> RateLimitAwareDeactivationPolicy:
        return self._deactivation

    @property
    def recovery(self) -> BaseRecoveryPolicy:
        return self._recovery

    @property
    def selection(self) -> RateLimitAwareSelectionStrategy:
        return self._selection
