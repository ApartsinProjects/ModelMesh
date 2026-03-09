---
layout: default
title: "DeactivationEvaluator"
---

# DeactivationEvaluator

Evaluates whether active models should move to standby status. The evaluator is triggered after each request completion or on state change events such as quota exhaustion, error threshold breach, budget cap, or maintenance window entry. It inspects the current model snapshot and returns a boolean decision along with an optional reason code that is recorded in the model's state history.

**Depends on:** [ModelState](ModelState.html), [RotationPolicyService](RotationPolicyService.html)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DeactivationReason(Enum):
    """Reason code recorded when a model is moved to standby."""
    ERROR_THRESHOLD = "error_threshold"
    QUOTA_EXHAUSTED = "quota_exhausted"
    BUDGET_EXCEEDED = "budget_exceeded"
    TOKEN_LIMIT = "token_limit"
    REQUEST_LIMIT = "request_limit"
    MAINTENANCE_WINDOW = "maintenance_window"
    MANUAL = "manual"


@dataclass
class ModelSnapshot:
    """Point-in-time view of a model's runtime state used for evaluation."""
    model_id: str
    provider_id: str
    status: str
    failure_count: int
    error_rate: float
    cooldown_remaining: float
    quota_used: int
    tokens_used: int
    cost_accumulated: float
    latency_history: list[float] = field(default_factory=list)
    last_request: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    deactivation_reason: Optional[str] = None


class DeactivationEvaluator:
    """Evaluates whether an active model should move to standby.

    Triggered after each request or on state change (quota exhausted,
    error threshold reached, budget exceeded, maintenance window entered).
    """

    def should_deactivate(self, snapshot: ModelSnapshot) -> bool:
        """Return True if the model should move to standby.

        Checks all configured thresholds (error rate, consecutive failures,
        quota usage, token consumption, budget, and maintenance windows)
        against the current model snapshot.

        Args:
            snapshot: Current point-in-time state of the model.

        Returns:
            True if any deactivation condition is met.
        """
        ...

    def get_reason(self, snapshot: ModelSnapshot) -> Optional[DeactivationReason]:
        """Return the specific reason the model should be deactivated.

        When multiple conditions are met simultaneously, returns the
        highest-priority reason in the order: MAINTENANCE_WINDOW,
        BUDGET_EXCEEDED, QUOTA_EXHAUSTED, ERROR_THRESHOLD, TOKEN_LIMIT,
        REQUEST_LIMIT.

        Args:
            snapshot: Current point-in-time state of the model.

        Returns:
            The deactivation reason, or None if no condition is met.
        """
        ...
```

## TypeScript

```typescript
/** Reason code recorded when a model is moved to standby. */
enum DeactivationReason {
    ERROR_THRESHOLD = "error_threshold",
    QUOTA_EXHAUSTED = "quota_exhausted",
    BUDGET_EXCEEDED = "budget_exceeded",
    TOKEN_LIMIT = "token_limit",
    REQUEST_LIMIT = "request_limit",
    MAINTENANCE_WINDOW = "maintenance_window",
    MANUAL = "manual",
}

/** Point-in-time view of a model's runtime state used for evaluation. */
interface ModelSnapshot {
    model_id: string;
    provider_id: string;
    status: string;
    failure_count: number;
    error_rate: number;
    cooldown_remaining: number;
    quota_used: number;
    tokens_used: number;
    cost_accumulated: number;
    latency_history: number[];
    last_request?: Date;
    last_failure?: Date;
    deactivation_reason?: string;
}

/** Evaluates whether an active model should move to standby. */
class DeactivationEvaluator {
    /**
     * Return true if the model should move to standby.
     *
     * Checks all configured thresholds against the current model snapshot.
     */
    shouldDeactivate(snapshot: ModelSnapshot): boolean {
        throw new Error("Not implemented");
    }

    /**
     * Return the specific reason the model should be deactivated.
     *
     * Returns null if no deactivation condition is met.
     */
    getReason(snapshot: ModelSnapshot): DeactivationReason | null {
        throw new Error("Not implemented");
    }
}
```

---

## Configuration

Parameters configured per pool under the `deactivation` key. See [SystemConfiguration.md -- Pools](../SystemConfiguration.html#pools) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `deactivation.retry_limit` | integer | Consecutive failures before deactivation. |
| `deactivation.error_rate_threshold` | float | Error rate over sliding window (0.0--1.0) that triggers deactivation. |
| `deactivation.error_codes` | list | HTTP status codes that count toward deactivation (e.g., `[429, 500, 503]`). |
| `deactivation.request_limit` | integer | Maximum requests before deactivation (free-tier cap). |
| `deactivation.token_limit` | integer | Maximum tokens consumed before deactivation. |
| `deactivation.budget_limit` | number | Maximum spend in USD before deactivation. |
| `deactivation.quota_window` | string | Deactivate on quota period expiry: `monthly`, `daily`. |
| `deactivation.maintenance_window` | string | Scheduled deactivation expressed as a cron expression. |
