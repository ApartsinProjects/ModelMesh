"""OpenTelemetry distributed tracing middleware for ModelMesh.

Creates spans for each request with model, provider, pool, and usage
attributes. Propagates trace context through headers for end-to-end
distributed tracing across services.

Requires the ``opentelemetry-api`` package as an optional dependency.
If not installed, the middleware acts as a silent no-op.

Usage::

    from modelmesh.middleware_contrib import OpenTelemetryMiddleware

    # Basic usage (uses default tracer)
    client = modelmesh.create(
        "chat-completion",
        middleware=[OpenTelemetryMiddleware()],
    )

    # Custom tracer name
    client = modelmesh.create(
        "chat-completion",
        middleware=[OpenTelemetryMiddleware(tracer_name="my-service")],
    )
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from modelmesh.interfaces.provider import CompletionRequest, CompletionResponse
from modelmesh.middleware import Middleware, MiddlewareContext

logger = logging.getLogger("modelmesh.middleware.opentelemetry")

# Optional OpenTelemetry imports -- graceful degradation when not installed
try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    StatusCode = None  # type: ignore[assignment,misc]

__all__ = ["OpenTelemetryMiddleware"]


class OpenTelemetryMiddleware(Middleware):
    """Middleware that creates OpenTelemetry spans for each request.

    Each request creates a span with the following attributes:

    - ``modelmesh.model``: The model ID selected by routing.
    - ``modelmesh.provider``: The provider connector ID.
    - ``modelmesh.pool``: The pool / virtual model name.
    - ``modelmesh.attempt``: The retry attempt number (1-based).
    - ``modelmesh.capability``: The requested capability (if available).
    - ``modelmesh.tokens.prompt``: Prompt token count (on success).
    - ``modelmesh.tokens.completion``: Completion token count (on success).
    - ``modelmesh.tokens.total``: Total token count (on success).
    - ``modelmesh.latency_ms``: Request latency in milliseconds (on success).

    On error, the span status is set to ``ERROR`` and the exception is
    recorded as a span event.

    If ``opentelemetry-api`` is not installed, a warning is logged once
    and the middleware becomes a transparent no-op.

    Args:
        tracer_name: Name for the OpenTelemetry tracer.
            Defaults to ``"modelmesh"``.
        record_exceptions: Whether to record exceptions as span events.
            Defaults to ``True``.
    """

    _warned: bool = False

    def __init__(
        self,
        tracer_name: str = "modelmesh",
        record_exceptions: bool = True,
    ) -> None:
        self._tracer_name = tracer_name
        self._record_exceptions = record_exceptions
        self._tracer: Any = None

        if _OTEL_AVAILABLE:
            self._tracer = trace.get_tracer(tracer_name)
        elif not OpenTelemetryMiddleware._warned:
            logger.warning(
                "opentelemetry-api is not installed. "
                "OpenTelemetryMiddleware will operate as a no-op. "
                "Install with: pip install opentelemetry-api"
            )
            OpenTelemetryMiddleware._warned = True

    async def before_request(
        self,
        request: CompletionRequest,
        context: MiddlewareContext,
    ) -> CompletionRequest:
        """Start a new span for the request.

        The span is stored in ``context.metadata`` so that
        :meth:`after_response` and :meth:`on_error` can finish it.

        Args:
            request: The completion request about to be sent.
            context: Routing context for this attempt.

        Returns:
            The unmodified request.
        """
        if not _OTEL_AVAILABLE or self._tracer is None:
            return request

        span = self._tracer.start_span(
            name=f"modelmesh.request {context.pool_name}",
            attributes={
                "modelmesh.model": context.model_id,
                "modelmesh.provider": context.provider_id,
                "modelmesh.pool": context.pool_name,
                "modelmesh.attempt": context.attempt,
            },
        )

        # Store span and timing in context metadata for later hooks
        context.metadata["_otel_span"] = span
        context.metadata["_otel_start_time"] = time.monotonic()

        # Propagate trace context: store trace/span IDs in metadata
        span_context = span.get_span_context()
        if span_context and span_context.is_valid:
            context.metadata["trace_id"] = format(
                span_context.trace_id, "032x"
            )
            context.metadata["span_id"] = format(
                span_context.span_id, "016x"
            )

        return request

    async def after_response(
        self,
        response: CompletionResponse,
        context: MiddlewareContext,
    ) -> CompletionResponse:
        """Record usage attributes and close the span on success.

        Args:
            response: The completion response from the provider.
            context: Routing context for this attempt.

        Returns:
            The unmodified response.
        """
        span = context.metadata.get("_otel_span")
        if span is None:
            return response

        start_time: Optional[float] = context.metadata.get("_otel_start_time")
        if start_time is not None:
            latency_ms = (time.monotonic() - start_time) * 1000
            span.set_attribute("modelmesh.latency_ms", round(latency_ms, 2))

        if response.usage:
            span.set_attribute(
                "modelmesh.tokens.prompt", response.usage.prompt_tokens
            )
            span.set_attribute(
                "modelmesh.tokens.completion",
                response.usage.completion_tokens,
            )
            span.set_attribute(
                "modelmesh.tokens.total", response.usage.total_tokens
            )

        span.set_status(StatusCode.OK)
        span.end()

        return response

    async def on_error(
        self,
        error: Exception,
        context: MiddlewareContext,
    ) -> CompletionResponse:
        """Set span status to ERROR and record the exception, then re-raise.

        Args:
            error: The exception raised by the provider.
            context: Routing context for this attempt.

        Raises:
            Exception: Always re-raises the original error.
        """
        span = context.metadata.get("_otel_span")
        if span is not None:
            span.set_status(StatusCode.ERROR, description=str(error))
            if self._record_exceptions:
                span.record_exception(error)
            span.end()

        raise error
