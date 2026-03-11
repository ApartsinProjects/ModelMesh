---
layout: default
title: "Discovery Interface"
---

# Discovery Interface

A discovery connector keeps the model catalogue accurate and provider health visible without manual intervention. Discovery connectors run as background processes on configurable schedules and feed results into the rotation policy for proactive deactivation.

> **Reference:** [ConnectorInterfaces.md -- Discovery](../ConnectorInterfaces.md#discovery) | [ConnectorCatalogue.md -- Discovery Connectors](../ConnectorCatalogue.md#discovery-connectors)

---

## Sub-Interfaces

| Sub-Interface | Required | Purpose |
| --- | --- | --- |
| **Registry Sync** | yes | Synchronize the local model catalogue with provider APIs |
| **Health Monitoring** | yes | Probe provider availability and performance |

---

## Supporting Types

### Python

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class SyncAction(Enum):
    """Action to take when a new model is discovered during sync."""
    REGISTER = "register"
    NOTIFY = "notify"
    IGNORE = "ignore"


class DeprecationAction(Enum):
    """Action to take when a model is detected as deprecated."""
    DEACTIVATE = "deactivate"
    NOTIFY = "notify"
    IGNORE = "ignore"


@dataclass
class SyncResult:
    """Outcome of a registry synchronization run."""
    new_models: list[str]
    deprecated_models: list[str]
    updated_models: list[str]
    errors: list[str]


@dataclass
class SyncStatus:
    """Current status of the registry synchronization process."""
    last_sync: Optional[datetime] = None
    next_sync: Optional[datetime] = None
    models_synced: int = 0
    status: str = "idle"


@dataclass
class HealthReport:
    """Health assessment for a single provider over a monitoring window."""
    provider_id: str
    available: bool
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    availability_score: float = 1.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ProbeResult:
    """Result of a single health probe against a provider."""
    provider_id: str
    success: bool
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
```

### TypeScript

```typescript
/** Action to take when a new model is discovered during sync. */
enum SyncAction {
    REGISTER = "register",
    NOTIFY = "notify",
    IGNORE = "ignore",
}

/** Action to take when a model is detected as deprecated. */
enum DeprecationAction {
    DEACTIVATE = "deactivate",
    NOTIFY = "notify",
    IGNORE = "ignore",
}

/** Outcome of a registry synchronization run. */
interface SyncResult {
    new_models: string[];
    deprecated_models: string[];
    updated_models: string[];
    errors: string[];
}

/** Current status of the registry synchronization process. */
interface SyncStatus {
    last_sync?: Date;
    next_sync?: Date;
    models_synced: number;
    status: string;
}

/** Health assessment for a single provider over a monitoring window. */
interface HealthReport {
    provider_id: string;
    available: boolean;
    latency_ms?: number;
    status_code?: number;
    error?: string;
    availability_score: number;
    timestamp: Date;
}

/** Result of a single health probe against a provider. */
interface ProbeResult {
    provider_id: string;
    success: boolean;
    latency_ms?: number;
    status_code?: number;
    error?: string;
}
```

---

## Interface Definitions

### Python

```python
from abc import ABC, abstractmethod


class RegistrySync(ABC):
    """Synchronize the local model catalogue with provider APIs.

    Detects new models, deprecated models, and pricing changes.
    Runs on a configurable schedule as a background process.
    """

    @abstractmethod
    async def sync(self, providers: list[str] | None = None) -> SyncResult:
        """Synchronize the model catalogue with the given providers.

        Args:
            providers: List of provider IDs to sync. If None, syncs all
                       enabled providers.

        Returns:
            A SyncResult describing new, deprecated, and updated models.
        """
        ...

    @abstractmethod
    async def get_sync_status(self) -> SyncStatus:
        """Return the current synchronization status."""
        ...


class HealthMonitoring(ABC):
    """Probe provider availability and performance.

    Records latency, error codes, and rolling availability scores.
    Feeds results into rotation policies for proactive deactivation.
    """

    @abstractmethod
    async def probe(self, provider_id: str) -> ProbeResult:
        """Send a health probe to the specified provider.

        Returns:
            A ProbeResult indicating success/failure, latency, and any error.
        """
        ...

    @abstractmethod
    async def get_health_report(
        self, provider_id: str | None = None
    ) -> list[HealthReport]:
        """Return health reports for one or all providers.

        Args:
            provider_id: A specific provider ID, or None for all providers.

        Returns:
            A list of HealthReport entries.
        """
        ...


class DiscoveryConnector(RegistrySync, HealthMonitoring):
    """Full discovery connector combining Registry Sync and Health Monitoring.

    Discovery connectors run as background processes on configurable
    schedules and feed results into the rotation policy for proactive
    deactivation.
    """
    pass
```

### TypeScript

```typescript
/** Synchronize the local model catalogue with provider APIs. */
interface RegistrySync {
    /**
     * Synchronize the model catalogue with the given providers.
     * @param providers - Provider IDs to sync. If omitted, syncs all enabled providers.
     */
    sync(providers?: string[]): Promise<SyncResult>;

    /** Return the current synchronization status. */
    getSyncStatus(): Promise<SyncStatus>;
}

/** Probe provider availability and performance. */
interface HealthMonitoring {
    /**
     * Send a health probe to the specified provider.
     * @returns A ProbeResult indicating success/failure, latency, and any error.
     */
    probe(providerId: string): Promise<ProbeResult>;

    /**
     * Return health reports for one or all providers.
     * @param providerId - A specific provider ID, or omit for all providers.
     */
    getHealthReport(providerId?: string): Promise<HealthReport[]>;
}

/** Full discovery connector combining Registry Sync and Health Monitoring. */
interface DiscoveryConnector extends RegistrySync, HealthMonitoring {}
```

---

## Common Configuration

Parameters shared by all discovery connectors. Individual connectors may add connector-specific parameters (see [ConnectorCatalogue.md -- Discovery Connectors](../ConnectorCatalogue.md#discovery-connectors)).

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `discovery.sync.enabled` | boolean | `true` | Enable registry synchronization. |
| `discovery.sync.interval` | duration | `1h` | Sync frequency. |
| `discovery.sync.auto_register` | boolean | `true` | Automatically register newly discovered models. |
| `discovery.sync.providers` | list | *(all enabled)* | Providers to sync. |
| `discovery.sync.on_new_model` | string | `register` | Action on new model: `register`, `notify`, `ignore`. |
| `discovery.sync.on_deprecated_model` | string | `notify` | Action on deprecated model: `deactivate`, `notify`, `ignore`. |
| `discovery.health.enabled` | boolean | `true` | Enable health monitoring. |
| `discovery.health.interval` | duration | `60s` | Probe frequency. |
| `discovery.health.timeout` | duration | `10s` | Probe timeout. |
| `discovery.health.failure_threshold` | integer | `3` | Consecutive failures before deactivation. |
| `discovery.health.providers` | list | *(all enabled)* | Providers to probe. |

---

## CDK Base Class

The CDK provides [BaseDiscovery](../cdk/BaseClasses.md#basediscovery) with diff-based sync and failure-threshold health monitoring. Specialized class: [HttpHealthDiscovery](../cdk/BaseClasses.md#httphealthdiscovery). See [DeveloperGuide -- Tutorial 5](../cdk/DeveloperGuide.md#tutorial-5-complete-connector-set-for-acmecorp).
