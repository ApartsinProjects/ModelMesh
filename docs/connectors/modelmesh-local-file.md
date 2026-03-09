# Local File Storage

**ID:** `storage.modelmesh.local-file.v1`
**Type:** Storage

Local filesystem storage connector. Reads and writes serialized state to a single JSON or YAML file on disk. Designed for development workflows and single-instance deployments where distributed coordination is unnecessary. File-based advisory locks provide basic concurrency protection on a single host but do not extend across machines or processes.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Persistence | Yes | Reads/writes JSON or YAML files to local disk. Atomic write via temp-file-and-rename. |
| Inventory | Yes | Lists files in the configured directory matching the state file pattern. |
| Stat Query | Yes | Returns file metadata: size, last modified time, existence check via filesystem stat. |
| Locking | Yes | File-based advisory locks (single-host only). Not suitable for multi-instance deployments. |

## Constants

```python
from enum import Enum

class SyncPolicy(str, Enum):
    IN_MEMORY = "in-memory"
    SYNC_ON_BOUNDARY = "sync-on-boundary"
    PERIODIC = "periodic"
    IMMEDIATE = "immediate"

class SerializationFormat(str, Enum):
    JSON = "json"
    YAML = "yaml"
    MSGPACK = "msgpack"
```

```typescript
export enum SyncPolicy {
    IN_MEMORY = "in-memory",
    SYNC_ON_BOUNDARY = "sync-on-boundary",
    PERIODIC = "periodic",
    IMMEDIATE = "immediate",
}

export enum SerializationFormat {
    JSON = "json",
    YAML = "yaml",
    MSGPACK = "msgpack",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `path` | string | `./mesh-state.json` | File path for persisted state data. |
| `backup` | boolean | `false` | Create a `.bak` copy of the state file before each overwrite. |

## YAML Example

```yaml
storage:
  connector: modelmesh.local-file.v1
  persistence:
    sync_policy: sync-on-boundary
    format: json
  locking:
    enabled: false
  local-file:
    path: ./mesh-state.json
    backup: false
```

> **Recommended sync policies:** `in-memory`, `sync-on-boundary`. The `periodic` and `immediate` policies require distributed locking, which this connector does not support across multiple processes.
