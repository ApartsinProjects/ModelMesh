"""Tests for the 7 developer experience features.

Covers:
1. Structured exception hierarchy
2. Request/response middleware
3. Async context manager on MeshClient
4. Cost/usage tracking exposure
5. Testing mock client
6. Capability discovery API
7. Routing explanation / debug API
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# Feature 1: Structured Exception Hierarchy
# ============================================================================


class TestExceptionHierarchy:
    """Verify that every exception class has the correct base and fields."""

    def test_modelmesh_error_is_base(self):
        from modelmesh.exceptions import ModelMeshError

        err = ModelMeshError("test error", details={"key": "val"}, retryable=True)
        assert isinstance(err, Exception)
        assert str(err) == "test error"
        assert err.message == "test error"
        assert err.details == {"key": "val"}
        assert err.retryable is True

    def test_modelmesh_error_defaults(self):
        from modelmesh.exceptions import ModelMeshError

        err = ModelMeshError()
        assert err.message == ""
        assert err.details == {}
        assert err.retryable is False

    def test_routing_error_inherits_modelmesh_error(self):
        from modelmesh.exceptions import ModelMeshError, RoutingError

        err = RoutingError("bad route", pool_name="my-pool")
        assert isinstance(err, ModelMeshError)
        assert err.pool_name == "my-pool"

    def test_no_active_model_error(self):
        from modelmesh.exceptions import (
            ModelMeshError,
            NoActiveModelError,
            RoutingError,
        )

        err = NoActiveModelError("none available", pool_name="text-gen")
        assert isinstance(err, RoutingError)
        assert isinstance(err, ModelMeshError)
        assert err.retryable is True
        assert err.pool_name == "text-gen"

    def test_all_providers_exhausted_error(self):
        from modelmesh.exceptions import (
            AllProvidersExhaustedError,
            RoutingError,
        )

        cause = RuntimeError("connection refused")
        err = AllProvidersExhaustedError(
            "all failed",
            pool_name="chat",
            attempts=3,
            last_error=cause,
        )
        assert isinstance(err, RoutingError)
        assert err.attempts == 3
        assert err.last_error is cause
        assert err.retryable is False

    def test_provider_error_fields(self):
        from modelmesh.exceptions import ModelMeshError, ProviderError

        err = ProviderError("timeout", provider_id="openai.llm.v1", model_id="gpt-4o")
        assert isinstance(err, ModelMeshError)
        assert err.provider_id == "openai.llm.v1"
        assert err.model_id == "gpt-4o"

    def test_authentication_error(self):
        from modelmesh.exceptions import AuthenticationError, ProviderError

        err = AuthenticationError("invalid key", provider_id="openai")
        assert isinstance(err, ProviderError)
        assert err.retryable is False

    def test_rate_limit_error(self):
        from modelmesh.exceptions import ProviderError, RateLimitError

        err = RateLimitError("429", provider_id="openai", retry_after=30.0)
        assert isinstance(err, ProviderError)
        assert err.retryable is True
        assert err.retry_after == 30.0

    def test_provider_timeout_error(self):
        from modelmesh.exceptions import ProviderError, ProviderTimeoutError

        err = ProviderTimeoutError("timed out", timeout_seconds=60.0)
        assert isinstance(err, ProviderError)
        assert err.retryable is True
        assert err.timeout_seconds == 60.0

    def test_configuration_error(self):
        from modelmesh.exceptions import ConfigurationError, ModelMeshError

        err = ConfigurationError("missing provider", details={"field": "providers"})
        assert isinstance(err, ModelMeshError)
        assert err.retryable is False

    def test_budget_exceeded_error(self):
        from modelmesh.exceptions import BudgetExceededError, ModelMeshError

        err = BudgetExceededError(
            "over limit",
            limit_type="daily",
            limit_value=10.0,
            actual_value=12.5,
        )
        assert isinstance(err, ModelMeshError)
        assert err.limit_type == "daily"
        assert err.limit_value == 10.0
        assert err.actual_value == 12.5

    def test_budget_exceeded_in_cost_tracker(self):
        """CostTracker should raise BudgetExceededError, not ValueError."""
        from modelmesh.core.budget import BudgetConfig, CostTracker
        from modelmesh.exceptions import BudgetExceededError
        from modelmesh.interfaces.provider import ModelPricing, TokenUsage

        tracker = CostTracker(BudgetConfig(per_request_limit=0.001, enforce=True))
        usage = TokenUsage(prompt_tokens=10000, completion_tokens=5000, total_tokens=15000)
        pricing = ModelPricing(
            input_per_1k_tokens=0.01,
            output_per_1k_tokens=0.03,
            per_request=0.0,
        )

        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.record("gpt-4o", "openai.llm.v1", usage, pricing)
        assert exc_info.value.limit_type == "per_request"

    def test_all_providers_exhausted_in_router(self):
        """Router should raise AllProvidersExhaustedError, not RuntimeError."""
        from modelmesh.exceptions import AllProvidersExhaustedError

        # Verify the exception is importable and has correct hierarchy
        err = AllProvidersExhaustedError("all models exhausted", attempts=3)
        assert isinstance(err, Exception)
        assert err.attempts == 3

    def test_broad_except_catches_all(self):
        """A single `except ModelMeshError` catches all subtypes."""
        from modelmesh.exceptions import (
            AllProvidersExhaustedError,
            AuthenticationError,
            BudgetExceededError,
            ConfigurationError,
            ModelMeshError,
            NoActiveModelError,
            ProviderTimeoutError,
            RateLimitError,
        )

        for ExcClass in [
            NoActiveModelError,
            AllProvidersExhaustedError,
            AuthenticationError,
            RateLimitError,
            ProviderTimeoutError,
            ConfigurationError,
            BudgetExceededError,
        ]:
            try:
                raise ExcClass("test")
            except ModelMeshError:
                pass  # Expected
            except Exception:
                pytest.fail(f"{ExcClass.__name__} not caught by except ModelMeshError")

    def test_exceptions_importable_from_package(self):
        """All exceptions should be importable from the top-level package."""
        import modelmesh

        assert hasattr(modelmesh, "ModelMeshError")
        assert hasattr(modelmesh, "NoActiveModelError")
        assert hasattr(modelmesh, "AllProvidersExhaustedError")
        assert hasattr(modelmesh, "ProviderError")
        assert hasattr(modelmesh, "BudgetExceededError")


# ============================================================================
# Feature 2: Request/Response Middleware
# ============================================================================


class TestMiddleware:
    """Test the middleware pipeline."""

    def test_middleware_base_is_noop(self):
        """Base Middleware passes through without modification."""
        from modelmesh.middleware import Middleware, MiddlewareContext

        mw = Middleware()
        ctx = MiddlewareContext(model_id="test", provider_id="test")

        from modelmesh.interfaces.provider import CompletionRequest

        request = CompletionRequest(model="test", messages=[])
        result = asyncio.run(
            mw.before_request(request, ctx)
        )
        assert result is request

    def test_middleware_context_fields(self):
        from modelmesh.middleware import MiddlewareContext

        ctx = MiddlewareContext(
            model_id="gpt-4o",
            provider_id="openai.llm.v1",
            pool_name="chat",
            attempt=2,
        )
        assert ctx.model_id == "gpt-4o"
        assert ctx.provider_id == "openai.llm.v1"
        assert ctx.pool_name == "chat"
        assert ctx.attempt == 2
        assert ctx.timestamp > 0
        assert ctx.metadata == {}

    def test_middleware_stack_before_request_chain(self):
        """before_request hooks run in order and can transform the request."""
        from modelmesh.interfaces.provider import CompletionRequest
        from modelmesh.middleware import (
            Middleware,
            MiddlewareContext,
            MiddlewareStack,
        )

        order = []

        class FirstMW(Middleware):
            async def before_request(self, request, context):
                order.append("first")
                return CompletionRequest(
                    model="transformed-by-first",
                    messages=request.messages,
                )

        class SecondMW(Middleware):
            async def before_request(self, request, context):
                order.append("second")
                assert request.model == "transformed-by-first"
                return request

        stack = MiddlewareStack([FirstMW(), SecondMW()])
        ctx = MiddlewareContext(model_id="test")

        request = CompletionRequest(model="original", messages=[])
        result = asyncio.run(
            stack.run_before_request(request, ctx)
        )
        assert result.model == "transformed-by-first"
        assert order == ["first", "second"]

    def test_middleware_stack_after_response_reverse_order(self):
        """after_response hooks run in reverse order (onion model)."""
        from modelmesh.middleware import (
            Middleware,
            MiddlewareContext,
            MiddlewareStack,
        )

        order = []

        class FirstMW(Middleware):
            async def after_response(self, response, context):
                order.append("first")
                return response

        class SecondMW(Middleware):
            async def after_response(self, response, context):
                order.append("second")
                return response

        stack = MiddlewareStack([FirstMW(), SecondMW()])
        ctx = MiddlewareContext()

        response = MagicMock()
        asyncio.run(
            stack.run_after_response(response, ctx)
        )
        assert order == ["second", "first"]

    def test_middleware_stack_on_error_fallback(self):
        """on_error hook can return a fallback response."""
        from modelmesh.interfaces.provider import (
            ChatMessage,
            CompletionChoice,
            CompletionResponse,
            TokenUsage,
        )
        from modelmesh.middleware import (
            Middleware,
            MiddlewareContext,
            MiddlewareStack,
        )

        class FallbackMW(Middleware):
            async def on_error(self, error, context):
                return CompletionResponse(
                    id="fallback",
                    model="fallback-model",
                    choices=[
                        CompletionChoice(
                            index=0,
                            message=ChatMessage(role="assistant", content="Fallback!"),
                            finish_reason="stop",
                        )
                    ],
                    usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    created=0,
                    object="chat.completion",
                )

        stack = MiddlewareStack([FallbackMW()])
        ctx = MiddlewareContext()

        result = asyncio.run(
            stack.run_on_error(RuntimeError("provider down"), ctx)
        )
        assert result.choices[0].message.content == "Fallback!"

    def test_middleware_stack_on_error_reraises(self):
        """If no middleware handles the error, it re-raises."""
        from modelmesh.middleware import MiddlewareContext, MiddlewareStack

        stack = MiddlewareStack([])
        ctx = MiddlewareContext()

        with pytest.raises(RuntimeError, match="original"):
            asyncio.run(
                stack.run_on_error(RuntimeError("original"), ctx)
            )

    def test_middleware_stack_add(self):
        from modelmesh.middleware import Middleware, MiddlewareStack

        stack = MiddlewareStack()
        assert len(stack) == 0
        stack.add(Middleware())
        assert len(stack) == 1

    def test_middleware_importable_from_package(self):
        import modelmesh

        assert hasattr(modelmesh, "Middleware")
        assert hasattr(modelmesh, "MiddlewareStack")
        assert hasattr(modelmesh, "MiddlewareContext")


# ============================================================================
# Feature 3: Async Context Manager
# ============================================================================


class TestContextManager:
    """Test MeshClient as a context manager."""

    def test_sync_context_manager(self):
        """MeshClient works with `with` statement."""
        mesh = MagicMock()
        from modelmesh.client.mesh_client import MeshClient

        with MeshClient(mesh) as client:
            assert client is not None
            assert client.mesh is mesh
        mesh.shutdown.assert_called_once()

    def test_async_context_manager(self):
        """MeshClient works with `async with` statement."""
        mesh = MagicMock()

        async def _test():
            from modelmesh.client.mesh_client import MeshClient

            async with MeshClient(mesh) as client:
                assert client is not None
            mesh.shutdown.assert_called_once()

        asyncio.run(_test())

    def test_context_manager_calls_shutdown_on_exception(self):
        """shutdown() is called even if an exception occurs inside `with`."""
        mesh = MagicMock()
        from modelmesh.client.mesh_client import MeshClient

        with pytest.raises(ValueError):
            with MeshClient(mesh) as client:
                raise ValueError("boom")
        mesh.shutdown.assert_called_once()


# ============================================================================
# Feature 4: Usage Tracking
# ============================================================================


class TestUsageTracking:
    """Test the UsageTracker facade."""

    def test_usage_tracker_with_no_cost_tracker(self):
        """UsageTracker returns zeros when no CostTracker is present."""
        from modelmesh.usage import UsageTracker

        mesh = MagicMock(spec=[])
        tracker = UsageTracker(mesh)
        assert tracker.total_cost == 0.0
        assert tracker.daily_cost == 0.0
        assert tracker.monthly_cost == 0.0
        assert tracker.total_tokens == 0
        assert tracker.by_model == {}
        assert tracker.by_provider == {}
        assert tracker.budget_status is None

    def test_usage_tracker_with_cost_tracker(self):
        """UsageTracker wraps CostTracker data correctly."""
        from modelmesh.core.budget import BudgetConfig, CostTracker
        from modelmesh.interfaces.provider import ModelPricing, TokenUsage
        from modelmesh.usage import UsageTracker

        cost_tracker = CostTracker(BudgetConfig(daily_limit=100.0))
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        pricing = ModelPricing(input_per_1k_tokens=0.01, output_per_1k_tokens=0.03, per_request=0.0)
        cost_tracker.record("gpt-4o", "openai.llm.v1", usage, pricing)

        mesh = MagicMock()
        mesh._cost_tracker = cost_tracker
        tracker = UsageTracker(mesh)

        assert tracker.total_cost > 0
        assert tracker.total_tokens == 150
        assert "gpt-4o" in tracker.by_model
        assert "openai.llm.v1" in tracker.by_provider
        assert tracker.budget_status is not None
        assert not tracker.budget_status.exceeded

    def test_usage_tracker_reset(self):
        """reset() clears daily and monthly counters."""
        from modelmesh.core.budget import CostTracker
        from modelmesh.usage import UsageTracker

        cost_tracker = CostTracker()
        mesh = MagicMock()
        mesh._cost_tracker = cost_tracker
        tracker = UsageTracker(mesh)
        # Should not raise
        tracker.reset()

    def test_usage_tracker_summary(self):
        """summary() returns a comprehensive dict."""
        from modelmesh.usage import UsageTracker

        mesh = MagicMock(spec=[])
        tracker = UsageTracker(mesh)
        s = tracker.summary()
        assert "total_cost" in s
        assert "total_tokens" in s
        assert "by_model" in s

    def test_usage_accessible_from_mesh_client(self):
        """client.usage should return a UsageTracker."""
        from modelmesh.client.mesh_client import MeshClient

        mesh = MagicMock()
        client = MeshClient(mesh)
        usage = client.usage
        assert usage is not None
        # Same instance on subsequent access
        assert client.usage is usage


# ============================================================================
# Feature 5: Testing Mock Client
# ============================================================================


class TestMockClient:
    """Test the mock_client testing utility."""

    def test_basic_mock_response(self):
        from modelmesh.testing import MockResponse, mock_client

        client = mock_client(responses=[
            MockResponse(content="Hello!", model="gpt-4o", tokens=10),
        ])
        resp = client.chat.completions.create(
            model="test-pool",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert resp.choices[0].message.content == "Hello!"
        assert resp.model == "gpt-4o"
        assert resp.usage.total_tokens == 10

    def test_call_recording(self):
        from modelmesh.testing import MockResponse, mock_client

        client = mock_client(responses=[MockResponse(content="A")])
        client.chat.completions.create(
            model="my-pool",
            messages=[{"role": "user", "content": "test"}],
        )
        assert len(client.calls) == 1
        assert client.calls[0].model == "my-pool"
        assert client.calls[0].messages[0]["content"] == "test"

    def test_multiple_responses_cycle(self):
        from modelmesh.testing import MockResponse, mock_client

        client = mock_client(responses=[
            MockResponse(content="First"),
            MockResponse(content="Second"),
        ])
        r1 = client.chat.completions.create(model="test", messages=[])
        r2 = client.chat.completions.create(model="test", messages=[])
        assert r1.choices[0].message.content == "First"
        assert r2.choices[0].message.content == "Second"

    def test_mock_client_context_manager(self):
        from modelmesh.testing import mock_client

        with mock_client() as client:
            resp = client.chat.completions.create(model="test", messages=[])
            assert resp.choices[0].message.content == "Mock response"

    def test_mock_client_pool_status(self):
        from modelmesh.testing import mock_client

        client = mock_client()
        status = client.pool_status()
        assert "mock-pool" in status

    def test_mock_client_explain(self):
        from modelmesh.testing import mock_client

        client = mock_client()
        explanation = client.explain(model="test")
        assert explanation["pool_name"] == "mock-pool"
        assert explanation["selected_model"] == "mock-model"

    def test_mock_client_models_list(self):
        from modelmesh.testing import mock_client

        client = mock_client()
        models = client.models.list()
        assert models.object == "list"

    def test_mock_response_token_split(self):
        """MockResponse auto-splits tokens between prompt and completion."""
        from modelmesh.testing import MockResponse

        mr = MockResponse(tokens=30)
        resp = mr.to_completion_response()
        assert resp.usage.prompt_tokens == 10  # 30 // 3
        assert resp.usage.completion_tokens == 20  # 30 - 10
        assert resp.usage.total_tokens == 30

    def test_mock_response_custom_tokens(self):
        from modelmesh.testing import MockResponse

        mr = MockResponse(tokens=100, prompt_tokens=40, completion_tokens=60)
        resp = mr.to_completion_response()
        assert resp.usage.prompt_tokens == 40
        assert resp.usage.completion_tokens == 60

    def test_mock_client_importable_from_package(self):
        import modelmesh

        assert hasattr(modelmesh, "mock_client")
        assert hasattr(modelmesh, "MockClient")
        assert hasattr(modelmesh, "MockResponse")


# ============================================================================
# Feature 6: Capability Discovery API
# ============================================================================


class TestCapabilities:
    """Test the capabilities namespace."""

    def test_list_all_returns_aliases(self):
        from modelmesh.capabilities import list_all

        caps = list_all()
        assert isinstance(caps, list)
        assert "chat-completion" in caps
        assert "text-embeddings" in caps
        assert "text-to-speech" in caps

    def test_list_all_is_sorted(self):
        from modelmesh.capabilities import list_all

        caps = list_all()
        assert caps == sorted(caps)

    def test_resolve_alias(self):
        from modelmesh.capabilities import resolve

        assert resolve("chat-completion") == "generation.text-generation.chat-completion"
        assert resolve("text-embeddings") == "representation.embeddings.text-embeddings"

    def test_resolve_dotted_path_passthrough(self):
        from modelmesh.capabilities import resolve

        assert resolve("generation.text-generation") == "generation.text-generation"

    def test_resolve_unknown_alias(self):
        from modelmesh.capabilities import resolve

        assert resolve("unknown-capability") == "unknown-capability"

    def test_search_by_keyword(self):
        from modelmesh.capabilities import search

        matches = search("text")
        assert "text-generation" in matches
        assert "text-embeddings" in matches
        assert "text-to-speech" in matches

    def test_search_case_insensitive(self):
        from modelmesh.capabilities import search

        matches = search("TEXT")
        assert len(matches) > 0

    def test_search_no_results(self):
        from modelmesh.capabilities import search

        assert search("zzz_nonexistent_zzz") == []

    def test_tree_structure(self):
        from modelmesh.capabilities import tree

        t = tree()
        assert "generation" in t
        assert "text-generation" in t["generation"]
        assert "chat-completion" in t["generation"]["text-generation"]

    def test_tree_has_all_paths(self):
        from modelmesh.capabilities import tree

        t = tree()
        # Should contain representation subtree
        assert "representation" in t
        assert "embeddings" in t["representation"]

    def test_capabilities_importable_from_package(self):
        import modelmesh

        assert hasattr(modelmesh, "capabilities")
        assert callable(modelmesh.capabilities.list_all)
        assert callable(modelmesh.capabilities.resolve)
        assert callable(modelmesh.capabilities.search)
        assert callable(modelmesh.capabilities.tree)


# ============================================================================
# Feature 7: Routing Explanation / Debug API
# ============================================================================


class TestRoutingExplanation:
    """Test the explain() API on MeshClient."""

    def _make_client_with_pool(self):
        """Create a MeshClient with a mock pool for explain() testing."""
        from modelmesh.client.mesh_client import MeshClient

        # Mock the mesh and router
        mock_pool = MagicMock()
        mock_pool.pool_id = "test-pool"
        mock_pool.config = {"strategy": "stick-until-failure", "capability": "generation.text-generation"}

        mock_model = MagicMock()
        mock_model.model_id = "gpt-4o"
        mock_model.provider_id = "openai.llm.v1"
        mock_model.status = MagicMock()
        mock_model.status.value = "active"

        mock_pool.models = [mock_model]
        mock_pool.select.return_value = mock_model

        mock_router = MagicMock()
        mock_router.resolve_pool.return_value = mock_pool

        mesh = MagicMock()
        mesh.get_router.return_value = mock_router

        return MeshClient(mesh)

    def test_explain_returns_pool_info(self):
        client = self._make_client_with_pool()
        result = client.explain(model="test-pool")
        assert result["pool_name"] == "test-pool"
        assert result["strategy"] == "stick-until-failure"

    def test_explain_returns_selected_model(self):
        client = self._make_client_with_pool()
        result = client.explain(model="test-pool")
        assert result["selected_model"] == "gpt-4o"

    def test_explain_returns_candidates(self):
        client = self._make_client_with_pool()
        result = client.explain(model="test-pool")
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["model_id"] == "gpt-4o"
        assert result["candidates"][0]["status"] == "active"

    def test_explain_returns_reason(self):
        client = self._make_client_with_pool()
        result = client.explain(model="test-pool")
        assert "stick-until-failure" in result["reason"]

    def test_explain_with_no_active_model(self):
        from modelmesh.client.mesh_client import MeshClient

        mock_pool = MagicMock()
        mock_pool.pool_id = "empty-pool"
        mock_pool.config = {"strategy": "round-robin", "capability": "test"}
        mock_pool.models = []
        mock_pool.select.return_value = None

        mock_router = MagicMock()
        mock_router.resolve_pool.return_value = mock_pool

        mesh = MagicMock()
        mesh.get_router.return_value = mock_router

        client = MeshClient(mesh)
        result = client.explain(model="empty-pool")
        assert result["selected_model"] is None
        assert "No active model" in result["reason"]

    def test_explain_with_messages(self):
        client = self._make_client_with_pool()
        result = client.explain(
            model="test-pool",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert result["selected_model"] == "gpt-4o"


# ============================================================================
# Integration: Ensure imports work cleanly
# ============================================================================


class TestTopLevelImports:
    """Verify that all new features are importable from the top-level package."""

    def test_exceptions_importable(self):
        from modelmesh import (
            AllProvidersExhaustedError,
            AuthenticationError,
            BudgetExceededError,
            ConfigurationError,
            ModelMeshError,
            NoActiveModelError,
            ProviderError,
            ProviderTimeoutError,
            RateLimitError,
            RoutingError,
        )

    def test_middleware_importable(self):
        from modelmesh import Middleware, MiddlewareContext, MiddlewareStack

    def test_testing_importable(self):
        from modelmesh import MockClient, MockResponse, mock_client

    def test_usage_importable(self):
        from modelmesh import UsageTracker

    def test_capabilities_importable(self):
        from modelmesh import capabilities

        assert callable(capabilities.list_all)
