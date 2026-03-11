---
layout: default
title: "StateManager"
---

# StateManager

Coordinates persistence of runtime state -- ModelState, ProviderState, and pool memberships -- through the configured storage connector. The manager handles the full sync lifecycle: loading state at startup, saving on shutdown, and syncing periodically or immediately depending on the configured policy. For multi-instance deployments, advisory locking prevents concurrent writes to the same storage backend.

**Depends on:** [StorageConnector](../ConnectorInterfaces.md#storage)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SyncPolicy(Enum):
    """Policy governing when state is persisted to the storage backend."""
    IN_MEMORY = "in-memory"
    SYNC_ON_BOUNDARY = "sync-on-boundary"
    PERIODIC = "periodic"
    IMMEDIATE = "immediate"


@dataclass
class ModelState:
    """Per-model health and usage tracking."""
    status: str
    failure_count: int
    error_rate: float
    cooldown_remaining: float
    quota_used: int
    tokens_used: int
    cost_accumulated: float
    last_request: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    deactivation_reason: Optional[str] = None


@dataclass
class ProviderState:
    """Per-provider aggregate health tracking."""
    available: bool
    auth_valid: bool
    last_probe: Optional[datetime] = None
    availability_score: float = 1.0
    active_model_count: int = 0
    total_quota_used: int = 0
    total_cost: float = 0.0


@dataclass
class PoolState:
    """Per-pool membership and rotation tracking."""
    active_models: list[str] = field(default_factory=list)
    standby_models: list[str] = field(default_factory=list)
    rotation_count: int = 0
    last_rotation: Optional[datetime] = None


@dataclass
class SystemState:
    """Complete system state snapshot for persistence."""
    models: dict[str, ModelState] = field(default_factory=dict)
    providers: dict[str, ProviderState] = field(default_factory=dict)
    pools: dict[str, PoolState] = field(default_factory=dict)
    timestamp: Optional[datetime] = None


@dataclass
class LockHandle:
    """Handle representing an acquired advisory lock."""
    lock_id: str
    owner: str
    acquired_at: datetime
    expires_at: Optional[datetime] = None


@dataclass
class SyncStatus:
    """Current synchronization status of the state manager."""
    last_sync: Optional[datetime] = None
    next_sync: Optional[datetime] = None
    pending_changes: int = 0
    locked: bool = False
    lock_owner: Optional[str] = None


class StateManager:
    """Coordinates state persistence through the storage connector.

    Manages the sync policy lifecycle: loading state at startup,
    saving on shutdown, and syncing periodically or immediately
    depending on policy. Supports advisory locking for multi-instance
    coordination.
    """

    def load(self) -> Optional[SystemState]:
        """Load persisted state from the storage backend.

        Called at initialization to restore ModelState, ProviderState,
        and pool memberships from the previous session.

        Returns:
            The restored SystemState, or None if no persisted state exists.
        """
        ...

    def save(self) -> None:
        """Persist current state to the storage backend.

        Called at shutdown and on sync boundaries. Serializes the
        complete SystemState and writes it through the storage connector.
        """
        ...

    def sync(self) -> None:
        """Execute a sync cycle according to the configured policy.

        For PERIODIC policy, saves state if the sync interval has
        elapsed since last sync. For IMMEDIATE policy, saves every
        pending change. For IN_MEMORY and SYNC_ON_BOUNDARY, this
        method is a no-op outside startup/shutdown.
        """
        ...

    def get_sync_status(self) -> SyncStatus:
        """Return current synchronization status.

        Returns:
            A SyncStatus with last sync time, next scheduled sync,
            pending changes, and lock information.
        """
        ...

    def acquire_lock(self) -> LockHandle:
        """Acquire advisory lock for multi-instance coordination.

        Blocks until the lock is acquired or the configured timeout
        expires. Required for PERIODIC and IMMEDIATE sync policies
        in multi-instance deployments.

        Returns:
            A LockHandle representing the acquired lock.

        Raises:
            TimeoutError: If the lock cannot be acquired within the
                configured timeout.
        """
        ...

    def release_lock(self, lock: LockHandle) -> None:
        """Release advisory lock.

        Args:
            lock: The LockHandle returned by acquire_lock().
        """
        ...
```

## TypeScript

```typescript
/** Policy governing when state is persisted to the storage backend. */
enum SyncPolicy {
    IN_MEMORY = "in-memory",
    SYNC_ON_BOUNDARY = "sync-on-boundary",
    PERIODIC = "periodic",
    IMMEDIATE = "immediate",
}

/** Per-model health and usage tracking. */
interface ModelState {
    status: string;
    failure_count: number;
    error_rate: number;
    cooldown_remaining: number;
    quota_used: number;
    tokens_used: number;
    cost_accumulated: number;
    last_request?: Date;
    last_failure?: Date;
    deactivation_reason?: string;
}

/** Per-provider aggregate health tracking. */
interface ProviderState {
    available: boolean;
    auth_valid: boolean;
    last_probe?: Date;
    availability_score: number;
    active_model_count: number;
    total_quota_used: number;
    total_cost: number;
}

/** Per-pool membership and rotation tracking. */
interface PoolState {
    active_models: string[];
    standby_models: string[];
    rotation_count: number;
    last_rotation?: Date;
}

/** Complete system state snapshot for persistence. */
interface SystemState {
    models: Record<string, ModelState>;
    providers: Record<string, ProviderState>;
    pools: Record<string, PoolState>;
    timestamp?: Date;
}

/** Handle representing an acquired advisory lock. */
interface LockHandle {
    lock_id: string;
    owner: string;
    acquired_at: Date;
    expires_at?: Date;
}

/** Current synchronization status of the state manager. */
interface SyncStatus {
    last_sync?: Date;
    next_sync?: Date;
    pending_changes: number;
    locked: boolean;
    lock_owner?: string;
}

/** Coordinates state persistence through the storage connector. */
class StateManager {
    /**
     * Load persisted state from the storage backend.
     *
     * Returns null if no persisted state exists.
     */
    load(): SystemState | null {
        throw new Error("Not implemented");
    }

    /** Persist current state to the storage backend. */
    save(): void {
        throw new Error("Not implemented");
    }

    /** Execute a sync cycle according to the configured policy. */
    sync(): void {
        throw new Error("Not implemented");
    }

    /** Return current synchronization status. */
    getSyncStatus(): SyncStatus {
        throw new Error("Not implemented");
    }

    /**
     * Acquire advisory lock for multi-instance coordination.
     *
     * Throws TimeoutError if the lock cannot be acquired within
     * the configured timeout.
     */
    acquireLock(): LockHandle {
        throw new Error("Not implemented");
    }

    /** Release advisory lock. */
    releaseLock(lock: LockHandle): void {
        throw new Error("Not implemented");
    }
}
```

---

## Sync Policies

| Policy | Behavior |
| --- | --- |
| `in-memory` | No persistence. State is lost on shutdown. Suitable for development and testing. |
| `sync-on-boundary` | Load at startup, save at shutdown. State survives restarts but not crashes. |
| `periodic` | Sync at configurable intervals (e.g., every 5 minutes). Balances durability with write frequency. |
| `immediate` | Persist every state change. Requires advisory locking for multi-instance deployments. Maximum durability. |

---

## Configuration

See [SystemConfiguration.md -- Storage](../SystemConfiguration.md#storage) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `storage.connector` | string | Storage connector ID (e.g., `modelmesh.local-file.v1`). |
| `storage.persistence.sync_policy` | string | Sync policy: `in-memory`, `sync-on-boundary`, `periodic`, `immediate`. |
| `storage.persistence.sync_interval` | duration | Interval for `periodic` sync (e.g., `300s`). |
