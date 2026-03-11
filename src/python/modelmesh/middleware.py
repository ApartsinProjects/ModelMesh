"""Request/response middleware for ModelMesh.

Provides an interception layer around provider calls so that users can
add logging, request transforms, response enrichment, caching, or
custom error handling without modifying library internals.

Usage::

    from modelmesh import Middleware

    class LoggingMiddleware(Middleware):
        async def before_request(self, request, context):
            print(f"Routing to {context.model_id}")
            return request

        async def after_response(self, response, context):
            print(f"Tokens: {response.usage.total_tokens}")
            return response

    client = modelmesh.create("chat", middleware=[LoggingMiddleware()])
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from modelmesh.interfaces.provider import CompletionRequest, CompletionResponse


@dataclass
class MiddlewareContext:
    """Context passed to middleware hooks for each request.

    Provides metadata about the current routing decision so
    middleware can make context-aware decisions without coupling
    to router internals.

    Attributes:
        model_id: The real model identifier selected for this attempt.
        provider_id: Connector ID of the provider being used.
        pool_name: The virtual model / pool name from the request.
        attempt: Current retry attempt number (1-based).
        timestamp: Unix timestamp when the request was initiated.
        metadata: Arbitrary key-value metadata for middleware chaining.
    """

    model_id: str = ""
    provider_id: str = ""
    pool_name: str = ""
    attempt: int = 1
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class Middleware:
    """Base class for request/response middleware.

    Subclass and override any of the three hooks. All hooks have
    default no-op implementations, so you only override what you need.

    Hooks:

    - :meth:`before_request`: Called before the provider receives the
      request. Can modify and return a new request.
    - :meth:`after_response`: Called after a successful provider
      response. Can modify and return a new response.
    - :meth:`on_error`: Called when the provider raises an exception.
      Can re-raise, return a fallback response, or raise a new error.
    """

    async def before_request(
        self,
        request: CompletionRequest,
        context: MiddlewareContext,
    ) -> CompletionRequest:
        """Called before the request is sent to the provider.

        Override to inspect or transform the request. Return the
        (possibly modified) request to proceed.

        Args:
            request: The completion request about to be sent.
            context: Routing context for this attempt.

        Returns:
            The request to send (may be the same or a new instance).
        """
        return request

    async def after_response(
        self,
        response: CompletionResponse,
        context: MiddlewareContext,
    ) -> CompletionResponse:
        """Called after a successful provider response.

        Override to inspect, log, or enrich the response. Return the
        (possibly modified) response.

        Args:
            response: The completion response from the provider.
            context: Routing context for this attempt.

        Returns:
            The response to return to the caller.
        """
        return response

    async def on_error(
        self,
        error: Exception,
        context: MiddlewareContext,
    ) -> CompletionResponse:
        """Called when the provider raises an exception.

        Override to handle errors, return a fallback response, or
        re-raise (possibly with wrapping). The default implementation
        re-raises the original error.

        Args:
            error: The exception raised by the provider.
            context: Routing context for this attempt.

        Returns:
            A fallback CompletionResponse to use instead of raising.

        Raises:
            Exception: Re-raised if not handled.
        """
        raise error


class MiddlewareStack:
    """Ordered collection of middleware that executes as a pipeline.

    ``before_request`` hooks run in order (first registered = first
    called). ``after_response`` hooks run in reverse order (last
    registered = first called), following the onion model.
    ``on_error`` hooks run in order until one returns a response.

    Args:
        middlewares: Initial list of middleware instances.
    """

    def __init__(self, middlewares: list[Middleware] | None = None) -> None:
        self._middlewares: list[Middleware] = list(middlewares or [])

    def add(self, middleware: Middleware) -> None:
        """Append a middleware to the stack."""
        self._middlewares.append(middleware)

    @property
    def middlewares(self) -> list[Middleware]:
        """Return the list of registered middleware instances."""
        return list(self._middlewares)

    def __len__(self) -> int:
        return len(self._middlewares)

    async def run_before_request(
        self,
        request: CompletionRequest,
        context: MiddlewareContext,
    ) -> CompletionRequest:
        """Run all ``before_request`` hooks in order.

        Each middleware receives the request returned by the previous
        one, enabling request transformation chains.
        """
        current = request
        for mw in self._middlewares:
            current = await mw.before_request(current, context)
        return current

    async def run_after_response(
        self,
        response: CompletionResponse,
        context: MiddlewareContext,
    ) -> CompletionResponse:
        """Run all ``after_response`` hooks in reverse order (onion model)."""
        current = response
        for mw in reversed(self._middlewares):
            current = await mw.after_response(current, context)
        return current

    async def run_on_error(
        self,
        error: Exception,
        context: MiddlewareContext,
    ) -> CompletionResponse:
        """Run ``on_error`` hooks until one returns a fallback response.

        If no middleware handles the error, the original exception is
        re-raised.
        """
        for mw in self._middlewares:
            try:
                return await mw.on_error(error, context)
            except Exception:
                # This middleware didn't handle it; try next
                continue
        raise error


__all__ = [
    "Middleware",
    "MiddlewareContext",
    "MiddlewareStack",
]
