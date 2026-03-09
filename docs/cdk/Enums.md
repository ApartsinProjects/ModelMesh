# CDK Enum Reference

All enums used by the CDK and connector interfaces, consolidated in one reference. Each enum is shown in both Python and TypeScript with its string values. The authoritative source for each enum is the corresponding interface document linked in each section.

---

## Provider Enums

> Source: [interfaces/Provider.md](../interfaces/Provider.md)

### AuthMethod

Authentication method used by a provider connector.

**Python:**

```python
class AuthMethod(Enum):
    API_KEY = "api_key"
    OAUTH = "oauth"
    SERVICE_ACCOUNT = "service_account"
```

**TypeScript:**

```typescript
enum AuthMethod {
    API_KEY = "api_key",
    OAUTH = "oauth",
    SERVICE_ACCOUNT = "service_account",
}
```

| Value | String | Description |
| --- | --- | --- |
| `API_KEY` | `"api_key"` | Static API key passed via header or query parameter |
| `OAUTH` | `"oauth"` | OAuth 2.0 token-based authentication |
| `SERVICE_ACCOUNT` | `"service_account"` | Service account credentials (e.g., GCP service account JSON) |

---

## Rotation Policy Enums

> Source: [interfaces/RotationPolicy.md](../interfaces/RotationPolicy.md)

### ModelStatus

Lifecycle status of a model within a pool.

**Python:**

```python
class ModelStatus(Enum):
    ACTIVE = "active"
    STANDBY = "standby"
```

**TypeScript:**

```typescript
enum ModelStatus {
    ACTIVE = "active",
    STANDBY = "standby",
}
```

| Value | String | Description |
| --- | --- | --- |
| `ACTIVE` | `"active"` | Model is available and eligible for selection |
| `STANDBY` | `"standby"` | Model is temporarily unavailable (deactivated) |

### DeactivationReason

Reason a model was moved from active to standby.

**Python:**

```python
class DeactivationReason(Enum):
    ERROR_THRESHOLD = "error_threshold"
    QUOTA_EXHAUSTED = "quota_exhausted"
    BUDGET_EXCEEDED = "budget_exceeded"
    TOKEN_LIMIT = "token_limit"
    REQUEST_LIMIT = "request_limit"
    MAINTENANCE_WINDOW = "maintenance_window"
    MANUAL = "manual"
```

**TypeScript:**

```typescript
enum DeactivationReason {
    ERROR_THRESHOLD = "error_threshold",
    QUOTA_EXHAUSTED = "quota_exhausted",
    BUDGET_EXCEEDED = "budget_exceeded",
    TOKEN_LIMIT = "token_limit",
    REQUEST_LIMIT = "request_limit",
    MAINTENANCE_WINDOW = "maintenance_window",
    MANUAL = "manual",
}
```

| Value | String | Description |
| --- | --- | --- |
| `ERROR_THRESHOLD` | `"error_threshold"` | Consecutive failures or error rate exceeded the configured threshold |
| `QUOTA_EXHAUSTED` | `"quota_exhausted"` | Provider quota fully consumed for the current period |
| `BUDGET_EXCEEDED` | `"budget_exceeded"` | Spend cap (daily or monthly) exceeded |
| `TOKEN_LIMIT` | `"token_limit"` | Token usage limit reached |
| `REQUEST_LIMIT` | `"request_limit"` | Request count limit reached (e.g., free-tier cap) |
| `MAINTENANCE_WINDOW` | `"maintenance_window"` | Scheduled maintenance window entered |
| `MANUAL` | `"manual"` | Operator-initiated deactivation |

### RecoveryTrigger

Trigger that caused a standby model to return to active.

**Python:**

```python
class RecoveryTrigger(Enum):
    COOLDOWN_EXPIRED = "cooldown_expired"
    QUOTA_RESET = "quota_reset"
    PROBE_SUCCESS = "probe_success"
    MANUAL = "manual"
    STARTUP_PROBE = "startup_probe"
```

**TypeScript:**

```typescript
enum RecoveryTrigger {
    COOLDOWN_EXPIRED = "cooldown_expired",
    QUOTA_RESET = "quota_reset",
    PROBE_SUCCESS = "probe_success",
    MANUAL = "manual",
    STARTUP_PROBE = "startup_probe",
}
```

| Value | String | Description |
| --- | --- | --- |
| `COOLDOWN_EXPIRED` | `"cooldown_expired"` | Cooldown timer elapsed since deactivation |
| `QUOTA_RESET` | `"quota_reset"` | Provider quota reset on calendar schedule |
| `PROBE_SUCCESS` | `"probe_success"` | Periodic health probe returned a successful response |
| `MANUAL` | `"manual"` | Operator-initiated reactivation |
| `STARTUP_PROBE` | `"startup_probe"` | Health probe at library startup confirmed availability |

---

## Storage Enums

> Source: [interfaces/Storage.md](../interfaces/Storage.md)

### SyncPolicy

Controls when storage persistence occurs.

**Python:**

```python
class SyncPolicy(Enum):
    IN_MEMORY = "in-memory"
    SYNC_ON_BOUNDARY = "sync-on-boundary"
    PERIODIC = "periodic"
    IMMEDIATE = "immediate"
```

**TypeScript:**

```typescript
enum SyncPolicy {
    IN_MEMORY = "in-memory",
    SYNC_ON_BOUNDARY = "sync-on-boundary",
    PERIODIC = "periodic",
    IMMEDIATE = "immediate",
}
```

| Value | String | Description |
| --- | --- | --- |
| `IN_MEMORY` | `"in-memory"` | No persistence; data lives only in process memory |
| `SYNC_ON_BOUNDARY` | `"sync-on-boundary"` | Persist at session boundaries (startup and shutdown) |
| `PERIODIC` | `"periodic"` | Persist on a configurable interval |
| `IMMEDIATE` | `"immediate"` | Persist after every write operation |

### SerializationFormat

Serialization format for stored data.

**Python:**

```python
class SerializationFormat(Enum):
    JSON = "json"
    YAML = "yaml"
    MSGPACK = "msgpack"
```

**TypeScript:**

```typescript
enum SerializationFormat {
    JSON = "json",
    YAML = "yaml",
    MSGPACK = "msgpack",
}
```

| Value | String | Description |
| --- | --- | --- |
| `JSON` | `"json"` | JSON text format (human-readable, widely supported) |
| `YAML` | `"yaml"` | YAML text format (human-readable, supports comments) |
| `MSGPACK` | `"msgpack"` | MessagePack binary format (compact, fast) |

---

## Observability Enums

> Source: [interfaces/Observability.md](../interfaces/Observability.md)

### EventType

Types of routing events emitted by the library.

**Python:**

```python
class EventType(Enum):
    MODEL_ACTIVATED = "model_activated"
    MODEL_DEACTIVATED = "model_deactivated"
    MODEL_ROTATED = "model_rotated"
    PROVIDER_HEALTH_CHANGED = "provider_health_changed"
    PROVIDER_DEACTIVATED = "provider_deactivated"
    PROVIDER_RECOVERED = "provider_recovered"
    POOL_MEMBERSHIP_CHANGED = "pool_membership_changed"
    DISCOVERY_MODELS_UPDATED = "discovery_models_updated"
```

**TypeScript:**

```typescript
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
```

| Value | String | Description |
| --- | --- | --- |
| `MODEL_ACTIVATED` | `"model_activated"` | A model moved from standby to active |
| `MODEL_DEACTIVATED` | `"model_deactivated"` | A model moved from active to standby |
| `MODEL_ROTATED` | `"model_rotated"` | Traffic was shifted from one model to another |
| `PROVIDER_HEALTH_CHANGED` | `"provider_health_changed"` | Provider availability or latency changed significantly |
| `PROVIDER_DEACTIVATED` | `"provider_deactivated"` | All models from a provider deactivated across pools |
| `PROVIDER_RECOVERED` | `"provider_recovered"` | A previously deactivated provider returned to service |
| `POOL_MEMBERSHIP_CHANGED` | `"pool_membership_changed"` | Models were added to or removed from a pool |
| `DISCOVERY_MODELS_UPDATED` | `"discovery_models_updated"` | Registry sync detected new, deprecated, or changed models |

### Severity

Severity levels for structured trace reporting. Used by `BaseObservability.trace()` to filter entries against the `min_severity` configuration threshold.

**Python:**

```python
class Severity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
```

**TypeScript:**

```typescript
enum Severity {
    DEBUG = "debug",
    INFO = "info",
    WARNING = "warning",
    ERROR = "error",
    CRITICAL = "critical",
}
```

| Value | String | Description |
| --- | --- | --- |
| `DEBUG` | `"debug"` | Fine-grained diagnostic information for development and debugging |
| `INFO` | `"info"` | Routine operational events (requests routed, providers initialized) |
| `WARNING` | `"warning"` | Unexpected but recoverable situations (retry triggered, model deactivated) |
| `ERROR` | `"error"` | Failures that prevent a request from completing (all models exhausted) |
| `CRITICAL` | `"critical"` | System-level failures requiring immediate attention |

### LogLevel

Detail level for request/response logging.

**Python:**

```python
class LogLevel(Enum):
    METADATA = "metadata"
    SUMMARY = "summary"
    FULL = "full"
```

**TypeScript:**

```typescript
enum LogLevel {
    METADATA = "metadata",
    SUMMARY = "summary",
    FULL = "full",
}
```

| Value | String | Description |
| --- | --- | --- |
| `METADATA` | `"metadata"` | Log only routing metadata (model, provider, latency, status code) |
| `SUMMARY` | `"summary"` | Log metadata plus token counts and cost |
| `FULL` | `"full"` | Log complete request and response payloads |

---

## Discovery Enums

> Source: [interfaces/Discovery.md](../interfaces/Discovery.md)

### SyncAction

Action to take when a new model is discovered during sync.

**Python:**

```python
class SyncAction(Enum):
    REGISTER = "register"
    NOTIFY = "notify"
    IGNORE = "ignore"
```

**TypeScript:**

```typescript
enum SyncAction {
    REGISTER = "register",
    NOTIFY = "notify",
    IGNORE = "ignore",
}
```

| Value | String | Description |
| --- | --- | --- |
| `REGISTER` | `"register"` | Automatically register the model in the local catalogue |
| `NOTIFY` | `"notify"` | Emit an event but do not register automatically |
| `IGNORE` | `"ignore"` | Take no action |

### DeprecationAction

Action to take when a model is detected as deprecated.

**Python:**

```python
class DeprecationAction(Enum):
    DEACTIVATE = "deactivate"
    NOTIFY = "notify"
    IGNORE = "ignore"
```

**TypeScript:**

```typescript
enum DeprecationAction {
    DEACTIVATE = "deactivate",
    NOTIFY = "notify",
    IGNORE = "ignore",
}
```

| Value | String | Description |
| --- | --- | --- |
| `DEACTIVATE` | `"deactivate"` | Move the model to standby immediately |
| `NOTIFY` | `"notify"` | Emit an event but keep the model active |
| `IGNORE` | `"ignore"` | Take no action |

---

## CDK-Specific Enums

These enums are defined by the CDK itself and are not part of any individual connector interface.

### ConnectorType

Identifies the category of a connector for registration and catalogue lookup.

**Python:**

```python
class ConnectorType(Enum):
    PROVIDER = "provider"
    ROTATION = "rotation"
    SECRET_STORE = "secret_store"
    STORAGE = "storage"
    OBSERVABILITY = "observability"
    DISCOVERY = "discovery"
```

**TypeScript:**

```typescript
enum ConnectorType {
    PROVIDER = "provider",
    ROTATION = "rotation",
    SECRET_STORE = "secret_store",
    STORAGE = "storage",
    OBSERVABILITY = "observability",
    DISCOVERY = "discovery",
}
```

| Value | String | Description |
| --- | --- | --- |
| `PROVIDER` | `"provider"` | AI model or web API provider |
| `ROTATION` | `"rotation"` | Model lifecycle and selection policy |
| `SECRET_STORE` | `"secret_store"` | API key and token resolution |
| `STORAGE` | `"storage"` | State, configuration, and log persistence |
| `OBSERVABILITY` | `"observability"` | Routing events, request logs, and statistics |
| `DISCOVERY` | `"discovery"` | Model catalogue sync and provider health monitoring |

---

## Cross-References

Each enum is authoritatively defined in its interface document. This file consolidates them for convenience; if a discrepancy exists, the interface document is the source of truth.

| Enum | Authoritative Source |
| --- | --- |
| `AuthMethod` | [interfaces/Provider.md](../interfaces/Provider.md) |
| `ModelStatus` | [interfaces/RotationPolicy.md](../interfaces/RotationPolicy.md) |
| `DeactivationReason` | [interfaces/RotationPolicy.md](../interfaces/RotationPolicy.md) |
| `RecoveryTrigger` | [interfaces/RotationPolicy.md](../interfaces/RotationPolicy.md) |
| `SyncPolicy` | [interfaces/Storage.md](../interfaces/Storage.md) |
| `SerializationFormat` | [interfaces/Storage.md](../interfaces/Storage.md) |
| `Severity` | [interfaces/Observability.md](../interfaces/Observability.md) |
| `EventType` | [interfaces/Observability.md](../interfaces/Observability.md) |
| `LogLevel` | [interfaces/Observability.md](../interfaces/Observability.md) |
| `SyncAction` | [interfaces/Discovery.md](../interfaces/Discovery.md) |
| `DeprecationAction` | [interfaces/Discovery.md](../interfaces/Discovery.md) |
| `ConnectorType` | CDK-specific (this document) |
