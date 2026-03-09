"""Pre-shipped storage connectors for ModelMesh Lite.

Exports the local file storage connector and its configuration class.
"""
from __future__ import annotations

from modelmesh.connectors.storage.local_file import (
    LocalFileStorage,
    LocalFileStorageConfig,
)

__all__ = [
    "LocalFileStorage",
    "LocalFileStorageConfig",
]
