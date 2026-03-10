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

from modelmesh.connectors.observability.callback_connector import (
    CallbackConnector,
)
from modelmesh.connectors.observability.console_connector import (
    ConsoleObservabilityConnector,
)
from modelmesh.connectors.observability.file_connector import (
    FileObservabilityConnector,
)
from modelmesh.connectors.observability.json_log_connector import (
    JsonLogConnector,
)
from modelmesh.connectors.observability.null_connector import (
    NullObservabilityConnector,
)
from modelmesh.connectors.observability.webhook_connector import (
    WebhookConnector,
)
from modelmesh.connectors.providers.anthropic_provider import AnthropicProvider
from modelmesh.connectors.providers.assemblyai_provider import AssemblyAIProvider
from modelmesh.connectors.providers.cohere_provider import CohereProvider
from modelmesh.connectors.providers.deepseek_provider import DeepSeekProvider
from modelmesh.connectors.providers.elevenlabs_provider import ElevenLabsProvider
from modelmesh.connectors.providers.firecrawl_provider import FirecrawlProvider
from modelmesh.connectors.providers.gemini_provider import GeminiProvider
from modelmesh.connectors.providers.groq_provider import GroqProvider
from modelmesh.connectors.providers.jina_provider import JinaProvider
from modelmesh.connectors.providers.mistral_provider import MistralProvider
from modelmesh.connectors.providers.openai_provider import OpenAIProvider
from modelmesh.connectors.providers.openrouter_provider import OpenRouterProvider
from modelmesh.connectors.providers.perplexity_provider import PerplexityProvider
from modelmesh.connectors.providers.serper_provider import SerperProvider
from modelmesh.connectors.providers.tavily_provider import TavilyProvider
from modelmesh.connectors.providers.together_provider import TogetherProvider
from modelmesh.connectors.providers.xai_provider import XAIProvider
from modelmesh.connectors.rotation.stick_until_failure import (
    StickUntilFailurePolicy,
)
from modelmesh.connectors.secret_stores.dotenv_store import DotenvSecretStore
from modelmesh.connectors.secret_stores.env_store import EnvSecretStore
from modelmesh.connectors.secret_stores.json_store import JsonSecretStore
from modelmesh.connectors.secret_stores.keyring_store import KeyringSecretStore
from modelmesh.connectors.storage.local_file import LocalFileStorage
from modelmesh.connectors.storage.memory_storage import MemoryStorage
from modelmesh.connectors.storage.sqlite_storage import SqliteStorage

CONNECTOR_REGISTRY: dict[str, type] = {
    # Providers
    OpenAIProvider.CONNECTOR_ID: OpenAIProvider,
    AnthropicProvider.CONNECTOR_ID: AnthropicProvider,
    GeminiProvider.CONNECTOR_ID: GeminiProvider,
    GroqProvider.CONNECTOR_ID: GroqProvider,
    DeepSeekProvider.CONNECTOR_ID: DeepSeekProvider,
    MistralProvider.CONNECTOR_ID: MistralProvider,
    TogetherProvider.CONNECTOR_ID: TogetherProvider,
    OpenRouterProvider.CONNECTOR_ID: OpenRouterProvider,
    XAIProvider.CONNECTOR_ID: XAIProvider,
    CohereProvider.CONNECTOR_ID: CohereProvider,
    PerplexityProvider.CONNECTOR_ID: PerplexityProvider,
    ElevenLabsProvider.CONNECTOR_ID: ElevenLabsProvider,
    TavilyProvider.CONNECTOR_ID: TavilyProvider,
    SerperProvider.CONNECTOR_ID: SerperProvider,
    JinaProvider.CONNECTOR_ID: JinaProvider,
    FirecrawlProvider.CONNECTOR_ID: FirecrawlProvider,
    AssemblyAIProvider.CONNECTOR_ID: AssemblyAIProvider,
    # Secret stores
    EnvSecretStore.CONNECTOR_ID: EnvSecretStore,
    DotenvSecretStore.CONNECTOR_ID: DotenvSecretStore,
    JsonSecretStore.CONNECTOR_ID: JsonSecretStore,
    KeyringSecretStore.CONNECTOR_ID: KeyringSecretStore,
    # Observability
    ConsoleObservabilityConnector.CONNECTOR_ID: ConsoleObservabilityConnector,
    NullObservabilityConnector.CONNECTOR_ID: NullObservabilityConnector,
    FileObservabilityConnector.CONNECTOR_ID: FileObservabilityConnector,
    JsonLogConnector.CONNECTOR_ID: JsonLogConnector,
    WebhookConnector.CONNECTOR_ID: WebhookConnector,
    CallbackConnector.CONNECTOR_ID: CallbackConnector,
    # Rotation
    StickUntilFailurePolicy.CONNECTOR_ID: StickUntilFailurePolicy,
    # Storage
    LocalFileStorage.CONNECTOR_ID: LocalFileStorage,
    SqliteStorage.CONNECTOR_ID: SqliteStorage,
    MemoryStorage.CONNECTOR_ID: MemoryStorage,
}

__all__ = [
    "CONNECTOR_REGISTRY",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "GroqProvider",
    "DeepSeekProvider",
    "MistralProvider",
    "TogetherProvider",
    "OpenRouterProvider",
    "XAIProvider",
    "CohereProvider",
    "PerplexityProvider",
    "ElevenLabsProvider",
    "TavilyProvider",
    "SerperProvider",
    "JinaProvider",
    "FirecrawlProvider",
    "AssemblyAIProvider",
    "EnvSecretStore",
    "DotenvSecretStore",
    "JsonSecretStore",
    "KeyringSecretStore",
    "ConsoleObservabilityConnector",
    "NullObservabilityConnector",
    "FileObservabilityConnector",
    "JsonLogConnector",
    "WebhookConnector",
    "CallbackConnector",
    "StickUntilFailurePolicy",
    "LocalFileStorage",
    "SqliteStorage",
    "MemoryStorage",
]
