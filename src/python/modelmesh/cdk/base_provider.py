"""Base provider connector implementation.

Implements the full ``ProviderConnector`` interface with OpenAI-compatible
default behavior.  Subclasses override protected hook methods to adapt
to non-OpenAI APIs without reimplementing transport, retries, or error
classification.

HTTP transport uses :mod:`urllib.request` from the standard library so
the package has zero external dependencies.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    ErrorClassification,
    ModelInfo,
    ModelPricing,
    ProviderConnector,
    QuotaStatus,
    RateLimitStatus,
    TokenUsage,
)

__all__ = [
    "BaseProviderConfig",
    "BaseProvider",
]


@dataclass
class BaseProviderConfig:
    """Configuration for a BaseProvider instance."""

    base_url: str = ""
    api_key: str = ""
    models: list[ModelInfo] = field(default_factory=list)
    timeout: float = 30.0
    max_retries: int = 3
    auth_method: str = "api_key"
    retryable_codes: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503]
    )
    non_retryable_codes: list[int] = field(
        default_factory=lambda: [400, 401, 403]
    )
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.text-generation.chat-completion"]
    )


class BaseProvider(ProviderConnector):
    """Base implementation of the ProviderConnector interface.

    Provides an OpenAI-compatible default behavior for all methods.
    Subclasses override protected hook methods to adapt to non-OpenAI
    APIs without reimplementing transport, retries, or error handling.

    HTTP transport uses :mod:`urllib.request` from the standard library.
    Async methods delegate blocking I/O to a thread via
    :func:`asyncio.to_thread`.
    """

    def __init__(
        self, config: BaseProviderConfig, observability=None
    ) -> None:
        self._config = config
        self._request_count: int = 0
        self._tokens_used: int = 0
        self._models_by_id: dict[str, ModelInfo] = {
            m.id: m for m in config.models
        }
        self._observability = observability

    def _trace(
        self,
        severity,
        component: str,
        message: str,
        error: str | None = None,
        **metadata,
    ) -> None:
        """Emit a trace entry through the observability connector."""
        from datetime import datetime

        from modelmesh.interfaces.observability import Severity as SevEnum
        from modelmesh.interfaces.observability import TraceEntry

        sev = severity if isinstance(severity, SevEnum) else SevEnum(severity.lower())
        entry = TraceEntry(
            severity=sev,
            timestamp=datetime.now(),
            component=component,
            message=message,
            error=error,
            metadata=metadata if metadata else None,
        )
        if self._observability:
            self._observability.trace(entry)

    # ── Model Execution ─────────────────────────────────────────────

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a completion request and return the full response.

        Builds the payload via ``_build_request_payload``, posts to the
        endpoint returned by ``_get_completion_endpoint``, and parses
        the response via ``_parse_response``.  Retries on retryable
        status codes up to ``max_retries`` times.
        """
        import time as _time

        component = f"provider.{request.model}"
        self._trace(
            "DEBUG",
            component,
            f"Sending completion request for model '{request.model}'",
            model=request.model,
        )

        payload = self._build_request_payload(request)
        headers = self._build_headers()
        endpoint = self._get_completion_endpoint()
        start_time = _time.monotonic()

        last_error: Optional[Exception] = None
        for attempt in range(self._config.max_retries + 1):
            try:
                data = await asyncio.to_thread(
                    self._http_post, endpoint, payload, headers
                )
                result = self._parse_response(data)
                self.report_usage(request.model, result.usage)
                latency_ms = (_time.monotonic() - start_time) * 1000
                self._trace(
                    "INFO",
                    component,
                    f"Completion succeeded for model '{request.model}'",
                    model=request.model,
                    latency_ms=round(latency_ms, 2),
                    prompt_tokens=result.usage.prompt_tokens,
                    completion_tokens=result.usage.completion_tokens,
                    total_tokens=result.usage.total_tokens,
                )
                return result
            except Exception as exc:
                last_error = exc
                classification = self.classify_error(exc)
                if (
                    not classification.retryable
                    or attempt == self._config.max_retries
                ):
                    self._trace(
                        "ERROR",
                        component,
                        f"Non-retryable error for model "
                        f"'{request.model}': {exc}",
                        error=str(exc),
                        model=request.model,
                        attempt=attempt + 1,
                        category=classification.category,
                    )
                    raise
                self._trace(
                    "WARNING",
                    component,
                    f"Retryable error for model '{request.model}' "
                    f"(attempt {attempt + 1}): {exc}",
                    error=str(exc),
                    model=request.model,
                    attempt=attempt + 1,
                    category=classification.category,
                )
                retry_after: float = 2 ** attempt
                # Check for Retry-After header on urllib HTTPError
                raw_retry = getattr(
                    getattr(exc, "headers", None), "get", lambda _: None
                )("Retry-After")
                if raw_retry is not None:
                    try:
                        retry_after = float(raw_retry)
                    except (ValueError, TypeError):
                        pass
                await asyncio.sleep(retry_after)

        raise last_error  # type: ignore[misc]

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncIterator[CompletionResponse]:
        """Send a completion request and yield partial responses via SSE.

        Sets ``stream: true`` in the payload and reads the response as
        a server-sent event stream, parsing each chunk through
        ``_parse_sse_chunk``.
        """
        self._trace(
            "DEBUG",
            f"provider.{request.model}",
            f"Starting streaming request for model '{request.model}'",
            model=request.model,
        )
        payload = self._build_request_payload(request)
        payload["stream"] = True
        headers = self._build_headers()
        endpoint = self._get_completion_endpoint()

        lines = await asyncio.to_thread(
            self._http_post_stream, endpoint, payload, headers
        )
        for line in lines:
            if not line or not line.startswith("data: "):
                continue
            data_str = line[len("data: "):]
            if data_str.strip() == "[DONE]":
                break
            chunk = self._parse_sse_chunk(data_str)
            if chunk is not None:
                yield chunk

    # ── Capabilities ────────────────────────────────────────────────

    def get_capabilities(self) -> list[str]:
        """Return the list of capability identifiers this provider supports."""
        return list(self._config.capabilities)

    def supports(self, capability: str) -> bool:
        """Check whether this provider supports a specific capability."""
        return capability in self._config.capabilities

    # ── Model Catalogue ─────────────────────────────────────────────

    def list_models(self) -> list[ModelInfo]:
        """Return all models available from this provider."""
        return list(self._config.models)

    def get_model_info(self, model_id: str) -> ModelInfo:
        """Return detailed information for a specific model.

        Raises:
            KeyError: If the model ID is not found in the catalogue.
        """
        if model_id not in self._models_by_id:
            raise KeyError(f"Model not found: {model_id}")
        return self._models_by_id[model_id]

    # ── Quota & Rate Limits ─────────────────────────────────────────

    def check_quota(self) -> QuotaStatus:
        """Return current quota consumption.  No limit enforced by default."""
        return QuotaStatus(used=self._request_count)

    def get_rate_limits(self) -> RateLimitStatus:
        """Return current rate-limit headroom.  Unknown by default."""
        return RateLimitStatus()

    # ── Cost & Pricing ──────────────────────────────────────────────

    def get_pricing(self, model_id: str) -> ModelPricing:
        """Return pricing information for a specific model.

        Raises:
            KeyError: If the model or its pricing is not configured.
        """
        info = self.get_model_info(model_id)
        if info.pricing is None:
            raise KeyError(f"No pricing configured for model: {model_id}")
        return info.pricing

    def report_usage(self, model_id: str, usage: TokenUsage) -> None:
        """Increment internal request and token counters."""
        self._request_count += 1
        self._tokens_used += usage.total_tokens

    # ── Error Classification ────────────────────────────────────────

    def classify_error(self, error: Exception) -> ErrorClassification:
        """Classify an error using configured retryable/non-retryable codes.

        Maps HTTP status codes to categories: ``rate_limit`` for 429,
        ``server`` for 5xx, ``client`` for 4xx, and ``unknown`` for
        everything else.
        """
        # Support both urllib.error.HTTPError (.code) and httpx-style
        # (.response.status_code) error objects.
        status_code: Optional[int] = getattr(error, "code", None)
        if status_code is None:
            status_code = getattr(
                getattr(error, "response", None), "status_code", None
            )
        if status_code is None:
            result = ErrorClassification(retryable=False, category="unknown")
            self._trace(
                "DEBUG",
                "provider",
                f"Error classified as '{result.category}' "
                f"(retryable={result.retryable})",
                error=str(error),
                category=result.category,
                retryable=result.retryable,
            )
            return result

        if status_code in self._config.retryable_codes:
            result = ErrorClassification(
                retryable=True,
                error_code=status_code,
                category="rate_limit" if status_code == 429 else "server",
            )
            self._trace(
                "DEBUG",
                "provider",
                f"Error classified as '{result.category}' "
                f"(retryable={result.retryable}, code={status_code})",
                error=str(error),
                status_code=status_code,
                category=result.category,
                retryable=result.retryable,
            )
            return result

        if status_code in self._config.non_retryable_codes:
            category = "auth" if status_code in (401, 403) else "client"
            result = ErrorClassification(
                retryable=False,
                error_code=status_code,
                category=category,
            )
            self._trace(
                "DEBUG",
                "provider",
                f"Error classified as '{result.category}' "
                f"(retryable={result.retryable}, code={status_code})",
                error=str(error),
                status_code=status_code,
                category=result.category,
                retryable=result.retryable,
            )
            return result

        result = ErrorClassification(
            retryable=False, error_code=status_code, category="unknown"
        )
        self._trace(
            "DEBUG",
            "provider",
            f"Error classified as '{result.category}' "
            f"(retryable={result.retryable}, code={status_code})",
            error=str(error),
            status_code=status_code,
            category=result.category,
            retryable=result.retryable,
        )
        return result

    def is_retryable(self, error: Exception) -> bool:
        """Return True if the error is eligible for retry."""
        return self.classify_error(error).retryable

    # ── Protected Hooks ─────────────────────────────────────────────

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate a CompletionRequest into an OpenAI-format JSON payload.

        Override this method to adapt the request format for
        non-OpenAI-compatible APIs.
        """
        payload: dict = {
            "model": request.model,
            "messages": request.messages,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = request.tools
        if request.stream:
            payload["stream"] = True
        return payload

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Parse an OpenAI-format JSON response into a CompletionResponse.

        Override this method to handle custom response schemas.
        """
        usage_data = data.get("usage", {})
        raw_choices = data.get("choices", [])
        choices: list[CompletionChoice] = []
        for raw in raw_choices:
            msg_data = raw.get("message")
            message = None
            if msg_data:
                message = ChatMessage(
                    role=msg_data.get("role", "assistant"),
                    content=msg_data.get("content"),
                    tool_calls=msg_data.get("tool_calls"),
                )
            choices.append(
                CompletionChoice(
                    index=raw.get("index", 0),
                    message=message,
                    finish_reason=raw.get("finish_reason"),
                )
            )
        return CompletionResponse(
            id=data.get("id", ""),
            model=data.get("model", ""),
            choices=choices,
            usage=TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
        )

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for the request.

        Override to add custom headers or change the auth scheme.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def _get_completion_endpoint(self) -> str:
        """Return the full URL for the chat completions endpoint.

        Override to change the URL path for non-OpenAI APIs.
        """
        base = self._config.base_url.rstrip("/")
        return f"{base}/v1/chat/completions"

    def _parse_sse_chunk(self, line: str) -> CompletionResponse | None:
        """Parse a single SSE data line into a partial CompletionResponse.

        Override to handle non-standard streaming formats.  Return
        ``None`` to skip a chunk.
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        raw_choices = data.get("choices", [])
        if not raw_choices:
            return None
        choices: list[CompletionChoice] = []
        for raw in raw_choices:
            delta_data = raw.get("delta")
            delta = None
            if delta_data:
                delta = ChatMessage(
                    role=delta_data.get("role", "assistant"),
                    content=delta_data.get("content"),
                    tool_calls=delta_data.get("tool_calls"),
                )
            choices.append(
                CompletionChoice(
                    index=raw.get("index", 0),
                    delta=delta,
                    finish_reason=raw.get("finish_reason"),
                )
            )
        return CompletionResponse(
            id=data.get("id", ""),
            model=data.get("model", ""),
            choices=choices,
            usage=TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0
            ),
        )

    async def close(self) -> None:
        """Release any resources held by this connector."""
        pass

    # ── HTTP Transport (stdlib) ─────────────────────────────────────

    def _http_post(
        self, url: str, payload: dict, headers: dict[str, str]
    ) -> dict:
        """Send a synchronous HTTP POST and return the parsed JSON body.

        Uses :mod:`urllib.request` so the package has zero external
        dependencies.  Called from async code via
        :func:`asyncio.to_thread`.
        """
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=self._config.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _http_post_stream(
        self, url: str, payload: dict, headers: dict[str, str]
    ) -> list[str]:
        """Send a synchronous HTTP POST and return raw SSE lines.

        Uses :mod:`urllib.request` so the package has zero external
        dependencies.  Called from async code via
        :func:`asyncio.to_thread`.
        """
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=self._config.timeout) as resp:
            raw = resp.read().decode("utf-8")
        return raw.splitlines()
