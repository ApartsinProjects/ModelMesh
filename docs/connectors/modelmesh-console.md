---
layout: default
title: "Console Observability"
---

# Console Observability

**ID:** `observability.modelmesh.console.v1`
**Type:** Observability

Console output observability connector. Writes routing events, request logs, and aggregate statistics to standard output (or standard error). This is the default observability connector, active when no other observability connector is configured. Best suited for development, debugging, and environments where structured log aggregation is not required.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Events | Yes | Routing events are printed to stdout with timestamps and event type labels. |
| Logging | Yes | Request/response metadata is printed to stdout. Detail level controlled by `observability.logging.level` (default: `metadata`). |
| Statistics | Yes | Periodic aggregate summaries (request counts, token usage, latency) are printed to stdout at each flush interval. |

## Constants

```python
from enum import Enum

class EventType(str, Enum):
    MODEL_ACTIVATED = "model_activated"
    MODEL_DEACTIVATED = "model_deactivated"
    MODEL_ROTATED = "model_rotated"
    PROVIDER_HEALTH_CHANGED = "provider_health_changed"
    PROVIDER_DEACTIVATED = "provider_deactivated"
    PROVIDER_RECOVERED = "provider_recovered"
    POOL_MEMBERSHIP_CHANGED = "pool_membership_changed"
    DISCOVERY_MODELS_UPDATED = "discovery_models_updated"

class LogLevel(str, Enum):
    METADATA = "metadata"
    SUMMARY = "summary"
    FULL = "full"

class StatsScope(str, Enum):
    MODEL = "model"
    PROVIDER = "provider"
    POOL = "pool"

class OutputTarget(str, Enum):
    STDOUT = "stdout"
    STDERR = "stderr"
```

```typescript
export enum EventType {
    MODEL_ACTIVATED = "model_activated",
    MODEL_DEACTIVATED = "model_deactivated",
    MODEL_ROTATED = "model_rotated",
    PROVIDER_HEALTH_CHANGED = "provider_health_changed",
    PROVIDER_DEACTIVATED = "provider_deactivated",
    PROVIDER_RECOVERED = "provider_recovered",
    POOL_MEMBERSHIP_CHANGED = "pool_membership_changed",
    DISCOVERY_MODELS_UPDATED = "discovery_models_updated",
}

export enum LogLevel {
    METADATA = "metadata",
    SUMMARY = "summary",
    FULL = "full",
}

export enum StatsScope {
    MODEL = "model",
    PROVIDER = "provider",
    POOL = "pool",
}

export enum OutputTarget {
    STDOUT = "stdout",
    STDERR = "stderr",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `colorize` | boolean | `true` | Enable ANSI color codes in output. Disable for environments that do not support colored output (e.g., log files, CI runners). |
| `timestamp_format` | string | `ISO8601` | Timestamp format for log entries. Accepts `ISO8601`, `UNIX`, or a custom strftime-compatible format string. |
| `verbose` | boolean | `false` | Include full event payloads in output. When false, only event type and summary fields are printed. |

## YAML Example

```yaml
observability:
  connector: modelmesh.console.v1
  events:
    filter: [rotation, deactivation, recovery, health]
    include_metadata: true
  logging:
    level: metadata
    redact_secrets: true
  statistics:
    flush_interval: 60s
    scopes: [model, provider, pool]
  console:
    colorize: true
    timestamp_format: ISO8601
    verbose: false
```
