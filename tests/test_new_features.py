"""Tests for new features: rotation strategies, config, resilience,
LangChain adapter, and auto-discovery.

Covers features #1, #3, #5, #7, #8, #9 from the improvement roadmap.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import time
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Rotation imports ──────────────────────────────────────────────────

from modelmesh.interfaces.rotation import (
    DeactivationReason,
    ModelState,
    ModelStatus,
)
from modelmesh.interfaces.provider import CompletionRequest
from modelmesh.cdk.base_rotation import BaseRotationConfig

# ── Feature imports ───────────────────────────────────────────────────

from modelmesh.connectors.rotation.round_robin import (
    RoundRobinConfig,
    RoundRobinPolicy,
)
from modelmesh.connectors.rotation.cost_first import (
    CostFirstConfig,
    CostFirstPolicy,
)
from modelmesh.connectors.rotation.latency_first import (
    LatencyFirstConfig,
    LatencyFirstPolicy,
)
from modelmesh.connectors.rotation.priority_selection import (
    PrioritySelectionConfig,
    PrioritySelectionPolicy,
)
from modelmesh.connectors.rotation.session_stickiness import (
    SessionStickinessConfig,
    SessionStickinessPolicy,
)
from modelmesh.connectors.rotation.rate_limit_aware import (
    RateLimitAwareConfig,
    RateLimitAwarePolicy,
)
from modelmesh.connectors.rotation.load_balanced import (
    LoadBalancedConfig,
    LoadBalancedPolicy,
)
from modelmesh.config.validation import ConfigValidator, ConfigError
from modelmesh.config.templates import (
    cost_optimized,
    latency_optimized,
    high_availability,
    development,
    balanced,
)
from modelmesh.cdk.mixins.circuit_breaker import (
    CircuitBreakerMixin,
    CircuitOpenError,
    CircuitState,
)
from modelmesh.cdk.mixins.timeout import (
    TimeoutMixin,
    RequestTimeoutError,
    TimeoutConfig,
)
from modelmesh.cdk.mixins.streaming_checkpoint import (
    StreamingCheckpointMixin,
    StreamCheckpoint,
)
from modelmesh.connectors.discovery.auto_discovery import (
    AutoDiscovery,
    DiscoveredModel,
    DiscoveryConfig,
    ModelRegistry,
)
from modelmesh.integrations.langchain import (
    ChatModelMesh,
    MeshMessage,
    MeshChatResult,
    _to_openai_messages,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _make_request(model: str = "test-pool") -> CompletionRequest:
    return CompletionRequest(
        model=model,
        messages=[{"role": "user", "content": "Hello"}],
    )


def _make_state(
    model_id: str,
    status: ModelStatus = ModelStatus.ACTIVE,
    **kwargs,
) -> ModelState:
    return ModelState(model_id=model_id, status=status, **kwargs)


# ======================================================================
# Feature #1: Rotation Strategies
# ======================================================================


class TestRoundRobinPolicy(unittest.TestCase):
    """Test round-robin rotation strategy."""

    def test_connector_id(self):
        policy = RoundRobinPolicy()
        self.assertEqual(policy.CONNECTOR_ID, "modelmesh.round-robin.v1")

    def test_cycles_through_models(self):
        policy = RoundRobinPolicy()
        candidates = [
            _make_state("m1"),
            _make_state("m2"),
            _make_state("m3"),
        ]
        req = _make_request()

        selections = []
        for _ in range(6):
            selected = policy.selection.select(candidates, req)
            selections.append(selected.model_id)

        # Should cycle: m1, m2, m3, m1, m2, m3
        self.assertEqual(selections, ["m1", "m2", "m3", "m1", "m2", "m3"])

    def test_skips_standby(self):
        policy = RoundRobinPolicy()
        candidates = [
            _make_state("m1"),
            _make_state("m2", status=ModelStatus.STANDBY),
            _make_state("m3"),
        ]
        req = _make_request()

        sel1 = policy.selection.select(candidates, req)
        sel2 = policy.selection.select(candidates, req)
        sel3 = policy.selection.select(candidates, req)

        # Should only cycle through m1 and m3 (active)
        self.assertEqual(sel1.model_id, "m1")
        self.assertEqual(sel2.model_id, "m3")
        self.assertEqual(sel3.model_id, "m1")

    def test_empty_candidates(self):
        policy = RoundRobinPolicy()
        result = policy.selection.select([], _make_request())
        self.assertIsNone(result)

    def test_all_standby(self):
        policy = RoundRobinPolicy()
        candidates = [
            _make_state("m1", status=ModelStatus.STANDBY),
        ]
        result = policy.selection.select(candidates, _make_request())
        self.assertIsNone(result)


class TestCostFirstPolicy(unittest.TestCase):
    """Test cost-first rotation strategy."""

    def test_connector_id(self):
        policy = CostFirstPolicy()
        self.assertEqual(policy.CONNECTOR_ID, "modelmesh.cost-first.v1")

    def test_selects_cheapest(self):
        policy = CostFirstPolicy()
        candidates = [
            _make_state("m1", total_cost=10.0),
            _make_state("m2", total_cost=1.0),
            _make_state("m3", total_cost=5.0),
        ]
        selected = policy.selection.select(candidates, _make_request())
        self.assertEqual(selected.model_id, "m2")

    def test_budget_deactivation(self):
        config = CostFirstConfig(budget_limit=10.0)
        policy = CostFirstPolicy(config)
        state = _make_state("m1", total_cost=11.0)
        reason = policy.deactivation.get_reason(state)
        self.assertEqual(reason, DeactivationReason.BUDGET_EXCEEDED)


class TestLatencyFirstPolicy(unittest.TestCase):
    """Test latency-first rotation strategy."""

    def test_connector_id(self):
        policy = LatencyFirstPolicy()
        self.assertEqual(policy.CONNECTOR_ID, "modelmesh.latency-first.v1")

    def test_latency_tracking(self):
        policy = LatencyFirstPolicy()
        policy.record_latency("m1", 100.0)
        policy.record_latency("m1", 200.0)
        policy.record_latency("m2", 50.0)

        candidates = [_make_state("m1"), _make_state("m2")]
        selected = policy.selection.select(candidates, _make_request())
        # m2 has lower latency (50ms avg) so should score higher
        self.assertEqual(selected.model_id, "m2")


class TestPrioritySelectionPolicy(unittest.TestCase):
    """Test priority-selection rotation strategy."""

    def test_connector_id(self):
        policy = PrioritySelectionPolicy()
        self.assertEqual(
            policy.CONNECTOR_ID, "modelmesh.priority-selection.v1"
        )

    def test_priority_ordering(self):
        config = PrioritySelectionConfig(
            model_priority=["m2", "m1", "m3"]
        )
        policy = PrioritySelectionPolicy(config)
        candidates = [
            _make_state("m1"),
            _make_state("m2"),
            _make_state("m3"),
        ]
        selected = policy.selection.select(candidates, _make_request())
        self.assertEqual(selected.model_id, "m2")

    def test_fallback_when_priority_unavailable(self):
        config = PrioritySelectionConfig(model_priority=["m4"])
        policy = PrioritySelectionPolicy(config)
        candidates = [
            _make_state("m1", error_rate=0.1),
            _make_state("m2", error_rate=0.5),
        ]
        selected = policy.selection.select(candidates, _make_request())
        # Falls back to lowest error rate
        self.assertEqual(selected.model_id, "m1")


class TestSessionStickinessPolicy(unittest.TestCase):
    """Test session-stickiness rotation strategy."""

    def test_connector_id(self):
        policy = SessionStickinessPolicy()
        self.assertEqual(
            policy.CONNECTOR_ID, "modelmesh.session-stickiness.v1"
        )

    def test_consistent_session_binding(self):
        policy = SessionStickinessPolicy()
        candidates = [
            _make_state("m1"),
            _make_state("m2"),
            _make_state("m3"),
        ]
        req = CompletionRequest(
            model="test",
            messages=[{"role": "user", "content": "Hi", "session_id": "abc123"}],
        )
        # Same session should always map to the same model
        selections = set()
        for _ in range(10):
            selected = policy.selection.select(candidates, req)
            selections.add(selected.model_id)
        self.assertEqual(len(selections), 1)

    def test_different_sessions_may_differ(self):
        policy = SessionStickinessPolicy()
        candidates = [
            _make_state(f"m{i}") for i in range(10)
        ]
        # Different sessions may map to different models
        models = set()
        for i in range(20):
            req = CompletionRequest(
                model="test",
                messages=[
                    {"role": "user", "content": "Hi", "session_id": f"session-{i}"}
                ],
            )
            selected = policy.selection.select(candidates, req)
            models.add(selected.model_id)
        # With 10 candidates and 20 sessions, should hit at least 2 models
        self.assertGreater(len(models), 1)

    def test_no_session_fallback(self):
        policy = SessionStickinessPolicy()
        candidates = [
            _make_state("m1", error_rate=0.1),
            _make_state("m2", error_rate=0.5),
        ]
        req = CompletionRequest(
            model="test",
            messages=[{"role": "user", "content": "Hi"}],
        )
        selected = policy.selection.select(candidates, req)
        # Should fall back to scoring (lowest error rate)
        self.assertEqual(selected.model_id, "m1")


class TestRateLimitAwarePolicy(unittest.TestCase):
    """Test rate-limit-aware rotation strategy."""

    def test_connector_id(self):
        policy = RateLimitAwarePolicy()
        self.assertEqual(
            policy.CONNECTOR_ID, "modelmesh.rate-limit-aware.v1"
        )

    def test_prefers_most_headroom(self):
        config = RateLimitAwareConfig(
            model_request_limits={"m1": 100, "m2": 100}
        )
        policy = RateLimitAwarePolicy(config)
        candidates = [
            _make_state("m1", total_requests=80),  # 20% headroom
            _make_state("m2", total_requests=20),  # 80% headroom
        ]
        selected = policy.selection.select(candidates, _make_request())
        self.assertEqual(selected.model_id, "m2")

    def test_quota_deactivation(self):
        config = RateLimitAwareConfig(
            model_request_limits={"m1": 100}
        )
        policy = RateLimitAwarePolicy(config)
        state = _make_state("m1", total_requests=100)
        reason = policy.deactivation.get_reason(state)
        self.assertEqual(reason, DeactivationReason.QUOTA_EXHAUSTED)

    def test_no_limits_neutral_score(self):
        config = RateLimitAwareConfig()
        policy = RateLimitAwarePolicy(config)
        state = _make_state("m1", total_requests=1000)
        score = policy.selection.score(state, _make_request())
        self.assertEqual(score, 100.0)  # Full headroom * 100


class TestLoadBalancedPolicy(unittest.TestCase):
    """Test load-balanced rotation strategy."""

    def test_connector_id(self):
        policy = LoadBalancedPolicy()
        self.assertEqual(policy.CONNECTOR_ID, "modelmesh.load-balanced.v1")

    def test_distributes_by_weight(self):
        config = LoadBalancedConfig(
            model_weights={"m1": 3.0, "m2": 1.0}
        )
        policy = LoadBalancedPolicy(config)
        candidates = [
            _make_state("m1", total_requests=0),
            _make_state("m2", total_requests=0),
        ]
        req = _make_request()

        # First selection should go to m1 (higher weight)
        selected = policy.selection.select(candidates, req)
        self.assertIsNotNone(selected)

    def test_empty_candidates(self):
        policy = LoadBalancedPolicy()
        result = policy.selection.select([], _make_request())
        self.assertIsNone(result)


# ======================================================================
# Feature #5: Config Validation + Hot Reload + Templates
# ======================================================================


class TestConfigValidator(unittest.TestCase):
    """Test configuration validation."""

    def test_valid_config(self):
        config = {
            "providers": {
                "openai": {"connector": "openai.llm.v1"},
            },
            "models": {
                "gpt-4o": {"provider": "openai"},
            },
            "pools": {
                "text-gen": {"models": ["gpt-4o"]},
            },
        }
        validator = ConfigValidator()
        errors = validator.validate(config)
        self.assertEqual(errors, [])

    def test_unknown_top_level_key(self):
        config = {"unknown_key": "value"}
        validator = ConfigValidator()
        errors = validator.validate(config)
        self.assertTrue(any("Unknown top-level key" in e for e in errors))

    def test_invalid_providers_type(self):
        config = {"providers": "not_a_dict"}
        validator = ConfigValidator()
        errors = validator.validate(config)
        self.assertTrue(any("must be a mapping" in e for e in errors))

    def test_missing_connector_or_instance(self):
        config = {
            "providers": {"my_prov": {"api_key": "xyz"}},
        }
        validator = ConfigValidator()
        errors = validator.validate(config)
        self.assertTrue(
            any("connector" in e and "instance" in e for e in errors)
        )

    def test_model_references_unknown_provider(self):
        config = {
            "providers": {"openai": {"connector": "openai.llm.v1"}},
            "models": {"gpt-4o": {"provider": "nonexistent"}},
        }
        validator = ConfigValidator()
        errors = validator.validate(config)
        self.assertTrue(any("unknown provider" in e for e in errors))

    def test_pool_references_unknown_model(self):
        config = {
            "models": {"gpt-4o": {"provider": "openai"}},
            "pools": {"text-gen": {"models": ["nonexistent"]}},
        }
        validator = ConfigValidator()
        errors = validator.validate(config)
        self.assertTrue(any("unknown model" in e for e in errors))

    def test_negative_budget_limit(self):
        config = {"budget": {"daily_limit": -5.0}}
        validator = ConfigValidator()
        errors = validator.validate(config)
        self.assertTrue(any("daily_limit" in e for e in errors))

    def test_invalid_failure_threshold(self):
        config = {
            "pools": {"text-gen": {"failure_threshold": 0}},
        }
        validator = ConfigValidator()
        errors = validator.validate(config)
        self.assertTrue(any("failure_threshold" in e for e in errors))

    def test_validate_strict_raises(self):
        config = {"unknown": "key"}
        validator = ConfigValidator()
        with self.assertRaises(ConfigError) as ctx:
            validator.validate_strict(config)
        self.assertTrue(len(ctx.exception.errors) > 0)


class TestConfigTemplates(unittest.TestCase):
    """Test pre-built configuration templates."""

    def test_cost_optimized_has_required_sections(self):
        config = cost_optimized()
        self.assertIn("providers", config)
        self.assertIn("models", config)
        self.assertIn("pools", config)
        self.assertIn("budget", config)

    def test_latency_optimized(self):
        config = latency_optimized()
        pool = config["pools"]["text-generation"]
        self.assertEqual(pool["strategy"], "modelmesh.latency-first.v1")

    def test_high_availability(self):
        config = high_availability()
        self.assertGreaterEqual(len(config["providers"]), 3)
        pool = config["pools"]["text-generation"]
        self.assertEqual(pool["strategy"], "modelmesh.stick-until-failure.v1")

    def test_development(self):
        config = development()
        self.assertIn("observability", config)

    def test_balanced(self):
        config = balanced()
        pool = config["pools"]["text-generation"]
        self.assertEqual(pool["strategy"], "modelmesh.load-balanced.v1")

    def test_all_templates_pass_validation(self):
        validator = ConfigValidator()
        for template_fn in [
            cost_optimized,
            latency_optimized,
            high_availability,
            development,
            balanced,
        ]:
            config = template_fn()
            errors = validator.validate(config)
            self.assertEqual(
                errors, [],
                f"Template {template_fn.__name__} failed: {errors}",
            )


class TestConfigHotReload(unittest.TestCase):
    """Test configuration hot-reload functionality."""

    def test_reconfigure_validates(self):
        from modelmesh.config.hot_reload import reconfigure
        from modelmesh.config.mesh_config import MeshConfig
        from modelmesh.core.mesh import ModelMesh

        mesh = ModelMesh()
        mesh.initialize(MeshConfig.from_dict({"providers": {}, "models": {}, "pools": {}}))

        # Try reloading with invalid config
        bad_config = MeshConfig.from_dict({"budget": {"daily_limit": -1}})
        errors = reconfigure(mesh, bad_config)
        self.assertTrue(len(errors) > 0)

    def test_reconfigure_success(self):
        from modelmesh.config.hot_reload import reconfigure
        from modelmesh.config.mesh_config import MeshConfig
        from modelmesh.core.mesh import ModelMesh

        mesh = ModelMesh()
        mesh.initialize(MeshConfig.from_dict({"providers": {}, "models": {}, "pools": {}}))

        good_config = MeshConfig.from_dict(
            {"providers": {}, "models": {}, "pools": {}}
        )
        errors = reconfigure(mesh, good_config)
        self.assertEqual(errors, [])

    def test_config_watcher_lifecycle(self):
        from modelmesh.config.hot_reload import ConfigWatcher
        from modelmesh.core.mesh import ModelMesh
        from modelmesh.config.mesh_config import MeshConfig

        mesh = ModelMesh()
        mesh.initialize(MeshConfig.from_dict({"providers": {}, "models": {}, "pools": {}}))

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("providers: {}\nmodels: {}\npools: {}\n")
            path = f.name

        try:
            watcher = ConfigWatcher(path, mesh, interval=0.1)
            watcher.start()
            self.assertTrue(watcher.is_running)
            time.sleep(0.2)
            watcher.stop()
            self.assertFalse(watcher.is_running)
        finally:
            os.unlink(path)


# ======================================================================
# Feature #7: Resilience Patterns
# ======================================================================


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker mixin."""

    def _make_breaker(self, **kwargs):
        class Breakable(CircuitBreakerMixin):
            pass

        obj = Breakable()
        obj.configure_circuit_breaker(**kwargs)
        return obj

    def test_starts_closed(self):
        cb = self._make_breaker()
        self.assertEqual(cb.circuit_state, CircuitState.CLOSED)

    def test_opens_after_failures(self):
        cb = self._make_breaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.circuit_state, CircuitState.CLOSED)
        cb.record_failure()
        self.assertEqual(cb.circuit_state, CircuitState.OPEN)

    def test_open_rejects_requests(self):
        cb = self._make_breaker(failure_threshold=1, reset_timeout=10.0)
        cb.record_failure()
        with self.assertRaises(CircuitOpenError) as ctx:
            cb.check_circuit()
        self.assertGreater(ctx.exception.remaining, 0)

    def test_transitions_to_half_open(self):
        cb = self._make_breaker(failure_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        self.assertEqual(cb.circuit_state, CircuitState.OPEN)
        time.sleep(0.02)
        self.assertEqual(cb.circuit_state, CircuitState.HALF_OPEN)

    def test_half_open_success_closes(self):
        cb = self._make_breaker(failure_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.check_circuit()  # Allowed in half-open
        cb.record_success()
        self.assertEqual(cb.circuit_state, CircuitState.CLOSED)

    def test_half_open_failure_reopens(self):
        cb = self._make_breaker(failure_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.check_circuit()
        cb.record_failure()
        self.assertEqual(cb.circuit_state, CircuitState.OPEN)

    def test_success_resets_failure_count(self):
        cb = self._make_breaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        # Only 1 failure after reset, should still be closed
        self.assertEqual(cb.circuit_state, CircuitState.CLOSED)

    def test_manual_reset(self):
        cb = self._make_breaker(failure_threshold=1, reset_timeout=999)
        cb.record_failure()
        self.assertEqual(cb.circuit_state, CircuitState.OPEN)
        cb.reset_circuit()
        self.assertEqual(cb.circuit_state, CircuitState.CLOSED)

    def test_stats(self):
        cb = self._make_breaker(failure_threshold=3)
        cb.record_failure()
        stats = cb.circuit_breaker_stats()
        self.assertEqual(stats["state"], "closed")
        self.assertEqual(stats["failure_count"], 1)


class TestTimeout(unittest.TestCase):
    """Test timeout mixin."""

    def _make_timeout(self, **kwargs):
        class Timeoutable(TimeoutMixin):
            pass

        obj = Timeoutable()
        obj.configure_timeout(**kwargs)
        return obj

    def test_default_config(self):
        t = self._make_timeout()
        self.assertEqual(t.timeout_config.default, 30.0)
        self.assertEqual(t.timeout_config.streaming, 60.0)

    def test_custom_config(self):
        t = self._make_timeout(default=5.0, streaming=10.0)
        self.assertEqual(t.timeout_config.default, 5.0)
        self.assertEqual(t.timeout_config.streaming, 10.0)

    def test_with_timeout_success(self):
        t = self._make_timeout(default=1.0)

        async def fast():
            return 42

        result = asyncio.run(
            t.with_timeout(fast())
        )
        self.assertEqual(result, 42)

    def test_with_timeout_fires(self):
        t = self._make_timeout(default=0.01)

        async def slow():
            await asyncio.sleep(1.0)

        with self.assertRaises(RequestTimeoutError) as ctx:
            asyncio.run(
                t.with_timeout(slow())
            )
        self.assertEqual(ctx.exception.timeout, 0.01)

    def test_timeout_zero_disables(self):
        t = self._make_timeout(default=0)

        async def fast():
            return "ok"

        result = asyncio.run(
            t.with_timeout(fast())
        )
        self.assertEqual(result, "ok")


class TestStreamingCheckpoint(unittest.TestCase):
    """Test streaming checkpoint mixin."""

    def _make_mixin(self, **kwargs):
        class Checkpointable(StreamingCheckpointMixin):
            pass

        obj = Checkpointable()
        if kwargs:
            obj.configure_checkpoints(**kwargs)
        return obj

    def test_create_and_get(self):
        m = self._make_mixin()
        cp = m.create_checkpoint("req-1", "gpt-4o")
        self.assertEqual(cp.request_id, "req-1")
        self.assertEqual(cp.model_id, "gpt-4o")
        self.assertFalse(cp.is_complete)

        retrieved = m.get_checkpoint("req-1")
        self.assertIs(cp, retrieved)

    def test_record_and_finalize(self):
        m = self._make_mixin()
        cp = m.create_checkpoint("req-1")
        cp.record("Hello ", token_count=1)
        cp.record("world!", token_count=1)
        self.assertEqual(cp.tokens_received, 2)
        self.assertEqual(cp.content_buffer, "Hello world!")

        cp.finalize("stop")
        self.assertTrue(cp.is_complete)
        self.assertEqual(cp.finish_reason, "stop")

    def test_to_dict(self):
        m = self._make_mixin()
        cp = m.create_checkpoint("req-1", "model-a")
        cp.record("test", token_count=5)
        d = cp.to_dict()
        self.assertEqual(d["request_id"], "req-1")
        self.assertEqual(d["tokens_received"], 5)
        self.assertEqual(d["content_length"], 4)

    def test_active_checkpoints(self):
        m = self._make_mixin()
        cp1 = m.create_checkpoint("req-1")
        cp2 = m.create_checkpoint("req-2")
        cp1.finalize()
        active = m.active_checkpoints()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].request_id, "req-2")

    def test_stats(self):
        m = self._make_mixin()
        m.create_checkpoint("req-1")
        m.create_checkpoint("req-2")
        stats = m.checkpoint_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["active"], 2)

    def test_eviction(self):
        m = self._make_mixin(max_checkpoints=3)
        for i in range(5):
            cp = m.create_checkpoint(f"req-{i}")
            if i < 3:
                cp.finalize()
        # Should have evicted some completed checkpoints
        stats = m.checkpoint_stats()
        self.assertLessEqual(stats["total"], 5)


# ======================================================================
# Feature #8: LangChain Adapter
# ======================================================================


class TestMessageConversion(unittest.TestCase):
    """Test message format conversion."""

    def test_dict_passthrough(self):
        msgs = [{"role": "user", "content": "Hi"}]
        result = _to_openai_messages(msgs)
        self.assertEqual(result, msgs)

    def test_mesh_message(self):
        msgs = [MeshMessage(content="Hello", role="user")]
        result = _to_openai_messages(msgs)
        self.assertEqual(result, [{"role": "user", "content": "Hello"}])

    def test_string_input(self):
        msgs = ["What is Python?"]
        result = _to_openai_messages(msgs)
        self.assertEqual(
            result, [{"role": "user", "content": "What is Python?"}]
        )

    def test_langchain_duck_type(self):
        # Simulate a LangChain BaseMessage
        msg = MagicMock()
        msg.content = "test"
        msg.type = "human"
        result = _to_openai_messages([msg])
        self.assertEqual(result, [{"role": "user", "content": "test"}])


class TestChatModelMesh(unittest.TestCase):
    """Test LangChain ChatModelMesh adapter."""

    def test_repr(self):
        mesh = MagicMock()
        llm = ChatModelMesh(mesh=mesh, model="text-gen", temperature=0.7)
        self.assertIn("text-gen", repr(llm))

    def test_bind_returns_new_instance(self):
        mesh = MagicMock()
        llm = ChatModelMesh(mesh=mesh, model="text-gen")
        bound = llm.bind(model="other-pool", temperature=0.5)
        self.assertEqual(bound._model, "other-pool")
        self.assertEqual(bound._temperature, 0.5)
        self.assertEqual(llm._model, "text-gen")  # Original unchanged

    def test_with_config_alias(self):
        mesh = MagicMock()
        llm = ChatModelMesh(mesh=mesh)
        bound = llm.with_config(model="custom")
        self.assertEqual(bound._model, "custom")

    def test_identifying_params(self):
        mesh = MagicMock()
        llm = ChatModelMesh(mesh=mesh, model="pool1", temperature=0.5)
        params = llm._identifying_params
        self.assertEqual(params["model"], "pool1")
        self.assertEqual(params["temperature"], 0.5)


class TestChatModelMeshAsync(unittest.TestCase):
    """Test async invocation of ChatModelMesh."""

    def test_ainvoke(self):
        from modelmesh.interfaces.provider import (
            CompletionResponse,
            CompletionChoice,
            ChatMessage,
            TokenUsage,
        )

        mock_response = CompletionResponse(
            id="test-id",
            model="gpt-4o",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hi there!"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(
                prompt_tokens=5, completion_tokens=3, total_tokens=8
            ),
        )

        mesh = MagicMock()
        mesh.route = AsyncMock(return_value=mock_response)
        llm = ChatModelMesh(mesh=mesh, model="text-gen")

        result = asyncio.run(
            llm.ainvoke("Hello!")
        )
        self.assertEqual(result.content, "Hi there!")
        self.assertEqual(result.role, "assistant")
        self.assertEqual(
            result.additional_kwargs["usage"]["total_tokens"], 8
        )


# ======================================================================
# Feature #9: Provider Auto-Discovery
# ======================================================================


class TestModelRegistry(unittest.TestCase):
    """Test the in-memory model registry."""

    def test_register_and_get(self):
        reg = ModelRegistry()
        model = DiscoveredModel(
            id="gpt-4o", provider="openai.llm.v1", name="GPT-4o"
        )
        reg.register(model)
        self.assertEqual(len(reg), 1)
        self.assertEqual(reg.get("gpt-4o").name, "GPT-4o")

    def test_by_provider(self):
        reg = ModelRegistry()
        reg.register(DiscoveredModel(id="m1", provider="openai.llm.v1"))
        reg.register(DiscoveredModel(id="m2", provider="anthropic.claude.v1"))
        reg.register(DiscoveredModel(id="m3", provider="openai.llm.v1"))
        results = reg.by_provider("openai.llm.v1")
        self.assertEqual(len(results), 2)

    def test_by_capability(self):
        reg = ModelRegistry()
        reg.register(
            DiscoveredModel(
                id="m1",
                provider="p1",
                capabilities=["generation.text-generation.chat-completion"],
            )
        )
        reg.register(
            DiscoveredModel(
                id="m2", provider="p2", capabilities=["generation.image"]
            )
        )
        results = reg.by_capability("generation.text-generation")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "m1")

    def test_cheapest(self):
        reg = ModelRegistry()
        reg.register(
            DiscoveredModel(id="m1", provider="p1", pricing_input=10.0)
        )
        reg.register(
            DiscoveredModel(id="m2", provider="p2", pricing_input=1.0)
        )
        reg.register(
            DiscoveredModel(id="m3", provider="p3", pricing_input=5.0)
        )
        cheapest = reg.cheapest(2)
        self.assertEqual(cheapest[0].id, "m2")
        self.assertEqual(cheapest[1].id, "m3")

    def test_to_config(self):
        reg = ModelRegistry()
        reg.register(
            DiscoveredModel(
                id="gpt-4o",
                provider="openai.llm.v1",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=128000,
            )
        )
        config = reg.to_config()
        self.assertIn("gpt-4o", config)
        self.assertEqual(config["gpt-4o"]["provider"], "openai.llm.v1")

    def test_clear(self):
        reg = ModelRegistry()
        reg.register(DiscoveredModel(id="m1", provider="p1"))
        reg.clear()
        self.assertEqual(len(reg), 0)


class TestAutoDiscovery(unittest.TestCase):
    """Test auto-discovery connector."""

    def test_connector_id(self):
        discovery = AutoDiscovery()
        self.assertEqual(
            discovery.CONNECTOR_ID, "modelmesh.auto-discovery.v1"
        )

    def test_discover_with_explicit_providers(self):
        config = DiscoveryConfig(providers=["openai", "anthropic"])
        discovery = AutoDiscovery(config)
        models = discovery.discover()
        self.assertGreater(len(models), 0)
        providers = {m.provider for m in models}
        self.assertIn("openai.llm.v1", providers)
        self.assertIn("anthropic.claude.v1", providers)

    def test_discover_caching(self):
        config = DiscoveryConfig(providers=["openai"], cache_ttl=100)
        discovery = AutoDiscovery(config)
        models1 = discovery.discover()
        models2 = discovery.discover()  # Should use cache
        self.assertEqual(len(models1), len(models2))

    def test_discover_force_refresh(self):
        config = DiscoveryConfig(providers=["openai"], cache_ttl=100)
        discovery = AutoDiscovery(config)
        discovery.discover()
        models = discovery.discover(force=True)
        self.assertGreater(len(models), 0)

    def test_include_patterns(self):
        config = DiscoveryConfig(
            providers=["openai"],
            include_patterns=["gpt-4o-mini"],
        )
        discovery = AutoDiscovery(config)
        models = discovery.discover()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "gpt-4o-mini")

    def test_exclude_patterns(self):
        config = DiscoveryConfig(
            providers=["openai"],
            exclude_patterns=["gpt-4o-mini"],
        )
        discovery = AutoDiscovery(config)
        models = discovery.discover()
        ids = [m.id for m in models]
        self.assertNotIn("gpt-4o-mini", ids)

    def test_generate_config(self):
        config = DiscoveryConfig(providers=["openai"])
        discovery = AutoDiscovery(config)
        generated = discovery.generate_config()
        self.assertIn("providers", generated)
        self.assertIn("models", generated)
        self.assertIn("pools", generated)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False)
    def test_detect_providers_from_env(self):
        discovery = AutoDiscovery()
        detected = discovery.detect_providers()
        self.assertIn("openai", detected)

    def test_discovered_model_to_config(self):
        model = DiscoveredModel(
            id="gpt-4o",
            provider="openai.llm.v1",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=128000,
            max_output_tokens=16384,
        )
        entry = model.to_config_entry()
        self.assertEqual(entry["provider"], "openai.llm.v1")
        self.assertIn("capabilities", entry)
        self.assertIn("constraints", entry)
        self.assertEqual(entry["constraints"]["context_window"], 128000)


# ======================================================================
# Feature #3: Prometheus connector (import test)
# ======================================================================


class TestPrometheusConnectorImport(unittest.TestCase):
    """Test that the Prometheus connector imports and registers."""

    def test_import(self):
        from modelmesh.connectors.observability.prometheus_connector import (
            PrometheusConnector,
        )
        self.assertEqual(
            PrometheusConnector.CONNECTOR_ID, "modelmesh.prometheus.v1"
        )

    def test_registry(self):
        from modelmesh.connectors import CONNECTOR_REGISTRY
        self.assertIn("modelmesh.prometheus.v1", CONNECTOR_REGISTRY)


# ======================================================================
# Registry completeness
# ======================================================================


class TestConnectorRegistryCompleteness(unittest.TestCase):
    """Verify all new connectors are registered."""

    def test_all_rotation_strategies_registered(self):
        from modelmesh.connectors import CONNECTOR_REGISTRY

        expected = [
            "modelmesh.stick-until-failure.v1",
            "modelmesh.cost-first.v1",
            "modelmesh.latency-first.v1",
            "modelmesh.round-robin.v1",
            "modelmesh.priority-selection.v1",
            "modelmesh.session-stickiness.v1",
            "modelmesh.rate-limit-aware.v1",
            "modelmesh.load-balanced.v1",
        ]
        for cid in expected:
            self.assertIn(
                cid, CONNECTOR_REGISTRY,
                f"Missing connector: {cid}",
            )

    def test_prometheus_registered(self):
        from modelmesh.connectors import CONNECTOR_REGISTRY
        self.assertIn("modelmesh.prometheus.v1", CONNECTOR_REGISTRY)

    def test_auto_discovery_registered(self):
        from modelmesh.connectors import CONNECTOR_REGISTRY
        self.assertIn("modelmesh.auto-discovery.v1", CONNECTOR_REGISTRY)


if __name__ == "__main__":
    unittest.main()
