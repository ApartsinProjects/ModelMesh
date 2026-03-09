---
layout: default
title: "AWS S3 Storage"
---

# AWS S3 Storage

**ID:** `storage.aws.s3.v1`
**Type:** Storage

AWS S3 storage connector. Persists serialized state to an S3 object, using conditional writes with ETags to ensure multi-instance safety. Supports S3-compatible services (MinIO, DigitalOcean Spaces, Backblaze B2) via a custom endpoint parameter. Optional DynamoDB-based distributed locking enables safe concurrent access for `periodic` and `immediate` sync policies across multiple instances.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Persistence | Yes | Reads/writes objects to S3. Uses conditional PutObject with ETags to prevent conflicting writes. |
| Inventory | Yes | Lists objects in the configured bucket with optional key prefix filtering. |
| Stat Query | Yes | HeadObject returns size, last modified, ETag, and storage class without downloading content. |
| Locking | Yes | DynamoDB-based distributed locking (optional). Requires a DynamoDB table with a `LockID` partition key. |

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
    IAM_ROLE = "iam-role"
    ACCESS_KEY = "access-key"
    PROFILE = "profile"
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
    IAM_ROLE = "iam-role",
    ACCESS_KEY = "access-key",
    PROFILE = "profile",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `bucket` | string | *(required)* | S3 bucket name. |
| `key` | string | `mesh-state.json` | Object key for the state file within the bucket. |
| `region` | string | *(required)* | AWS region (e.g., `us-east-1`). |
| `endpoint` | string \| null | `null` | Custom S3-compatible endpoint URL (e.g., for MinIO, DigitalOcean Spaces). When null, uses the default AWS S3 endpoint. |
| `lock_table` | string \| null | `null` | DynamoDB table name for distributed locking. The table must have a `LockID` string partition key. When null, locking is disabled. |

## YAML Example

```yaml
storage:
  connector: aws.s3.v1
  persistence:
    sync_policy: periodic
    sync_interval: 300s
    format: json
  locking:
    enabled: true
    timeout: 30s
  s3:
    bucket: my-modelmesh-state
    key: mesh-state.json
    region: us-east-1
    endpoint: null
    lock_table: modelmesh-locks
```

> **Recommended sync policies:** `periodic`, `immediate`. Both are fully supported when DynamoDB locking is enabled. For single-instance deployments without a lock table, `sync-on-boundary` is also safe.
