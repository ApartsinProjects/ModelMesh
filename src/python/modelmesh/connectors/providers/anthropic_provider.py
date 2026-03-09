"""Pre-shipped Anthropic provider connector.

Extends BaseProvider with Anthropic-specific API translation. The
Anthropic Messages API uses a different request/response format than
the OpenAI chat completions spec, so this connector overrides the
four key hook methods to handle the translation.

Connector ID: ``anthropic.claude.v1``
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

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
    "AnthropicProviderConfig",
    "AnthropicProvider",
]

# -- Default Anthropic API version -------------------------------------------

_DEFAULT_ANTHROPIC_VERSION = "2023-06-01"

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="claude-sonnet-4-20250514",
        name="Claude Sonnet 4",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "vision": True, "system_prompt": True},
        context_window=200_000,
        max_output_tokens=16_384,
        pricing=ModelPricing(
            input_per_1k_tokens=0.003,
            output_per_1k_tokens=0.015,
        ),
    ),
    ModelInfo(
        id="claude-haiku-4-5-20251001",
        name="Claude Haiku 4.5",
        capabilities=["generation.text-generation.chat-completion"],
        features={"tool_calling": True, "vision": True, "system_prompt": True},
        context_window=200_000,
        max_output_tokens=8_192,
        pricing=ModelPricing(
            input_per_1k_tokens=0.0008,
            output_per_1k_tokens=0.004,
        ),
    ),
]


@dataclass
class AnthropicProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped Anthropic provider.

    Extends BaseProviderConfig with an ``anthropic_version`` field for
    the required API version header and sensible defaults for the
    Anthropic Messages API.

    Attributes:
        base_url: Anthropic API base URL. Defaults to
            ``"https://api.anthropic.com"``.
        anthropic_version: API version string sent in the
            ``anthropic-version`` header. Defaults to ``"2023-06-01"``.
        models: Model catalogue. Defaults to the built-in list of
            supported Anthropic models with pricing information.
    """

    base_url: str = "https://api.anthropic.com"
    anthropic_version: str = _DEFAULT_ANTHROPIC_VERSION
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.text-generation.chat-completion"]
    )


class AnthropicProvider(BaseProvider):
    """Pre-shipped provider connector for the Anthropic Messages API.

    Anthropic uses a different API format than OpenAI, so this connector
    overrides the four protected hook methods on BaseProvider:

    - ``_get_completion_endpoint()`` -- returns ``/v1/messages``
    - ``_build_headers()`` -- uses ``x-api-key`` and ``anthropic-version``
    - ``_build_request_payload()`` -- translates OpenAI format to
      Anthropic format (separate system message, messages array)
    - ``_parse_response()`` -- translates Anthropic response to
      CompletionResponse format

    Connector ID: ``anthropic.claude.v1``

    Usage::

        provider = AnthropicProvider(AnthropicProviderConfig(
            api_key="sk-ant-...",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "anthropic.claude.v1"

    def __init__(self, config: AnthropicProviderConfig | None = None) -> None:
        if config is None:
            config = AnthropicProviderConfig()
        super().__init__(config)
        self._anthropic_config = config

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the Anthropic Messages API endpoint.

        The Anthropic API uses ``/v1/messages`` instead of the OpenAI
        ``/v1/chat/completions`` path.
        """
        base = self._config.base_url.rstrip("/")
        return f"{base}/v1/messages"

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers with Anthropic-specific authentication.

        Anthropic uses ``x-api-key`` for authentication instead of the
        ``Authorization: Bearer`` scheme, and requires an
        ``anthropic-version`` header.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "anthropic-version": self._anthropic_config.anthropic_version,
        }
        if self._config.api_key:
            headers["x-api-key"] = self._config.api_key
        return headers

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate an OpenAI-format request to the Anthropic Messages format.

        Key differences from OpenAI format:

        - The system message is extracted from the messages list and
          placed in a top-level ``system`` field.
        - The ``max_tokens`` field is required by Anthropic (defaults
          to the model's max output tokens if not specified).
        - Tool definitions use Anthropic's schema format.
        """
        # Separate system messages from conversation messages
        system_parts: list[str] = []
        messages: list[dict] = []

        for msg in request.messages:
            role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "role", "")
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")

            if role == "system":
                if content:
                    system_parts.append(content)
            else:
                messages.append({"role": role, "content": content})

        # Determine max_tokens -- required by Anthropic
        max_tokens = request.max_tokens
        if max_tokens is None:
            # Look up the model's max_output_tokens, fall back to 4096
            if request.model in self._models_by_id:
                max_tokens = self._models_by_id[request.model].max_output_tokens or 4096
            else:
                max_tokens = 4096

        payload: dict = {
            "model": request.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        if request.temperature is not None:
            payload["temperature"] = request.temperature

        if request.tools:
            payload["tools"] = request.tools

        if request.stream:
            payload["stream"] = True

        return payload

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Translate an Anthropic Messages response to CompletionResponse.

        Maps the Anthropic ``content`` array (which contains content
        blocks) into OpenAI-compatible ``choices`` with ``message``
        objects. Usage information is translated from Anthropic's
        ``input_tokens`` / ``output_tokens`` fields.
        """
        # Extract usage
        usage_data = data.get("usage", {})
        input_tokens = usage_data.get("input_tokens", 0)
        output_tokens = usage_data.get("output_tokens", 0)

        # Extract text content from Anthropic's content blocks
        content_blocks = data.get("content", [])
        text_parts: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        content_text = "".join(text_parts) if text_parts else None

        # Map stop_reason to OpenAI finish_reason
        stop_reason = data.get("stop_reason")
        finish_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
            "tool_use": "tool_calls",
        }
        finish_reason = finish_reason_map.get(stop_reason, stop_reason)

        # Build the choice with a ChatMessage
        choice = CompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content_text),
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
        """Parse a single SSE data line from the Anthropic streaming format.

        Anthropic streaming uses event types like ``content_block_delta``
        with nested delta objects. This method extracts text deltas and
        maps them to CompletionResponse format.
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None

        event_type = data.get("type", "")

        if event_type == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                return CompletionResponse(
                    id="",
                    model="",
                    choices=[
                        CompletionChoice(
                            index=data.get("index", 0),
                            delta=ChatMessage(role="assistant", content=text),
                        )
                    ],
                    usage=TokenUsage(),
                )

        if event_type == "message_delta":
            stop_reason = data.get("delta", {}).get("stop_reason")
            finish_reason_map = {
                "end_turn": "stop",
                "max_tokens": "length",
                "stop_sequence": "stop",
                "tool_use": "tool_calls",
            }
            finish_reason = finish_reason_map.get(stop_reason, stop_reason)
            usage_data = data.get("usage", {})
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
                    prompt_tokens=0,
                    completion_tokens=usage_data.get("output_tokens", 0),
                    total_tokens=usage_data.get("output_tokens", 0),
                ),
            )

        return None
