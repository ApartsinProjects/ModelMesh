"""Pre-shipped Tavily web search provider connector.

Wraps the Tavily Search API as a ModelMesh provider so web search
capabilities can participate in capability pools.  The search query
is extracted from the last message's content, and results are returned
as formatted text in a CompletionResponse.

Connector ID: ``tavily.search.v1``
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
    "TavilyProviderConfig",
    "TavilyProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="tavily-search",
        name="Tavily Search (Advanced)",
        capabilities=["retrieval.semantic-search.web-search"],
        features={"include_answer": True, "search_depth": True},
        context_window=400,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.01),
    ),
    ModelInfo(
        id="tavily-search-basic",
        name="Tavily Search (Basic)",
        capabilities=["retrieval.semantic-search.web-search"],
        features={"include_answer": True, "search_depth": False},
        context_window=400,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.005),
    ),
]


@dataclass
class TavilyProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped Tavily provider.

    Extends BaseProviderConfig with sensible defaults for the Tavily
    Search API.  Tavily authenticates via an ``api_key`` field in the
    request body rather than via HTTP headers.

    Attributes:
        base_url: Tavily API base URL.  Defaults to
            ``"https://api.tavily.com"``.
        max_results: Maximum number of search results to return.
            Defaults to ``5``.
        models: Model catalogue.  Defaults to the built-in list of
            Tavily search models.
    """

    base_url: str = "https://api.tavily.com"
    max_results: int = 5
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["retrieval.semantic-search.web-search"]
    )


class TavilyProvider(BaseProvider):
    """Pre-shipped provider connector for the Tavily Search API.

    Tavily provides AI-optimized web search results.  This connector
    translates the OpenAI chat completions interface into Tavily's
    native search API format.

    The query is extracted from ``messages[-1].content``.  The response
    includes Tavily's AI-generated answer followed by individual search
    result snippets.

    Connector ID: ``tavily.search.v1``

    Usage::

        provider = TavilyProvider(TavilyProviderConfig(
            api_key="tvly-...",
        ))
        response = await provider.complete(CompletionRequest(
            model="tavily-search",
            messages=[{"role": "user", "content": "latest news on AI"}],
        ))
    """

    CONNECTOR_ID: str = "tavily.search.v1"

    def __init__(self, config: TavilyProviderConfig | None = None) -> None:
        if config is None:
            config = TavilyProviderConfig()
        super().__init__(config)
        self._tavily_config = config

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the Tavily Search API endpoint."""
        base = self._config.base_url.rstrip("/")
        return f"{base}/search"

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for Tavily.

        Tavily authenticates via the request body, so no Authorization
        header is needed.  Only the Content-Type header is set.
        """
        return {"Content-Type": "application/json"}

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate a chat completion request to Tavily's search format.

        Extracts the query from the last message's content.  Sets the
        search depth based on the requested model: ``"advanced"`` for
        ``tavily-search`` and ``"basic"`` for ``tavily-search-basic``.
        """
        query = ""
        if request.messages:
            last_msg = request.messages[-1]
            if isinstance(last_msg, dict):
                query = last_msg.get("content", "")
            else:
                query = getattr(last_msg, "content", "")

        search_depth = "basic" if request.model == "tavily-search-basic" else "advanced"

        return {
            "api_key": self._config.api_key,
            "query": query,
            "search_depth": search_depth,
            "include_answer": True,
            "max_results": self._tavily_config.max_results,
        }

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Translate Tavily's search response to CompletionResponse.

        Formats the AI answer and search results into readable text
        placed in a ChatMessage content field.
        """
        parts: list[str] = []

        # Include the AI-generated answer if present
        answer = data.get("answer")
        if answer:
            parts.append(f"Answer: {answer}")
            parts.append("")

        # Format individual search results
        results = data.get("results", [])
        if results:
            parts.append("Sources:")
            for i, result in enumerate(results, 1):
                title = result.get("title", "Untitled")
                url = result.get("url", "")
                content = result.get("content", "")
                parts.append(f"\n[{i}] {title}")
                if url:
                    parts.append(f"    URL: {url}")
                if content:
                    parts.append(f"    {content}")

        content_text = "\n".join(parts) if parts else "No results found."

        # Estimate token usage based on character counts
        query_chars = len(data.get("query", ""))
        response_chars = len(content_text)
        prompt_tokens = max(1, query_chars // 4)
        completion_tokens = max(1, response_chars // 4)

        choice = CompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content_text),
            finish_reason="stop",
        )

        return CompletionResponse(
            id=f"tavily-{uuid.uuid4().hex[:12]}",
            model=data.get("query", "tavily-search"),
            choices=[choice],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
