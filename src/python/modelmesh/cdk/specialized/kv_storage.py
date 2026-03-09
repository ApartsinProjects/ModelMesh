"""Key-value storage for the CDK.

Extends BaseStorage with pluggable backends: in-memory (default) or
file-based JSON persistence. The memory backend uses the inherited
dictionary; the file backend serializes to and deserializes from a
JSON file on each write and at initialization.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from modelmesh.cdk.base_storage import BaseStorage, BaseStorageConfig
from modelmesh.interfaces.storage import StorageEntry

__all__ = [
    "KeyValueStorageConfig",
    "KeyValueStorage",
]


@dataclass
class KeyValueStorageConfig(BaseStorageConfig):
    """Configuration for key-value storage.

    Attributes:
        backend: Storage backend -- ``"memory"`` or ``"file"``.
        file_path: Path to the JSON file (required when backend is
            ``"file"``).
    """

    backend: str = "memory"
    file_path: Optional[str] = None


class KeyValueStorage(BaseStorage):
    """Pluggable key-value storage with memory or file backend.

    - **Memory backend**: Uses the inherited in-memory dictionary from
      ``BaseStorage``. Data is lost when the process exits.
    - **File backend**: Persists all entries to a JSON file. The file
      is loaded at initialization and written after each save or delete
      operation.

    Usage::

        # In-memory (default)
        store = KeyValueStorage(KeyValueStorageConfig())

        # File-backed
        store = KeyValueStorage(KeyValueStorageConfig(
            backend="file",
            file_path="/var/data/modelmesh/state.json",
        ))
    """

    def __init__(self, config: KeyValueStorageConfig) -> None:
        super().__init__(config)
        self._kv_config = config

        if config.backend == "file" and config.file_path:
            self._load_from_file()

    # -- Persistence overrides for file backend ------------------------------

    async def save(self, key: str, entry: StorageEntry) -> None:
        """Save an entry, persisting to file if using the file backend."""
        await super().save(key, entry)
        if self._kv_config.backend == "file":
            self._save_to_file()

    async def delete(self, key: str) -> bool:
        """Delete an entry, persisting to file if using the file backend."""
        result = await super().delete(key)
        if result and self._kv_config.backend == "file":
            self._save_to_file()
        return result

    # -- File I/O ------------------------------------------------------------

    def _load_from_file(self) -> None:
        """Load stored entries from the JSON file.

        The file format is a dictionary mapping keys to objects with
        ``data`` (base64-encoded bytes), ``metadata``, and
        ``timestamp`` fields. If the file does not exist or cannot
        be parsed, the store starts empty.
        """
        if not self._kv_config.file_path:
            return

        try:
            with open(self._kv_config.file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, IOError, json.JSONDecodeError, ValueError):
            return

        if not isinstance(raw, dict):
            return

        import base64

        for key, record in raw.items():
            if not isinstance(record, dict):
                continue
            data_b64 = record.get("data", "")
            try:
                data = base64.b64decode(data_b64)
            except Exception:
                data = data_b64.encode("utf-8") if isinstance(data_b64, str) else b""
            metadata = record.get("metadata", {})
            self._store[key] = StorageEntry(
                key=key, data=data, metadata=metadata
            )
            ts_str = record.get("timestamp")
            if ts_str:
                try:
                    self._timestamps[key] = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    self._timestamps[key] = datetime.utcnow()
            else:
                self._timestamps[key] = datetime.utcnow()

    def _save_to_file(self) -> None:
        """Persist all stored entries to the JSON file.

        Each entry is serialized with base64-encoded data, its
        metadata dictionary, and an ISO-format timestamp.
        """
        if not self._kv_config.file_path:
            return

        import base64

        output: dict = {}
        for key, entry in self._store.items():
            output[key] = {
                "data": base64.b64encode(entry.data).decode("ascii"),
                "metadata": entry.metadata,
                "timestamp": self._timestamps.get(
                    key, datetime.utcnow()
                ).isoformat(),
            }

        try:
            with open(self._kv_config.file_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, default=str)
        except (OSError, IOError):
            pass
