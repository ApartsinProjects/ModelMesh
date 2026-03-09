# StatisticsCollector

Aggregate metrics buffer that records operational data from completed requests and flushes it on a configurable schedule through observability connectors. The collector maintains in-memory aggregates at three scopes -- model, provider, and pool -- and exposes a query API for programmatic access to operational statistics. Metrics are retained in memory for a configurable window and flushed to external systems at regular intervals.

**Depends on:** [ObservabilityConnector](../ConnectorInterfaces.md#observability)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StatsScope(Enum):
    """Aggregation scope for statistics queries."""
    MODEL = "model"
    PROVIDER = "provider"
    POOL = "pool"


@dataclass
class RequestMetrics:
    """Metrics recorded from a single completed request."""
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost: Optional[float] = None
    success: bool = True


@dataclass
class AggregateStats:
    """Aggregated statistics for a model, provider, or pool."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    rotation_events: int
    last_updated: datetime


class StatisticsCollector:
    """Aggregate metrics buffer with query API.

    Buffers metrics from completed requests and flushes on a configurable
    schedule through observability connectors. Queryable at model,
    provider, and pool scopes.
    """

    def record(
        self,
        model_id: str,
        provider_id: str,
        pool_id: str,
        metrics: RequestMetrics,
    ) -> None:
        """Record metrics from a completed request.

        Updates in-memory aggregates at all three scopes (model,
        provider, pool) with the provided metrics.

        Args:
            model_id: The model that handled the request.
            provider_id: The provider that served the request.
            pool_id: The pool from which the model was selected.
            metrics: Latency, token counts, cost, and success status.
        """
        ...

    def flush(self) -> None:
        """Push buffered metrics to all observability connectors.

        Called automatically on the configured flush interval and
        at shutdown. Can also be called manually to force an
        immediate flush.
        """
        ...

    def query(self, scope: StatsScope, name: str) -> AggregateStats:
        """Return aggregate statistics for a model, provider, or pool.

        Args:
            scope: The aggregation scope (MODEL, PROVIDER, or POOL).
            name: The identifier within the scope (e.g., model name,
                provider name, or pool name).

        Returns:
            Aggregated statistics for the specified scope and name.

        Raises:
            KeyError: If no data exists for the given scope and name.
        """
        ...

    def reset(self) -> None:
        """Clear all buffered statistics.

        Removes all in-memory aggregates. Does not affect data already
        flushed to observability connectors.
        """
        ...
```

## TypeScript

```typescript
/** Aggregation scope for statistics queries. */
enum StatsScope {
    MODEL = "model",
    PROVIDER = "provider",
    POOL = "pool",
}

/** Metrics recorded from a single completed request. */
interface RequestMetrics {
    latency_ms: number;
    tokens_in: number;
    tokens_out: number;
    cost?: number;
    success: boolean;
}

/** Aggregated statistics for a model, provider, or pool. */
interface AggregateStats {
    total_requests: number;
    successful_requests: number;
    failed_requests: number;
    total_tokens_in: number;
    total_tokens_out: number;
    total_cost: number;
    avg_latency_ms: number;
    p50_latency_ms: number;
    p95_latency_ms: number;
    p99_latency_ms: number;
    error_rate: number;
    rotation_events: number;
    last_updated: Date;
}

/** Aggregate metrics buffer with query API. */
class StatisticsCollector {
    /**
     * Record metrics from a completed request.
     *
     * Updates in-memory aggregates at model, provider, and pool scopes.
     */
    record(
        modelId: string,
        providerId: string,
        poolId: string,
        metrics: RequestMetrics,
    ): void {
        throw new Error("Not implemented");
    }

    /** Push buffered metrics to all observability connectors. */
    flush(): void {
        throw new Error("Not implemented");
    }

    /**
     * Return aggregate statistics for a model, provider, or pool.
     *
     * Throws if no data exists for the given scope and name.
     */
    query(scope: StatsScope, name: string): AggregateStats {
        throw new Error("Not implemented");
    }

    /** Clear all buffered statistics. */
    reset(): void {
        throw new Error("Not implemented");
    }
}
```

---

## Query API Examples

### Python

```python
from modelmesh import ModelMesh

mesh = ModelMesh()
mesh.initialize("config.yaml")
stats = mesh.get_statistics()

# Per-model statistics
model_stats = stats.query(StatsScope.MODEL, "gpt-4o")
print(f"Requests: {model_stats.total_requests}")
print(f"Avg latency: {model_stats.avg_latency_ms:.1f}ms")
print(f"Error rate: {model_stats.error_rate:.2%}")
print(f"Total cost: ${model_stats.total_cost:.4f}")

# Per-provider statistics
provider_stats = stats.query(StatsScope.PROVIDER, "openai")
print(f"Active models: {provider_stats.successful_requests}")
print(f"P95 latency: {provider_stats.p95_latency_ms:.1f}ms")

# Per-pool statistics
pool_stats = stats.query(StatsScope.POOL, "text-generation")
print(f"Rotation events: {pool_stats.rotation_events}")
print(f"Total tokens: {pool_stats.total_tokens_in + pool_stats.total_tokens_out}")
```

### TypeScript

```typescript
import { ModelMesh, StatsScope } from "modelmesh";

const mesh = new ModelMesh();
await mesh.initialize("config.yaml");
const stats = mesh.getStatistics();

// Per-model statistics
const modelStats = stats.query(StatsScope.MODEL, "gpt-4o");
console.log(`Requests: ${modelStats.total_requests}`);
console.log(`Avg latency: ${modelStats.avg_latency_ms.toFixed(1)}ms`);
console.log(`Error rate: ${(modelStats.error_rate * 100).toFixed(2)}%`);
console.log(`Total cost: $${modelStats.total_cost.toFixed(4)}`);

// Per-provider statistics
const providerStats = stats.query(StatsScope.PROVIDER, "openai");
console.log(`P95 latency: ${providerStats.p95_latency_ms.toFixed(1)}ms`);

// Per-pool statistics
const poolStats = stats.query(StatsScope.POOL, "text-generation");
console.log(`Rotation events: ${poolStats.rotation_events}`);
console.log(`Total tokens: ${poolStats.total_tokens_in + poolStats.total_tokens_out}`);
```

---

## Configuration

See [SystemConfiguration.md -- Observability](../SystemConfiguration.md#observability) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `observability.statistics.connector` | string | Observability connector ID for statistics. |
| `observability.statistics.flush_interval` | duration | Interval to flush buffered metrics (e.g., `60s`). |
| `observability.statistics.retention` | duration | In-memory retention window for statistics (e.g., `7d`). |
| `observability.statistics.scopes` | list | Aggregation scopes to track: `model`, `provider`, `pool`. Default: all. |
