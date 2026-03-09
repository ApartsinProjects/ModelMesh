"""Local file storage connector.

Pre-configured KeyValueStorage with a file backend for single-process
deployments and development use. Persists model state, configuration
snapshots, and rotation data to a local JSON file.

Connector ID: ``modelmesh.local-file.v1``
"""
from __future__ import annotations

from dataclasses import dataclass

from modelmesh.cdk.specialized.kv_storage import (
    KeyValueStorage,
    KeyValueStorageConfig,
)

__all__ = [
    "LocalFileStorageConfig",
    "LocalFileStorage",
]


@dataclass
class LocalFileStorageConfig(KeyValueStorageConfig):
    """Configuration for the local file storage connector.

    Pre-configures the KeyValueStorage backend to ``"file"`` with a
    sensible default file path.

    Attributes:
        file_path: Path to the JSON state file. Defaults to
            ``"modelmesh_state.json"`` in the current working directory.
    """

    backend: str = "file"
    file_path: str = "modelmesh_state.json"


class LocalFileStorage(KeyValueStorage):
    """Pre-shipped storage connector using a local JSON file.

    Provides persistent key-value storage backed by a single JSON file.
    Suitable for development, testing, and single-process production
    deployments. Not suitable for multi-process or distributed
    deployments -- use a shared backend (Redis, S3, etc.) instead.

    Connector ID: ``modelmesh.local-file.v1``

    Usage::

        storage = LocalFileStorage(LocalFileStorageConfig(
            file_path="/var/data/modelmesh/state.json",
        ))
        await storage.save("key", entry)
        loaded = await storage.load("key")
    """

    CONNECTOR_ID: str = "modelmesh.local-file.v1"

    def __init__(self, config: LocalFileStorageConfig | None = None) -> None:
        if config is None:
            config = LocalFileStorageConfig()
        super().__init__(config)
