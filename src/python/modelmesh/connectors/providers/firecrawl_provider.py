"""Pre-shipped Firecrawl web scraping provider connector.

Wraps the Firecrawl API as a ModelMesh provider so web scraping and
crawling capabilities can participate in capability pools.  The target
URL is extracted from the last message's content, and the scraped
markdown content is returned in a CompletionResponse.

Connector ID: ``firecrawl.scrape.v1``
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from modelmesh.cdk.base_provider import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    ModelInfo,
    ModelPricing,
    TokenUsage,
)

__all__ = [
    "FirecrawlProviderConfig",
    "FirecrawlProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="firecrawl-scrape",
        name="Firecrawl Scrape",
        capabilities=["understanding.document-understanding.content-extraction"],
        features={"markdown_output": True, "single_page": True},
        context_window=0,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.001),
    ),
    ModelInfo(
        id="firecrawl-crawl",
        name="Firecrawl Crawl",
        capabilities=["understanding.document-understanding.content-extraction"],
        features={"markdown_output": True, "multi_page": True},
        context_window=0,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.005),
    ),
]


@dataclass
class FirecrawlProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped Firecrawl provider.

    Extends BaseProviderConfig with sensible defaults for the
    Firecrawl scraping API.

    Attributes:
        base_url: Firecrawl API base URL.  Defaults to
            ``"https://api.firecrawl.dev"``.
        output_formats: List of output formats to request from
            Firecrawl.  Defaults to ``["markdown"]``.
        models: Model catalogue.  Defaults to the built-in list of
            Firecrawl models.
    """

    base_url: str = "https://api.firecrawl.dev"
    output_formats: list[str] = field(default_factory=lambda: ["markdown"])
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: [
            "understanding.document-understanding.content-extraction",
        ]
    )


class FirecrawlProvider(BaseProvider):
    """Pre-shipped provider connector for the Firecrawl API.

    Firecrawl converts web pages to clean markdown, making them
    suitable for LLM processing.  This connector translates the
    OpenAI chat completions interface into Firecrawl's native
    scraping API format.

    The target URL is extracted from ``messages[-1].content``.  The
    scraped page content is returned as markdown text in a
    CompletionResponse.

    Connector ID: ``firecrawl.scrape.v1``

    Usage::

        provider = FirecrawlProvider(FirecrawlProviderConfig(
            api_key="fc-...",
        ))
        response = await provider.complete(CompletionRequest(
            model="firecrawl-scrape",
            messages=[{"role": "user", "content": "https://example.com"}],
        ))
    """

    CONNECTOR_ID: str = "firecrawl.scrape.v1"

    def __init__(self, config: FirecrawlProviderConfig | None = None) -> None:
        if config is None:
            config = FirecrawlProviderConfig()
        super().__init__(config)
        self._firecrawl_config = config

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the Firecrawl scrape endpoint.

        Both ``firecrawl-scrape`` and ``firecrawl-crawl`` use the
        ``/v1/scrape`` endpoint.  The crawl model could be extended
        to use ``/v1/crawl`` for multi-page crawling in the future.
        """
        base = self._config.base_url.rstrip("/")
        return f"{base}/v1/scrape"

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers with Bearer token authentication.

        Firecrawl uses standard ``Authorization: Bearer`` authentication.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate a chat completion request to Firecrawl's scrape format.

        Extracts the target URL from the last message's content and
        sets the desired output format(s).
        """
        url = ""
        if request.messages:
            last_msg = request.messages[-1]
            if isinstance(last_msg, dict):
                url = last_msg.get("content", "")
            else:
                url = getattr(last_msg, "content", "")

        return {
            "url": url.strip(),
            "formats": list(self._firecrawl_config.output_formats),
        }

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Translate Firecrawl's scrape response to CompletionResponse.

        Extracts the markdown content from the response data and wraps
        it in a ChatMessage.  Falls back to HTML or raw text if
        markdown is not available.
        """
        # Firecrawl wraps the result in a "data" object
        scrape_data = data.get("data", {})

        # Prefer markdown, fall back to html, then raw content
        content_text = (
            scrape_data.get("markdown")
            or scrape_data.get("html")
            or scrape_data.get("rawHtml")
            or scrape_data.get("content")
            or ""
        )

        if not content_text:
            content_text = "No content extracted from the URL."

        # Include metadata if available
        metadata = scrape_data.get("metadata", {})
        if metadata:
            meta_parts: list[str] = []
            title = metadata.get("title")
            description = metadata.get("description")
            if title:
                meta_parts.append(f"Title: {title}")
            if description:
                meta_parts.append(f"Description: {description}")
            if meta_parts:
                content_text = "\n".join(meta_parts) + "\n\n" + content_text

        # Estimate token usage
        prompt_tokens = max(1, len(scrape_data.get("url", "")) // 4)
        completion_tokens = max(1, len(content_text) // 4)

        choice = CompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content_text),
            finish_reason="stop",
        )

        return CompletionResponse(
            id=f"firecrawl-{uuid.uuid4().hex[:12]}",
            model="firecrawl-scrape",
            choices=[choice],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
