"""Pre-shipped Perplexity provider connector.

Extends OpenAICompatibleProvider for the Perplexity Sonar API. Perplexity
uses an OpenAI-compatible request/response format, so no hook overrides
are needed. This connector primarily provides the model catalogue with
grounded-generation capabilities and sets the correct base URL.

Perplexity models are search-augmented -- they perform web searches as
part of generation. Their primary capability is
``retrieval.grounded-generation.web-search`` rather than plain
chat-completion.

Connector ID: ``perplexity.search.v1``
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.interfaces.provider import ModelInfo

__all__ = [
    "PerplexityProviderConfig",
    "PerplexityProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="sonar-pro",
        name="Sonar Pro",
        capabilities=["retrieval.grounded-generation.web-search"],
        context_window=200_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="sonar",
        name="Sonar",
        capabilities=["retrieval.grounded-generation.web-search"],
        context_window=128_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="sonar-reasoning-pro",
        name="Sonar Reasoning Pro",
        capabilities=["retrieval.grounded-generation.web-search"],
        features={"reasoning": True},
        context_window=128_000,
        max_output_tokens=8_192,
    ),
]


@dataclass
class PerplexityProviderConfig(OpenAICompatibleConfig):
    """Configuration for the pre-shipped Perplexity provider.

    Extends OpenAICompatibleConfig with sensible defaults for the
    Perplexity Sonar API. Since Perplexity follows the OpenAI chat
    completions spec, no additional configuration fields are needed.

    Attributes:
        base_url: Perplexity API base URL. Defaults to
            ``"https://api.perplexity.ai"``.
        models: Model catalogue. Defaults to the built-in list of
            supported Perplexity Sonar models.
    """

    base_url: str = "https://api.perplexity.ai"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: [
            "retrieval.grounded-generation.web-search",
        ]
    )


class PerplexityProvider(OpenAICompatibleProvider):
    """Pre-shipped provider connector for the Perplexity Sonar API.

    Perplexity uses an OpenAI-compatible API format, so this connector
    inherits all behavior from OpenAICompatibleProvider. The primary
    value of this connector is the pre-configured model catalogue
    with grounded-generation capabilities and the correct base URL.

    Perplexity Sonar models are search-augmented: they perform web
    searches during generation and return grounded responses with
    citations. Their capability is
    ``retrieval.grounded-generation.web-search``.

    Connector ID: ``perplexity.search.v1``

    Usage::

        provider = PerplexityProvider(PerplexityProviderConfig(
            api_key="pplx-...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "perplexity.search.v1"

    def __init__(self, config: PerplexityProviderConfig | None = None) -> None:
        if config is None:
            config = PerplexityProviderConfig()
        super().__init__(config)
