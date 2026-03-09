"""
Custom Storage Connector -- SQLite Backend

Demonstrates how to implement a custom storage connector for ModelMesh Lite
using SQLite as the persistence backend. Includes key/value storage with
metadata tracking, entry enumeration, stat queries, and advisory locking
using database rows.

SQLite is a good fit for single-instance deployments, development, and
testing where a full external store (Redis, S3) is not needed.

See: docs/interfaces/Storage.md

Requirements:
    aiosqlite  -- pip install aiosqlite
"""
# For a simpler CDK-based approach, see samples/cdk/python/

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import aiosqlite


# ---------------------------------------------------------------------------
# Supporting types (from Storage interface)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Interface ABCs (from Storage interface)
# ---------------------------------------------------------------------------

class Persistence(ABC):
    @abstractmethod
    async def load(self, key: str) -> StorageEntry | None: ...

    @abstractmethod
    async def save(self, key: str, entry: StorageEntry) -> None: ...


class Inventory(ABC):
    @abstractmethod
    async def list(self, prefix: str | None = None) -> list[str]: ...

    @abstractmethod
    async def delete(self, key: str) -> bool: ...


class StatQuery(ABC):
    @abstractmethod
    async def stat(self, key: str) -> EntryMetadata | None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...


class Locking(ABC):
    @abstractmethod
    async def acquire(self, key: str, timeout: float | None = None) -> LockHandle: ...

    @abstractmethod
    async def release(self, lock: LockHandle) -> None: ...

    @abstractmethod
    async def is_locked(self, key: str) -> bool: ...


class StorageConnector(Persistence, Inventory, StatQuery):
    """Full storage connector combining all required interfaces."""
    pass


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------

class SqliteStorageConnector(StorageConnector, Locking):
    """Storage connector backed by a SQLite database.

    Data is stored in a single ``storage_entries`` table with columns for the
    key, raw data (BLOB), metadata (JSON), size, content type, and timestamp.
    Advisory locks are managed in a separate ``advisory_locks`` table.

    This connector uses ``aiosqlite`` to provide async access to SQLite.
    SQLite itself is synchronous, but aiosqlite runs queries in a background
    thread, making it safe to use from async code.

    Schema:

        CREATE TABLE IF NOT EXISTS storage_entries (
            key           TEXT PRIMARY KEY,
            data          BLOB NOT NULL,
            metadata      TEXT NOT NULL DEFAULT '{}',
            content_type  TEXT DEFAULT 'application/octet-stream',
            size          INTEGER NOT NULL DEFAULT 0,
            last_modified TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS advisory_locks (
            key         TEXT PRIMARY KEY,
            lock_id     TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at  TEXT NOT NULL
        );

    Configuration example (YAML):

        storage:
          connector: custom
          connector_class: SqliteStorageConnector
          config:
            db_path: "./data/modelmesh.db"
            wal_mode: true
            lock_expiration_seconds: 30
            lock_retry_interval_ms: 100
          persistence:
            sync_policy: immediate
            format: json
            compression: false
            encryption: false
          locking:
            enabled: true
            timeout: 30s
            retry_interval: 100ms
    """

    def __init__(
        self,
        db_path: str = "./data/modelmesh.db",
        wal_mode: bool = True,
        lock_expiration_seconds: int = 30,
        lock_retry_interval_ms: int = 100,
    ) -> None:
        """Initialize the SQLite storage connector.

        Args:
            db_path: Path to the SQLite database file. Use ":memory:" for
                     an in-memory database (useful for testing).
            wal_mode: Enable WAL mode for better concurrent read performance.
            lock_expiration_seconds: Lock expiration in seconds. Expired locks
                                     are auto-released.
            lock_retry_interval_ms: Lock acquisition retry interval in ms.
        """
        self._db_path = db_path
        self._wal_mode = wal_mode
        self._lock_expiration_seconds = lock_expiration_seconds
        self._lock_retry_interval_ms = lock_retry_interval_ms
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Open the database connection and create tables if needed.

        Must be called before any other operations. In a real connector,
        the framework would call this during initialization.
        """
        self._db = await aiosqlite.connect(self._db_path)

        # Enable WAL mode for better concurrent read performance.
        if self._wal_mode:
            await self._db.execute("PRAGMA journal_mode=WAL")

        # Set a reasonable busy timeout (5 seconds).
        await self._db.execute("PRAGMA busy_timeout=5000")

        # Create the storage_entries table.
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS storage_entries (
                key           TEXT PRIMARY KEY,
                data          BLOB NOT NULL,
                metadata      TEXT NOT NULL DEFAULT '{}',
                content_type  TEXT DEFAULT 'application/octet-stream',
                size          INTEGER NOT NULL DEFAULT 0,
                last_modified TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_storage_entries_key
                ON storage_entries(key)
        """)

        # Create the advisory_locks table for advisory locking.
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS advisory_locks (
                key         TEXT PRIMARY KEY,
                lock_id     TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                expires_at  TEXT NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_advisory_locks_expires
                ON advisory_locks(expires_at)
        """)

        await self._db.commit()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def load(self, key: str) -> StorageEntry | None:
        """Load a stored entry by key.

        Returns None if the key does not exist.
        """
        self._ensure_connected()

        cursor = await self._db.execute(
            "SELECT key, data, metadata FROM storage_entries WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()

        if row is None:
            return None

        return StorageEntry(
            key=row[0],
            data=row[1],
            metadata=json.loads(row[2]),
        )

    async def save(self, key: str, entry: StorageEntry) -> None:
        """Save an entry under the given key. Overwrites if it exists.

        Automatically tracks the data size and timestamps.
        """
        self._ensure_connected()

        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(entry.metadata)
        content_type = entry.metadata.get("content_type")
        data_size = len(entry.data)

        await self._db.execute(
            """
            INSERT INTO storage_entries (key, data, metadata, content_type, size, last_modified)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                data = excluded.data,
                metadata = excluded.metadata,
                content_type = excluded.content_type,
                size = excluded.size,
                last_modified = excluded.last_modified
            """,
            (key, entry.data, metadata_json, content_type, data_size, now),
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    async def list(self, prefix: str | None = None) -> list[str]:
        """Return keys matching the optional prefix, or all keys."""
        self._ensure_connected()

        if prefix:
            cursor = await self._db.execute(
                "SELECT key FROM storage_entries WHERE key LIKE ? ORDER BY key",
                (f"{prefix}%",),
            )
        else:
            cursor = await self._db.execute(
                "SELECT key FROM storage_entries ORDER BY key"
            )

        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def delete(self, key: str) -> bool:
        """Delete an entry by key. Returns True if it existed."""
        self._ensure_connected()

        cursor = await self._db.execute(
            "DELETE FROM storage_entries WHERE key = ?", (key,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # StatQuery
    # ------------------------------------------------------------------

    async def stat(self, key: str) -> EntryMetadata | None:
        """Return metadata for a key without loading the full data blob."""
        self._ensure_connected()

        cursor = await self._db.execute(
            "SELECT key, size, last_modified, content_type FROM storage_entries WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()

        if row is None:
            return None

        return EntryMetadata(
            key=row[0],
            size=row[1],
            last_modified=datetime.fromisoformat(row[2]),
            content_type=row[3],
        )

    async def exists(self, key: str) -> bool:
        """Return True if an entry exists at the given key."""
        self._ensure_connected()

        cursor = await self._db.execute(
            "SELECT 1 FROM storage_entries WHERE key = ? LIMIT 1", (key,)
        )
        row = await cursor.fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # Locking
    # ------------------------------------------------------------------

    async def acquire(self, key: str, timeout: float | None = None) -> LockHandle:
        """Acquire an advisory lock on the given key.

        The lock is implemented as a row in the ``locks`` table. If the key
        is already locked, this method polls at 0.5s intervals until the
        lock is available or the timeout expires.

        Expired locks are automatically cleaned up before attempting to
        acquire.

        Args:
            key: The storage key to lock.
            timeout: Maximum seconds to wait. None uses the default timeout.

        Raises:
            TimeoutError: If the lock cannot be acquired within the timeout.
        """
        import asyncio

        self._ensure_connected()

        effective_timeout = timeout if timeout is not None else self._lock_expiration_seconds
        lock_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        acquired_at = now.isoformat()
        expires_at_dt = now.replace(
            second=now.second + int(effective_timeout),
        ) if effective_timeout else None

        deadline = asyncio.get_event_loop().time() + effective_timeout

        while True:
            # Clean up expired locks first.
            await self._cleanup_expired_locks()

            try:
                await self._db.execute(
                    """
                    INSERT INTO advisory_locks (key, lock_id, acquired_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        key,
                        lock_id,
                        acquired_at,
                        expires_at_dt.isoformat() if expires_at_dt else None,
                    ),
                )
                await self._db.commit()

                return LockHandle(
                    key=key,
                    lock_id=lock_id,
                    acquired_at=now,
                    expires_at=expires_at_dt,
                )

            except aiosqlite.IntegrityError:
                # Lock already held by another caller.
                if asyncio.get_event_loop().time() >= deadline:
                    raise TimeoutError(
                        f"Could not acquire lock on '{key}' within "
                        f"{effective_timeout}s"
                    )
                await asyncio.sleep(self._lock_retry_interval_ms / 1000.0)

    async def release(self, lock: LockHandle) -> None:
        """Release a previously acquired lock.

        Only the holder (identified by lock_id) can release the lock.
        """
        self._ensure_connected()

        await self._db.execute(
            "DELETE FROM advisory_locks WHERE key = ? AND lock_id = ?",
            (lock.key, lock.lock_id),
        )
        await self._db.commit()

    async def is_locked(self, key: str) -> bool:
        """Return True if the given key is currently locked.

        Expired locks are cleaned up before checking.
        """
        self._ensure_connected()
        await self._cleanup_expired_locks()

        cursor = await self._db.execute(
            "SELECT 1 FROM advisory_locks WHERE key = ? LIMIT 1", (key,)
        )
        row = await cursor.fetchone()
        return row is not None

    async def _cleanup_expired_locks(self) -> None:
        """Remove locks whose expires_at timestamp has passed."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "DELETE FROM advisory_locks WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _ensure_connected(self) -> None:
        """Raise an error if the database connection is not open."""
        if self._db is None:
            raise RuntimeError(
                "Database not initialized. Call 'await connector.initialize()' first."
            )


# ---------------------------------------------------------------------------
# Usage example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import tempfile
    import os

    async def main() -> None:
        # Use a temporary file for the demo database.
        tmp_dir = tempfile.mkdtemp()
        db_path = os.path.join(tmp_dir, "demo_state.db")

        connector = SqliteStorageConnector(
            db_path=db_path,
            wal_mode=True,
            lock_expiration_seconds=30,
            lock_retry_interval_ms=100,
        )
        await connector.initialize()

        try:
            # ----- Persistence -----
            print("=== Persistence ===")

            # Save some entries.
            state_data = json.dumps({
                "models": {
                    "gpt-4o": {"status": "active", "failure_count": 0},
                    "claude-sonnet": {"status": "standby", "failure_count": 3},
                },
                "last_rotation": "2025-01-15T10:30:00Z",
            }).encode("utf-8")

            entry = StorageEntry(
                key="state/pool/default",
                data=state_data,
                metadata={"content_type": "application/json", "pool_id": "default"},
            )
            await connector.save("state/pool/default", entry)
            print("Saved: state/pool/default")

            config_data = json.dumps({
                "providers": ["openai", "anthropic"],
                "rotation_policy": "time-of-day",
            }).encode("utf-8")

            await connector.save(
                "config/pools/default",
                StorageEntry(
                    key="config/pools/default",
                    data=config_data,
                    metadata={"content_type": "application/json"},
                ),
            )
            print("Saved: config/pools/default")

            # Load an entry.
            loaded = await connector.load("state/pool/default")
            if loaded:
                parsed = json.loads(loaded.data)
                print(f"Loaded: {loaded.key}, models={list(parsed['models'].keys())}")

            # ----- Inventory -----
            print("\n=== Inventory ===")

            all_keys = await connector.list()
            print(f"All keys: {all_keys}")

            state_keys = await connector.list(prefix="state/")
            print(f"State keys: {state_keys}")

            config_keys = await connector.list(prefix="config/")
            print(f"Config keys: {config_keys}")

            # ----- StatQuery -----
            print("\n=== StatQuery ===")

            meta = await connector.stat("state/pool/default")
            if meta:
                print(f"Key: {meta.key}")
                print(f"  Size: {meta.size} bytes")
                print(f"  Last modified: {meta.last_modified}")
                print(f"  Content type: {meta.content_type}")

            exists = await connector.exists("state/pool/default")
            print(f"Exists 'state/pool/default': {exists}")

            exists2 = await connector.exists("nonexistent/key")
            print(f"Exists 'nonexistent/key': {exists2}")

            # ----- Locking -----
            print("\n=== Locking ===")

            lock = await connector.acquire("state/pool/default", timeout=5.0)
            print(f"Acquired lock: id={lock.lock_id[:8]}..., key={lock.key}")

            is_locked = await connector.is_locked("state/pool/default")
            print(f"Is locked: {is_locked}")

            # Try to acquire the same lock (should timeout quickly).
            try:
                await connector.acquire("state/pool/default", timeout=1.0)
            except TimeoutError as e:
                print(f"Expected timeout: {e}")

            # Release and verify.
            await connector.release(lock)
            print(f"Released lock: {lock.lock_id[:8]}...")

            is_locked = await connector.is_locked("state/pool/default")
            print(f"Is locked after release: {is_locked}")

            # ----- Delete -----
            print("\n=== Delete ===")

            deleted = await connector.delete("config/pools/default")
            print(f"Deleted 'config/pools/default': {deleted}")

            deleted2 = await connector.delete("nonexistent/key")
            print(f"Deleted 'nonexistent/key': {deleted2}")

            remaining = await connector.list()
            print(f"Remaining keys: {remaining}")

        finally:
            await connector.close()
            # Clean up temp files.
            for f in os.listdir(tmp_dir):
                os.unlink(os.path.join(tmp_dir, f))
            os.rmdir(tmp_dir)
            print("\nDone. Temp database cleaned up.")

    asyncio.run(main())
