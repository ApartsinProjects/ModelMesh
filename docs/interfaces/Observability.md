---
layout: default
title: "Observability Interface"
---

# Observability Interface

An observability connector exports routing activity to an external output. Multiple connectors can be active simultaneously (e.g., webhook for alerts + file for dashboards). The library pushes data through the connector at four levels of detail: events for state changes, logs for request/response data, statistics for aggregate metrics, and traces for structured severity-tagged diagnostic output.

> **Reference:** [ConnectorInterfaces.md -- Observability](../ConnectorInterfaces.html#observability) | [ConnectorCatalogue.md -- Observability Connectors](../ConnectorCatalogue.html#observability-connectors)

---

## Sub-Interfaces

| Sub-Interface | Required | Purpose |
| --- | --- | --- |
| **Events** | yes | Publish routing decisions and state changes |
| **Logging** | yes | Record request/response data at configurable detail level |
| **Statistics** | yes | Buffer and flush aggregate metrics |
| **Tracing** | yes | Structured trace reporting with severity levels |

---

## Supporting Types

### Python

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(Enum):
    """Types of routing events emitted by the library."""
    MODEL_ACTIVATED = "model_activated"
    MODEL_DEACTIVATED = "model_deactivated"
    MODEL_ROTATED = "model_rotated"
    PROVIDER_HEALTH_CHANGED = "provider_health_changed"
    PROVIDER_DEACTIVATED = "provider_deactivated"
    PROVIDER_RECOVERED = "provider_recovered"
    POOL_MEMBERSHIP_CHANGED = "pool_membership_changed"
    DISCOVERY_MODELS_UPDATED = "discovery_models_updated"


class LogLevel(Enum):
    """Detail level for request/response logging."""
    METADATA = "metadata"
    SUMMARY = "summary"
    FULL = "full"


@dataclass
class RoutingEvent:
    """A routing state-change event."""
    event_type: EventType
    timestamp: datetime
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    pool_id: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class RequestLogEntry:
    """A single request/response log record."""
    timestamp: datetime
    model_id: str
    provider_id: str
    capability: str
    delivery_mode: str
    latency_ms: float
    status_code: int
    tokens_in: int
    tokens_out: int
    cost: Optional[float] = None
    error: Optional[str] = None


@dataclass
class AggregateStats:
    """Aggregate metrics for a single model, provider, or pool over a time window."""
    requests_total: int
    requests_success: int
    requests_failed: int
    tokens_in: int
    tokens_out: int
    cost_total: float
    latency_avg: float
    latency_p95: float
    downtime_total: float
    rotation_events: int


class Severity(Enum):
    """Severity levels for structured trace reporting."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class TraceEntry:
    """A structured trace/log entry with severity level."""
    severity: Severity
    timestamp: datetime
    component: str  # e.g. "router", "pool.text-generation", "provider.openai"
    message: str
    metadata: dict = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
```

### TypeScript

```typescript
/** Types of routing events emitted by the library. */
enum EventType {
    MODEL_ACTIVATED = "model_activated",
    MODEL_DEACTIVATED = "model_deactivated",
    MODEL_ROTATED = "model_rotated",
    PROVIDER_HEALTH_CHANGED = "provider_health_changed",
    PROVIDER_DEACTIVATED = "provider_deactivated",
    PROVIDER_RECOVERED = "provider_recovered",
    POOL_MEMBERSHIP_CHANGED = "pool_membership_changed",
    DISCOVERY_MODELS_UPDATED = "discovery_models_updated",
}

/** Detail level for request/response logging. */
enum LogLevel {
    METADATA = "metadata",
    SUMMARY = "summary",
    FULL = "full",
}

/** A routing state-change event. */
interface RoutingEvent {
    event_type: EventType;
    timestamp: Date;
    model_id?: string;
    provider_id?: string;
    pool_id?: string;
    metadata: Record<string, unknown>;
}

/** A single request/response log record. */
interface RequestLogEntry {
    timestamp: Date;
    model_id: string;
    provider_id: string;
    capability: string;
    delivery_mode: string;
    latency_ms: number;
    status_code: number;
    tokens_in: number;
    tokens_out: number;
    cost?: number;
    error?: string;
}

/** Aggregate metrics for a single model, provider, or pool over a time window. */
interface AggregateStats {
    requests_total: number;
    requests_success: number;
    requests_failed: number;
    tokens_in: number;
    tokens_out: number;
    cost_total: number;
    latency_avg: number;
    latency_p95: number;
    downtime_total: number;
    rotation_events: number;
}

/** Severity levels for structured trace reporting. */
enum Severity {
    DEBUG = "debug",
    INFO = "info",
    WARNING = "warning",
    ERROR = "error",
    CRITICAL = "critical",
}

/** A structured trace/log entry with severity level. */
interface TraceEntry {
    severity: Severity;
    timestamp: Date;
    component: string;  // e.g. "router", "pool.text-generation", "provider.openai"
    message: string;
    metadata?: Record<string, unknown>;
    error?: string;
}
```

---

## Interface Definitions

### Python

```python
from abc import ABC, abstractmethod


class Events(ABC):
    """Publish routing decisions and state changes.

    Emits events such as model activation, deactivation, rotation,
    and provider health changes.
    """

    @abstractmethod
    def emit(self, event: RoutingEvent) -> None:
        """Emit a routing event to the configured output."""
        ...


class Logging(ABC):
    """Record request/response data at a configurable detail level.

    Detail level is controlled by the ``observability.logging.level``
    configuration parameter: ``metadata``, ``summary``, or ``full``.
    """

    @abstractmethod
    def log(self, entry: RequestLogEntry) -> None:
        """Record a request/response log entry."""
        ...


class Statistics(ABC):
    """Buffer and flush aggregate metrics.

    Metrics are keyed by scope (model ID, provider ID, or pool ID)
    and flushed on a configurable interval.
    """

    @abstractmethod
    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Flush buffered aggregate statistics to the configured output.

        Args:
            stats: A mapping from scope identifier (model, provider, or
                   pool ID) to its aggregate metrics for the current window.
        """
        ...


class Tracing(ABC):
    """Structured trace reporting with severity levels.

    All core components (Router, Pool, Mesh, BaseProvider) emit
    traces through this interface. Traces carry a severity level
    that can be filtered by ``min_severity`` configuration.
    """

    @abstractmethod
    def trace(self, entry: TraceEntry) -> None:
        """Record a trace entry at the specified severity level."""
        ...


class ObservabilityConnector(Events, Logging, Statistics, Tracing):
    """Full observability connector combining all required interfaces.

    Multiple observability connectors can be active simultaneously
    (e.g., webhook for alerts + file for dashboards).
    """
    pass
```

### TypeScript

```typescript
/** Publish routing decisions and state changes. */
interface Events {
    /** Emit a routing event to the configured output. */
    emit(event: RoutingEvent): void;
}

/** Record request/response data at a configurable detail level. */
interface Logging {
    /** Record a request/response log entry. */
    log(entry: RequestLogEntry): void;
}

/** Buffer and flush aggregate metrics. */
interface Statistics {
    /**
     * Flush buffered aggregate statistics to the configured output.
     * @param stats - Mapping from scope identifier to aggregate metrics.
     */
    flush(stats: Record<string, AggregateStats>): void;
}

/** Structured trace reporting with severity levels. */
interface Tracing {
    /** Record a trace entry at the specified severity level. */
    trace(entry: TraceEntry): void;
}

/** Full observability connector combining all required interfaces. */
interface ObservabilityConnector extends Events, Logging, Statistics, Tracing {}
```

---

## Common Configuration

Parameters shared by all observability connectors. Individual connectors may add connector-specific parameters (see [ConnectorCatalogue.md -- Observability Connectors](../ConnectorCatalogue.html#observability-connectors)).

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `observability.events.filter` | list | *(all)* | Event types to emit (e.g., `[rotation, deactivation, recovery, health]`). |
| `observability.events.include_metadata` | boolean | `true` | Include model and provider metadata in event payloads. |
| `observability.logging.level` | string | `metadata` | Detail level: `metadata`, `summary`, `full`. |
| `observability.logging.redact_secrets` | boolean | `true` | Redact API keys and tokens from logged payloads. |
| `observability.logging.max_payload_size` | integer | -- | Truncate logged payloads exceeding this byte count. |
| `observability.tracing.min_severity` | string | `info` | Minimum severity for trace entries: `debug`, `info`, `warning`, `error`, `critical`. Entries below this threshold are discarded. |
| `observability.statistics.flush_interval` | duration | `60s` | Interval to flush buffered metrics. |
| `observability.statistics.retention` | duration | `7d` | Retention window for in-memory statistics. |
| `observability.statistics.scopes` | list | *(all)* | Aggregation scopes: `model`, `provider`, `pool`. |

---

## CDK Base Class

The CDK provides [BaseObservability](../cdk/BaseClasses.html#baseobservability) with event filtering, log-level control, and secret redaction. Specialized class: [ConsoleObservability](../cdk/BaseClasses.html#consoleobservability). See [DeveloperGuide -- Tutorial 5](../cdk/DeveloperGuide.html#tutorial-5-complete-connector-set-for-acmecorp).
