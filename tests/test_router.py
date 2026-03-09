"""Tests for the Router class."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.core.capability_tree import CapabilityTree
from modelmesh.core.event_emitter import EventEmitter
from modelmesh.core.pool import CapabilityPool, PoolModel
from modelmesh.core.router import Router, NoActiveModelError
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
from modelmesh.interfaces.rotation import ModelStatus


class MockProvider(ProviderConnector):
    """A mock provider that returns canned responses."""

    def __init__(self, fail_count=0):
        self._fail_count = fail_count
        self._call_count = 0
        self._models = [
            ModelInfo(id="mock-model", name="Mock Model", capabilities=["chat"]),
        ]

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise RuntimeError(f"Mock failure #{self._call_count}")
        return CompletionResponse(
            id="mock-response",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hello from mock"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(
                prompt_tokens=10, completion_tokens=5, total_tokens=15
            ),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionResponse]:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise RuntimeError(f"Mock stream failure #{self._call_count}")
        yield CompletionResponse(
            id="mock-chunk",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content="Hello"),
                    finish_reason=None,
                )
            ],
            usage=TokenUsage(),
        )
        yield CompletionResponse(
            id="mock-chunk",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content="!"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(),
        )

    def get_capabilities(self):
        return ["chat"]

    def supports(self, capability):
        return capability in ["chat"]

    def list_models(self):
        return list(self._models)

    def get_model_info(self, model_id):
        for m in self._models:
            if m.id == model_id:
                return m
        raise KeyError(f"Model not found: {model_id}")

    def check_quota(self):
        return QuotaStatus()

    def get_rate_limits(self):
        return RateLimitStatus()

    def get_pricing(self, model_id):
        return ModelPricing()

    def report_usage(self, model_id, usage):
        pass

    def classify_error(self, error):
        return ErrorClassification(retryable=False, category="unknown")


class TestRouter(unittest.TestCase):
    """Test the Router class."""

    def _make_router(self, provider=None, observability=None, max_retries=3):
        tree = CapabilityTree()
        tree.register("generation.text-generation.chat-completion")

        pool = CapabilityPool(
            "chat-completion",
            {"capability": "generation.text-generation.chat-completion"},
            observability=observability,
        )
        model_a = PoolModel(
            model_id="mock.model-a",
            real_model_id="model-a",
            provider_id="mock.v1",
        )
        model_b = PoolModel(
            model_id="mock.model-b",
            real_model_id="model-b",
            provider_id="mock.v1",
        )
        pool.add_model(model_a)
        pool.add_model(model_b)

        if provider is None:
            provider = MockProvider()

        pools = {"chat-completion": pool}
        providers = {"mock.v1": provider}
        emitter = EventEmitter()

        return Router(
            pools,
            tree,
            providers,
            event_emitter=emitter,
            observability=observability,
            max_retries=max_retries,
        )

    def test_route_to_correct_pool(self):
        router = self._make_router()
        request = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hello"}],
        )
        response = asyncio.run(router.route(request))
        self.assertIsInstance(response, CompletionResponse)
        self.assertEqual(response.choices[0].message.content, "Hello from mock")

    def test_route_unknown_pool_raises(self):
        router = self._make_router()
        request = CompletionRequest(
            model="unknown-pool",
            messages=[{"role": "user", "content": "Hello"}],
        )
        with self.assertRaises(KeyError):
            asyncio.run(router.route(request))

    def test_rotation_on_failure(self):
        # Provider fails first call, succeeds on second
        provider = MockProvider(fail_count=1)
        router = self._make_router(provider=provider)
        request = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hello"}],
        )
        response = asyncio.run(router.route(request))
        self.assertIsInstance(response, CompletionResponse)
        self.assertEqual(provider._call_count, 2)

    def test_max_retries_exhausted(self):
        # Provider fails more times than max_retries
        provider = MockProvider(fail_count=10)
        router = self._make_router(provider=provider, max_retries=2)
        request = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hello"}],
        )
        with self.assertRaises(RuntimeError) as ctx:
            asyncio.run(router.route(request))
        self.assertIn("All models exhausted", str(ctx.exception))

    def test_streaming_route(self):
        router = self._make_router()
        request = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True,
        )

        async def collect_stream():
            chunks = []
            async for chunk in router.route_stream(request):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(collect_stream())
        self.assertEqual(len(chunks), 2)

    def test_no_active_model_raises(self):
        tree = CapabilityTree()
        tree.register("test")
        pool = CapabilityPool("test-pool", {"capability": "test"})
        # Pool has no models
        pools = {"test-pool": pool}
        providers = {}
        router = Router(pools, tree, providers)

        request = CompletionRequest(
            model="test-pool",
            messages=[{"role": "user", "content": "Hello"}],
        )
        with self.assertRaises(NoActiveModelError):
            asyncio.run(router.route(request))

    def test_resolve_pool_direct(self):
        router = self._make_router()
        pool = router.resolve_pool("chat-completion")
        self.assertEqual(pool.pool_id, "chat-completion")

    # -- WITH OBSERVABILITY --

    def test_route_emits_traces(self):
        """Route a request and verify traces appear in the file log."""
        from modelmesh.cdk.specialized.file_observability import (
            FileObservability,
            FileObservabilityConfig,
        )

        tmp = tempfile.mktemp(suffix=".log")
        try:
            obs = FileObservability(
                FileObservabilityConfig(file_path=tmp, min_severity="debug")
            )
            router = self._make_router(observability=obs)
            request = CompletionRequest(
                model="chat-completion",
                messages=[{"role": "user", "content": "Hello"}],
            )
            asyncio.run(router.route(request))
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn('"type": "trace"', content)
            self.assertIn("router", content)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_failure_emits_error_trace(self):
        """Route a failing request and verify ERROR traces appear."""
        from modelmesh.cdk.specialized.file_observability import (
            FileObservability,
            FileObservabilityConfig,
        )

        tmp = tempfile.mktemp(suffix=".log")
        try:
            obs = FileObservability(
                FileObservabilityConfig(file_path=tmp, min_severity="debug")
            )
            provider = MockProvider(fail_count=10)
            router = self._make_router(
                provider=provider, observability=obs, max_retries=2
            )
            request = CompletionRequest(
                model="chat-completion",
                messages=[{"role": "user", "content": "Hello"}],
            )
            with self.assertRaises(RuntimeError):
                asyncio.run(router.route(request))
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                lines = f.readlines()

            error_lines = [
                l for l in lines if '"severity": "error"' in l
            ]
            self.assertGreater(len(error_lines), 0, "Expected ERROR trace entries")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


if __name__ == "__main__":
    unittest.main()
