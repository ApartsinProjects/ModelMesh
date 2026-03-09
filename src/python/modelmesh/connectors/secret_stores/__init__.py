"""Pre-shipped secret store connectors for ModelMesh Lite.

Exports the environment variable secret store connector and its
configuration class.
"""
from __future__ import annotations

from modelmesh.connectors.secret_stores.env_store import (
    EnvSecretStore,
    EnvSecretStoreConfig,
)

__all__ = [
    "EnvSecretStore",
    "EnvSecretStoreConfig",
]
