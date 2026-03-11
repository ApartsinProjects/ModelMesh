"""Pre-shipped Together AI provider connector.

Wraps the CDK's OpenAICompatibleProvider with default model catalogue,
pricing, and configuration for the Together AI API. This connector is
registered as ``together.api.v1`` and requires only an API key to use.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.interfaces.provider import ModelInfo

__all__ = [
    "TogetherProviderConfig",
    "TogetherProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        name="Llama 3.3 70B Instruct Turbo",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "system_prompt": True},
        context_window=128_000,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="meta-llama/Llama-3.1-8B-Instruct-Turbo",
        name="Llama 3.1 8B Instruct Turbo",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=128_000,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="Qwen/Qwen2.5-72B-Instruct-Turbo",
        name="Qwen 2.5 72B Instruct Turbo",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "system_prompt": True},
        context_window=128_000,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="deepseek-ai/DeepSeek-V3",
        name="DeepSeek V3",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=128_000,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="BAAI/bge-large-en-v1.5",
        name="BGE Large EN v1.5",
        capabilities=["representation.embeddings.text-embeddings"],
        features={},
        context_window=512,
        max_output_tokens=0,
    ),
    ModelInfo(
        id="stabilityai/stable-diffusion-xl-base-1.0",
        name="Stable Diffusion XL Base 1.0",
        capabilities=["generation.image.text-to-image"],
        features={},
        context_window=0,
        max_output_tokens=0,
    ),
]


@dataclass
class TogetherProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped Together AI provider.

    Extends OpenAICompatibleConfig with sensible defaults for the
    Together AI API. The default model catalogue includes Llama, Qwen,
    DeepSeek, BGE embedding, and Stable Diffusion models.

    Attributes:
        base_url: Together AI API base URL. Defaults to
            ``"https://api.together.xyz"``.
        models: Model catalogue. Defaults to the built-in list of
            supported Together AI models.
    """

    base_url: str = "https://api.together.xyz"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: [
            "generation.text-generation.chat-completion",
            "representation.embeddings.text-embeddings",
            "generation.image.text-to-image",
        ]
    )


class TogetherProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for the Together AI API.

    Provides a zero-configuration entry point for Together AI models.
    Supply an API key and optionally override the model list.

    Overrides ``_get_completion_endpoint`` to use the Together-specific
    endpoint path.

    Connector ID: ``together.api.v1``

    Usage::

        provider = TogetherProvider(TogetherProviderConfig(
            api_key="...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "together.api.v1"

    def __init__(self, config: TogetherProviderConfig | None = None) -> None:
        if config is None:
            config = TogetherProviderConfig()
        super().__init__(config)

    def _get_completion_endpoint(self) -> str:
        """Return the Together AI chat completions endpoint URL."""
        base = self._config.base_url.rstrip("/")
        return f"{base}/v1/chat/completions"
