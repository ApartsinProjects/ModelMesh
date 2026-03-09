---
layout: default
title: "RequestLogger"
---

# RequestLogger

Records request and response data at a configurable detail level through observability connectors. The logger supports three detail levels to balance observability against payload size and privacy: metadata-only (timestamps, model, latency), summary (metadata plus truncated payloads), and full (complete request and response bodies). Sensitive data such as API keys and tokens can be automatically redacted from logged payloads.

**Depends on:** [ObservabilityConnector](../ConnectorInterfaces.html#observability)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LogLevel(Enum):
    """Detail level for request/response logging."""
    METADATA = "metadata"
    SUMMARY = "summary"
    FULL = "full"


@dataclass
class RequestLogEntry:
    """A single request/response record for logging."""
    request_id: str
    timestamp: datetime
    model_id: str
    provider_id: str
    pool_id: str
    capability: str
    delivery_mode: str
    status_code: int
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost: Optional[float] = None
    request_payload: Optional[str] = None
    response_payload: Optional[str] = None
    error: Optional[str] = None
    routing_reason: Optional[str] = None


class RequestLogger:
    """Records request/response data at a configurable detail level.

    Supports three detail levels: metadata (timestamps, model, provider,
    token counts, latency, status code), summary (metadata plus truncated
    request/response), and full (complete payloads).
    """

    def log(self, entry: RequestLogEntry) -> None:
        """Record a request with its routing decision and response metadata.

        The entry is filtered according to the current log level before
        being forwarded to the observability connector. At METADATA level,
        payload fields are stripped. At SUMMARY level, payloads are
        truncated to max_payload_size.

        Args:
            entry: The complete request/response record.
        """
        ...

    def set_level(self, level: LogLevel) -> None:
        """Change the detail level at runtime.

        Takes effect immediately for subsequent log calls.

        Args:
            level: The new detail level (METADATA, SUMMARY, or FULL).
        """
        ...
```

## TypeScript

```typescript
/** Detail level for request/response logging. */
enum LogLevel {
    METADATA = "metadata",
    SUMMARY = "summary",
    FULL = "full",
}

/** A single request/response record for logging. */
interface RequestLogEntry {
    request_id: string;
    timestamp: Date;
    model_id: string;
    provider_id: string;
    pool_id: string;
    capability: string;
    delivery_mode: string;
    status_code: number;
    latency_ms: number;
    tokens_in: number;
    tokens_out: number;
    cost?: number;
    request_payload?: string;
    response_payload?: string;
    error?: string;
    routing_reason?: string;
}

/** Records request/response data at a configurable detail level. */
class RequestLogger {
    /**
     * Record a request with its routing decision and response metadata.
     *
     * The entry is filtered according to the current log level before
     * being forwarded to the observability connector.
     */
    log(entry: RequestLogEntry): void {
        throw new Error("Not implemented");
    }

    /**
     * Change the detail level at runtime.
     *
     * Takes effect immediately for subsequent log calls.
     */
    setLevel(level: LogLevel): void {
        throw new Error("Not implemented");
    }
}
```

---

## Configuration

See [SystemConfiguration.md -- Observability](../SystemConfiguration.html#observability) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `observability.logging.connector` | string | Observability connector ID for request logs. |
| `observability.logging.level` | string | Detail level: `metadata`, `summary`, `full`. Default: `metadata`. |
| `observability.logging.redact` | boolean | Redact API keys and tokens from logged payloads. Default: `true`. |
| `observability.logging.max_payload_size` | integer | Truncate logged payloads exceeding this byte count. |
