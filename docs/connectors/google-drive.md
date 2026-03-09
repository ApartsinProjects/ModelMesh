# Google Drive Storage

**ID:** `storage.google.drive.v1`
**Type:** Storage

Google Drive storage connector. Persists serialized state to a file in a Google Drive folder. Uses Drive's revision history for concurrency control, enabling optimistic locking without external infrastructure. Well suited for shared team state in client-side applications and environments where Google Workspace is already in use.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Persistence | Yes | Reads/writes files to a Google Drive folder. Supports JSON and YAML serialization formats. |
| Inventory | Yes | Lists files in the configured folder using the Drive API query interface. |
| Stat Query | Yes | Retrieves file metadata (size, modified time, revision ID) without downloading file content. |
| Locking | Yes | Revision-based optimistic locking. Writes include the expected revision ID; conflicts are rejected by the Drive API. |

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

class AuthMethod(str, Enum):
    SERVICE_ACCOUNT = "service-account"
    OAUTH = "oauth"
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

export enum AuthMethod {
    SERVICE_ACCOUNT = "service-account",
    OAUTH = "oauth",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `folder_id` | string | *(required)* | Google Drive folder ID where state files are stored. |
| `credentials` | string | *(required)* | Path to a service account JSON file or a secret reference (`${secrets:drive-credentials}`). |
| `filename` | string | `mesh-state.json` | Name of the state file within the Drive folder. |

## YAML Example

```yaml
storage:
  connector: google.drive.v1
  persistence:
    sync_policy: sync-on-boundary
    format: json
  locking:
    enabled: true
    timeout: 30s
  drive:
    folder_id: 1aBcDeFgHiJkLmNoPqRsTuVwXyZ
    credentials: ${secrets:google-drive-sa}
    filename: mesh-state.json
```

> **Recommended sync policies:** `sync-on-boundary`, `periodic`. Drive API rate limits (300 requests per minute per user) make `immediate` sync impractical for high-throughput deployments.
