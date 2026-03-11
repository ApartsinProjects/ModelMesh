"""Pre-shipped Mistral AI provider connector.

Wraps the CDK's OpenAICompatibleProvider with default model catalogue,
pricing, and configuration for the Mistral AI API. This connector is
registered as ``mistral.api.v1`` and requires only an API key to use.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.interfaces.provider import ModelInfo

__all__ = [
    "MistralProviderConfig",
    "MistralProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="mistral-large-latest",
        name="Mistral Large",
        capabilities=["generation.text-generation.chat-completion"],
        features={
            "tool_calling": True,
            "vision": True,
            "system_prompt": True,
        },
        context_window=128_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="mistral-small-latest",
        name="Mistral Small",
        capabilities=[
            "generation.text-generation.chat-completion",
            "representation.embeddings.text-embeddings",
        ],
        features={"tool_calling": True, "system_prompt": True},
        context_window=128_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="codestral-latest",
        name="Codestral",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=32_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="mistral-embed",
        name="Mistral Embed",
        capabilities=["representation.embeddings.text-embeddings"],
        features={},
        context_window=8_192,
        max_output_tokens=0,
    ),
]


@dataclass
class MistralProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped Mistral AI provider.

    Extends OpenAICompatibleConfig with sensible defaults for the
    Mistral AI API. The default model catalogue includes Mistral Large,
    Mistral Small, Codestral, and Mistral Embed.

    Attributes:
        base_url: Mistral AI API base URL. Defaults to
            ``"https://api.mistral.ai"``.
        models: Model catalogue. Defaults to the built-in list of
            supported Mistral models.
    """

    base_url: str = "https://api.mistral.ai"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: [
            "generation.text-generation.chat-completion",
            "representation.embeddings.text-embeddings",
        ]
    )


class MistralProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for the Mistral AI API.

    Provides a zero-configuration entry point for Mistral models.
    Supply an API key and optionally override the model list.

    Overrides ``_get_completion_endpoint`` to use the Mistral-specific
    endpoint path.

    Connector ID: ``mistral.api.v1``

    Usage::

        provider = MistralProvider(MistralProviderConfig(
            api_key="...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "mistral.api.v1"

    def __init__(self, config: MistralProviderConfig | None = None) -> None:
        if config is None:
            config = MistralProviderConfig()
        super().__init__(config)

    def _get_completion_endpoint(self) -> str:
        """Return the Mistral chat completions endpoint URL."""
        base = self._config.base_url.rstrip("/")
        return f"{base}/v1/chat/completions"
