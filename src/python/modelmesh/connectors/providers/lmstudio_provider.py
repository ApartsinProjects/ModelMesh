"""Pre-shipped LM Studio provider connector.

Wraps the CDK's OpenAICompatibleProvider with configuration for
LM Studio, a desktop application that serves locally-loaded models
via an OpenAI-compatible REST API.

Connector ID: ``lmstudio.local.v1``

LM Studio runs locally and requires no API key.  Models are loaded
by the user in the LM Studio GUI, so the default model list is
empty.  Set the ``LMSTUDIO_HOST`` environment variable to override
the default URL.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.interfaces.provider import ModelInfo

__all__ = [
    "LMStudioProviderConfig",
    "LMStudioProvider",
]


@dataclass
class LMStudioProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped LM Studio provider.

    Attributes:
        base_url: LM Studio server URL. Defaults to
            ``"http://localhost:1234"``.
        api_key: Not required.  Defaults to empty string.
    """

    base_url: str = "http://localhost:1234"
    api_key: str = ""
    models: list[ModelInfo] = field(default_factory=list)
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.text-generation.chat-completion"]
    )


class LMStudioProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for LM Studio.

    Connector ID: ``lmstudio.local.v1``

    Usage::

        provider = LMStudioProvider()
    """

    CONNECTOR_ID: str = "lmstudio.local.v1"
    RUNTIME: str = "node"

    def __init__(self, config: LMStudioProviderConfig | None = None) -> None:
        if config is None:
            config = LMStudioProviderConfig()
        super().__init__(config)
