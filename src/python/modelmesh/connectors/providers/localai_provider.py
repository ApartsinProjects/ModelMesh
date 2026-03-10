"""Pre-shipped LocalAI provider connector.

Wraps the CDK's OpenAICompatibleProvider with configuration for
LocalAI, a self-hosted AI inference server that exposes an
OpenAI-compatible REST API and supports multiple model backends.

Connector ID: ``localai.local.v1``

LocalAI runs locally and requires no API key.  Models are loaded
from the model gallery or local files.  Set the ``LOCALAI_HOST``
environment variable to override the default URL.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.interfaces.provider import ModelInfo

__all__ = [
    "LocalAIProviderConfig",
    "LocalAIProvider",
]


@dataclass
class LocalAIProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped LocalAI provider.

    Attributes:
        base_url: LocalAI server URL. Defaults to
            ``"http://localhost:8080"``.
        api_key: Not required.  Defaults to empty string.
    """

    base_url: str = "http://localhost:8080"
    api_key: str = ""
    models: list[ModelInfo] = field(default_factory=list)
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.text-generation.chat-completion"]
    )


class LocalAIProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for LocalAI.

    Connector ID: ``localai.local.v1``

    Usage::

        provider = LocalAIProvider()
    """

    CONNECTOR_ID: str = "localai.local.v1"
    RUNTIME: str = "node"

    def __init__(self, config: LocalAIProviderConfig | None = None) -> None:
        if config is None:
            config = LocalAIProviderConfig()
        super().__init__(config)
