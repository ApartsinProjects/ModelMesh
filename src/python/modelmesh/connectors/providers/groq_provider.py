"""Pre-shipped Groq provider connector.

Wraps the CDK's OpenAICompatibleProvider with default model catalogue,
pricing, and configuration for the Groq API. This connector is
registered as ``groq.api.v1`` and requires only an API key to use.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.interfaces.provider import ModelInfo

__all__ = [
    "GroqProviderConfig",
    "GroqProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="llama-3.3-70b-versatile",
        name="Llama 3.3 70B Versatile",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "system_prompt": True},
        context_window=128_000,
        max_output_tokens=32_768,
    ),
    ModelInfo(
        id="llama-3.1-8b-instant",
        name="Llama 3.1 8B Instant",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=128_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="gemma2-9b-it",
        name="Gemma 2 9B IT",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=8_192,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="mixtral-8x7b-32768",
        name="Mixtral 8x7B 32768",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=32_768,
        max_output_tokens=32_768,
    ),
    ModelInfo(
        id="whisper-large-v3-turbo",
        name="Whisper Large V3 Turbo",
        capabilities=["understanding.audio.speech-to-text"],
        features={},
        context_window=0,
        max_output_tokens=0,
    ),
]


@dataclass
class GroqProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped Groq provider.

    Extends OpenAICompatibleConfig with sensible defaults for the
    Groq API. The default model catalogue includes Llama, Gemma,
    Mixtral, and Whisper models.

    Attributes:
        base_url: Groq API base URL. Defaults to
            ``"https://api.groq.com/openai"``.
        models: Model catalogue. Defaults to the built-in list of
            supported Groq models.
    """

    base_url: str = "https://api.groq.com/openai"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: [
            "generation.text-generation.chat-completion",
            "understanding.audio.speech-to-text",
        ]
    )


class GroqProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for the Groq API.

    Provides a zero-configuration entry point for Groq models.
    Supply an API key and optionally override the model list.

    Connector ID: ``groq.api.v1``

    Usage::

        provider = GroqProvider(GroqProviderConfig(
            api_key="gsk_...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "groq.api.v1"

    def __init__(self, config: GroqProviderConfig | None = None) -> None:
        if config is None:
            config = GroqProviderConfig()
        super().__init__(config)
