"""Pre-shipped Serper (Google Search) provider connector.

Wraps the Serper.dev Google Search API as a ModelMesh provider so web
search capabilities can participate in capability pools.  The search
query is extracted from the last message's content, and results are
returned as formatted text in a CompletionResponse.

Connector ID: ``serper.search.v1``
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
    "SerperProviderConfig",
    "SerperProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="serper-google-search",
        name="Serper Google Search",
        capabilities=["retrieval.semantic-search.web-search"],
        features={"answer_box": True, "organic_results": True},
        context_window=2048,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.001),
    ),
]


@dataclass
class SerperProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped Serper provider.

    Extends BaseProviderConfig with sensible defaults for the
    Serper.dev Google Search API.

    Attributes:
        base_url: Serper API base URL.  Defaults to
            ``"https://google.serper.dev"``.
        models: Model catalogue.  Defaults to the built-in list of
            Serper search models.
    """

    base_url: str = "https://google.serper.dev"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["retrieval.semantic-search.web-search"]
    )


class SerperProvider(BaseProvider):
    """Pre-shipped provider connector for the Serper Google Search API.

    Serper provides fast Google Search results via a simple JSON API.
    This connector translates the OpenAI chat completions interface
    into Serper's native search format.

    The query is extracted from ``messages[-1].content``.  The response
    includes the answer box (if available) followed by organic search
    result snippets.

    Connector ID: ``serper.search.v1``

    Usage::

        provider = SerperProvider(SerperProviderConfig(
            api_key="...",
        ))
        response = await provider.complete(CompletionRequest(
            model="serper-google-search",
            messages=[{"role": "user", "content": "weather in New York"}],
        ))
    """

    CONNECTOR_ID: str = "serper.search.v1"

    def __init__(self, config: SerperProviderConfig | None = None) -> None:
        if config is None:
            config = SerperProviderConfig()
        super().__init__(config)

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the Serper search endpoint."""
        base = self._config.base_url.rstrip("/")
        return f"{base}/search"

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers with Serper-specific authentication.

        Serper uses ``X-API-KEY`` for authentication instead of the
        standard ``Authorization: Bearer`` scheme.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["X-API-KEY"] = self._config.api_key
        return headers

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate a chat completion request to Serper's search format.

        Extracts the query from the last message's content and maps it
        to Serper's ``q`` parameter.
        """
        query = ""
        if request.messages:
            last_msg = request.messages[-1]
            if isinstance(last_msg, dict):
                query = last_msg.get("content", "")
            else:
                query = getattr(last_msg, "content", "")

        return {"q": query}

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Translate Serper's search response to CompletionResponse.

        Formats the answer box and organic results into readable text
        placed in a ChatMessage content field.
        """
        parts: list[str] = []

        # Include the answer box if present
        answer_box = data.get("answerBox")
        if answer_box:
            answer = answer_box.get("answer") or answer_box.get("snippet", "")
            if answer:
                parts.append(f"Answer: {answer}")
                parts.append("")

        # Include knowledge graph if present
        knowledge_graph = data.get("knowledgeGraph")
        if knowledge_graph:
            kg_title = knowledge_graph.get("title", "")
            kg_desc = knowledge_graph.get("description", "")
            if kg_title:
                parts.append(f"{kg_title}")
            if kg_desc:
                parts.append(f"{kg_desc}")
            if kg_title or kg_desc:
                parts.append("")

        # Format organic search results
        organic = data.get("organic", [])
        if organic:
            parts.append("Search Results:")
            for i, result in enumerate(organic, 1):
                title = result.get("title", "Untitled")
                link = result.get("link", "")
                snippet = result.get("snippet", "")
                parts.append(f"\n[{i}] {title}")
                if link:
                    parts.append(f"    URL: {link}")
                if snippet:
                    parts.append(f"    {snippet}")

        content_text = "\n".join(parts) if parts else "No results found."

        # Estimate token usage based on character counts
        query_text = data.get("searchParameters", {}).get("q", "")
        prompt_tokens = max(1, len(query_text) // 4)
        completion_tokens = max(1, len(content_text) // 4)

        choice = CompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content_text),
            finish_reason="stop",
        )

        return CompletionResponse(
            id=f"serper-{uuid.uuid4().hex[:12]}",
            model="serper-google-search",
            choices=[choice],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
