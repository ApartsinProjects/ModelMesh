---
layout: default
title: "ProviderState"
---

# ProviderState

Per-provider aggregate health tracking dataclass. Provider-level issues (authentication failure, API outage) trigger deactivation of all the provider's models across all pools. Serializable for persistence through the `StateManager`. This is a data structure, not a service.

**Depends on:** [StateManager](StateManager.html) (for persistence).

---

## Python

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderState:
    """Per-provider aggregate health tracking."""

    available: bool = True
    """Provider is operational."""

    auth_valid: bool = True
    """Authentication is valid."""

    last_probe: float | None = None
    """Unix timestamp of last health probe."""

    availability_score: float = 1.0
    """Rolling availability score (0.0-1.0)."""

    active_model_count: int = 0
    """Number of active models from this provider."""

    total_quota_used: int = 0
    """Aggregate quota consumption across all models."""

    total_cost: float = 0.0
    """Aggregate cost across all models (USD)."""

    # --- query methods ----------------------------------------------------

    def is_healthy(self) -> bool:
        """Return True if the provider is available and authenticated.

        A provider is healthy when both `available` and `auth_valid` are
        True and the availability score is above the minimum threshold.

        Returns:
            True if the provider is considered healthy.
        """
        ...

    # --- mutation methods -------------------------------------------------

    def record_probe(
        self,
        success: bool,
        latency: float | None = None,
    ) -> None:
        """Record a health probe result.

        Updates the availability score using an exponential moving average.
        Sets `available` to False if the score drops below the minimum
        threshold.

        Args:
            success: Whether the probe succeeded.
            latency: Probe response latency in seconds (if available).
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
    def from_dict(cls, data: dict[str, Any]) -> ProviderState:
        """Deserialize a state from a dictionary.

        Args:
            data: Dictionary previously produced by to_dict().

        Returns:
            A restored ProviderState instance.
        """
        ...
```

---

## TypeScript

```typescript
interface ProviderStateData {
  available: boolean;
  authValid: boolean;
  lastProbe: number | null;
  availabilityScore: number;
  activeModelCount: number;
  totalQuotaUsed: number;
  totalCost: number;
}

class ProviderState implements ProviderStateData {
  available: boolean;
  authValid: boolean;
  lastProbe: number | null;
  availabilityScore: number;
  activeModelCount: number;
  totalQuotaUsed: number;
  totalCost: number;

  constructor(data?: Partial<ProviderStateData>);

  /** Return true if the provider is available and authenticated. */
  isHealthy(): boolean;

  /** Record a health probe result. */
  recordProbe(success: boolean, latency?: number | null): void;

  /** Serialize the state to a plain object for persistence. */
  toDict(): ProviderStateData;

  /** Deserialize a state from a plain object. */
  static fromDict(data: ProviderStateData): ProviderState;
}
```

---

## Fields Reference

| Field | Type | Description |
| --- | --- | --- |
| `available` | boolean | Provider is operational |
| `auth_valid` | boolean | Authentication is valid |
| `last_probe` | timestamp | Time of last health probe |
| `availability_score` | float | Rolling availability score (0.0-1.0) |
| `active_model_count` | integer | Number of active models from this provider |
| `total_quota_used` | integer | Aggregate quota consumption across all models |
| `total_cost` | number | Aggregate cost across all models (USD) |
