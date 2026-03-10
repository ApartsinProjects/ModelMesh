"""Base storage implementation for the CDK.

Implements the full StorageConnector interface (Persistence, Inventory,
StatQuery) plus the optional Locking interface using an in-memory
dictionary backend. Subclasses override persistence methods to write to
files, databases, or cloud storage.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from modelmesh.interfaces.storage import (
    EntryMetadata,
    LockHandle,
    Locking,
    StorageConnector,
    StorageEntry,
)


@dataclass
class BaseStorageConfig:
    """Configuration for a BaseStorage instance."""

    format: str = "json"
    compression: bool = False
    locking_enabled: bool = True
    lock_timeout_seconds: float = 30.0


class BaseStorage(StorageConnector, Locking):
    """Base implementation of the StorageConnector and Locking interfaces.

    Provides an in-memory storage backend with JSON serialization,
    optional compression, and advisory locking. Subclasses override
    persistence methods to write to files, databases, or cloud storage.
    """

    def __init__(self, config: BaseStorageConfig) -> None:
        self._config = config
        self._store: dict[str, StorageEntry] = {}
        self._timestamps: dict[str, datetime] = {}
        self._locks: dict[str, LockHandle] = {}

    # -- Persistence ---------------------------------------------------------

    async def load(self, key: str) -> StorageEntry | None:
        """Load a stored entry by key, or return None if not found."""
        return self._store.get(key)

    async def save(self, key: str, entry: StorageEntry) -> None:
        """Save an entry under the given key. Overwrites if the key exists."""
        if self._config.compression:
            import gzip

            entry = StorageEntry(
                key=entry.key,
                data=gzip.compress(entry.data),
                metadata={**entry.metadata, "_compressed": True},
            )
        self._store[key] = entry
        self._timestamps[key] = datetime.now(timezone.utc)

    # -- Inventory -----------------------------------------------------------

    async def list(self, prefix: str | None = None) -> list[str]:
        """Return keys matching the optional prefix, or all keys."""
        if prefix is None:
            return list(self._store.keys())
        return [k for k in self._store if k.startswith(prefix)]

    async def delete(self, key: str) -> bool:
        """Delete the entry at the given key. Return True if it existed."""
        if key in self._store:
            del self._store[key]
            self._timestamps.pop(key, None)
            self._locks.pop(key, None)
            return True
        return False

    # -- Stat Query ----------------------------------------------------------

    async def stat(self, key: str) -> EntryMetadata | None:
        """Return metadata for the given key, or None if not found."""
        entry = self._store.get(key)
        if entry is None:
            return None
        return EntryMetadata(
            key=key,
            size=len(entry.data),
            last_modified=self._timestamps.get(key, datetime.now(timezone.utc)),
            content_type=self._config.format,
        )

    async def exists(self, key: str) -> bool:
        """Return True if an entry exists at the given key."""
        return key in self._store

    # -- Locking -------------------------------------------------------------

    async def acquire(
        self, key: str, timeout: float | None = None
    ) -> LockHandle:
        """Acquire an advisory lock on the given key.

        Raises:
            RuntimeError: If locking is disabled in configuration.
            TimeoutError: If the lock cannot be acquired within the timeout.
        """
        if not self._config.locking_enabled:
            raise RuntimeError("Locking is disabled in configuration")

        effective_timeout = timeout or self._config.lock_timeout_seconds

        if key in self._locks:
            existing = self._locks[key]
            if (
                existing.expires_at is not None
                and datetime.now(timezone.utc) > existing.expires_at
            ):
                del self._locks[key]
            else:
                deadline = datetime.now(timezone.utc) + timedelta(
                    seconds=effective_timeout
                )
                while key in self._locks and datetime.now(timezone.utc) < deadline:
                    await asyncio.sleep(0.1)
                if key in self._locks:
                    raise TimeoutError(
                        f"Could not acquire lock on '{key}' "
                        f"within {effective_timeout}s"
                    )

        now = datetime.now(timezone.utc)
        handle = LockHandle(
            key=key,
            lock_id=str(uuid.uuid4()),
            acquired_at=now,
            expires_at=now + timedelta(seconds=effective_timeout),
        )
        self._locks[key] = handle
        return handle

    async def release(self, lock: LockHandle) -> None:
        """Release a previously acquired lock."""
        if (
            lock.key in self._locks
            and self._locks[lock.key].lock_id == lock.lock_id
        ):
            del self._locks[lock.key]

    async def is_locked(self, key: str) -> bool:
        """Return True if the given key is currently locked."""
        if key not in self._locks:
            return False
        handle = self._locks[key]
        if (
            handle.expires_at is not None
            and datetime.now(timezone.utc) > handle.expires_at
        ):
            del self._locks[key]
            return False
        return True


__all__ = [
    "BaseStorageConfig",
    "BaseStorage",
]
