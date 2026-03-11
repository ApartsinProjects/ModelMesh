"""Pre-shipped Google Gemini provider connector.

Extends BaseProvider with Gemini-specific API translation. The
Google Generative Language API uses a different request/response format
than the OpenAI chat completions spec, so this connector overrides the
four key hook methods to handle the translation.

Key differences from OpenAI:
- API key is passed as a ``?key=`` query parameter (not in headers).
- System messages go in a top-level ``systemInstruction`` field.
- Role mapping: ``"assistant"`` -> ``"model"``, ``"user"`` -> ``"user"``.
- Response wraps content in ``candidates[].content.parts[]``.

Connector ID: ``google.gemini.v1``
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
    "GeminiProviderConfig",
    "GeminiProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="gemini-2.5-flash-preview-05-20",
        name="Gemini 2.5 Flash Preview",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "vision": True},
        context_window=1_000_000,
        max_output_tokens=65_536,
    ),
    ModelInfo(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "vision": True},
        context_window=1_000_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="gemini-2.0-flash-lite",
        name="Gemini 2.0 Flash Lite",
        capabilities=["generation.text-generation.chat-completion"],
        context_window=1_000_000,
        max_output_tokens=8_192,
    ),
    ModelInfo(
        id="text-embedding-004",
        name="Text Embedding 004",
        capabilities=["representation.embeddings.text-embeddings"],
        context_window=2_048,
    ),
]


@dataclass
class GeminiProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped Google Gemini provider.

    Extends BaseProviderConfig with sensible defaults for the Google
    Generative Language API. The API key is passed as a query parameter
    rather than in the Authorization header.

    Attributes:
        base_url: Gemini API base URL. Defaults to
            ``"https://generativelanguage.googleapis.com"``.
        models: Model catalogue. Defaults to the built-in list of
            supported Gemini models.
    """

    base_url: str = "https://generativelanguage.googleapis.com"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: [
            "generation.text-generation.chat-completion",
            "representation.embeddings.text-embeddings",
        ]
    )


# -- Role mapping helpers ----------------------------------------------------

_ROLE_TO_GEMINI = {"assistant": "model", "user": "user"}
_ROLE_FROM_GEMINI = {"model": "assistant", "user": "user"}

# -- Finish reason mapping ---------------------------------------------------

_FINISH_REASON_MAP = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "content_filter",
}


class GeminiProvider(BaseProvider):
    """Pre-shipped provider connector for the Google Generative Language API.

    Google Gemini uses a different API format than OpenAI, so this
    connector overrides the four protected hook methods on BaseProvider:

    - ``_get_completion_endpoint()`` -- constructs the
      ``/v1beta/models/{model}:generateContent?key=`` URL
    - ``_build_headers()`` -- omits Authorization (key is in the URL)
    - ``_build_request_payload()`` -- translates OpenAI format to
      Gemini format (contents array, systemInstruction, generationConfig)
    - ``_parse_response()`` -- translates Gemini response to
      CompletionResponse format

    Connector ID: ``google.gemini.v1``

    Usage::

        provider = GeminiProvider(GeminiProviderConfig(
            api_key="AIza...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "google.gemini.v1"

    def __init__(self, config: GeminiProviderConfig | None = None) -> None:
        if config is None:
            config = GeminiProviderConfig()
        super().__init__(config)
        self._gemini_config = config
        # Store the current model for endpoint construction
        self._current_model: str = ""

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the Gemini generateContent endpoint.

        The Gemini API uses ``/v1beta/models/{model}:generateContent``
        with the API key as a query parameter instead of in the
        Authorization header.
        """
        base = self._config.base_url.rstrip("/")
        model = self._current_model or "gemini-2.0-flash"
        api_key = self._config.api_key or ""
        return f"{base}/v1beta/models/{model}:generateContent?key={api_key}"

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers without Authorization.

        The Gemini API authenticates via a ``?key=`` query parameter
        rather than an Authorization header, so this override only
        sets Content-Type.
        """
        return {"Content-Type": "application/json"}

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate an OpenAI-format request to the Gemini format.

        Key differences from OpenAI format:

        - System messages are extracted and placed in a top-level
          ``systemInstruction`` field with ``parts`` array.
        - Conversation messages go in a ``contents`` array with
          ``role`` and ``parts`` fields.
        - Generation parameters go in a ``generationConfig`` object.
        - Role mapping: ``"assistant"`` -> ``"model"``.
        """
        # Store model for endpoint construction
        self._current_model = request.model

        # Separate system messages from conversation messages
        system_parts: list[str] = []
        contents: list[dict] = []

        for msg in request.messages:
            role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "role", "")
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")

            if role == "system":
                if content:
                    system_parts.append(content)
            else:
                gemini_role = _ROLE_TO_GEMINI.get(role, role)
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}],
                })

        payload: dict = {"contents": contents}

        # Add system instruction if present
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}],
            }

        # Build generationConfig
        generation_config: dict = {}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_tokens
        if request.top_p is not None and request.top_p != 1.0:
            generation_config["topP"] = request.top_p
        if request.stop:
            generation_config["stopSequences"] = request.stop

        if generation_config:
            payload["generationConfig"] = generation_config

        if request.tools:
            payload["tools"] = request.tools

        return payload

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Translate a Gemini response to CompletionResponse.

        Maps the Gemini ``candidates`` array with ``content.parts``
        into OpenAI-compatible ``choices`` with ``message`` objects.
        Usage information is translated from Gemini's
        ``usageMetadata`` fields.
        """
        # Extract usage
        usage_data = data.get("usageMetadata", {})
        prompt_tokens = usage_data.get("promptTokenCount", 0)
        completion_tokens = usage_data.get("candidatesTokenCount", 0)
        total_tokens = usage_data.get("totalTokenCount", 0)

        # Extract candidates
        candidates = data.get("candidates", [])
        choices: list[CompletionChoice] = []

        for i, candidate in enumerate(candidates):
            content_data = candidate.get("content", {})
            parts = content_data.get("parts", [])

            # Collect text from all parts
            text_parts: list[str] = []
            for part in parts:
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])

            content_text = "".join(text_parts) if text_parts else None

            # Map finish reason
            raw_finish = candidate.get("finishReason", "")
            finish_reason = _FINISH_REASON_MAP.get(raw_finish, raw_finish.lower() if raw_finish else None)

            # Map role back from Gemini
            gemini_role = content_data.get("role", "model")
            role = _ROLE_FROM_GEMINI.get(gemini_role, gemini_role)

            choices.append(
                CompletionChoice(
                    index=i,
                    message=ChatMessage(role=role, content=content_text),
                    finish_reason=finish_reason,
                )
            )

        return CompletionResponse(
            id="",
            model=self._current_model,
            choices=choices,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
        )

    def _parse_sse_chunk(self, line: str) -> CompletionResponse | None:
        """Parse a single SSE data line from the Gemini streaming format.

        Gemini streaming returns the same candidate structure as
        non-streaming, but incrementally. Each chunk contains partial
        ``candidates`` with ``content.parts``.
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None

        candidates = data.get("candidates", [])
        if not candidates:
            return None

        choices: list[CompletionChoice] = []
        for candidate in candidates:
            content_data = candidate.get("content", {})
            parts = content_data.get("parts", [])

            text_parts: list[str] = []
            for part in parts:
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])

            text = "".join(text_parts) if text_parts else ""

            raw_finish = candidate.get("finishReason")
            finish_reason = _FINISH_REASON_MAP.get(raw_finish, None) if raw_finish else None

            choices.append(
                CompletionChoice(
                    index=candidate.get("index", 0),
                    delta=ChatMessage(role="assistant", content=text),
                    finish_reason=finish_reason,
                )
            )

        usage_data = data.get("usageMetadata", {})
        return CompletionResponse(
            id="",
            model=self._current_model,
            choices=choices,
            usage=TokenUsage(
                prompt_tokens=usage_data.get("promptTokenCount", 0),
                completion_tokens=usage_data.get("candidatesTokenCount", 0),
                total_tokens=usage_data.get("totalTokenCount", 0),
            ),
        )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a completion request, setting the current model first.

        Overrides the base ``complete`` to ensure ``_current_model`` is
        set before ``_get_completion_endpoint`` is called.
        """
        self._current_model = request.model
        return await super().complete(request)

    async def stream(self, request):
        """Send a streaming request using the Gemini streamGenerateContent endpoint.

        Overrides base ``stream`` to use the correct streaming endpoint
        with ``alt=sse`` query parameter.
        """
        self._current_model = request.model
        async for chunk in super().stream(request):
            yield chunk

    def _get_streaming_endpoint(self) -> str:
        """Return the Gemini streamGenerateContent endpoint."""
        base = self._config.base_url.rstrip("/")
        model = self._current_model or "gemini-2.0-flash"
        api_key = self._config.api_key or ""
        return f"{base}/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}"
