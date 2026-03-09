---
layout: default
title: "Local File Observability"
---

# Local File Observability

**ID:** `observability.modelmesh.local-file.v1`
**Type:** Observability

JSONL file output observability connector. Each event, log entry, and statistics record is written as a single JSON line appended to the configured output file. Supports automatic log rotation by file size to prevent unbounded disk usage. Suitable for development, single-instance deployments, and environments where logs are collected from disk by external agents.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Events | Yes | Each routing event is appended as a JSON line with a timestamp, event type, and payload. |
| Logging | Yes | Each request/response log entry is appended as a JSON line. Detail level controlled by `observability.logging.level`. |
| Statistics | Yes | Aggregate metrics are flushed as JSON lines at each flush interval. |

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

class RotationPolicy(str, Enum):
    SIZE = "size"
    DAILY = "daily"
    NEVER = "never"
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

export enum RotationPolicy {
    SIZE = "size",
    DAILY = "daily",
    NEVER = "never",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `path` | string | *(required)* | File path for JSONL output (e.g., `./requests.jsonl`). |
| `max_size` | string | `10MB` | Maximum file size before rotation is triggered. Accepts values like `1MB`, `100MB`, `1GB`. |
| `max_files` | integer | `5` | Number of rotated log files to retain. Older files beyond this count are deleted. |

## YAML Example

```yaml
observability:
  connector: modelmesh.local-file.v1
  events:
    filter: [rotation, deactivation, recovery, health]
    include_metadata: true
  logging:
    level: summary
    redact_secrets: true
  statistics:
    flush_interval: 60s
    scopes: [model, provider, pool]
  local-file:
    path: ./modelmesh-events.jsonl
    max_size: 10MB
    max_files: 5
```
