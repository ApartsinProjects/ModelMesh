"""Pre-shipped OpenAI provider connector.

Wraps the CDK's OpenAICompatibleProvider with default model catalogue,
pricing, and configuration for the OpenAI API. This connector is
registered as ``openai.llm.v1`` and requires only an API key to use.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.interfaces.provider import ModelInfo, ModelPricing

__all__ = [
    "OpenAIProviderConfig",
    "OpenAIProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="gpt-4o",
        name="GPT-4o",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "vision": True, "system_prompt": True},
        context_window=128_000,
        max_output_tokens=16_384,
        pricing=ModelPricing(
            input_per_1k_tokens=0.0025,
            output_per_1k_tokens=0.01,
        ),
    ),
    ModelInfo(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "vision": True, "system_prompt": True},
        context_window=128_000,
        max_output_tokens=16_384,
        pricing=ModelPricing(
            input_per_1k_tokens=0.00015,
            output_per_1k_tokens=0.0006,
        ),
    ),
    ModelInfo(
        id="gpt-4-turbo",
        name="GPT-4 Turbo",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "vision": True, "system_prompt": True},
        context_window=128_000,
        max_output_tokens=4_096,
        pricing=ModelPricing(
            input_per_1k_tokens=0.01,
            output_per_1k_tokens=0.03,
        ),
    ),
    ModelInfo(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "vision": True, "system_prompt": True},
        context_window=128_000,
        max_output_tokens=16_384,
        pricing=ModelPricing(
            input_per_1k_tokens=0.00015,
            output_per_1k_tokens=0.0006,
        ),
    ),
]


@dataclass
class OpenAIProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped OpenAI provider.

    Extends OpenAICompatibleConfig with sensible defaults for the
    OpenAI API. The default model catalogue includes GPT-4o,
    GPT-4o Mini, GPT-4 Turbo, and GPT-3.5 Turbo.

    Attributes:
        base_url: OpenAI API base URL. Defaults to
            ``"https://api.openai.com"``.
        models: Model catalogue. Defaults to the built-in list of
            supported OpenAI models with pricing information.
    """

    base_url: str = "https://api.openai.com"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.text-generation.chat-completion"]
    )


class OpenAIProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for the OpenAI API.

    Provides a zero-configuration entry point for OpenAI models.
    Supply an API key and optionally override the model list or
    organization.

    Connector ID: ``openai.llm.v1``

    Usage::

        provider = OpenAIProvider(OpenAIProviderConfig(
            api_key="sk-...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "openai.llm.v1"

    def __init__(self, config: OpenAIProviderConfig | None = None) -> None:
        if config is None:
            config = OpenAIProviderConfig()
        super().__init__(config)
