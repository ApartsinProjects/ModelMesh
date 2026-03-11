"""Pre-shipped Cohere provider connector.

Extends BaseProvider with Cohere v2 API translation. The Cohere v2
Chat API uses an OpenAI-compatible message format but has a different
response structure, so this connector overrides the key hook methods
to handle the translation.

Key differences from OpenAI:
- Chat endpoint is ``/v2/chat`` (not ``/v1/chat/completions``).
- Response wraps content in ``message.content[0].text`` (array of
  content blocks) instead of ``choices[0].message.content``.
- Usage is reported under ``usage.billed_units`` with
  ``input_tokens`` and ``output_tokens``.
- Finish reason values differ: ``"COMPLETE"`` -> ``"stop"``,
  ``"MAX_TOKENS"`` -> ``"length"``.

Connector ID: ``cohere.nlp.v1``
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from modelmesh.cdk.base_provider import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    ModelInfo,
    TokenUsage,
)

__all__ = [
    "CohereProviderConfig",
    "CohereProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="command-a-03-2025",
        name="Command A",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True},
        context_window=256_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="command-r-plus-08-2024",
        name="Command R+",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True},
        context_window=128_000,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="command-r-08-2024",
        name="Command R",
        capabilities=["generation.text-generation.chat-completion"],
        context_window=128_000,
        max_output_tokens=4_096,
    ),
    ModelInfo(
        id="embed-english-v3.0",
        name="Embed English v3.0",
        capabilities=["representation.embeddings.text-embeddings"],
        context_window=512,
    ),
    ModelInfo(
        id="rerank-english-v3.0",
        name="Rerank English v3.0",
        capabilities=["retrieval.reranking"],
        context_window=4_096,
    ),
]

# -- Finish reason mapping ---------------------------------------------------

_FINISH_REASON_MAP = {
    "COMPLETE": "stop",
    "MAX_TOKENS": "length",
}


@dataclass
class CohereProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped Cohere provider.

    Extends BaseProviderConfig with sensible defaults for the Cohere
    v2 Chat API.

    Attributes:
        base_url: Cohere API base URL. Defaults to
            ``"https://api.cohere.com"``.
        models: Model catalogue. Defaults to the built-in list of
            supported Cohere models.
    """

    base_url: str = "https://api.cohere.com"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: [
            "generation.text-generation.chat-completion",
            "representation.embeddings.text-embeddings",
            "retrieval.reranking",
        ]
    )


class CohereProvider(BaseProvider):
    """Pre-shipped provider connector for the Cohere v2 Chat API.

    Cohere v2 uses an OpenAI-compatible message format for requests
    but returns responses in a different structure, so this connector
    overrides the key protected hook methods on BaseProvider:

    - ``_get_completion_endpoint()`` -- returns ``/v2/chat``
    - ``_build_request_payload()`` -- uses Cohere v2 message format
      (OpenAI-compatible messages with model field)
    - ``_parse_response()`` -- translates Cohere v2 response to
      CompletionResponse format (content blocks, billed_units usage)

    Connector ID: ``cohere.nlp.v1``

    Usage::

        provider = CohereProvider(CohereProviderConfig(
            api_key="...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "cohere.nlp.v1"

    def __init__(self, config: CohereProviderConfig | None = None) -> None:
        if config is None:
            config = CohereProviderConfig()
        super().__init__(config)
        self._cohere_config = config

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the Cohere v2 Chat endpoint.

        The Cohere v2 API uses ``/v2/chat`` instead of the OpenAI
        ``/v1/chat/completions`` path.
        """
        base = self._config.base_url.rstrip("/")
        return f"{base}/v2/chat"

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate an OpenAI-format request to the Cohere v2 format.

        Cohere v2 uses an OpenAI-compatible message format, so the
        translation is straightforward. The main difference is that
        the ``max_tokens`` field name stays the same.
        """
        payload: dict = {
            "model": request.model,
            "messages": request.messages,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature

        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        if request.top_p is not None and request.top_p != 1.0:
            payload["p"] = request.top_p

        if request.stop:
            payload["stop_sequences"] = request.stop

        if request.tools:
            payload["tools"] = request.tools

        if request.stream:
            payload["stream"] = True

        return payload

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Translate a Cohere v2 response to CompletionResponse.

        Maps the Cohere ``message.content`` array (content blocks)
        into OpenAI-compatible ``choices`` with ``message`` objects.
        Usage information is translated from Cohere's
        ``usage.billed_units`` fields.
        """
        # Extract usage from billed_units
        usage_data = data.get("usage", {})
        billed = usage_data.get("billed_units", {})
        input_tokens = billed.get("input_tokens", 0)
        output_tokens = billed.get("output_tokens", 0)

        # Extract content from message.content array
        message_data = data.get("message", {})
        content_blocks = message_data.get("content", [])

        text_parts: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        content_text = "".join(text_parts) if text_parts else None

        # Map role
        role = message_data.get("role", "assistant")

        # Map finish_reason
        raw_finish = data.get("finish_reason", "")
        finish_reason = _FINISH_REASON_MAP.get(raw_finish, raw_finish.lower() if raw_finish else None)

        # Build the choice with a ChatMessage
        choice = CompletionChoice(
            index=0,
            message=ChatMessage(role=role, content=content_text),
            finish_reason=finish_reason,
        )

        return CompletionResponse(
            id=data.get("id", ""),
            model=data.get("model", ""),
            choices=[choice],
            usage=TokenUsage(
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
        )

    def _parse_sse_chunk(self, line: str) -> CompletionResponse | None:
        """Parse a single SSE data line from the Cohere streaming format.

        Cohere v2 streaming uses event types with content deltas.
        This method extracts text deltas and maps them to
        CompletionResponse format.
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None

        event_type = data.get("type", "")

        if event_type == "content-delta":
            delta = data.get("delta", {})
            message_delta = delta.get("message", {})
            content_blocks = message_delta.get("content", {})
            text = content_blocks.get("text", "")

            return CompletionResponse(
                id="",
                model="",
                choices=[
                    CompletionChoice(
                        index=0,
                        delta=ChatMessage(role="assistant", content=text),
                    )
                ],
                usage=TokenUsage(),
            )

        if event_type == "message-end":
            delta = data.get("delta", {})
            raw_finish = delta.get("finish_reason", "")
            finish_reason = _FINISH_REASON_MAP.get(raw_finish, raw_finish.lower() if raw_finish else None)

            usage_data = delta.get("usage", {})
            billed = usage_data.get("billed_units", {})
            input_tokens = billed.get("input_tokens", 0)
            output_tokens = billed.get("output_tokens", 0)

            return CompletionResponse(
                id="",
                model="",
                choices=[
                    CompletionChoice(
                        index=0,
                        finish_reason=finish_reason,
                    )
                ],
                usage=TokenUsage(
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                ),
            )

        return None
