"""Pre-shipped Ollama provider connector.

Wraps the CDK's OpenAICompatibleProvider with default model catalogue
and configuration for Ollama, a local inference server that exposes
an OpenAI-compatible REST API.

Connector ID: ``ollama.local.v1``

Ollama runs locally and requires no API key.  Set the ``OLLAMA_HOST``
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
    "OllamaProviderConfig",
    "OllamaProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="llama3",
        name="Llama 3",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=8_192,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="codellama",
        name="Code Llama",
        capabilities=[
            "generation.text-generation.chat-completion",
            "generation.text-generation.code-generation",
        ],
        features={"system_prompt": True},
        context_window=16_384,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="mistral",
        name="Mistral",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=8_192,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="gemma2",
        name="Gemma 2",
        capabilities=["generation.text-generation.chat-completion"],
        features={"system_prompt": True},
        context_window=8_192,
        max_output_tokens=4_096,
    ),
]


@dataclass
class OllamaProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped Ollama provider.

    Extends OpenAICompatibleConfig with sensible defaults for the
    Ollama local inference server.  No API key is required.

    Attributes:
        base_url: Ollama server URL. Defaults to
            ``"http://localhost:11434"``.
        api_key: Not required.  Defaults to empty string.
        models: Model catalogue. Defaults to the built-in list of
            common Ollama models.
    """

    base_url: str = "http://localhost:11434"
    api_key: str = ""
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: [
            "generation.text-generation.chat-completion",
            "generation.text-generation.code-generation",
        ]
    )


class OllamaProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for Ollama.

    Provides a zero-configuration entry point for locally-hosted
    models via Ollama.  No API key is needed.

    Connector ID: ``ollama.local.v1``

    Usage::

        provider = OllamaProvider()
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "ollama.local.v1"
    RUNTIME: str = "node"

    def __init__(self, config: OllamaProviderConfig | None = None) -> None:
        if config is None:
            config = OllamaProviderConfig()
        super().__init__(config)
