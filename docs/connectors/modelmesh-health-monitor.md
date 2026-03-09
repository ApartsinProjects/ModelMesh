# Health Monitor

**ID:** `discovery.modelmesh.health-monitor.v1`
**Type:** Discovery

Provider health monitoring connector. Runs as a background process that probes configured providers at regular intervals to assess availability and performance. Records latency measurements, success/failure outcomes, and error codes for each probe. Maintains rolling availability scores that feed into rotation policies for proactive deactivation of degraded or unavailable providers before user requests are affected.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Health Monitoring | Primary | Probes providers at configurable intervals. Records latency, error codes, and rolling availability scores. |
| Registry Sync | Yes | Minimal registry awareness. Delegates full synchronization to `discovery.modelmesh.registry-sync.v1`. |

## Constants

```python
from enum import Enum

class SyncAction(str, Enum):
    REGISTER = "register"
    NOTIFY = "notify"
    IGNORE = "ignore"

class DeprecationAction(str, Enum):
    DEACTIVATE = "deactivate"
    NOTIFY = "notify"
    IGNORE = "ignore"

class ProbeMethod(str, Enum):
    LIGHTWEIGHT = "lightweight"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
```

```typescript
export enum SyncAction {
    REGISTER = "register",
    NOTIFY = "notify",
    IGNORE = "ignore",
}

export enum DeprecationAction {
    DEACTIVATE = "deactivate",
    NOTIFY = "notify",
    IGNORE = "ignore",
}

export enum ProbeMethod {
    LIGHTWEIGHT = "lightweight",
    STANDARD = "standard",
    COMPREHENSIVE = "comprehensive",
}

export enum HealthStatus {
    HEALTHY = "healthy",
    DEGRADED = "degraded",
    UNAVAILABLE = "unavailable",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `health.enabled` | boolean | `true` | Enable or disable health monitoring. |
| `health.interval` | duration | `60s` | Time between health probe cycles. |
| `health.timeout` | duration | `10s` | Maximum time to wait for a probe response before marking it as failed. |
| `health.failure_threshold` | integer | `3` | Number of consecutive probe failures before triggering provider deactivation. |
| `health.providers` | list \| null | `null` | Specific provider IDs to probe. When null, all enabled providers are probed. |

## YAML Example

```yaml
discovery:
  connectors:
    - connector: modelmesh.health-monitor.v1
      health:
        enabled: true
        interval: 60s
        timeout: 10s
        failure_threshold: 3
        providers: null
```
