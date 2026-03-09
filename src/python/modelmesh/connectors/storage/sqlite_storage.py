"""SQLite-backed key-value storage connector.

Uses the standard library ``sqlite3`` module to persist key-value data
in a local SQLite database. Auto-creates the storage table on
initialization.

Connector ID: ``modelmesh.sqlite.v1``
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from modelmesh.interfaces.storage import (
    EntryMetadata,
    StorageConnector,
    StorageEntry,
)

__all__ = [
    "SqliteStorageConfig",
    "SqliteStorage",
]


@dataclass
class SqliteStorageConfig:
    """Configuration for the SQLite storage connector.

    Attributes:
        db_path: Path to the SQLite database file. Defaults to
            ``"modelmesh_state.db"``.
        table_name: Name of the key-value table. Defaults to
            ``"kv_store"``.
    """

    db_path: str = "modelmesh_state.db"
    table_name: str = "kv_store"


class SqliteStorage(StorageConnector):
    """Key-value storage backed by a local SQLite database.

    Implements the full ``StorageConnector`` interface (``load``,
    ``save``, ``list``, ``delete``, ``stat``, ``exists``) using a
    single SQLite table with columns for key, data (BLOB),
    metadata (JSON text), and last_modified timestamp.

    The table is auto-created on initialization if it does not exist.

    Connector ID: ``modelmesh.sqlite.v1``

    Usage::

        storage = SqliteStorage(SqliteStorageConfig(
            db_path="/var/data/modelmesh/state.db",
            table_name="kv_store",
        ))
        await storage.save("key", StorageEntry(key="key", data=b"...", metadata={}))
        entry = await storage.load("key")
    """

    CONNECTOR_ID: str = "modelmesh.sqlite.v1"

    def __init__(self, config: SqliteStorageConfig | None = None) -> None:
        if config is None:
            config = SqliteStorageConfig()
        self._config = config
        self._conn = sqlite3.connect(config.db_path)
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the key-value table if it does not exist."""
        table = self._config.table_name
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS [{table}] ("
            f"  key TEXT PRIMARY KEY,"
            f"  data BLOB NOT NULL,"
            f"  metadata TEXT NOT NULL DEFAULT '{{}}',"
            f"  last_modified TEXT NOT NULL"
            f")"
        )
        self._conn.commit()

    # -- Persistence ---------------------------------------------------------

    async def load(self, key: str) -> StorageEntry | None:
        """Load a stored entry by key, or return None if not found."""
        table = self._config.table_name
        cursor = self._conn.execute(
            f"SELECT key, data, metadata FROM [{table}] WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return StorageEntry(
            key=row[0],
            data=row[1] if isinstance(row[1], bytes) else row[1].encode("utf-8"),
            metadata=json.loads(row[2]),
        )

    async def save(self, key: str, entry: StorageEntry) -> None:
        """Save an entry under the given key. Overwrites if key exists."""
        table = self._config.table_name
        now = datetime.now(tz=timezone.utc).isoformat()
        metadata_str = json.dumps(entry.metadata, default=str)
        self._conn.execute(
            f"INSERT OR REPLACE INTO [{table}] (key, data, metadata, last_modified) "
            f"VALUES (?, ?, ?, ?)",
            (key, entry.data, metadata_str, now),
        )
        self._conn.commit()

    # -- Inventory -----------------------------------------------------------

    async def list(self, prefix: str | None = None) -> list[str]:
        """Return keys matching the optional prefix, or all keys."""
        table = self._config.table_name
        if prefix is None:
            cursor = self._conn.execute(
                f"SELECT key FROM [{table}] ORDER BY key"
            )
        else:
            cursor = self._conn.execute(
                f"SELECT key FROM [{table}] WHERE key LIKE ? ORDER BY key",
                (prefix + "%",),
            )
        return [row[0] for row in cursor.fetchall()]

    async def delete(self, key: str) -> bool:
        """Delete the entry at the given key. Return True if it existed."""
        table = self._config.table_name
        cursor = self._conn.execute(
            f"DELETE FROM [{table}] WHERE key = ?", (key,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # -- Stat Query ----------------------------------------------------------

    async def stat(self, key: str) -> EntryMetadata | None:
        """Return metadata for the given key, or None if not found."""
        table = self._config.table_name
        cursor = self._conn.execute(
            f"SELECT key, LENGTH(data), last_modified, metadata FROM [{table}] "
            f"WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return EntryMetadata(
            key=row[0],
            size=row[1],
            last_modified=datetime.fromisoformat(row[2]),
            content_type="application/octet-stream",
        )

    async def exists(self, key: str) -> bool:
        """Return True if an entry exists at the given key."""
        table = self._config.table_name
        cursor = self._conn.execute(
            f"SELECT 1 FROM [{table}] WHERE key = ?", (key,)
        )
        return cursor.fetchone() is not None

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()

    def __del__(self) -> None:
        self.close()
