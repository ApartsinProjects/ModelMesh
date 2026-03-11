"""OpenAI-compatible provider for the CDK.

Pre-configured provider for any API that follows the OpenAI chat
completions specification. No method overrides are needed because
BaseProvider defaults are already OpenAI-compatible. This class
adds optional ``organization`` and ``api_version`` configuration
fields and sets appropriate defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from modelmesh.cdk.base_provider import BaseProvider, BaseProviderConfig

__all__ = [
    "OpenAICompatibleConfig",
    "OpenAICompatibleProvider",
]


@dataclass
class OpenAICompatibleConfig(BaseProviderConfig):
    """Configuration for an OpenAI-compatible provider.

    Extends BaseProviderConfig with optional organization and API
    version fields used by providers that follow the OpenAI spec
    but require additional identification headers.
    """

    organization: Optional[str] = None
    api_version: Optional[str] = None


class OpenAICompatibleProvider(BaseProvider):
    """Provider for APIs that follow the OpenAI chat completions spec.

    This is the simplest specialized provider: BaseProvider already
    implements OpenAI-compatible request/response handling, so this
    class only adds organization/version header support and validates
    the configuration.

    Usage::

        provider = OpenAICompatibleProvider(OpenAICompatibleConfig(
            base_url="https://api.openai.com",
            api_key="sk-...",
            models=[ModelInfo(id="gpt-4o", name="GPT-4o",
                              capabilities=["generation.text-generation.chat-completion"],
                              features={"tool_calling": True})],
        ))
    """

    def __init__(self, config: OpenAICompatibleConfig) -> None:
        if not config.base_url:
            config.base_url = "https://api.openai.com"
        super().__init__(config)
        self._oai_config = config

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers, adding OpenAI-specific headers if configured."""
        headers = super()._build_headers()
        if self._oai_config.organization:
            headers["OpenAI-Organization"] = self._oai_config.organization
        if self._oai_config.api_version:
            headers["OpenAI-Version"] = self._oai_config.api_version
        return headers
