"""Pre-shipped DeepSeek provider connector.

Wraps the CDK's OpenAICompatibleProvider with default model catalogue,
pricing, and configuration for the DeepSeek API. This connector is
registered as ``deepseek.api.v1`` and requires only an API key to use.
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
    "DeepSeekProviderConfig",
    "DeepSeekProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="deepseek-chat",
        name="DeepSeek Chat",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "system_prompt": True},
        context_window=64_000,
        max_output_tokens=8_192,
        pricing=ModelPricing(
            input_per_1k_tokens=0.00014,
            output_per_1k_tokens=0.00028,
        ),
    ),
    ModelInfo(
        id="deepseek-reasoner",
        name="DeepSeek Reasoner",
        capabilities=["generation.text-generation.chat-completion"],
        features={"reasoning": True, "system_prompt": True},
        context_window=64_000,
        max_output_tokens=8_192,
    ),
]


@dataclass
class DeepSeekProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped DeepSeek provider.

    Extends OpenAICompatibleConfig with sensible defaults for the
    DeepSeek API. The default model catalogue includes DeepSeek Chat
    and DeepSeek Reasoner.

    Attributes:
        base_url: DeepSeek API base URL. Defaults to
            ``"https://api.deepseek.com"``.
        models: Model catalogue. Defaults to the built-in list of
            supported DeepSeek models with pricing information.
    """

    base_url: str = "https://api.deepseek.com"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.text-generation.chat-completion"]
    )


class DeepSeekProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for the DeepSeek API.

    Provides a zero-configuration entry point for DeepSeek models.
    Supply an API key and optionally override the model list.

    Connector ID: ``deepseek.api.v1``

    Usage::

        provider = DeepSeekProvider(DeepSeekProviderConfig(
            api_key="sk-...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "deepseek.api.v1"

    def __init__(self, config: DeepSeekProviderConfig | None = None) -> None:
        if config is None:
            config = DeepSeekProviderConfig()
        super().__init__(config)
