"""Tests for realistic routing scenarios: failover, quota, latency, production routing.

Validates real-world routing behaviors including failover cascades,
deactivation on failure thresholds, quota exhaustion handling,
cost/latency-based selection strategies, and full mesh routing with
mock providers.
"""
import asyncio
import os
import sys
import time
import unittest
from typing import AsyncIterator, Optional
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.exceptions import AllProvidersExhaustedError
from modelmesh.config.mesh_config import MeshConfig
from modelmesh.core.capability_tree import CapabilityTree
from modelmesh.core.event_emitter import EventEmitter, EventType
from modelmesh.core.mesh import ModelMesh
from modelmesh.core.pool import CapabilityPool, PoolModel
from modelmesh.core.router import NoActiveModelError, Router
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
from modelmesh.interfaces.rotation import (
    ModelState,
    ModelStatus,
    SelectionStrategy,
)


# ---------------------------------------------------------------------------
# Reusable mock providers
# ---------------------------------------------------------------------------

class _BaseProvider(ProviderConnector):
    """Base class for mock providers with minimal boilerplate."""

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, capability):
        return capability in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="mock-model", name="Mock Model")]

    def get_model_info(self, model_id):
        return ModelInfo(id=model_id, name=model_id)

    def check_quota(self):
        return QuotaStatus()

    def get_rate_limits(self):
        return RateLimitStatus()

    def get_pricing(self, model_id):
        return ModelPricing()

    def report_usage(self, model_id, usage):
        pass

    def classify_error(self, error):
        return ErrorClassification(retryable=False)


class AlwaysFailProvider(_BaseProvider):
    """Provider that always raises an error on complete/stream."""

    def __init__(self, error_msg="provider failure"):
        self._error_msg = error_msg
        self.call_count = 0

    async def complete(self, request):
        self.call_count += 1
        raise RuntimeError(self._error_msg)

    async def stream(self, request):
        self.call_count += 1
        raise RuntimeError(self._error_msg)
        yield  # pragma: no cover


class AlwaysSucceedProvider(_BaseProvider):
    """Provider that always succeeds."""

    def __init__(self, content="OK"):
        self._content = content
        self.call_count = 0

    async def complete(self, request):
        self.call_count += 1
        return CompletionResponse(
            id="ok-resp",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=self._content),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )

    async def stream(self, request):
        self.call_count += 1
        yield CompletionResponse(
            id="ok-chunk-1",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content="chunk1"),
                    finish_reason=None,
                )
            ],
        )
        yield CompletionResponse(
            id="ok-chunk-2",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content="chunk2"),
                    finish_reason="stop",
                )
            ],
        )


class FailNTimesProvider(_BaseProvider):
    """Provider that fails the first N calls then succeeds."""

    def __init__(self, fail_count=1, content="recovered"):
        self._fail_count = fail_count
        self._content = content
        self.call_count = 0

    async def complete(self, request):
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise RuntimeError(f"Failure #{self.call_count}")
        return CompletionResponse(
            id="recovered-resp",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=self._content),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )

    async def stream(self, request):
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise RuntimeError(f"Stream failure #{self.call_count}")
        yield CompletionResponse(
            id="recovered-chunk",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content=self._content),
                    finish_reason="stop",
                )
            ],
        )


class QuotaExhaustedProvider(_BaseProvider):
    """Provider that simulates a 429 quota exhaustion error."""

    def __init__(self):
        self.call_count = 0

    async def complete(self, request):
        self.call_count += 1
        raise RuntimeError("429 Too Many Requests: quota exhausted")

    async def stream(self, request):
        self.call_count += 1
        raise RuntimeError("429 Too Many Requests: quota exhausted")
        yield  # pragma: no cover

    def check_quota(self):
        return QuotaStatus(used=1000, limit=1000, remaining=0)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _make_request(model="test-pool"):
    return CompletionRequest(
        model=model,
        messages=[{"role": "user", "content": "test"}],
    )


def _make_pool(pool_id="test-pool", failure_threshold=3, models=None):
    """Create a CapabilityPool with given models."""
    pool = CapabilityPool(
        pool_id,
        {"capability": "generation.text-generation.chat-completion",
         "failure_threshold": failure_threshold},
    )
    if models:
        for m in models:
            pool.add_model(m)
    return pool


def _make_pool_model(model_id, provider_id):
    parts = model_id.split(".", 1)
    real_model_id = parts[1] if len(parts) > 1 else model_id
    return PoolModel(
        model_id=model_id,
        real_model_id=real_model_id,
        provider_id=provider_id,
    )


def _make_router(pools, providers, max_retries=3):
    tree = CapabilityTree()
    tree.register("generation.text-generation.chat-completion")
    return Router(
        pools, tree, providers,
        event_emitter=EventEmitter(),
        max_retries=max_retries,
    )


def _make_mesh_config(providers_dict, models_dict, pool_id="chat-completion",
                       failure_threshold=3):
    """Build a MeshConfig with inline provider instances."""
    providers_cfg = {}
    for pid, instance in providers_dict.items():
        providers_cfg[pid] = {
            "connector": pid,
            "enabled": True,
            "instance": instance,
            "config": {},
        }

    return MeshConfig(raw={
        "providers": providers_cfg,
        "models": models_dict,
        "pools": {
            pool_id: {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "stick-until-failure",
                "failure_threshold": failure_threshold,
            },
        },
        "observability": {"connector": "modelmesh.null.v1"},
    })


# ===================================================================
# FAILOVER BEHAVIOR
# ===================================================================

class TestFailoverBehavior(unittest.TestCase):
    """Tests for failover and rotation on provider failures."""

    def test_single_failure_rotates_to_next_model(self):
        """After record_failure(), pool.select() should return a different model."""
        model_a = _make_pool_model("a.model-a", "prov-a")
        model_b = _make_pool_model("b.model-b", "prov-b")
        pool = _make_pool(models=[model_a, model_b])

        req = _make_request()
        first = pool.select(req)
        self.assertEqual(first.model_id, "a.model-a")

        # Record failure on model A (not enough to deactivate)
        pool.record_failure("a.model-a", RuntimeError("err"))
        self.assertEqual(model_a.failure_count, 1)
        self.assertEqual(model_a.status, ModelStatus.ACTIVE)

    def test_deactivation_after_threshold_failures(self):
        """After N consecutive failures, model should be set to STANDBY."""
        model = _make_pool_model("test.model", "prov")
        pool = _make_pool(failure_threshold=3, models=[model])

        for i in range(3):
            pool.record_failure("test.model", RuntimeError(f"err{i}"))

        self.assertEqual(model.status, ModelStatus.STANDBY)
        self.assertEqual(model.failure_count, 3)

    def test_deactivation_skips_model_on_select(self):
        """After deactivation, select() should skip the standby model."""
        model_a = _make_pool_model("a.model-a", "prov-a")
        model_b = _make_pool_model("b.model-b", "prov-b")
        pool = _make_pool(failure_threshold=2, models=[model_a, model_b])

        # Deactivate model A
        pool.record_failure("a.model-a", RuntimeError("e1"))
        pool.record_failure("a.model-a", RuntimeError("e2"))
        self.assertEqual(model_a.status, ModelStatus.STANDBY)

        req = _make_request()
        selected = pool.select(req)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.model_id, "b.model-b")

    def test_multi_model_cascade_a_fails_b_fails_c_succeeds(self):
        """Model A fails -> B fails -> C succeeds: router returns C's response."""
        prov_a = AlwaysFailProvider("A failed")
        prov_b = AlwaysFailProvider("B failed")
        prov_c = AlwaysSucceedProvider("C ok")

        model_a = _make_pool_model("a.m", "prov-a")
        model_b = _make_pool_model("b.m", "prov-b")
        model_c = _make_pool_model("c.m", "prov-c")
        # failure_threshold=1 so each failure immediately deactivates,
        # allowing the router to select the next model on retry.
        pool = _make_pool(failure_threshold=1, models=[model_a, model_b, model_c])

        pools = {"test-pool": pool}
        providers = {"prov-a": prov_a, "prov-b": prov_b, "prov-c": prov_c}
        router = _make_router(pools, providers, max_retries=3)

        req = _make_request()
        response = asyncio.run(router.route(req))
        self.assertEqual(response.choices[0].message.content, "C ok")
        self.assertEqual(prov_a.call_count, 1)
        self.assertEqual(prov_b.call_count, 1)
        self.assertEqual(prov_c.call_count, 1)

    def test_all_models_exhausted_raises_error(self):
        """When all models fail, router raises AllProvidersExhaustedError."""
        prov = AlwaysFailProvider("all down")
        model_a = _make_pool_model("a.m", "prov")
        model_b = _make_pool_model("b.m", "prov")
        pool = _make_pool(models=[model_a, model_b])

        pools = {"test-pool": pool}
        providers = {"prov": prov}
        router = _make_router(pools, providers, max_retries=2)

        req = _make_request()
        with self.assertRaises(AllProvidersExhaustedError) as ctx:
            asyncio.run(router.route(req))
        self.assertIn("All models exhausted", str(ctx.exception))

    def test_pool_select_returns_none_when_all_standby(self):
        """select() returns None when all models are in STANDBY."""
        model_a = _make_pool_model("a.m", "prov")
        model_b = _make_pool_model("b.m", "prov")
        pool = _make_pool(failure_threshold=1, models=[model_a, model_b])

        pool.record_failure("a.m", RuntimeError("e"))
        pool.record_failure("b.m", RuntimeError("e"))

        req = _make_request()
        selected = pool.select(req)
        self.assertIsNone(selected)

    def test_no_models_in_pool_raises_no_active_model_error(self):
        """NoActiveModelError when pool has zero models."""
        pool = _make_pool(models=[])
        pools = {"test-pool": pool}
        providers = {}
        router = _make_router(pools, providers)

        req = _make_request()
        with self.assertRaises(NoActiveModelError):
            asyncio.run(router.route(req))

    def test_success_resets_failure_count(self):
        """record_success resets failure_count to 0."""
        model = _make_pool_model("test.m", "prov")
        pool = _make_pool(failure_threshold=5, models=[model])

        pool.record_failure("test.m", RuntimeError("e1"))
        pool.record_failure("test.m", RuntimeError("e2"))
        self.assertEqual(model.failure_count, 2)

        pool.record_success("test.m")
        self.assertEqual(model.failure_count, 0)
        self.assertEqual(model.status, ModelStatus.ACTIVE)

    def test_router_rotation_on_single_provider_failure(self):
        """When provider fails first call, router rotates to second model."""
        prov = FailNTimesProvider(fail_count=1, content="recovered")
        model_a = _make_pool_model("a.m", "prov")
        model_b = _make_pool_model("b.m", "prov")
        pool = _make_pool(models=[model_a, model_b])

        pools = {"test-pool": pool}
        providers = {"prov": prov}
        router = _make_router(pools, providers, max_retries=3)

        req = _make_request()
        response = asyncio.run(router.route(req))
        self.assertEqual(response.choices[0].message.content, "recovered")
        self.assertEqual(prov.call_count, 2)

    def test_provider_not_found_records_failure(self):
        """Missing provider connector causes rotation, not crash."""
        model_a = _make_pool_model("a.m", "missing-prov")
        model_b = _make_pool_model("b.m", "good-prov")
        # failure_threshold=1 so the missing-provider failure immediately
        # deactivates model_a, letting the router select model_b.
        pool = _make_pool(failure_threshold=1, models=[model_a, model_b])

        good_prov = AlwaysSucceedProvider("from good")
        pools = {"test-pool": pool}
        providers = {"good-prov": good_prov}
        router = _make_router(pools, providers, max_retries=3)

        req = _make_request()
        response = asyncio.run(router.route(req))
        self.assertEqual(response.choices[0].message.content, "from good")

    def test_failure_records_timestamp(self):
        """record_failure sets last_failure_at timestamp."""
        model = _make_pool_model("test.m", "prov")
        pool = _make_pool(models=[model])

        before = time.time()
        pool.record_failure("test.m", RuntimeError("e"))
        after = time.time()

        self.assertIsNotNone(model.last_failure_at)
        self.assertGreaterEqual(model.last_failure_at, before)
        self.assertLessEqual(model.last_failure_at, after)


# ===================================================================
# QUOTA EXHAUSTION
# ===================================================================

class TestQuotaExhaustion(unittest.TestCase):
    """Tests for quota-based routing decisions."""

    def test_quota_exhausted_provider_causes_failover(self):
        """Quota-exhausted provider triggers routing to next provider."""
        quota_prov = QuotaExhaustedProvider()
        good_prov = AlwaysSucceedProvider("from backup")

        model_a = _make_pool_model("q.m", "quota-prov")
        model_b = _make_pool_model("g.m", "good-prov")
        # failure_threshold=1 so the quota error deactivates model_a
        # immediately, letting the router select model_b.
        pool = _make_pool(failure_threshold=1, models=[model_a, model_b])

        pools = {"test-pool": pool}
        providers = {"quota-prov": quota_prov, "good-prov": good_prov}
        router = _make_router(pools, providers, max_retries=3)

        req = _make_request()
        response = asyncio.run(router.route(req))
        self.assertEqual(response.choices[0].message.content, "from backup")

    def test_quota_status_remaining_zero(self):
        """QuotaStatus with remaining=0 is correctly reported."""
        prov = QuotaExhaustedProvider()
        quota = prov.check_quota()
        self.assertEqual(quota.remaining, 0)
        self.assertEqual(quota.used, 1000)
        self.assertEqual(quota.limit, 1000)

    def test_reactivation_after_quota_reset(self):
        """reactivate() brings a standby model back to ACTIVE with reset failure_count."""
        model = _make_pool_model("test.m", "prov")
        pool = _make_pool(failure_threshold=2, models=[model])

        pool.record_failure("test.m", RuntimeError("e1"))
        pool.record_failure("test.m", RuntimeError("e2"))
        self.assertEqual(model.status, ModelStatus.STANDBY)

        # Simulate quota reset -> reactivate
        pool.reactivate("test.m")
        self.assertEqual(model.status, ModelStatus.ACTIVE)
        self.assertEqual(model.failure_count, 0)

        req = _make_request()
        selected = pool.select(req)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.model_id, "test.m")

    def test_multiple_quota_exhausted_providers(self):
        """All quota-exhausted providers cause AllProvidersExhaustedError."""
        prov_a = QuotaExhaustedProvider()
        prov_b = QuotaExhaustedProvider()

        model_a = _make_pool_model("a.m", "prov-a")
        model_b = _make_pool_model("b.m", "prov-b")
        pool = _make_pool(models=[model_a, model_b])

        pools = {"test-pool": pool}
        providers = {"prov-a": prov_a, "prov-b": prov_b}
        router = _make_router(pools, providers, max_retries=2)

        req = _make_request()
        with self.assertRaises(AllProvidersExhaustedError):
            asyncio.run(router.route(req))


# ===================================================================
# LATENCY / COST TRADE-OFFS
# ===================================================================

class CostFirstStrategy(SelectionStrategy):
    """Selection strategy that prefers cheaper models (lower cost score = higher priority)."""

    def __init__(self, pricing_map):
        self._pricing = pricing_map

    def select(self, candidates, request):
        active = [c for c in candidates if c.status == ModelStatus.ACTIVE]
        if not active:
            return None
        return max(active, key=lambda c: self.score(c, request))

    def score(self, state, request):
        cost = self._pricing.get(state.model_id, 1.0)
        return 1.0 / (cost + 0.001)  # Higher score for cheaper models


class TestLatencyCostTradeoffs(unittest.TestCase):
    """Tests for selection strategy scoring and trade-offs."""

    def test_cost_first_strategy_prefers_cheaper(self):
        """CostFirstStrategy selects the cheapest model."""
        pricing = {
            "expensive.m": 10.0,
            "cheap.m": 0.5,
            "medium.m": 3.0,
        }
        strategy = CostFirstStrategy(pricing)

        candidates = [
            ModelState(model_id="expensive.m", status=ModelStatus.ACTIVE),
            ModelState(model_id="cheap.m", status=ModelStatus.ACTIVE),
            ModelState(model_id="medium.m", status=ModelStatus.ACTIVE),
        ]
        req = _make_request()
        selected = strategy.select(candidates, req)
        self.assertEqual(selected.model_id, "cheap.m")

    def test_cost_first_skips_standby(self):
        """CostFirstStrategy ignores standby models."""
        pricing = {"cheap.m": 0.1, "expensive.m": 10.0}
        strategy = CostFirstStrategy(pricing)

        candidates = [
            ModelState(model_id="cheap.m", status=ModelStatus.STANDBY),
            ModelState(model_id="expensive.m", status=ModelStatus.ACTIVE),
        ]
        req = _make_request()
        selected = strategy.select(candidates, req)
        self.assertEqual(selected.model_id, "expensive.m")

    def test_stick_until_failure_stays_on_same_model(self):
        """Default stick-until-failure selects the same model on consecutive calls."""
        model_a = _make_pool_model("a.m", "prov")
        model_b = _make_pool_model("b.m", "prov")
        pool = _make_pool(models=[model_a, model_b])

        req = _make_request()
        s1 = pool.select(req)
        pool.record_success(s1.model_id)
        s2 = pool.select(req)
        self.assertEqual(s1.model_id, s2.model_id)

    def test_custom_strategy_can_be_set_on_pool(self):
        """Pool.set_strategy() replaces the default strategy."""
        model_a = _make_pool_model("expensive.m", "prov")
        model_b = _make_pool_model("cheap.m", "prov")
        pool = _make_pool(models=[model_a, model_b])

        pricing = {"expensive.m": 10.0, "cheap.m": 0.5}
        pool.set_strategy(CostFirstStrategy(pricing))

        req = _make_request()
        selected = pool.select(req)
        self.assertEqual(selected.model_id, "cheap.m")

    def test_cost_first_scoring_values(self):
        """CostFirstStrategy score is inversely proportional to cost."""
        pricing = {"cheap.m": 0.5, "expensive.m": 10.0}
        strategy = CostFirstStrategy(pricing)
        req = _make_request()

        cheap_score = strategy.score(
            ModelState(model_id="cheap.m", status=ModelStatus.ACTIVE), req
        )
        expensive_score = strategy.score(
            ModelState(model_id="expensive.m", status=ModelStatus.ACTIVE), req
        )
        self.assertGreater(cheap_score, expensive_score)


# ===================================================================
# PRODUCTION ROUTING (FULL MESH)
# ===================================================================

class TestProductionRouting(unittest.TestCase):
    """Tests for full ModelMesh.route() with realistic scenarios."""

    def test_route_with_failover_mock(self):
        """route() with a provider that fails first call, succeeds on retry."""
        prov = FailNTimesProvider(fail_count=1, content="recovered via mesh")
        config = _make_mesh_config(
            providers_dict={"failover.v1": prov},
            models_dict={
                "failover.model-a": {
                    "provider": "failover.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
                "failover.model-b": {
                    "provider": "failover.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
        )
        mesh = ModelMesh()
        mesh.initialize(config)

        req = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "hello"}],
        )
        response = asyncio.run(mesh.route(req))
        self.assertEqual(response.choices[0].message.content, "recovered via mesh")
        self.assertEqual(prov.call_count, 2)

    def test_route_stream_returns_chunks(self):
        """route_stream() with a mock provider returning chunks."""
        prov = AlwaysSucceedProvider("streamed")
        config = _make_mesh_config(
            providers_dict={"stream.v1": prov},
            models_dict={
                "stream.model-a": {
                    "provider": "stream.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
        )
        mesh = ModelMesh()
        mesh.initialize(config)

        req = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "hello"}],
            stream=True,
        )

        async def collect():
            chunks = []
            async for chunk in mesh.route_stream(req):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(collect())
        self.assertEqual(len(chunks), 2)
        self.assertIsNotNone(chunks[0].choices[0].delta.content)

    def test_pool_status_after_failures(self):
        """pool_status() correctly reports active/standby counts."""
        prov = AlwaysSucceedProvider("ok")
        config = _make_mesh_config(
            providers_dict={"status.v1": prov},
            models_dict={
                "status.model-a": {
                    "provider": "status.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
                "status.model-b": {
                    "provider": "status.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
            failure_threshold=2,
        )
        mesh = ModelMesh()
        mesh.initialize(config)

        # Verify initial status
        status = mesh.pool_status()
        self.assertIn("chat-completion", status)
        self.assertEqual(status["chat-completion"]["active"], 2)
        self.assertEqual(status["chat-completion"]["standby"], 0)
        self.assertEqual(status["chat-completion"]["total"], 2)

        # Manually deactivate model-a via pool
        pool = mesh._pools["chat-completion"]
        pool.record_failure("status.model-a", RuntimeError("e1"))
        pool.record_failure("status.model-a", RuntimeError("e2"))

        status = mesh.pool_status()
        self.assertEqual(status["chat-completion"]["active"], 1)
        self.assertEqual(status["chat-completion"]["standby"], 1)

    def test_mesh_route_before_init_raises(self):
        """route() before initialize() raises RuntimeError."""
        mesh = ModelMesh()
        req = _make_request()
        with self.assertRaises(RuntimeError):
            asyncio.run(mesh.route(req))

    def test_mesh_route_stream_before_init_raises(self):
        """route_stream() before initialize() raises RuntimeError."""
        mesh = ModelMesh()
        req = _make_request()

        async def try_stream():
            async for _ in mesh.route_stream(req):
                pass

        with self.assertRaises(RuntimeError):
            asyncio.run(try_stream())

    def test_mesh_rotate_forces_switch(self):
        """mesh.rotate() deactivates current model and returns next."""
        prov = AlwaysSucceedProvider("ok")
        config = _make_mesh_config(
            providers_dict={"rot.v1": prov},
            models_dict={
                "rot.model-a": {
                    "provider": "rot.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
                "rot.model-b": {
                    "provider": "rot.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
        )
        mesh = ModelMesh()
        mesh.initialize(config)

        new_model = mesh.rotate("chat-completion")
        self.assertEqual(new_model, "rot.model-b")

        pool = mesh._pools["chat-completion"]
        model_a = pool._models_by_id["rot.model-a"]
        self.assertEqual(model_a.status, ModelStatus.STANDBY)

    def test_mesh_shutdown_blocks_routing(self):
        """After shutdown(), route() raises RuntimeError."""
        prov = AlwaysSucceedProvider("ok")
        config = _make_mesh_config(
            providers_dict={"shut.v1": prov},
            models_dict={
                "shut.model-a": {
                    "provider": "shut.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
        )
        mesh = ModelMesh()
        mesh.initialize(config)
        mesh.shutdown()

        req = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "hello"}],
        )
        with self.assertRaises(RuntimeError):
            asyncio.run(mesh.route(req))

    def test_event_emitter_fires_on_rotation(self):
        """EventEmitter emits MODEL_ROTATED when router rotates."""
        events = []

        prov = FailNTimesProvider(fail_count=1, content="ok")
        model_a = _make_pool_model("a.m", "prov")
        model_b = _make_pool_model("b.m", "prov")
        pool = _make_pool(models=[model_a, model_b])

        emitter = EventEmitter()
        emitter.on(EventType.MODEL_ROTATED, lambda e: events.append(e))

        tree = CapabilityTree()
        tree.register("generation.text-generation.chat-completion")
        router = Router(
            {"test-pool": pool}, tree, {"prov": prov},
            event_emitter=emitter, max_retries=3,
        )

        req = _make_request()
        asyncio.run(router.route(req))
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0].type, EventType.MODEL_ROTATED)

    def test_event_emitter_fires_on_success(self):
        """EventEmitter emits REQUEST_SUCCESS on successful route."""
        events = []

        prov = AlwaysSucceedProvider("ok")
        model = _make_pool_model("a.m", "prov")
        pool = _make_pool(models=[model])

        emitter = EventEmitter()
        emitter.on(EventType.REQUEST_SUCCESS, lambda e: events.append(e))

        tree = CapabilityTree()
        tree.register("generation.text-generation.chat-completion")
        router = Router(
            {"test-pool": pool}, tree, {"prov": prov},
            event_emitter=emitter,
        )

        req = _make_request()
        asyncio.run(router.route(req))
        self.assertEqual(len(events), 1)

    def test_event_emitter_fires_on_failure(self):
        """EventEmitter emits REQUEST_FAILURE when provider fails."""
        events = []

        prov = AlwaysFailProvider("bad")
        model = _make_pool_model("a.m", "prov")
        pool = _make_pool(models=[model])

        emitter = EventEmitter()
        emitter.on(EventType.REQUEST_FAILURE, lambda e: events.append(e))

        tree = CapabilityTree()
        tree.register("generation.text-generation.chat-completion")
        router = Router(
            {"test-pool": pool}, tree, {"prov": prov},
            event_emitter=emitter, max_retries=1,
        )

        req = _make_request()
        with self.assertRaises(AllProvidersExhaustedError):
            asyncio.run(router.route(req))
        self.assertGreater(len(events), 0)

    def test_pool_exhausted_event(self):
        """POOL_EXHAUSTED event fires when no models are available."""
        events = []

        pool = _make_pool(models=[])
        emitter = EventEmitter()
        emitter.on(EventType.POOL_EXHAUSTED, lambda e: events.append(e))

        tree = CapabilityTree()
        tree.register("generation.text-generation.chat-completion")
        router = Router(
            {"test-pool": pool}, tree, {},
            event_emitter=emitter,
        )

        req = _make_request()
        with self.assertRaises(NoActiveModelError):
            asyncio.run(router.route(req))
        self.assertEqual(len(events), 1)

    def test_streaming_failover(self):
        """Stream routing falls over to next model on stream failure."""
        prov_a = AlwaysFailProvider("stream A fail")
        prov_b = AlwaysSucceedProvider("stream B ok")

        model_a = _make_pool_model("a.m", "prov-a")
        model_b = _make_pool_model("b.m", "prov-b")
        # failure_threshold=1 so model_a is deactivated after the
        # first stream failure, allowing route_stream to select model_b.
        pool = _make_pool(failure_threshold=1, models=[model_a, model_b])

        pools = {"test-pool": pool}
        providers = {"prov-a": prov_a, "prov-b": prov_b}
        router = _make_router(pools, providers, max_retries=3)

        req = CompletionRequest(
            model="test-pool",
            messages=[{"role": "user", "content": "test"}],
            stream=True,
        )

        async def collect():
            chunks = []
            async for chunk in router.route_stream(req):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(collect())
        self.assertGreater(len(chunks), 0)

    def test_streaming_all_fail_raises(self):
        """Stream routing raises AllProvidersExhaustedError when all models fail."""
        prov = AlwaysFailProvider("stream fail")
        model_a = _make_pool_model("a.m", "prov")
        model_b = _make_pool_model("b.m", "prov")
        pool = _make_pool(models=[model_a, model_b])

        pools = {"test-pool": pool}
        providers = {"prov": prov}
        router = _make_router(pools, providers, max_retries=2)

        req = CompletionRequest(
            model="test-pool",
            messages=[{"role": "user", "content": "test"}],
            stream=True,
        )

        async def try_stream():
            async for _ in router.route_stream(req):
                pass

        with self.assertRaises(AllProvidersExhaustedError):
            asyncio.run(try_stream())

    def test_three_provider_cascade_via_mesh(self):
        """Full mesh route with three different providers, A and B fail, C succeeds."""
        prov_a = AlwaysFailProvider("A down")
        prov_b = AlwaysFailProvider("B down")
        prov_c = AlwaysSucceedProvider("C is up")

        config = MeshConfig(raw={
            "providers": {
                "prov-a": {"connector": "prov-a", "instance": prov_a},
                "prov-b": {"connector": "prov-b", "instance": prov_b},
                "prov-c": {"connector": "prov-c", "instance": prov_c},
            },
            "models": {
                "a.model": {
                    "provider": "prov-a",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
                "b.model": {
                    "provider": "prov-b",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
                "c.model": {
                    "provider": "prov-c",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
            "pools": {
                "chat-completion": {
                    "capability": "generation.text-generation.chat-completion",
                    "strategy": "stick-until-failure",
                    "failure_threshold": 1,
                },
            },
            "observability": {"connector": "modelmesh.null.v1"},
        })

        mesh = ModelMesh()
        mesh.initialize(config)

        req = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "hello"}],
        )
        response = asyncio.run(mesh.route(req))
        self.assertEqual(response.choices[0].message.content, "C is up")

    def test_pool_status_current_model(self):
        """pool_status reports the current model correctly."""
        prov = AlwaysSucceedProvider("ok")
        config = _make_mesh_config(
            providers_dict={"cur.v1": prov},
            models_dict={
                "cur.model-a": {
                    "provider": "cur.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
        )
        mesh = ModelMesh()
        mesh.initialize(config)

        status = mesh.pool_status()
        self.assertEqual(
            status["chat-completion"]["current_model"], "cur.model-a"
        )

    def test_multiple_routes_count_requests(self):
        """Multiple successful routes increment total_requests on the model."""
        prov = AlwaysSucceedProvider("ok")
        model = _make_pool_model("test.m", "prov")
        pool = _make_pool(models=[model])
        pools = {"test-pool": pool}
        providers = {"prov": prov}
        router = _make_router(pools, providers)

        req = _make_request()
        for _ in range(5):
            asyncio.run(router.route(req))

        self.assertEqual(model.total_requests, 5)
        self.assertEqual(model.failure_count, 0)
        self.assertIsNotNone(model.last_success_at)

    def test_active_providers_reflects_state(self):
        """active_providers() returns only providers with active models."""
        prov = AlwaysSucceedProvider("ok")
        config = _make_mesh_config(
            providers_dict={"ap.v1": prov},
            models_dict={
                "ap.model-a": {
                    "provider": "ap.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
        )
        mesh = ModelMesh()
        mesh.initialize(config)

        active = mesh.active_providers()
        self.assertIn("ap.v1", active)

        # Deactivate the only model
        pool = mesh._pools["chat-completion"]
        model = pool._models_by_id["ap.model-a"]
        model.status = ModelStatus.STANDBY

        active_after = mesh.active_providers()
        self.assertNotIn("ap.v1", active_after)


if __name__ == "__main__":
    unittest.main()
