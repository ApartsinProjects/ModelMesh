---
layout: default
title: "ModelState"
---

# ModelState

Per-model health and usage tracking dataclass. Updated after each request and persisted through the `StateManager`. Serializable for storage and recovery across restarts. This is a data structure, not a service.

**Depends on:** [StateManager](StateManager.md) (for persistence).

---

## Python

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelState:
    """Per-model health and usage tracking."""

    status: str = "active"
    """Current status: 'active' or 'standby'."""

    failure_count: int = 0
    """Consecutive failures since last success."""

    error_rate: float = 0.0
    """Error rate over sliding window (0.0-1.0)."""

    cooldown_remaining: float = 0.0
    """Time remaining in seconds before recovery eligibility."""

    quota_used: int = 0
    """Requests consumed in current quota period."""

    tokens_used: int = 0
    """Tokens consumed in current quota period."""

    cost_accumulated: float = 0.0
    """Cost accumulated in current budget period (USD)."""

    latency_history: list[float] = field(default_factory=list)
    """Recent request latencies in seconds for scoring."""

    last_request: float | None = None
    """Unix timestamp of last successful request."""

    last_failure: float | None = None
    """Unix timestamp of last failure."""

    deactivation_reason: str | None = None
    """Reason for standby status (if applicable).  Values include:
    'error_threshold', 'quota_exhausted', 'budget_exceeded',
    'token_limit', 'request_limit', 'maintenance_window', 'manual'.
    """

    # --- query methods ----------------------------------------------------

    def is_healthy(self) -> bool:
        """Return True if the model is active with no excessive failures.

        A model is healthy when its status is 'active' and its error rate
        is below the configured threshold.

        Returns:
            True if the model is considered healthy.
        """
        ...

    def is_over_quota(self) -> bool:
        """Return True if the model has exceeded its quota limit.

        Returns:
            True if quota_used exceeds the configured request or token
            limit.
        """
        ...

    def is_over_budget(self) -> bool:
        """Return True if the model has exceeded its budget limit.

        Returns:
            True if cost_accumulated exceeds the configured budget limit.
        """
        ...

    # --- mutation methods -------------------------------------------------

    def record_success(
        self,
        latency: float,
        tokens: int,
        cost: float,
    ) -> None:
        """Record a successful request.

        Resets the consecutive failure count, appends to latency history,
        and increments quota and cost counters.

        Args:
            latency: Request latency in seconds.
            tokens: Tokens consumed by the request.
            cost: Cost of the request in USD.
        """
        ...

    def record_failure(self, error: Exception) -> None:
        """Record a failed request.

        Increments the consecutive failure count, updates the error rate
        over the sliding window, and records the failure timestamp.

        Args:
            error: The exception raised by the provider.
        """
        ...

    # --- serialization ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the state to a dictionary for persistence.

        Returns:
            Dictionary representation of all state fields.
        """
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelState:
        """Deserialize a state from a dictionary.

        Args:
            data: Dictionary previously produced by to_dict().

        Returns:
            A restored ModelState instance.
        """
        ...
```

---

## TypeScript

```typescript
interface ModelStateData {
  status: string;
  failureCount: number;
  errorRate: number;
  cooldownRemaining: number;
  quotaUsed: number;
  tokensUsed: number;
  costAccumulated: number;
  latencyHistory: number[];
  lastRequest: number | null;
  lastFailure: number | null;
  deactivationReason: string | null;
}

class ModelState implements ModelStateData {
  status: string;
  failureCount: number;
  errorRate: number;
  cooldownRemaining: number;
  quotaUsed: number;
  tokensUsed: number;
  costAccumulated: number;
  latencyHistory: number[];
  lastRequest: number | null;
  lastFailure: number | null;
  deactivationReason: string | null;

  constructor(data?: Partial<ModelStateData>);

  /** Return true if the model is active with no excessive failures. */
  isHealthy(): boolean;

  /** Return true if the model has exceeded its quota limit. */
  isOverQuota(): boolean;

  /** Return true if the model has exceeded its budget limit. */
  isOverBudget(): boolean;

  /** Record a successful request. */
  recordSuccess(latency: number, tokens: number, cost: number): void;

  /** Record a failed request. */
  recordFailure(error: Error): void;

  /** Serialize the state to a plain object for persistence. */
  toDict(): ModelStateData;

  /** Deserialize a state from a plain object. */
  static fromDict(data: ModelStateData): ModelState;
}
```

---

## Fields Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Current status: `active` or `standby` |
| `failure_count` | integer | Consecutive failures since last success |
| `error_rate` | float | Error rate over sliding window (0.0-1.0) |
| `cooldown_remaining` | duration | Time remaining before recovery eligibility |
| `quota_used` | integer | Requests consumed in current quota period |
| `tokens_used` | integer | Tokens consumed in current quota period |
| `cost_accumulated` | number | Cost accumulated in current budget period (USD) |
| `latency_history` | list | Recent request latencies for scoring |
| `last_request` | timestamp | Time of last successful request |
| `last_failure` | timestamp | Time of last failure |
| `deactivation_reason` | string | Reason for standby status (if applicable) |
