"""Pre-shipped Jina AI provider connector.

Wraps multiple Jina AI services (Reader, Search, Embeddings, Reranker)
as a single ModelMesh provider.  Different models route to different
Jina endpoints, allowing content extraction, web search, embedding
generation, and reranking through the unified chat completions interface.

Connector ID: ``jina.ai.v1``
"""
from __future__ import annotations

import asyncio
import json
import urllib.request
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
    "JinaProviderConfig",
    "JinaProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="jina-reader",
        name="Jina Reader",
        capabilities=["understanding.document-understanding.content-extraction"],
        features={"url_extraction": True},
        context_window=0,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.002),
    ),
    ModelInfo(
        id="jina-search",
        name="Jina Search",
        capabilities=["retrieval.semantic-search.web-search"],
        features={"web_search": True},
        context_window=2048,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.005),
    ),
    ModelInfo(
        id="jina-embeddings-v3",
        name="Jina Embeddings v3",
        capabilities=["representation.embeddings.text-embeddings"],
        features={"embedding_generation": True},
        context_window=8192,
        max_output_tokens=0,
        pricing=ModelPricing(
            input_per_1k_tokens=0.00002,
        ),
    ),
    ModelInfo(
        id="jina-reranker-v2-base-multilingual",
        name="Jina Reranker v2 Base Multilingual",
        capabilities=["retrieval.reranking"],
        features={"multilingual": True},
        context_window=8192,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.002),
    ),
]


@dataclass
class JinaProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped Jina AI provider.

    Extends BaseProviderConfig with sensible defaults for the Jina AI
    family of APIs.

    Attributes:
        base_url: Jina API base URL.  Defaults to
            ``"https://api.jina.ai"``.
        reader_base_url: Base URL for the Jina Reader service.
            Defaults to ``"https://r.jina.ai"``.
        search_base_url: Base URL for the Jina Search service.
            Defaults to ``"https://s.jina.ai"``.
        models: Model catalogue.  Defaults to the built-in list of
            Jina models spanning reader, search, embeddings, and
            reranking capabilities.
    """

    base_url: str = "https://api.jina.ai"
    reader_base_url: str = "https://r.jina.ai"
    search_base_url: str = "https://s.jina.ai"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: [
            "understanding.document-understanding.content-extraction",
            "retrieval.semantic-search.web-search",
            "representation.embeddings.text-embeddings",
            "retrieval.reranking",
        ]
    )


class JinaProvider(BaseProvider):
    """Pre-shipped provider connector for Jina AI services.

    Jina AI provides multiple services accessible through different
    endpoints.  This connector routes requests to the appropriate
    endpoint based on the requested model:

    - ``jina-reader``: Extracts content from URLs via the Reader API
    - ``jina-search``: Performs web search via the Search API
    - ``jina-embeddings-v3``: Generates embeddings via the Embeddings API
    - ``jina-reranker-v2-base-multilingual``: Reranks results via the
      Reranker API

    For the chat completions interface, Reader and Search models
    extract the URL or query from ``messages[-1].content`` and return
    the results as text in a CompletionResponse.

    Connector ID: ``jina.ai.v1``

    Usage::

        provider = JinaProvider(JinaProviderConfig(
            api_key="jina_...",
        ))
        # Extract content from a URL
        response = await provider.complete(CompletionRequest(
            model="jina-reader",
            messages=[{"role": "user", "content": "https://example.com"}],
        ))
    """

    CONNECTOR_ID: str = "jina.ai.v1"

    def __init__(self, config: JinaProviderConfig | None = None) -> None:
        if config is None:
            config = JinaProviderConfig()
        super().__init__(config)
        self._jina_config = config
        self._current_model: str = ""

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the appropriate Jina endpoint based on the current model.

        This is dynamically resolved in ``complete()`` based on the
        requested model, but the base implementation returns the
        embeddings endpoint as a fallback.
        """
        base = self._config.base_url.rstrip("/")
        return f"{base}/v1/embeddings"

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers with Bearer token authentication.

        Jina AI uses standard ``Authorization: Bearer`` authentication
        across all its APIs.  The ``Accept`` header requests JSON
        responses from the Reader and Search services.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate a chat completion request to the native Jina format.

        The payload structure depends on the requested model:
        - Reader/Search: not used (these are GET requests)
        - Embeddings: ``{"model": "...", "input": ["..."]}``
        - Reranker: ``{"model": "...", "query": "...", "documents": [...]}``
        """
        content = ""
        if request.messages:
            last_msg = request.messages[-1]
            if isinstance(last_msg, dict):
                content = last_msg.get("content", "")
            else:
                content = getattr(last_msg, "content", "")

        if request.model == "jina-embeddings-v3":
            return {
                "model": "jina-embeddings-v3",
                "input": [content],
            }
        elif request.model == "jina-reranker-v2-base-multilingual":
            # For reranking via chat interface, content should be
            # JSON with "query" and "documents" fields
            try:
                parsed = json.loads(content)
                query = parsed.get("query", content)
                documents = parsed.get("documents", [])
            except (json.JSONDecodeError, AttributeError):
                query = content
                documents = []
            return {
                "model": "jina-reranker-v2-base-multilingual",
                "query": query,
                "documents": documents,
            }
        else:
            # Reader and Search use GET requests; payload not used
            return {"content": content}

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Translate a Jina API response to CompletionResponse format.

        Handles responses from all Jina services and normalizes them
        into text content within a ChatMessage.
        """
        content_text = ""

        if "data" in data and isinstance(data["data"], list):
            # Embeddings or reranker response
            items = data["data"]
            if items and "embedding" in items[0]:
                # Embeddings response - format as JSON array
                embeddings = [item.get("embedding", []) for item in items]
                content_text = json.dumps({"embeddings": embeddings})
            elif items and "relevance_score" in items[0]:
                # Reranker response - format as ranked list
                parts: list[str] = ["Reranked Results:"]
                for i, item in enumerate(items, 1):
                    score = item.get("relevance_score", 0.0)
                    doc = item.get("document", {})
                    text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
                    parts.append(f"\n[{i}] Score: {score:.4f}")
                    if text:
                        parts.append(f"    {text}")
                content_text = "\n".join(parts)
            else:
                content_text = json.dumps(data)
        elif "content" in data:
            # Reader response (when returned as JSON)
            content_text = data.get("content", "")
        elif "results" in data:
            # Search response
            parts = ["Search Results:"]
            for i, result in enumerate(data["results"], 1):
                title = result.get("title", "Untitled")
                url = result.get("url", "")
                content = result.get("content", result.get("description", ""))
                parts.append(f"\n[{i}] {title}")
                if url:
                    parts.append(f"    URL: {url}")
                if content:
                    parts.append(f"    {content}")
            content_text = "\n".join(parts)
        else:
            content_text = json.dumps(data)

        if not content_text:
            content_text = "No results returned."

        prompt_tokens = max(1, len(content_text) // 10)
        completion_tokens = max(1, len(content_text) // 4)

        choice = CompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content_text),
            finish_reason="stop",
        )

        return CompletionResponse(
            id=f"jina-{uuid.uuid4().hex[:12]}",
            model=self._current_model or "jina",
            choices=[choice],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    # -- Override complete() for model-dependent routing ----------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Route the request to the appropriate Jina endpoint.

        Reader and Search models use GET requests to dedicated
        subdomains, while Embeddings and Reranker use POST requests
        to the main API.
        """
        self._current_model = request.model

        content = ""
        if request.messages:
            last_msg = request.messages[-1]
            if isinstance(last_msg, dict):
                content = last_msg.get("content", "")
            else:
                content = getattr(last_msg, "content", "")

        if request.model == "jina-reader":
            return await self._handle_reader(content)
        elif request.model == "jina-search":
            return await self._handle_search(content)
        else:
            # Embeddings and Reranker use standard POST via BaseProvider
            return await super().complete(request)

    async def _handle_reader(self, url: str) -> CompletionResponse:
        """Extract content from a URL using the Jina Reader API.

        Sends a GET request to ``https://r.jina.ai/{url}`` and returns
        the extracted content as a CompletionResponse.
        """
        reader_url = f"{self._jina_config.reader_base_url.rstrip('/')}/{url}"
        headers = self._build_headers()
        data = await asyncio.to_thread(self._http_get_text, reader_url, headers)

        content_text = data if isinstance(data, str) else json.dumps(data)
        prompt_tokens = max(1, len(url) // 4)
        completion_tokens = max(1, len(content_text) // 4)

        choice = CompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content_text),
            finish_reason="stop",
        )

        result = CompletionResponse(
            id=f"jina-reader-{uuid.uuid4().hex[:12]}",
            model="jina-reader",
            choices=[choice],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
        self.report_usage("jina-reader", result.usage)
        return result

    async def _handle_search(self, query: str) -> CompletionResponse:
        """Perform a web search using the Jina Search API.

        Sends a GET request to ``https://s.jina.ai/{query}`` and
        returns the search results as a CompletionResponse.
        """
        # URL-encode the query for the path
        encoded_query = urllib.request.quote(query, safe="")
        search_url = f"{self._jina_config.search_base_url.rstrip('/')}/{encoded_query}"
        headers = self._build_headers()
        data = await asyncio.to_thread(self._http_get_text, search_url, headers)

        if isinstance(data, str):
            content_text = data
        elif isinstance(data, dict):
            content_text = self._parse_response(data).choices[0].message.content or ""
        else:
            content_text = str(data)

        prompt_tokens = max(1, len(query) // 4)
        completion_tokens = max(1, len(content_text) // 4)

        choice = CompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content_text),
            finish_reason="stop",
        )

        result = CompletionResponse(
            id=f"jina-search-{uuid.uuid4().hex[:12]}",
            model="jina-search",
            choices=[choice],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
        self.report_usage("jina-search", result.usage)
        return result

    def _http_get_text(self, url: str, headers: dict[str, str]) -> str | dict:
        """Send a synchronous HTTP GET and return the response body.

        Attempts to parse the response as JSON; falls back to plain
        text if JSON parsing fails.

        Called from async code via :func:`asyncio.to_thread`.
        """
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=self._config.timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return body

    def _get_completion_endpoint_for_model(self, model: str) -> str:
        """Return the endpoint URL for a specific model.

        Used internally to route requests to the correct Jina API.
        """
        base = self._config.base_url.rstrip("/")
        if model == "jina-embeddings-v3":
            return f"{base}/v1/embeddings"
        elif model == "jina-reranker-v2-base-multilingual":
            return f"{base}/v1/rerank"
        else:
            return f"{base}/v1/embeddings"
