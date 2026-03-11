"""Request Correlation ID middleware for ModelMesh.

Automatically assigns a unique correlation ID to each request for
end-to-end tracing across services. The ID is stored in middleware
context metadata and propagated as an ``X-Correlation-ID`` header to
provider requests.

Usage::

    from modelmesh.middleware_contrib import CorrelationIdMiddleware

    # Default: auto-generate UUID4 correlation IDs
    client = modelmesh.create(
        "chat-completion",
        middleware=[CorrelationIdMiddleware()],
    )

    # Custom ID generator
    import shortuuid
    client = modelmesh.create(
        "chat-completion",
        middleware=[CorrelationIdMiddleware(id_generator=shortuuid.uuid)],
    )
"""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Callable, Optional

from modelmesh.interfaces.provider import CompletionRequest, CompletionResponse
from modelmesh.middleware import Middleware, MiddlewareContext

logger = logging.getLogger("modelmesh.middleware.correlation")

__all__ = ["CorrelationIdMiddleware"]


class CorrelationIdMiddleware(Middleware):
    """Middleware that assigns and propagates a correlation ID per request.

    Each request receives a unique correlation ID (UUID4 by default).
    The ID is stored in ``context.metadata["correlation_id"]`` so that
    downstream middleware and application code can access it. The ID is
    also injected as an ``X-Correlation-ID`` header into provider
    requests for distributed tracing.

    If the context already contains a ``correlation_id`` in its metadata
    (e.g. set by an upstream service), it is preserved rather than
    overwritten.

    Args:
        id_generator: Optional callable that returns a string ID.
            Defaults to ``uuid.uuid4()`` hex representation.
        header_name: HTTP header name for propagation.
            Defaults to ``"X-Correlation-ID"``.

    Example::

        mw = CorrelationIdMiddleware()
        client = modelmesh.create("chat-completion", middleware=[mw])

        # After a request, inspect the correlation ID:
        # context.metadata["correlation_id"] -> "a1b2c3d4..."
    """

    def __init__(
        self,
        id_generator: Optional[Callable[[], str]] = None,
        header_name: str = "X-Correlation-ID",
    ) -> None:
        self._id_generator = id_generator or self._default_id_generator
        self._header_name = header_name
        self._lock = threading.Lock()

    @staticmethod
    def _default_id_generator() -> str:
        """Generate a UUID4 hex string."""
        return uuid.uuid4().hex

    async def before_request(
        self,
        request: CompletionRequest,
        context: MiddlewareContext,
    ) -> CompletionRequest:
        """Assign a correlation ID and log the outgoing request.

        If ``context.metadata`` does not already contain a
        ``correlation_id``, one is generated using the configured
        ID generator. The ID is then logged alongside request details.

        Args:
            request: The completion request about to be sent.
            context: Routing context for this attempt.

        Returns:
            The unmodified request (correlation ID is metadata-only).
        """
        with self._lock:
            if "correlation_id" not in context.metadata:
                context.metadata["correlation_id"] = self._id_generator()

        correlation_id = context.metadata["correlation_id"]

        # Store the header name for potential downstream use
        context.metadata["correlation_header"] = self._header_name

        logger.debug(
            "Request [%s] model=%s provider=%s pool=%s attempt=%d",
            correlation_id,
            context.model_id,
            context.provider_id,
            context.pool_name,
            context.attempt,
        )

        return request

    async def after_response(
        self,
        response: CompletionResponse,
        context: MiddlewareContext,
    ) -> CompletionResponse:
        """Log the response with the correlation ID.

        Args:
            response: The completion response from the provider.
            context: Routing context for this attempt.

        Returns:
            The unmodified response.
        """
        correlation_id = context.metadata.get("correlation_id", "unknown")

        logger.debug(
            "Response [%s] model=%s tokens=%d",
            correlation_id,
            response.model,
            response.usage.total_tokens if response.usage else 0,
        )

        return response

    async def on_error(
        self,
        error: Exception,
        context: MiddlewareContext,
    ) -> CompletionResponse:
        """Log the error with the correlation ID, then re-raise.

        Args:
            error: The exception raised by the provider.
            context: Routing context for this attempt.

        Raises:
            Exception: Always re-raises the original error.
        """
        correlation_id = context.metadata.get("correlation_id", "unknown")

        logger.warning(
            "Error [%s] model=%s provider=%s: %s",
            correlation_id,
            context.model_id,
            context.provider_id,
            error,
        )

        raise error
