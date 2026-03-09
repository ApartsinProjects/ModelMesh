# RecoveryEvaluator

Evaluates whether standby models should return to active status. The evaluator is triggered on timer expiry, calendar events (quota reset), health probe results, manual commands, or startup probes. It inspects the current model snapshot and determines whether the conditions that caused deactivation have been resolved, optionally returning a scheduled recovery time for deferred reactivation.

**Depends on:** [ModelState](ModelState.md), [RotationPolicyService](RotationPolicyService.md)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RecoveryTrigger(Enum):
    """Event that triggered a model's recovery from standby to active."""
    COOLDOWN_EXPIRED = "cooldown_expired"
    QUOTA_RESET = "quota_reset"
    PROBE_SUCCESS = "probe_success"
    MANUAL = "manual"
    STARTUP_PROBE = "startup_probe"


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


class RecoveryEvaluator:
    """Evaluates whether a standby model should return to active.

    Triggered on timer expiry, calendar event, probe result, or
    manual command. Checks whether deactivation conditions have
    cleared and the model is eligible for reactivation.
    """

    def should_recover(self, snapshot: ModelSnapshot) -> bool:
        """Return True if the model should return to active status.

        Evaluates recovery eligibility based on the deactivation reason:
        - ERROR_THRESHOLD / QUOTA_EXHAUSTED: checks cooldown expiry
        - BUDGET_EXCEEDED: checks budget period reset
        - MAINTENANCE_WINDOW: checks window exit
        - MANUAL: always returns False (requires explicit recovery)

        Args:
            snapshot: Current point-in-time state of the standby model.

        Returns:
            True if the model is eligible for recovery.
        """
        ...

    def get_recovery_schedule(self, snapshot: ModelSnapshot) -> Optional[datetime]:
        """Return the next scheduled recovery time for a standby model.

        Calculates when the model will next be eligible for recovery
        based on cooldown timers, quota reset schedules, or maintenance
        window boundaries.

        Args:
            snapshot: Current point-in-time state of the standby model.

        Returns:
            The next recovery datetime, or None if recovery requires
            a manual trigger or probe success.
        """
        ...
```

## TypeScript

```typescript
/** Event that triggered a model's recovery from standby to active. */
enum RecoveryTrigger {
    COOLDOWN_EXPIRED = "cooldown_expired",
    QUOTA_RESET = "quota_reset",
    PROBE_SUCCESS = "probe_success",
    MANUAL = "manual",
    STARTUP_PROBE = "startup_probe",
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

/** Evaluates whether a standby model should return to active. */
class RecoveryEvaluator {
    /**
     * Return true if the model should return to active status.
     *
     * Evaluates recovery eligibility based on cooldown expiry,
     * quota resets, probe results, and maintenance window boundaries.
     */
    shouldRecover(snapshot: ModelSnapshot): boolean {
        throw new Error("Not implemented");
    }

    /**
     * Return the next scheduled recovery time for a standby model.
     *
     * Returns null if recovery requires a manual trigger or probe success.
     */
    getRecoverySchedule(snapshot: ModelSnapshot): Date | null {
        throw new Error("Not implemented");
    }
}
```

---

## Configuration

Parameters configured per pool under the `recovery` key. See [SystemConfiguration.md -- Pools](../SystemConfiguration.md#pools) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `recovery.cooldown` | duration | Time from deactivation before recovery eligibility (e.g., `60s`). |
| `recovery.probe_on_start` | boolean | Test standby models at library startup. |
| `recovery.probe_interval` | duration | Periodically test standby models (e.g., `300s`). |
| `recovery.on_quota_reset` | boolean | Reactivate models when provider quota resets. |
| `recovery.quota_reset_schedule` | string | Calendar schedule for quota resets: `monthly`, `daily_utc`. |
