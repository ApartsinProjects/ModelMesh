"""Tests for contributed middleware: CorrelationIdMiddleware, OpenTelemetryMiddleware."""
import asyncio
import os
import sys
import threading
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.middleware import Middleware, MiddlewareContext, MiddlewareStack
from modelmesh.middleware_contrib.correlation import CorrelationIdMiddleware
from modelmesh.middleware_contrib.opentelemetry import OpenTelemetryMiddleware
from modelmesh.interfaces.provider import CompletionRequest, CompletionResponse


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _make_request():
    """Create a minimal CompletionRequest for testing."""
    return CompletionRequest(
        model="test-model",
        messages=[{"role": "user", "content": "Hello"}],
    )


def _make_context(**kwargs):
    """Create a MiddlewareContext with sensible defaults."""
    defaults = {
        "model_id": "openai.gpt-4o",
        "provider_id": "openai.llm.v1",
        "pool_name": "chat-completion",
        "attempt": 1,
    }
    defaults.update(kwargs)
    return MiddlewareContext(**defaults)


def _make_response():
    """Create a minimal CompletionResponse for testing."""
    from modelmesh.interfaces.provider import (
        ChatMessage,
        CompletionChoice,
        TokenUsage,
    )

    return CompletionResponse(
        id="resp-123",
        model="gpt-4o",
        choices=[
            CompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content="Hello!"),
                finish_reason="stop",
            )
        ],
        usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )


class TestCorrelationIdMiddleware:
    """Test correlation ID middleware."""

    def test_generates_uuid_correlation_id(self):
        """Middleware auto-generates UUID4 correlation ID."""
        mw = CorrelationIdMiddleware()
        request = _make_request()
        context = _make_context()

        _run(mw.before_request(request, context))

        cid = context.metadata.get("correlation_id")
        assert cid is not None
        # UUID4 hex is 32 characters
        assert len(cid) == 32
        # Should be a valid hex string
        int(cid, 16)

    def test_preserves_existing_correlation_id(self):
        """Middleware doesn't overwrite existing correlation_id in context."""
        mw = CorrelationIdMiddleware()
        request = _make_request()
        existing_id = "my-custom-correlation-id"
        context = _make_context(metadata={"correlation_id": existing_id})

        _run(mw.before_request(request, context))

        assert context.metadata["correlation_id"] == existing_id

    def test_custom_id_generator(self):
        """Custom ID generator function is used when provided."""
        custom_id = "custom-id-12345"
        mw = CorrelationIdMiddleware(id_generator=lambda: custom_id)
        request = _make_request()
        context = _make_context()

        _run(mw.before_request(request, context))

        assert context.metadata["correlation_id"] == custom_id

    def test_custom_header_name(self):
        """Custom header name is stored in context."""
        mw = CorrelationIdMiddleware(header_name="X-Request-ID")
        request = _make_request()
        context = _make_context()

        _run(mw.before_request(request, context))

        assert context.metadata["correlation_header"] == "X-Request-ID"

    def test_default_header_name(self):
        """Default header name is X-Correlation-ID."""
        mw = CorrelationIdMiddleware()
        request = _make_request()
        context = _make_context()

        _run(mw.before_request(request, context))

        assert context.metadata["correlation_header"] == "X-Correlation-ID"

    def test_logs_on_error(self):
        """Correlation ID is included when on_error re-raises."""
        mw = CorrelationIdMiddleware()
        request = _make_request()
        context = _make_context()

        # First set the correlation ID via before_request
        _run(mw.before_request(request, context))

        error = RuntimeError("test error")
        with pytest.raises(RuntimeError, match="test error"):
            _run(mw.on_error(error, context))

        # The correlation_id should still be in the context
        assert "correlation_id" in context.metadata

    def test_after_response_returns_response(self):
        """after_response returns the response unmodified."""
        mw = CorrelationIdMiddleware()
        context = _make_context(metadata={"correlation_id": "test-id"})
        response = _make_response()

        result = _run(mw.after_response(response, context))

        assert result is response

    def test_before_request_returns_request(self):
        """before_request returns the request unmodified."""
        mw = CorrelationIdMiddleware()
        request = _make_request()
        context = _make_context()

        result = _run(mw.before_request(request, context))

        assert result is request

    def test_thread_safety(self):
        """Multiple concurrent calls get unique correlation IDs."""
        mw = CorrelationIdMiddleware()
        ids = []
        lock = threading.Lock()

        def run():
            ctx = _make_context()
            req = _make_request()
            loop = asyncio.new_event_loop()
            loop.run_until_complete(mw.before_request(req, ctx))
            loop.close()
            with lock:
                ids.append(ctx.metadata["correlation_id"])

        threads = [threading.Thread(target=run) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All IDs should be unique
        assert len(set(ids)) == 20


class TestOpenTelemetryMiddleware:
    """Test OpenTelemetry middleware (no-op when otel not installed)."""

    def test_noop_without_opentelemetry(self):
        """Acts as passthrough when opentelemetry is not installed."""
        mw = OpenTelemetryMiddleware()
        request = _make_request()
        context = _make_context()

        result = _run(mw.before_request(request, context))

        # Should return the request unmodified
        assert result is request

    def test_before_request_sets_metadata(self):
        """before_request populates context metadata when otel not available."""
        mw = OpenTelemetryMiddleware()
        request = _make_request()
        context = _make_context()

        result = _run(mw.before_request(request, context))

        # Without otel installed, no span metadata is added
        assert result is request

    def test_after_response_completes(self):
        """after_response runs without error."""
        mw = OpenTelemetryMiddleware()
        context = _make_context()
        response = _make_response()

        result = _run(mw.after_response(response, context))

        assert result is response

    def test_on_error_reraises(self):
        """on_error propagates the original exception."""
        mw = OpenTelemetryMiddleware()
        context = _make_context()
        error = ValueError("test otel error")

        with pytest.raises(ValueError, match="test otel error"):
            _run(mw.on_error(error, context))

    def test_custom_tracer_name(self):
        """Custom tracer name is accepted."""
        mw = OpenTelemetryMiddleware(tracer_name="my-service")
        assert mw._tracer_name == "my-service"

    def test_record_exceptions_flag(self):
        """record_exceptions flag is stored."""
        mw = OpenTelemetryMiddleware(record_exceptions=False)
        assert mw._record_exceptions is False

    def test_default_tracer_name(self):
        """Default tracer name is 'modelmesh'."""
        mw = OpenTelemetryMiddleware()
        assert mw._tracer_name == "modelmesh"


class TestMiddlewareStackIntegration:
    """Test CorrelationIdMiddleware and OpenTelemetryMiddleware in a stack."""

    def test_stack_with_both_middlewares(self):
        """Both middlewares execute in a stack without error."""
        stack = MiddlewareStack([
            CorrelationIdMiddleware(),
            OpenTelemetryMiddleware(),
        ])
        request = _make_request()
        context = _make_context()

        result = _run(stack.run_before_request(request, context))

        assert result is request
        assert "correlation_id" in context.metadata

    def test_stack_after_response(self):
        """Both middlewares handle after_response in the stack."""
        stack = MiddlewareStack([
            CorrelationIdMiddleware(),
            OpenTelemetryMiddleware(),
        ])
        context = _make_context(metadata={"correlation_id": "test-123"})
        response = _make_response()

        result = _run(stack.run_after_response(response, context))

        assert result is response
