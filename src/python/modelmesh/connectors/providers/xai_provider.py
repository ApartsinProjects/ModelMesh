"""Pre-shipped xAI (Grok) provider connector.

Wraps the CDK's OpenAICompatibleProvider with default model catalogue,
pricing, and configuration for the xAI API. This connector is
registered as ``xai.grok.v1`` and requires only an API key to use.
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
    "XAIProviderConfig",
    "XAIProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="grok-2",
        name="Grok 2",
        capabilities=["generation.text-generation.chat-completion"],
        features={
            "tool_calling": True,
            "vision": True,
            "system_prompt": True,
        },
        context_window=128_000,
        max_output_tokens=32_768,
    ),
    ModelInfo(
        id="grok-2-mini",
        name="Grok 2 Mini",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=128_000,
        max_output_tokens=32_768,
    ),
]


@dataclass
class XAIProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped xAI provider.

    Extends OpenAICompatibleConfig with sensible defaults for the
    xAI API. The default model catalogue includes Grok 2 and
    Grok 2 Mini.

    Attributes:
        base_url: xAI API base URL. Defaults to
            ``"https://api.x.ai"``.
        models: Model catalogue. Defaults to the built-in list of
            supported xAI models.
    """

    base_url: str = "https://api.x.ai"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.text-generation.chat-completion"]
    )


class XAIProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for the xAI API.

    Provides a zero-configuration entry point for xAI Grok models.
    Supply an API key and optionally override the model list.

    Connector ID: ``xai.grok.v1``

    Usage::

        provider = XAIProvider(XAIProviderConfig(
            api_key="xai-...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "xai.grok.v1"

    def __init__(self, config: XAIProviderConfig | None = None) -> None:
        if config is None:
            config = XAIProviderConfig()
        super().__init__(config)
