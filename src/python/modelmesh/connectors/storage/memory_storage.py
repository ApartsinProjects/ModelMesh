"""In-memory key-value storage connector.

Provides an ephemeral dict-based storage backend. All data is lost
when the process exits. Useful for testing, serverless functions,
and short-lived processes.

Connector ID: ``modelmesh.memory.v1``
"""
from __future__ import annotations

from datetime import datetime, timezone

from modelmesh.interfaces.storage import (
    EntryMetadata,
    StorageConnector,
    StorageEntry,
)

__all__ = [
    "MemoryStorage",
]


class MemoryStorage(StorageConnector):
    """Ephemeral in-memory key-value storage.

    Implements the full ``StorageConnector`` interface using a plain
    Python dictionary. No configuration is needed. All data is lost
    when the process exits or the instance is garbage-collected.

    Connector ID: ``modelmesh.memory.v1``

    Usage::

        storage = MemoryStorage()
        await storage.save("key", StorageEntry(key="key", data=b"hello", metadata={}))
        entry = await storage.load("key")
        assert entry.data == b"hello"
    """

    CONNECTOR_ID: str = "modelmesh.memory.v1"

    def __init__(self) -> None:
        self._store: dict[str, StorageEntry] = {}
        self._timestamps: dict[str, datetime] = {}

    # -- Persistence ---------------------------------------------------------

    async def load(self, key: str) -> StorageEntry | None:
        """Load a stored entry by key, or return None if not found."""
        return self._store.get(key)

    async def save(self, key: str, entry: StorageEntry) -> None:
        """Save an entry under the given key. Overwrites if key exists."""
        self._store[key] = entry
        self._timestamps[key] = datetime.now(tz=timezone.utc)

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
            last_modified=self._timestamps.get(key, datetime.now(tz=timezone.utc)),
            content_type="application/octet-stream",
        )

    async def exists(self, key: str) -> bool:
        """Return True if an entry exists at the given key."""
        return key in self._store
