"""Storage connector interface and associated data types.

Defines the abstract StorageConnector interface for serializing and
deserializing library data to an external backend. Three data types flow
through it: state, configuration, and observability logs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
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


class Persistence(ABC):
    """Read and write serialized data."""

    @abstractmethod
    async def load(self, key: str) -> StorageEntry | None:
        """Load a stored entry by key, or return None if not found."""
        ...

    @abstractmethod
    async def save(self, key: str, entry: StorageEntry) -> None:
        """Save an entry under the given key. Overwrites if the key exists."""
        ...


class Inventory(ABC):
    """Enumerate and remove stored entries."""

    @abstractmethod
    async def list(self, prefix: str | None = None) -> list[str]:
        """Return keys matching the optional prefix, or all keys if None."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete the entry at the given key. Return True if it existed."""
        ...


class StatQuery(ABC):
    """Query metadata about stored entries without loading full content."""

    @abstractmethod
    async def stat(self, key: str) -> EntryMetadata | None:
        """Return metadata for the given key, or None if not found."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if an entry exists at the given key."""
        ...


class Locking(ABC):
    """Acquire and release advisory locks on stored entries."""

    @abstractmethod
    async def acquire(self, key: str, timeout: float | None = None) -> LockHandle:
        """Acquire an advisory lock on the given key.

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
    from Locking.
    """

    pass


__all__ = [
    "SyncPolicy",
    "SerializationFormat",
    "StorageEntry",
    "EntryMetadata",
    "LockHandle",
    "Persistence",
    "Inventory",
    "StatQuery",
    "Locking",
    "StorageConnector",
]
