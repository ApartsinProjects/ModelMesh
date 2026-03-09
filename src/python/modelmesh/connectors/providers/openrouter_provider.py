"""Pre-shipped OpenRouter provider connector.

Wraps the CDK's OpenAICompatibleProvider with default model catalogue,
pricing, and configuration for the OpenRouter gateway API. This connector
is registered as ``openrouter.gateway.v1`` and requires only an API key
to use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.interfaces.provider import ModelInfo, ModelPricing

__all__ = [
    "OpenRouterProviderConfig",
    "OpenRouterProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="auto",
        name="Auto (Best Available)",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=128_000,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="openai/gpt-4o",
        name="OpenAI GPT-4o",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=128_000,
        max_output_tokens=16_384,
    ),
    ModelInfo(
        id="anthropic/claude-sonnet-4",
        name="Anthropic Claude Sonnet 4",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=200_000,
        max_output_tokens=16_384,
    ),
    ModelInfo(
        id="google/gemini-2.0-flash-exp",
        name="Google Gemini 2.0 Flash Exp",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=1_000_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="meta-llama/llama-3.3-70b-instruct",
        name="Meta Llama 3.3 70B Instruct",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=128_000,
        max_output_tokens=4_096,
    ),
]


@dataclass
class OpenRouterProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped OpenRouter provider.

    Extends OpenAICompatibleConfig with sensible defaults for the
    OpenRouter gateway API. The default model catalogue includes models
    from OpenAI, Anthropic, Google, and Meta via the OpenRouter gateway.

    Attributes:
        base_url: OpenRouter API base URL. Defaults to
            ``"https://openrouter.ai/api"``.
        models: Model catalogue. Defaults to the built-in list of
            supported OpenRouter models.
        http_referer: Value for the ``HTTP-Referer`` header required
            by OpenRouter. Defaults to an empty string.
        x_title: Value for the ``X-Title`` header used by OpenRouter
            for app identification. Defaults to ``"ModelMesh"``.
    """

    base_url: str = "https://openrouter.ai/api"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.text-generation.chat-completion"]
    )
    http_referer: str = ""
    x_title: str = "ModelMesh"


class OpenRouterProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for the OpenRouter gateway API.

    Provides a zero-configuration entry point for models accessible
    through the OpenRouter gateway. Supply an API key and optionally
    override the model list or gateway headers.

    Overrides ``_build_headers`` to include the ``HTTP-Referer`` and
    ``X-Title`` headers required by the OpenRouter API.

    Connector ID: ``openrouter.gateway.v1``

    Usage::

        provider = OpenRouterProvider(OpenRouterProviderConfig(
            api_key="sk-or-...",
            http_referer="https://myapp.example.com",
            x_title="My Application",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "openrouter.gateway.v1"

    def __init__(self, config: OpenRouterProviderConfig | None = None) -> None:
        if config is None:
            config = OpenRouterProviderConfig()
        super().__init__(config)
        self._or_config = config

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers, adding OpenRouter-specific headers."""
        headers = super()._build_headers()
        if self._or_config.http_referer:
            headers["HTTP-Referer"] = self._or_config.http_referer
        if self._or_config.x_title:
            headers["X-Title"] = self._or_config.x_title
        return headers
