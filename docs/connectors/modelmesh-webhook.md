---
layout: default
title: "Webhook Observability"
---

# Webhook Observability

**ID:** `observability.modelmesh.webhook.v1`
**Type:** Observability

HTTP POST webhook observability connector. Sends routing events, request logs, and aggregate statistics as JSON payloads to a configurable HTTP endpoint. Supports request batching to reduce overhead and automatic retry with exponential backoff on delivery failure. Use this connector for alerting pipelines, external dashboards, or log aggregation services that accept webhook input.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Events | Yes | Routing events are sent as JSON payloads to the configured endpoint. Supports batching multiple events per request. |
| Logging | Yes | Request/response log entries are delivered as JSON. Detail level controlled by `observability.logging.level`. |
| Statistics | Yes | Aggregate metrics are flushed and delivered as JSON payloads at each flush interval. |

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

class HttpMethod(str, Enum):
    POST = "POST"
    PUT = "PUT"
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

export enum HttpMethod {
    POST = "POST",
    PUT = "PUT",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `url` | string | *(required)* | Webhook endpoint URL that receives JSON payloads. |
| `headers` | dict \| null | `null` | Custom HTTP headers to include with each request (e.g., `{"Authorization": "Bearer ${secrets:webhook-token}"}`). |
| `timeout` | duration | `10s` | HTTP request timeout. Requests exceeding this duration are considered failed and eligible for retry. |
| `retry_count` | integer | `3` | Number of retry attempts on delivery failure. Uses exponential backoff between retries. |
| `batch_size` | integer | `1` | Number of entries to buffer before sending a single batched request. Set to `1` for immediate delivery. |
| `content_type` | string | `application/json` | Content-Type header value for outgoing requests. |

## YAML Example

```yaml
observability:
  connector: modelmesh.webhook.v1
  events:
    filter: [rotation, deactivation, recovery, health]
    include_metadata: true
  logging:
    level: metadata
    redact_secrets: true
  statistics:
    flush_interval: 60s
    scopes: [model, provider, pool]
  webhook:
    url: https://hooks.example.com/modelmesh/events
    headers:
      Authorization: Bearer ${secrets:webhook-token}
    timeout: 10s
    retry_count: 3
    batch_size: 10
    content_type: application/json
```
