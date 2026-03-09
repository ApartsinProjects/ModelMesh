# Registry Sync

**ID:** `discovery.modelmesh.registry-sync.v1`
**Type:** Discovery

Model registry synchronization connector. Runs as a background process that periodically queries provider APIs (`list_models`, `get_model_info`) to detect new models, deprecated models, and pricing changes. Automatically updates the ModelRegistry based on configurable actions for each change type. Primary interface is RegistrySync; also implements basic HealthMonitoring (delegates to the health-monitor connector for advanced probing).

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Registry Sync | Primary | Periodically queries provider APIs to detect model additions, deprecations, pricing changes, and capability updates. |
| Health Monitoring | Yes | Basic health awareness through sync failures. Delegates advanced probing to `discovery.modelmesh.health-monitor.v1`. |

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

class ModelChangeType(str, Enum):
    NEW = "new"
    DEPRECATED = "deprecated"
    PRICING_CHANGED = "pricing_changed"
    CAPABILITIES_CHANGED = "capabilities_changed"
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

export enum ModelChangeType {
    NEW = "new",
    DEPRECATED = "deprecated",
    PRICING_CHANGED = "pricing_changed",
    CAPABILITIES_CHANGED = "capabilities_changed",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `sync.enabled` | boolean | `true` | Enable or disable registry synchronization. |
| `sync.interval` | duration | `1h` | Time between synchronization cycles. |
| `sync.auto_register` | boolean | `true` | Automatically register newly discovered models in the ModelRegistry. |
| `sync.providers` | list \| null | `null` | Specific provider IDs to synchronize. When null, all enabled providers are synced. |
| `sync.on_new_model` | SyncAction | `register` | Action when a new model is discovered: `register` (add to registry), `notify` (emit event only), or `ignore`. |
| `sync.on_deprecated_model` | DeprecationAction | `notify` | Action when a model is deprecated: `deactivate` (remove from active pools), `notify` (emit event only), or `ignore`. |

## YAML Example

```yaml
discovery:
  connectors:
    - connector: modelmesh.registry-sync.v1
      sync:
        enabled: true
        interval: 1h
        auto_register: true
        providers: null
        on_new_model: register
        on_deprecated_model: notify
```
