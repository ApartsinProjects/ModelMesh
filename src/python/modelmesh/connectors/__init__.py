"""Pre-shipped connector implementations for ModelMesh Lite.

This package provides ready-to-use connectors for all six connector
types: providers, secret stores, observability, rotation, storage,
and discovery. Each connector is registered in the
:data:`CONNECTOR_REGISTRY` dictionary, which maps dot-notated connector
IDs to their implementation classes.

Usage::

    from modelmesh.connectors import CONNECTOR_REGISTRY

    # Look up a connector class by ID
    provider_cls = CONNECTOR_REGISTRY["openai.llm.v1"]
    provider = provider_cls(config)
"""
from __future__ import annotations

from modelmesh.connectors.observability.console_connector import (
    ConsoleObservabilityConnector,
)
from modelmesh.connectors.observability.file_connector import (
    FileObservabilityConnector,
)
from modelmesh.connectors.observability.null_connector import (
    NullObservabilityConnector,
)
from modelmesh.connectors.providers.anthropic_provider import AnthropicProvider
from modelmesh.connectors.providers.openai_provider import OpenAIProvider
from modelmesh.connectors.rotation.stick_until_failure import (
    StickUntilFailurePolicy,
)
from modelmesh.connectors.secret_stores.env_store import EnvSecretStore
from modelmesh.connectors.storage.local_file import LocalFileStorage

CONNECTOR_REGISTRY: dict[str, type] = {
    # Providers
    OpenAIProvider.CONNECTOR_ID: OpenAIProvider,
    AnthropicProvider.CONNECTOR_ID: AnthropicProvider,
    # Secret stores
    EnvSecretStore.CONNECTOR_ID: EnvSecretStore,
    # Observability
    ConsoleObservabilityConnector.CONNECTOR_ID: ConsoleObservabilityConnector,
    NullObservabilityConnector.CONNECTOR_ID: NullObservabilityConnector,
    FileObservabilityConnector.CONNECTOR_ID: FileObservabilityConnector,
    # Rotation
    StickUntilFailurePolicy.CONNECTOR_ID: StickUntilFailurePolicy,
    # Storage
    LocalFileStorage.CONNECTOR_ID: LocalFileStorage,
}

__all__ = [
    "CONNECTOR_REGISTRY",
    "OpenAIProvider",
    "AnthropicProvider",
    "EnvSecretStore",
    "ConsoleObservabilityConnector",
    "NullObservabilityConnector",
    "FileObservabilityConnector",
    "StickUntilFailurePolicy",
    "LocalFileStorage",
]
