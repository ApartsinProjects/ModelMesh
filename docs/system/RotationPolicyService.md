---
layout: default
title: "RotationPolicyService"
---

# RotationPolicyService

Composite rotation governance object managing model lifecycle within a capability pool. Contains three independently replaceable components: deactivation evaluation, recovery evaluation, and selection strategy. Each component receives the current model state and makes decisions accordingly. Operates at model level (individual model to standby) or provider level (all models from a provider deactivated across pools). Named `RotationPolicyService` to distinguish from the conceptual rotation policy described in [SystemConcept.md](../SystemConcept.html).

**Depends on:** [DeactivationEvaluator](DeactivationEvaluator.html), [RecoveryEvaluator](RecoveryEvaluator.html), [SelectionStrategy](SelectionStrategy.html).

---

## Python

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class DeactivationReason(Enum):
    """Reasons a model may be moved to standby."""

    ERROR_THRESHOLD = "error_threshold"
    """Consecutive failure count exceeded the configured limit."""

    QUOTA_EXHAUSTED = "quota_exhausted"
    """Request or token quota has been fully consumed."""

    BUDGET_EXCEEDED = "budget_exceeded"
    """Spend cap for the budget period has been reached."""

    TOKEN_LIMIT = "token_limit"
    """Token consumption limit has been reached."""

    REQUEST_LIMIT = "request_limit"
    """Request count limit has been reached (free-tier cap)."""

    MAINTENANCE_WINDOW = "maintenance_window"
    """Scheduled maintenance window is active."""

    MANUAL = "manual"
    """An operator manually deactivated the model."""


class RecoveryTrigger(Enum):
    """Triggers that return a standby model to active."""

    COOLDOWN_EXPIRED = "cooldown_expired"
    """The configured cooldown duration has elapsed."""

    QUOTA_RESET = "quota_reset"
    """The provider's quota period has reset."""

    PROBE_SUCCESS = "probe_success"
    """A health probe to the standby model succeeded."""

    MANUAL = "manual"
    """An operator manually recovered the model."""

    STARTUP_PROBE = "startup_probe"
    """A startup probe to the standby model succeeded."""


@dataclass
class ModelSnapshot:
    """Point-in-time snapshot of a model's operational state.

    Passed to deactivation, recovery, and selection policies so they can
    make decisions based on current health, usage, and performance data.
    """
    model_id: str
    provider_id: str
    status: str
    failure_count: int
    error_rate: float
    cooldown_remaining: Optional[float] = None
    quota_used: int = 0
    tokens_used: int = 0
    cost_accumulated: float = 0.0
    latency_avg: Optional[float] = None
    last_request: Optional[datetime] = None
    last_failure: Optional[datetime] = None


@dataclass
class SelectionResult:
    """Result of the selection strategy."""

    model: Model
    """The selected model."""

    score: float
    """Numeric score assigned to the selected model."""

    fallback_chain: list[Model]
    """Ordered fallback candidates if the primary fails."""


# --------------------------------------------------------------------------
# Component: DeactivationEvaluator
# --------------------------------------------------------------------------

class DeactivationEvaluator:
    """Evaluates whether an active model should move to standby."""

    def should_deactivate(self, snapshot: ModelSnapshot) -> bool:
        """Return True if the model should move to standby.

        Args:
            snapshot: Current point-in-time state of the model.

        Returns:
            True if deactivation criteria are met.
        """
        ...

    def get_reason(self, snapshot: ModelSnapshot) -> DeactivationReason | None:
        """Return the deactivation reason, or None if no criteria are met.

        Args:
            snapshot: Current point-in-time state of the model.

        Returns:
            The applicable DeactivationReason, or None.
        """
        ...


# --------------------------------------------------------------------------
# Component: RecoveryEvaluator
# --------------------------------------------------------------------------

class RecoveryEvaluator:
    """Evaluates whether a standby model should return to active."""

    def should_recover(self, snapshot: ModelSnapshot) -> bool:
        """Return True if the model should return to active.

        Args:
            snapshot: Current point-in-time state of the standby model.

        Returns:
            True if recovery criteria are met.
        """
        ...

    def get_recovery_schedule(
        self,
        snapshot: ModelSnapshot,
    ) -> float | None:
        """Return the next scheduled recovery time as a Unix timestamp,
        or None if no recovery is scheduled.

        Args:
            snapshot: Current point-in-time state of the standby model.

        Returns:
            Unix timestamp of next recovery, or None.
        """
        ...


# --------------------------------------------------------------------------
# Component: SelectionStrategy
# --------------------------------------------------------------------------

class SelectionStrategy:
    """Chooses the best model from active candidates for a given request.

    Pre-shipped strategies:
        - modelmesh.stick-until-failure.v1 (default)
        - modelmesh.priority-selection.v1
        - modelmesh.round-robin.v1
        - modelmesh.cost-first.v1
        - modelmesh.latency-first.v1
        - modelmesh.session-stickiness.v1
        - modelmesh.rate-limit-aware.v1
        - modelmesh.load-balanced.v1
    """

    def select(
        self,
        candidates: list[ModelSnapshot],
        request: CompletionRequest,
    ) -> SelectionResult:
        """Return the best candidate for the request.

        Args:
            candidates: Active model snapshots available for selection.
            request: The completion request for context-aware scoring.

        Returns:
            A SelectionResult identifying the chosen model with its score.

        Raises:
            NoAvailableModelError: If candidates list is empty.
        """
        ...

    def score(self, candidate: ModelSnapshot, request: CompletionRequest) -> float:
        """Return a numeric score for a single candidate.

        Higher scores indicate better suitability. Used internally by
        select() for ranking.

        Args:
            candidate: A single candidate model snapshot.
            request: The completion request for context-aware scoring.

        Returns:
            Numeric score (higher is better).
        """
        ...


# --------------------------------------------------------------------------
# Composite: RotationPolicyService
# --------------------------------------------------------------------------

class RotationPolicyService:
    """Composite rotation governance wrapping deactivation, recovery, and
    selection components.
    """

    _deactivation_evaluator: DeactivationEvaluator
    _recovery_evaluator: RecoveryEvaluator
    _selection_strategy: SelectionStrategy

    def __init__(
        self,
        deactivation_evaluator: DeactivationEvaluator,
        recovery_evaluator: RecoveryEvaluator,
        selection_strategy: SelectionStrategy,
    ) -> None:
        self._deactivation_evaluator = deactivation_evaluator
        self._recovery_evaluator = recovery_evaluator
        self._selection_strategy = selection_strategy

    def evaluate_deactivation(
        self,
        model: Model,
    ) -> tuple[bool, DeactivationReason | None]:
        """Evaluate whether a model should be deactivated.

        Delegates to the DeactivationEvaluator.

        Args:
            model: The model to evaluate.

        Returns:
            A tuple of (should_deactivate, reason).  reason is None when
            should_deactivate is False.
        """
        ...

    def evaluate_recovery(
        self,
        model: Model,
    ) -> tuple[bool, RecoveryTrigger | None]:
        """Evaluate whether a standby model should recover.

        Delegates to the RecoveryEvaluator.

        Args:
            model: The standby model to evaluate.

        Returns:
            A tuple of (should_recover, trigger).  trigger is None when
            should_recover is False.
        """
        ...

    def select_model(
        self,
        candidates: list[Model],
        request: CompletionRequest,
    ) -> SelectionResult:
        """Select the best model from candidates for the request.

        Delegates to the SelectionStrategy.

        Args:
            candidates: Active models available for selection.
            request: The completion request for context-aware scoring.

        Returns:
            A SelectionResult with the selected model, score, and
            fallback chain.
        """
        ...
```

---

## TypeScript

```typescript
enum DeactivationReason {
  /** Consecutive failure count exceeded the configured limit. */
  ERROR_THRESHOLD = "error_threshold",
  /** Request or token quota has been fully consumed. */
  QUOTA_EXHAUSTED = "quota_exhausted",
  /** Spend cap for the budget period has been reached. */
  BUDGET_EXCEEDED = "budget_exceeded",
  /** Token consumption limit has been reached. */
  TOKEN_LIMIT = "token_limit",
  /** Request count limit has been reached (free-tier cap). */
  REQUEST_LIMIT = "request_limit",
  /** Scheduled maintenance window is active. */
  MAINTENANCE_WINDOW = "maintenance_window",
  /** An operator manually deactivated the model. */
  MANUAL = "manual",
}

enum RecoveryTrigger {
  /** The configured cooldown duration has elapsed. */
  COOLDOWN_EXPIRED = "cooldown_expired",
  /** The provider's quota period has reset. */
  QUOTA_RESET = "quota_reset",
  /** A health probe to the standby model succeeded. */
  PROBE_SUCCESS = "probe_success",
  /** An operator manually recovered the model. */
  MANUAL = "manual",
  /** A startup probe to the standby model succeeded. */
  STARTUP_PROBE = "startup_probe",
}

/** Point-in-time snapshot of a model's operational state. */
interface ModelSnapshot {
  model_id: string;
  provider_id: string;
  status: string;
  failure_count: number;
  error_rate: number;
  cooldown_remaining?: number;
  quota_used: number;
  tokens_used: number;
  cost_accumulated: number;
  latency_avg?: number;
  last_request?: Date;
  last_failure?: Date;
}

interface SelectionResult {
  /** The selected model. */
  model: Model;
  /** Numeric score assigned to the selected model. */
  score: number;
  /** Ordered fallback candidates if the primary fails. */
  fallbackChain: Model[];
}

// --- Component: DeactivationEvaluator ------------------------------------

class DeactivationEvaluator {
  /** Return true if the model should move to standby. */
  shouldDeactivate(snapshot: ModelSnapshot): boolean;

  /** Return the deactivation reason, or null. */
  getReason(snapshot: ModelSnapshot): DeactivationReason | null;
}

// --- Component: RecoveryEvaluator ----------------------------------------

class RecoveryEvaluator {
  /** Return true if the model should return to active. */
  shouldRecover(snapshot: ModelSnapshot): boolean;

  /** Return the next scheduled recovery time (Unix ms), or null. */
  getRecoverySchedule(snapshot: ModelSnapshot): number | null;
}

// --- Component: SelectionStrategy ----------------------------------------

class SelectionStrategy {
  /** Return the best candidate for the request. */
  select(candidates: ModelSnapshot[], request: CompletionRequest): SelectionResult;

  /** Return a numeric score for a single candidate. */
  score(candidate: ModelSnapshot, request: CompletionRequest): number;
}

// --- Composite: RotationPolicyService ------------------------------------

class RotationPolicyService {
  private deactivationEvaluator: DeactivationEvaluator;
  private recoveryEvaluator: RecoveryEvaluator;
  private selectionStrategy: SelectionStrategy;

  constructor(
    deactivationEvaluator: DeactivationEvaluator,
    recoveryEvaluator: RecoveryEvaluator,
    selectionStrategy: SelectionStrategy,
  );

  /** Evaluate whether a model should be deactivated. */
  evaluateDeactivation(
    model: Model,
  ): [boolean, DeactivationReason | null];

  /** Evaluate whether a standby model should recover. */
  evaluateRecovery(model: Model): [boolean, RecoveryTrigger | null];

  /** Select the best model from candidates for the request. */
  selectModel(
    candidates: Model[],
    request: CompletionRequest,
  ): SelectionResult;
}
```

---

## Configuration

Rotation parameters are configured per pool under the `pools` section. See [SystemConfiguration.md -- Pools](../SystemConfiguration.html#pools).

### Deactivation Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `deactivation.retry_limit` | integer | Consecutive failures before deactivation |
| `deactivation.error_rate_threshold` | float | Error rate threshold (0.0-1.0) |
| `deactivation.error_codes` | list | HTTP codes that count toward deactivation |
| `deactivation.request_limit` | integer | Max requests before deactivation (free-tier cap) |
| `deactivation.token_limit` | integer | Max tokens before deactivation |
| `deactivation.budget_limit` | number | Max spend (USD) before deactivation |
| `deactivation.quota_window` | string | Deactivate on quota period expiry: `monthly`, `daily` |
| `deactivation.maintenance_window` | string | Scheduled deactivation (cron expression) |

### Recovery Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `recovery.cooldown` | duration | Time from deactivation before recovery eligibility |
| `recovery.probe_on_start` | boolean | Test standby models at library startup |
| `recovery.probe_interval` | duration | Periodically test standby models |
| `recovery.on_quota_reset` | boolean | Reactivate when provider quota resets |
| `recovery.quota_reset_schedule` | string | Calendar schedule for quota resets: `monthly`, `daily_utc` |

### Selection Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `strategy` | string | Selection strategy connector ID |
| `model_priority` | list | Ordered model preference list |
| `provider_priority` | list | Ordered provider preference list |
| `fallback_strategy` | string | Strategy after priority list exhausted |
| `balance_mode` | string | For load-balanced: `absolute` or `relative` |
| `rate_limit.threshold` | float | Switch models at this fraction of the limit (0.0-1.0) |
| `rate_limit.min_delta` | duration | Minimum time between requests to the same model |
| `rate_limit.max_rpm` | integer | Max requests per minute before switching |

### Pre-shipped Selection Strategies

| Strategy | Behavior |
| --- | --- |
| `modelmesh.stick-until-failure.v1` | Use the same model until it fails, then rotate (default) |
| `modelmesh.priority-selection.v1` | Always prefer the highest-priority available model |
| `modelmesh.round-robin.v1` | Cycle through active models in order |
| `modelmesh.cost-first.v1` | Select the cheapest available model |
| `modelmesh.latency-first.v1` | Select the model with lowest recent latency |
| `modelmesh.session-stickiness.v1` | Route all requests in a session to the same model |
| `modelmesh.rate-limit-aware.v1` | Switch models preemptively before hitting rate limits |
| `modelmesh.load-balanced.v1` | Distribute requests proportionally to rate-limit headroom |
