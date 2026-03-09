# Storage Interface

A storage connector serializes and deserializes library data to an external backend. Three data types flow through it: **state** (model health, failure counts, cooldown timers, quota usage), **configuration** (providers, pools, policies, credential references), and **observability logs** (routing decisions, request records, statistics). Sync policies control when persistence occurs: `in-memory`, `sync-on-boundary`, `periodic`, or `immediate`.

> **Reference:** [ConnectorInterfaces.md -- Storage](../ConnectorInterfaces.md#storage) | [ConnectorCatalogue.md -- Storage Connectors](../ConnectorCatalogue.md#storage-connectors)

---

## Sub-Interfaces

| Sub-Interface | Required | Purpose |
| --- | --- | --- |
| **Persistence** | yes | Read and write serialized data |
| **Inventory** | yes | Enumerate and remove stored entries |
| **Stat Query** | yes | Query metadata about stored entries without loading full content |
| **Locking** | no | Acquire and release advisory locks for concurrent access |

---

## Supporting Types

### Python

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class SyncPolicy(Enum):
    """Controls when storage persistence occurs."""
    IN_MEMORY = "in-memory"
    SYNC_ON_BOUNDARY = "sync-on-boundary"
    PERIODIC = "periodic"
    IMMEDIATE = "immediate"


class SerializationFormat(Enum):
    """Serialization format for stored data."""
    JSON = "json"
    YAML = "yaml"
    MSGPACK = "msgpack"


@dataclass
class StorageEntry:
    """A single stored data entry with its raw content and metadata."""
    key: str
    data: bytes
    metadata: dict


@dataclass
class EntryMetadata:
    """Metadata about a stored entry, without the full content."""
    key: str
    size: int
    last_modified: datetime
    content_type: Optional[str] = None


@dataclass
class LockHandle:
    """Handle representing an acquired advisory lock on a stored entry."""
    key: str
    lock_id: str
    acquired_at: datetime
    expires_at: Optional[datetime] = None
```

### TypeScript

```typescript
/** Controls when storage persistence occurs. */
enum SyncPolicy {
    IN_MEMORY = "in-memory",
    SYNC_ON_BOUNDARY = "sync-on-boundary",
    PERIODIC = "periodic",
    IMMEDIATE = "immediate",
}

/** Serialization format for stored data. */
enum SerializationFormat {
    JSON = "json",
    YAML = "yaml",
    MSGPACK = "msgpack",
}

/** A single stored data entry with its raw content and metadata. */
interface StorageEntry {
    key: string;
    data: Uint8Array;
    metadata: Record<string, unknown>;
}

/** Metadata about a stored entry, without the full content. */
interface EntryMetadata {
    key: string;
    size: number;
    last_modified: Date;
    content_type?: string;
}

/** Handle representing an acquired advisory lock on a stored entry. */
interface LockHandle {
    key: string;
    lock_id: string;
    acquired_at: Date;
    expires_at?: Date;
}
```

---

## Interface Definitions

### Python

```python
from abc import ABC, abstractmethod
from typing import Optional


class Persistence(ABC):
    """Read and write serialized data.

    The connector handles format and transport; the library handles
    serialization logic.
    """

    @abstractmethod
    async def load(self, key: str) -> StorageEntry | None:
        """Load a stored entry by key, or return None if not found."""
        ...

    @abstractmethod
    async def save(self, key: str, entry: StorageEntry) -> None:
        """Save an entry under the given key. Overwrites if the key exists."""
        ...


class Inventory(ABC):
    """Enumerate and remove stored entries.

    Used for cleanup, migration, and administrative tooling.
    """

    @abstractmethod
    async def list(self, prefix: str | None = None) -> list[str]:
        """Return keys matching the optional prefix, or all keys if None."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete the entry at the given key. Return True if it existed."""
        ...


class StatQuery(ABC):
    """Query metadata about stored entries without loading full content.

    Used for cache validation and change detection.
    """

    @abstractmethod
    async def stat(self, key: str) -> EntryMetadata | None:
        """Return metadata for the given key, or None if not found."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if an entry exists at the given key."""
        ...


class Locking(ABC):
    """Acquire and release advisory locks on stored entries.

    Prevents concurrent writes in multi-instance deployments. Required
    for ``periodic`` and ``immediate`` sync policies.
    """

    @abstractmethod
    async def acquire(self, key: str, timeout: float | None = None) -> LockHandle:
        """Acquire an advisory lock on the given key.

        Args:
            key: The storage key to lock.
            timeout: Maximum seconds to wait for the lock. None means wait
                     indefinitely.

        Raises:
            TimeoutError: If the lock cannot be acquired within the timeout.
        """
        ...

    @abstractmethod
    async def release(self, lock: LockHandle) -> None:
        """Release a previously acquired lock."""
        ...

    @abstractmethod
    async def is_locked(self, key: str) -> bool:
        """Return True if the given key is currently locked."""
        ...


class StorageConnector(Persistence, Inventory, StatQuery):
    """Full storage connector combining all required interfaces.

    Implementations that support concurrent access should also inherit
    from Locking. Locking is required when using ``periodic`` or
    ``immediate`` sync policies in multi-instance deployments.
    """
    pass
```

### TypeScript

```typescript
/** Read and write serialized data. */
interface Persistence {
    /** Load a stored entry by key, or return null if not found. */
    load(key: string): Promise<StorageEntry | null>;

    /** Save an entry under the given key. Overwrites if the key exists. */
    save(key: string, entry: StorageEntry): Promise<void>;
}

/** Enumerate and remove stored entries. */
interface Inventory {
    /** Return keys matching the optional prefix, or all keys if null. */
    list(prefix?: string): Promise<string[]>;

    /** Delete the entry at the given key. Return true if it existed. */
    delete(key: string): Promise<boolean>;
}

/** Query metadata about stored entries without loading full content. */
interface StatQuery {
    /** Return metadata for the given key, or null if not found. */
    stat(key: string): Promise<EntryMetadata | null>;

    /** Return true if an entry exists at the given key. */
    exists(key: string): Promise<boolean>;
}

/** Acquire and release advisory locks on stored entries. */
interface Locking {
    /**
     * Acquire an advisory lock on the given key.
     * @throws {Error} If the lock cannot be acquired within the timeout.
     */
    acquire(key: string, timeout?: number): Promise<LockHandle>;

    /** Release a previously acquired lock. */
    release(lock: LockHandle): Promise<void>;

    /** Return true if the given key is currently locked. */
    isLocked(key: string): Promise<boolean>;
}

/** Full storage connector combining all required interfaces. */
interface StorageConnector extends Persistence, Inventory, StatQuery {}
```

---

## Common Configuration

Parameters shared by all storage connectors. Individual connectors may add connector-specific parameters (see [ConnectorCatalogue.md -- Storage Connectors](../ConnectorCatalogue.md#storage-connectors)).

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `storage.persistence.sync_policy` | string | `in-memory` | When to persist: `in-memory`, `sync-on-boundary`, `periodic`, `immediate`. |
| `storage.persistence.sync_interval` | duration | `300s` | Interval for `periodic` sync. |
| `storage.persistence.format` | string | `json` | Serialization format: `json`, `yaml`, `msgpack`. |
| `storage.persistence.compression` | boolean | `false` | Compress serialized data before writing. |
| `storage.persistence.encryption` | boolean | `false` | Encrypt data at rest using the configured secret store. |
| `storage.locking.enabled` | boolean | `true` | Enable advisory locking for concurrent access. Defaults to `true` for multi-instance sync policies. |
| `storage.locking.timeout` | duration | `30s` | Maximum time to wait for a lock. |
| `storage.locking.retry_interval` | duration | `1s` | Interval between lock acquisition attempts. |

---

## CDK Base Class

The CDK provides [BaseStorage](../cdk/BaseClasses.md#basestorage) with in-memory dict and advisory locking. Specialized class: [KeyValueStorage](../cdk/BaseClasses.md#keyvaluestorage). See [DeveloperGuide -- Tutorial 5](../cdk/DeveloperGuide.md#tutorial-5-complete-connector-set-for-acmecorp).
