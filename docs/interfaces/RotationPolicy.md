# Rotation Policy Interface

A rotation policy governs model lifecycle within a pool through three independently replaceable components. Rotation operates at model level (individual model moves to standby) or provider level (all models from a provider deactivated across pools). Each component receives the current model state -- failure counts, cooldown timers, quota usage, latency history -- and makes decisions accordingly.

> **Reference:** [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.md#rotation-policy) | [ConnectorCatalogue.md -- Rotation Policies](../ConnectorCatalogue.md#rotation-policies)

---

## Sub-Interfaces

| Sub-Interface | Required | Purpose |
| --- | --- | --- |
| **Deactivation** | yes | Evaluate whether an active model should move to standby |
| **Recovery** | yes | Evaluate whether a standby model should return to active |
| **Selection** | yes | Choose the best model from active candidates for a given request |

---

## Supporting Types

### Python

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ModelStatus(Enum):
    """Lifecycle status of a model within a pool."""
    ACTIVE = "active"
    STANDBY = "standby"


class DeactivationReason(Enum):
    """Reason a model was moved from active to standby."""
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
class ModelSnapshot:
    """Point-in-time snapshot of a model's operational state.

    Passed to deactivation, recovery, and selection policies so they can
    make decisions based on current health, usage, and performance data.
    """
    model_id: str
    provider_id: str
    status: ModelStatus
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
    """Result of the selection strategy choosing a model for a request."""
    model_id: str
    provider_id: str
    score: float
    reason: str
```

### TypeScript

```typescript
/** Lifecycle status of a model within a pool. */
enum ModelStatus {
    ACTIVE = "active",
    STANDBY = "standby",
}

/** Reason a model was moved from active to standby. */
enum DeactivationReason {
    ERROR_THRESHOLD = "error_threshold",
    QUOTA_EXHAUSTED = "quota_exhausted",
    BUDGET_EXCEEDED = "budget_exceeded",
    TOKEN_LIMIT = "token_limit",
    REQUEST_LIMIT = "request_limit",
    MAINTENANCE_WINDOW = "maintenance_window",
    MANUAL = "manual",
}

/** Trigger that caused a standby model to return to active. */
enum RecoveryTrigger {
    COOLDOWN_EXPIRED = "cooldown_expired",
    QUOTA_RESET = "quota_reset",
    PROBE_SUCCESS = "probe_success",
    MANUAL = "manual",
    STARTUP_PROBE = "startup_probe",
}

/** Point-in-time snapshot of a model's operational state. */
interface ModelSnapshot {
    model_id: string;
    provider_id: string;
    status: ModelStatus;
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

/** Result of the selection strategy choosing a model for a request. */
interface SelectionResult {
    model_id: string;
    provider_id: string;
    score: number;
    reason: string;
}
```

---

## Interface Definitions

### Python

```python
from abc import ABC, abstractmethod


class DeactivationPolicy(ABC):
    """Evaluate whether an active model should move to standby.

    Triggered after each request or on state change (quota exhausted,
    error threshold reached, maintenance window entered).
    """

    @abstractmethod
    def should_deactivate(self, snapshot: ModelSnapshot) -> bool:
        """Return True if the model should be moved to standby."""
        ...

    @abstractmethod
    def get_reason(self, snapshot: ModelSnapshot) -> DeactivationReason | None:
        """Return the reason for deactivation, or None if the model should stay active."""
        ...


class RecoveryPolicy(ABC):
    """Evaluate whether a standby model should return to active.

    Triggered on timer, calendar event, probe result, or manual command.
    """

    @abstractmethod
    def should_recover(self, snapshot: ModelSnapshot) -> bool:
        """Return True if the model should be reactivated."""
        ...

    @abstractmethod
    def get_recovery_schedule(self, snapshot: ModelSnapshot) -> datetime | None:
        """Return the next scheduled recovery check time, or None if not scheduled."""
        ...


class SelectionStrategy(ABC):
    """Choose the best model from active candidates for a given request.

    Considers cost, latency, rate-limit headroom, session affinity,
    or custom scoring depending on the strategy implementation.
    """

    @abstractmethod
    def select(
        self, candidates: list[ModelSnapshot], request: "CompletionRequest"
    ) -> SelectionResult:
        """Select the best model from the candidate list for the given request."""
        ...

    @abstractmethod
    def score(
        self, candidate: ModelSnapshot, request: "CompletionRequest"
    ) -> float:
        """Score a single candidate for the given request. Higher is better."""
        ...
```

Note: `CompletionRequest` is imported from the [Provider interface](Provider.md).

### TypeScript

```typescript
/** Evaluate whether an active model should move to standby. */
interface DeactivationPolicy {
    /** Return true if the model should be moved to standby. */
    shouldDeactivate(snapshot: ModelSnapshot): boolean;

    /** Return the reason for deactivation, or null if the model should stay active. */
    getReason(snapshot: ModelSnapshot): DeactivationReason | null;
}

/** Evaluate whether a standby model should return to active. */
interface RecoveryPolicy {
    /** Return true if the model should be reactivated. */
    shouldRecover(snapshot: ModelSnapshot): boolean;

    /** Return the next scheduled recovery check time, or null if not scheduled. */
    getRecoverySchedule(snapshot: ModelSnapshot): Date | null;
}

/** Choose the best model from active candidates for a given request. */
interface SelectionStrategy {
    /** Select the best model from the candidate list for the given request. */
    select(candidates: ModelSnapshot[], request: CompletionRequest): SelectionResult;

    /** Score a single candidate for the given request. Higher is better. */
    score(candidate: ModelSnapshot, request: CompletionRequest): number;
}
```

---

## Common Configuration

Parameters shared by all rotation policies. Configured per pool; policies receive these through the pool context.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `rotation.deactivation.retry_limit` | integer | `3` | Consecutive failures before deactivation. |
| `rotation.deactivation.error_rate_threshold` | float | `0.5` | Error rate over sliding window (0.0--1.0) before deactivation. |
| `rotation.deactivation.error_codes` | list | `[429, 500, 503]` | HTTP codes that count toward deactivation. |
| `rotation.deactivation.request_limit` | integer | -- | Max requests before deactivation (free-tier cap). |
| `rotation.deactivation.token_limit` | integer | -- | Max tokens before deactivation. |
| `rotation.deactivation.budget_limit` | number | -- | Max spend (USD) before deactivation. |
| `rotation.deactivation.quota_window` | string | -- | Deactivate when quota period expires: `monthly`, `daily`. |
| `rotation.deactivation.maintenance_window` | string | -- | Scheduled deactivation (cron expression). |
| `rotation.recovery.cooldown` | duration | `60s` | Time from deactivation before reactivation. |
| `rotation.recovery.probe_on_start` | boolean | `false` | Test standby models at library startup. |
| `rotation.recovery.probe_interval` | duration | `300s` | Periodically test standby models. |
| `rotation.recovery.on_quota_reset` | boolean | `true` | Reactivate when provider quota resets. |
| `rotation.recovery.quota_reset_schedule` | string | `monthly` | Calendar schedule for quota resets: `monthly`, `daily_utc`. |
| `rotation.selection.model_priority` | list | -- | Ordered model preference list. |
| `rotation.selection.provider_priority` | list | -- | Ordered provider preference list. |
| `rotation.selection.fallback_strategy` | string | `round-robin` | Strategy after priority list exhausted. |
| `rotation.selection.balance_mode` | string | `relative` | For load-balanced: `absolute` or `relative` distribution. |
| `rotation.selection.rate_limit.threshold` | float | `0.8` | Switch models at this fraction of the limit (0.0--1.0). |
| `rotation.selection.rate_limit.min_delta` | duration | -- | Minimum time between requests to the same model. |
| `rotation.selection.rate_limit.max_rpm` | integer | -- | Max requests per minute before switching models. |
| `rotation.provider_deactivation` | string | `on_auth_failure` | Deactivate all models of a provider across all pools: `on_auth_failure`, `on_api_outage`. |
| `rotation.provider_recovery` | string | `on_probe_success` | Reactivate all models when provider recovers: `on_probe_success`, `on_manual`. |

---

## CDK Base Class

The CDK provides [BaseRotationPolicy](../cdk/BaseClasses.md#baserotationpolicy) with threshold-based deactivation, cooldown recovery, and priority selection. Specialized class: [ThresholdRotationPolicy](../cdk/BaseClasses.md#thresholdrotationpolicy). See [DeveloperGuide -- Tutorial 3](../cdk/DeveloperGuide.md#tutorial-3-custom-rotation-policy-from-scratch).
