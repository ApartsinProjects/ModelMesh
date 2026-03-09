---
layout: default
title: "Redis Storage"
---

# Redis Storage

**ID:** `storage.redis.redis.v1`
**Type:** Storage

Redis storage connector. Persists serialized state to a Redis key using atomic operations. Native distributed locking via `SETNX` with TTL provides safe concurrent access across multiple instances without external locking infrastructure. Best suited for multi-instance deployments that require low-latency state access and coordination.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Persistence | Yes | Reads/writes serialized data to Redis keys using atomic GET/SET operations. |
| Inventory | Yes | Enumerates stored entries using key pattern scanning with the configured prefix. |
| Stat Query | Yes | Queries key metadata (existence, TTL, memory usage) without retrieving full values. |
| Locking | Yes | Redis `SETNX` with TTL provides fully distributed advisory locking. Supports lock renewal and automatic expiration. |

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
| `url` | string \| null | `null` | Full Redis connection URL (e.g., `redis://localhost:6379/0`). Overrides `host`, `port`, and `db` when set. |
| `host` | string | `localhost` | Redis server hostname. Ignored when `url` is set. |
| `port` | integer | `6379` | Redis server port. Ignored when `url` is set. |
| `db` | integer | `0` | Redis database number. Ignored when `url` is set. |
| `password` | string \| null | `null` | Redis password or secret reference (`${secrets:redis-password}`). |
| `key_prefix` | string | `modelmesh:` | Namespace prefix applied to all keys managed by this connector. |
| `ttl` | duration \| null | `null` | Optional TTL for stored keys. When null, keys do not expire. |

## YAML Example

```yaml
storage:
  connector: redis.redis.v1
  persistence:
    sync_policy: periodic
    sync_interval: 60s
    format: json
  locking:
    enabled: true
    timeout: 10s
    retry_interval: 500ms
  redis:
    url: redis://localhost:6379/0
    key_prefix: modelmesh:
    ttl: null
```

> **Recommended sync policies:** `periodic`, `immediate`. Redis atomic operations and native distributed locking make both policies fully safe for multi-instance deployments. The low latency of Redis operations makes `immediate` practical even at moderate request volumes.
