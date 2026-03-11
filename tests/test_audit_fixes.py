"""Tests for audit-identified blind spots and gaps.

Covers:
1. CacheMixin thread safety and TTL expiration
2. RateLimiterMixin thread safety
3. CostTracker / BudgetConfig (budget.py)
4. PrometheusConnector functional tests
5. TimeoutMixin streaming timeout
6. StreamingCheckpointMixin edge cases
7. CircuitBreaker advanced scenarios
8. SqliteStorage async wrapping
9. AutoDiscovery caching and registry queries
10. Rotation strategy edge cases
11. Export completeness checks
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from modelmesh.exceptions import BudgetExceededError

# ═══════════════════════════════════════════════════════════════════════
# 1. CacheMixin -- thread safety and TTL expiration
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.cdk.mixins.cache import CacheMixin, CacheStats


class _CacheUser(CacheMixin):
    def __init__(self, ttl_ms=60_000, max_entries=1024):
        self._init_cache(ttl_ms=ttl_ms, max_entries=max_entries)


class TestCacheMixinThreadSafety:
    """Thread safety and TTL tests for CacheMixin."""

    def test_ttl_expiration(self):
        """Entries expire after TTL elapses."""
        cache = _CacheUser(ttl_ms=50)  # 50ms TTL
        cache._cache_set("key", "value")
        assert cache._cache_get("key") == "value"

        time.sleep(0.1)  # wait for TTL to elapse
        assert cache._cache_get("key") is None

        stats = cache._cache_stats()
        assert stats.hits == 1
        assert stats.misses == 1

    def test_ttl_not_expired(self):
        """Entries are returned when TTL hasn't elapsed."""
        cache = _CacheUser(ttl_ms=5_000)
        cache._cache_set("key", "value")
        assert cache._cache_get("key") == "value"

    def test_lru_eviction_order(self):
        """LRU eviction removes least recently accessed entry."""
        cache = _CacheUser(ttl_ms=60_000, max_entries=3)
        cache._cache_set("a", 1)
        cache._cache_set("b", 2)
        cache._cache_set("c", 3)

        # Access 'a' to make it recently used
        cache._cache_get("a")

        # Adding 'd' should evict 'b' (least recently accessed)
        cache._cache_set("d", 4)
        assert cache._cache_get("a") is not None
        assert cache._cache_get("b") is None  # evicted
        assert cache._cache_get("d") is not None

    def test_concurrent_access(self):
        """Concurrent reads and writes don't corrupt cache."""
        cache = _CacheUser(ttl_ms=60_000, max_entries=100)
        errors = []

        def writer(start, count):
            try:
                for i in range(count):
                    cache._cache_set(f"key_{start + i}", i)
            except Exception as e:
                errors.append(e)

        def reader(count):
            try:
                for i in range(count):
                    cache._cache_get(f"key_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0, 50)),
            threading.Thread(target=writer, args=(50, 50)),
            threading.Thread(target=reader, args=(100,)),
            threading.Thread(target=reader, args=(100,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent access errors: {errors}"
        stats = cache._cache_stats()
        assert stats.size <= 100

    def test_invalidate(self):
        """Invalidating a key removes it."""
        cache = _CacheUser()
        cache._cache_set("key", "value")
        assert cache._cache_get("key") == "value"
        cache._cache_invalidate("key")
        assert cache._cache_get("key") is None

    def test_invalidate_nonexistent(self):
        """Invalidating nonexistent key is a no-op."""
        cache = _CacheUser()
        cache._cache_invalidate("nonexistent")  # should not raise

    def test_clear_resets_all(self):
        """Clear removes all entries and resets stats."""
        cache = _CacheUser()
        cache._cache_set("a", 1)
        cache._cache_set("b", 2)
        cache._cache_get("a")
        cache._cache_get("missing")
        cache._cache_clear()

        stats = cache._cache_stats()
        assert stats.size == 0
        assert stats.hits == 0
        assert stats.misses == 0

    def test_has_lock_attribute(self):
        """Cache must have a threading lock for thread safety."""
        cache = _CacheUser()
        assert hasattr(cache, "_cache_lock")
        assert isinstance(cache._cache_lock, type(threading.Lock()))


# ═══════════════════════════════════════════════════════════════════════
# 2. RateLimiterMixin -- thread safety
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.cdk.mixins.rate_limiter import RateLimiterMixin


class _RateLimitedService(RateLimiterMixin):
    _rate_limit_rpm = 60
    _rate_limit_tpm = 100_000
    _rate_limit_min_delay = 0

    def __init__(self):
        self.__init_rate_limiter__()


class TestRateLimiterThreadSafety:
    """Thread safety tests for RateLimiterMixin."""

    def test_has_lock(self):
        """Rate limiter must have a threading lock."""
        svc = _RateLimitedService()
        assert hasattr(svc, "_rate_limit_lock")

    def test_record_tokens(self):
        """Recording tokens appends to window."""
        svc = _RateLimitedService()
        svc._rate_limit_record_tokens(100)
        svc._rate_limit_record_tokens(200)
        assert len(svc._token_counts) == 2

    def test_concurrent_record_tokens(self):
        """Concurrent token recordings don't corrupt state."""
        svc = _RateLimitedService()
        errors = []

        def record(count):
            try:
                for i in range(count):
                    svc._rate_limit_record_tokens(10)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record, args=(50,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(svc._token_counts) == 200


# ═══════════════════════════════════════════════════════════════════════
# 3. CostTracker / budget.py
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.core.budget import BudgetConfig, BudgetStatus, CostTracker
from modelmesh.interfaces.provider import ModelPricing, TokenUsage


class TestCostTracker:
    """Tests for CostTracker budget management."""

    def _usage(self, prompt=100, completion=50):
        return TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        )

    def _pricing(self, input_1k=0.01, output_1k=0.03):
        return ModelPricing(
            input_per_1k_tokens=input_1k,
            output_per_1k_tokens=output_1k,
        )

    def test_calculate_cost(self):
        """Cost calculation uses per-1k-token pricing."""
        usage = self._usage(1000, 500)
        pricing = self._pricing(0.01, 0.03)
        cost = CostTracker.calculate_cost(usage, pricing)
        # 1000/1000 * 0.01 + 500/1000 * 0.03 = 0.01 + 0.015 = 0.025
        assert abs(cost - 0.025) < 1e-6

    def test_record_and_get_daily(self):
        """Recording costs updates daily totals."""
        tracker = CostTracker()
        cost = tracker.record("gpt-4o", "openai", self._usage(), self._pricing())
        assert cost > 0
        assert tracker.get_daily_cost() == cost

    def test_record_and_get_monthly(self):
        """Recording costs updates monthly totals."""
        tracker = CostTracker()
        tracker.record("gpt-4o", "openai", self._usage(), self._pricing())
        assert tracker.get_monthly_cost() > 0

    def test_model_cost_tracking(self):
        """Per-model cost tracking works."""
        tracker = CostTracker()
        tracker.record("gpt-4o", "openai", self._usage(), self._pricing())
        tracker.record("claude", "anthropic", self._usage(), self._pricing())
        assert tracker.get_model_cost("gpt-4o") > 0
        assert tracker.get_model_cost("claude") > 0
        assert tracker.get_model_cost("nonexistent") == 0.0

    def test_provider_cost_tracking(self):
        """Per-provider cost tracking works."""
        tracker = CostTracker()
        tracker.record("gpt-4o", "openai", self._usage(), self._pricing())
        assert tracker.get_provider_cost("openai") > 0
        assert tracker.get_provider_cost("anthropic") == 0.0

    def test_budget_not_exceeded_no_limits(self):
        """No limits means never exceeded."""
        tracker = CostTracker()
        tracker.record("gpt-4o", "openai", self._usage(), self._pricing())
        status = tracker.check_budget()
        assert not status.exceeded
        assert not status.alert

    def test_daily_limit_exceeded(self):
        """Daily limit triggers exceeded flag."""
        tracker = CostTracker(BudgetConfig(daily_limit=0.001))
        tracker.record("gpt-4o", "openai", self._usage(1000, 1000), self._pricing())
        status = tracker.check_budget()
        assert status.exceeded
        assert status.daily_remaining == 0.0

    def test_monthly_limit_exceeded(self):
        """Monthly limit triggers exceeded flag."""
        tracker = CostTracker(BudgetConfig(monthly_limit=0.001))
        tracker.record("gpt-4o", "openai", self._usage(1000, 1000), self._pricing())
        status = tracker.check_budget()
        assert status.exceeded

    def test_per_request_limit_raises(self):
        """Per-request limit raises ValueError when exceeded."""
        tracker = CostTracker(BudgetConfig(per_request_limit=0.001))
        with pytest.raises(BudgetExceededError, match="exceeds per-request limit"):
            tracker.record("gpt-4o", "openai", self._usage(10000, 10000), self._pricing())

    def test_per_request_limit_no_enforce(self):
        """Per-request limit with enforce=False doesn't raise."""
        tracker = CostTracker(BudgetConfig(per_request_limit=0.001, enforce=False))
        cost = tracker.record("gpt-4o", "openai", self._usage(10000, 10000), self._pricing())
        assert cost > 0.001

    def test_alert_threshold(self):
        """Alert is raised when usage crosses threshold."""
        tracker = CostTracker(BudgetConfig(daily_limit=0.1, alert_threshold=0.5))
        # Record enough to cross 50% of 0.1
        tracker.record("gpt-4o", "openai", self._usage(5000, 5000), self._pricing(0.01, 0.03))
        status = tracker.check_budget()
        assert status.alert

    def test_summary(self):
        """Summary returns complete breakdown."""
        tracker = CostTracker()
        tracker.record("gpt-4o", "openai", self._usage(), self._pricing())
        summary = tracker.summary()
        assert "daily_cost" in summary
        assert "monthly_cost" in summary
        assert "total_cost" in summary
        assert "by_model" in summary
        assert "by_provider" in summary
        assert "record_count" in summary
        assert summary["record_count"] == 1

    def test_reset_daily(self):
        """reset_daily clears today's records."""
        tracker = CostTracker()
        tracker.record("gpt-4o", "openai", self._usage(), self._pricing())
        assert tracker.get_daily_cost() > 0
        tracker.reset_daily()
        assert tracker.get_daily_cost() == 0.0

    def test_reset_monthly(self):
        """reset_monthly clears this month's records."""
        tracker = CostTracker()
        tracker.record("gpt-4o", "openai", self._usage(), self._pricing())
        assert tracker.get_monthly_cost() > 0
        tracker.reset_monthly()
        assert tracker.get_monthly_cost() == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 4. PrometheusConnector functional tests
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.connectors.observability.prometheus_connector import (
    PrometheusConfig,
    PrometheusConnector,
    _Counter,
    _Gauge,
    _Histogram,
    _format_labels,
)
from modelmesh.interfaces.observability import (
    AggregateStats,
    EventType,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)


class TestPrometheusCounter:
    """Tests for the _Counter primitive."""

    def test_inc(self):
        c = _Counter()
        c.inc({"model": "gpt-4"})
        c.inc({"model": "gpt-4"})
        items = c.items()
        assert len(items) == 1
        assert items[0][1] == 2.0

    def test_inc_different_labels(self):
        c = _Counter()
        c.inc({"model": "gpt-4"})
        c.inc({"model": "claude"})
        assert len(c.items()) == 2

    def test_inc_custom_amount(self):
        c = _Counter()
        c.inc({"key": "val"}, amount=5.0)
        assert c.items()[0][1] == 5.0


class TestPrometheusGauge:
    """Tests for the _Gauge primitive."""

    def test_set(self):
        g = _Gauge()
        g.set({"pool": "text"}, 3.0)
        assert g.items()[0][1] == 3.0

    def test_inc_dec(self):
        g = _Gauge()
        g.inc({"pool": "text"}, 5.0)
        g.dec({"pool": "text"}, 2.0)
        assert g.items()[0][1] == 3.0


class TestPrometheusHistogram:
    """Tests for the _Histogram primitive."""

    def test_observe(self):
        h = _Histogram([0.1, 0.5, 1.0])
        h.observe({}, 0.05)
        h.observe({}, 0.3)
        h.observe({}, 0.7)

        items = h.items()
        assert len(items) == 1
        labels, buckets, counts, total_sum, total_count = items[0]
        assert total_count == 3
        assert abs(total_sum - 1.05) < 1e-6
        # Storage is cumulative: each value increments all buckets it fits in
        # 0.05 fits in <=0.1, <=0.5, <=1.0
        # 0.3 fits in <=0.5, <=1.0
        # 0.7 fits in <=1.0
        assert counts[0] == 1  # <= 0.1: only 0.05
        assert counts[1] == 2  # <= 0.5: 0.05 + 0.3
        assert counts[2] == 3  # <= 1.0: 0.05 + 0.3 + 0.7

    def test_observe_above_all_buckets(self):
        """Observation above all bucket bounds still counted in total."""
        h = _Histogram([0.1, 0.5])
        h.observe({}, 999.0)
        items = h.items()
        _, _, counts, _, total_count = items[0]
        assert total_count == 1
        assert counts[0] == 0  # not in any bucket
        assert counts[1] == 0


class TestPrometheusConnectorFunctional:
    """Functional tests for PrometheusConnector."""

    def test_trace(self):
        conn = PrometheusConnector()
        entry = TraceEntry(
            timestamp=datetime.now(timezone.utc),
            severity=Severity.INFO,
            component="test",
            message="test trace",
        )
        conn.trace(entry)
        output = conn.render_metrics()
        assert "traces_total" in output
        assert 'severity="info"' in output

    def test_log_request(self):
        conn = PrometheusConnector(PrometheusConfig(prefix="test"))
        entry = RequestLogEntry(
            timestamp=datetime.now(timezone.utc),
            model_id="gpt-4o",
            provider_id="openai",
            capability="chat",
            delivery_mode="sync",
            latency_ms=150.0,
            status_code=200,
            tokens_in=100,
            tokens_out=50,
            cost=0.01,
            error=None,
        )
        conn.log(entry)
        output = conn.render_metrics()
        assert "test_requests_total" in output
        assert 'status="success"' in output
        assert "test_tokens_total" in output
        assert "test_cost_dollars_total" in output
        assert "test_request_duration_seconds" in output

    def test_log_error_request(self):
        conn = PrometheusConnector()
        entry = RequestLogEntry(
            timestamp=datetime.now(timezone.utc),
            model_id="gpt-4o",
            provider_id="openai",
            capability="chat",
            delivery_mode="sync",
            latency_ms=500.0,
            status_code=500,
            tokens_in=10,
            tokens_out=0,
            cost=None,
            error="ServerError: internal failure",
        )
        conn.log(entry)
        output = conn.render_metrics()
        assert 'status="error"' in output
        assert "errors_total" in output
        assert 'error_type="ServerError"' in output

    def test_emit_rotation(self):
        conn = PrometheusConnector()
        event = RoutingEvent(
            event_type=EventType.MODEL_ROTATED,
            timestamp=datetime.now(timezone.utc),
            pool_id="text-gen",
            model_id="gpt-4o",
            provider_id="openai",
        )
        conn.emit(event)
        output = conn.render_metrics()
        assert "rotation_events_total" in output

    def test_emit_with_metadata_gauges(self):
        conn = PrometheusConnector()
        event = RoutingEvent(
            event_type=EventType.MODEL_ROTATED,
            timestamp=datetime.now(timezone.utc),
            pool_id="text-gen",
            model_id="gpt-4o",
            provider_id="openai",
            metadata={"active_count": 3, "standby_count": 1},
        )
        conn.emit(event)
        output = conn.render_metrics()
        assert "active_models" in output
        assert "standby_models" in output

    def test_flush_aggregate_stats(self):
        conn = PrometheusConnector()
        stats = {
            "pool.text": AggregateStats(
                requests_total=100,
                requests_success=95,
                requests_failed=5,
                tokens_in=10000,
                tokens_out=5000,
                cost_total=1.5,
                latency_avg=200.0,
                latency_p95=500.0,
                downtime_total=0.0,
                rotation_events=3,
            )
        }
        conn.flush(stats)
        output = conn.render_metrics()
        assert "requests_total" in output
        assert "tokens_total" in output

    def test_render_empty(self):
        conn = PrometheusConnector()
        output = conn.render_metrics()
        assert output == ""

    def test_histogram_text_format(self):
        conn = PrometheusConnector(PrometheusConfig(prefix="p"))
        entry = RequestLogEntry(
            timestamp=datetime.now(timezone.utc),
            model_id="m",
            provider_id="p",
            capability="c",
            delivery_mode="sync",
            latency_ms=250.0,
            status_code=200,
            tokens_in=0,
            tokens_out=0,
            cost=None,
            error=None,
        )
        conn.log(entry)
        output = conn.render_metrics()
        assert "# HELP p_request_duration_seconds" in output
        assert "# TYPE p_request_duration_seconds histogram" in output
        assert "_bucket{" in output
        assert 'le="+Inf"' in output
        assert "_sum" in output
        assert "_count" in output

    def test_label_filtering(self):
        """include_model_labels=False hides model label."""
        conn = PrometheusConnector(PrometheusConfig(
            include_model_labels=False,
            include_provider_labels=True,
        ))
        entry = RequestLogEntry(
            timestamp=datetime.now(timezone.utc),
            model_id="gpt-4o",
            provider_id="openai",
            capability="chat",
            delivery_mode="sync",
            latency_ms=100.0,
            status_code=200,
            tokens_in=10,
            tokens_out=5,
            cost=None,
            error=None,
        )
        conn.log(entry)
        output = conn.render_metrics()
        assert 'model="gpt-4o"' not in output
        assert 'provider="openai"' in output


class TestFormatLabels:
    """Tests for Prometheus label formatting helper."""

    def test_empty_labels(self):
        assert _format_labels({}) == ""

    def test_single_label(self):
        assert _format_labels({"model": "gpt"}) == '{model="gpt"}'

    def test_sorted_labels(self):
        result = _format_labels({"z": "1", "a": "2"})
        assert result == '{a="2",z="1"}'


# ═══════════════════════════════════════════════════════════════════════
# 5. TimeoutMixin -- streaming timeouts
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.cdk.mixins.timeout import (
    RequestTimeoutError,
    TimeoutConfig,
    TimeoutMixin,
)


class _TimeoutUser(TimeoutMixin):
    pass


class TestStreamTimeout:
    """Tests for TimeoutMixin.with_stream_timeout."""

    def test_stream_completes_normally(self):
        tm = _TimeoutUser()
        tm.configure_timeout(streaming=5.0, streaming_total=10.0)

        async def gen():
            for i in range(3):
                yield i

        async def run():
            results = []
            async for item in tm.with_stream_timeout(gen()):
                results.append(item)
            return results

        results = asyncio.run(run())
        assert results == [0, 1, 2]

    def test_first_chunk_timeout(self):
        tm = _TimeoutUser()
        tm.configure_timeout(streaming=0.1, streaming_total=10.0)

        async def slow_gen():
            await asyncio.sleep(5.0)
            yield 1

        async def run():
            async for _ in tm.with_stream_timeout(slow_gen()):
                pass

        with pytest.raises(RequestTimeoutError) as exc_info:
            asyncio.run(run())
        assert "stream_first_chunk" in exc_info.value.operation

    def test_total_stream_timeout(self):
        tm = _TimeoutUser()
        tm.configure_timeout(streaming=5.0, streaming_total=0.2)

        async def slow_gen():
            for i in range(100):
                await asyncio.sleep(0.05)
                yield i

        async def run():
            items = []
            async for item in tm.with_stream_timeout(slow_gen()):
                items.append(item)
            return items

        with pytest.raises(RequestTimeoutError) as exc_info:
            asyncio.run(run())
        assert "stream_total" in exc_info.value.operation

    def test_timeout_zero_disables(self):
        """Timeout of 0 means no timeout enforcement."""
        tm = _TimeoutUser()
        tm.configure_timeout(default=0)

        async def slow():
            await asyncio.sleep(0.05)
            return "ok"

        result = asyncio.run(tm.with_timeout(slow()))
        assert result == "ok"


# ═══════════════════════════════════════════════════════════════════════
# 6. StreamingCheckpointMixin edge cases
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.cdk.mixins.streaming_checkpoint import (
    StreamCheckpoint,
    StreamingCheckpointMixin,
)


class _CheckpointUser(StreamingCheckpointMixin):
    pass


class TestStreamingCheckpointEdgeCases:
    """Edge case tests for StreamingCheckpointMixin."""

    def test_remove_checkpoint(self):
        """Removing a checkpoint by ID works."""
        user = _CheckpointUser()
        cp = user.create_checkpoint("req1", "model1")
        assert user.get_checkpoint("req1") is cp
        user.remove_checkpoint("req1")
        assert user.get_checkpoint("req1") is None

    def test_remove_nonexistent(self):
        """Removing nonexistent checkpoint is a no-op."""
        user = _CheckpointUser()
        user.remove_checkpoint("nonexistent")  # should not raise

    def test_active_checkpoints(self):
        """active_checkpoints returns only non-completed ones."""
        user = _CheckpointUser()
        cp1 = user.create_checkpoint("req1", "model1")
        cp2 = user.create_checkpoint("req2", "model2")
        cp1.record("hello ")
        cp2.record("world")
        cp2.finalize()

        active = user.active_checkpoints()
        assert len(active) == 1
        assert active[0].request_id == "req1"

    def test_checkpoint_duration(self):
        """Duration property calculates elapsed time."""
        user = _CheckpointUser()
        cp = user.create_checkpoint("r1", "m1")  # sets started_at
        time.sleep(0.05)
        cp.record("token")
        assert cp.duration > 0

    def test_checkpoint_tokens_per_second(self):
        """tokens_per_second calculates throughput."""
        user = _CheckpointUser()
        cp = user.create_checkpoint("r1", "m1")  # sets started_at
        time.sleep(0.05)
        cp.record("token1 ")
        cp.record("token2 ")
        cp.record("token3")
        cp.finalize()
        assert cp.tokens_per_second > 0

    def test_eviction_on_capacity(self):
        """Completed checkpoints are evicted when at max capacity."""
        user = _CheckpointUser()
        user.configure_checkpoints(max_checkpoints=3)

        # Fill up with completed checkpoints
        for i in range(3):
            cp = user.create_checkpoint(f"req{i}", "model")
            cp.record("data")
            cp.finalize()

        # Adding another should trigger eviction of completed ones
        cp_new = user.create_checkpoint("new", "model")
        stats = user.checkpoint_stats()
        # Eviction removes half of completed (floor 1), so 3-1 + 1 = 3
        assert stats["total"] <= 3


# ═══════════════════════════════════════════════════════════════════════
# 7. CircuitBreaker advanced scenarios
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.cdk.mixins.circuit_breaker import (
    CircuitBreakerMixin,
    CircuitOpenError,
    CircuitState,
)


class _CBUser(CircuitBreakerMixin):
    pass


class TestCircuitBreakerAdvanced:
    """Advanced circuit breaker scenarios."""

    def test_half_open_max_calls(self):
        """In half-open state, only half_open_max calls are allowed."""
        cb = _CBUser()
        cb.configure_circuit_breaker(
            failure_threshold=2,
            reset_timeout=0.05,
            half_open_max=2,
        )
        # Trip the breaker
        cb.record_failure()
        cb.record_failure()
        assert cb._cb_state == CircuitState.OPEN

        time.sleep(0.1)

        # First two calls should pass (half_open_max=2)
        cb.check_circuit()  # transitions to half-open, allows
        cb.check_circuit()  # second allowed
        # Third should fail
        with pytest.raises(CircuitOpenError):
            cb.check_circuit()

    def test_success_threshold_multi(self):
        """success_threshold > 1 requires multiple successes to close."""
        cb = _CBUser()
        cb.configure_circuit_breaker(
            failure_threshold=1,
            reset_timeout=0.05,
            success_threshold=3,
        )
        cb.record_failure()
        assert cb._cb_state == CircuitState.OPEN

        time.sleep(0.1)
        cb.check_circuit()  # transitions to half-open

        cb.record_success()
        assert cb._cb_state == CircuitState.HALF_OPEN  # still half-open (1/3)
        cb.record_success()
        assert cb._cb_state == CircuitState.HALF_OPEN  # still half-open (2/3)
        cb.record_success()
        assert cb._cb_state == CircuitState.CLOSED  # now closed (3/3)

    def test_circuit_open_error_message(self):
        """CircuitOpenError contains useful information."""
        cb = _CBUser()
        cb.configure_circuit_breaker(failure_threshold=1, reset_timeout=10.0)
        cb.record_failure()

        with pytest.raises(CircuitOpenError) as exc_info:
            cb.check_circuit()
        err = exc_info.value
        assert err.remaining > 0
        assert "circuit breaker is open" in str(err).lower()

    def test_rapid_oscillation(self):
        """Circuit can go CLOSED->OPEN->HALF_OPEN->OPEN repeatedly."""
        cb = _CBUser()
        cb.configure_circuit_breaker(
            failure_threshold=1,
            reset_timeout=0.05,
        )
        # Trip it
        cb.record_failure()
        assert cb._cb_state == CircuitState.OPEN

        # Wait and transition to half-open
        time.sleep(0.1)
        cb.check_circuit()
        assert cb._cb_state == CircuitState.HALF_OPEN

        # Fail again -> back to open
        cb.record_failure()
        assert cb._cb_state == CircuitState.OPEN

        # Recover again
        time.sleep(0.1)
        cb.check_circuit()
        assert cb._cb_state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb._cb_state == CircuitState.CLOSED


# ═══════════════════════════════════════════════════════════════════════
# 8. SqliteStorage async wrapping
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.connectors.storage.sqlite_storage import SqliteStorage, SqliteStorageConfig
from modelmesh.interfaces.storage import StorageEntry


class TestSqliteStorageAsync:
    """Verify SqliteStorage methods are properly async-wrapped."""

    def test_crud_operations(self):
        """Full CRUD cycle works through async wrappers."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            storage = SqliteStorage(SqliteStorageConfig(db_path=db_path))

            async def run():
                # Save
                entry = StorageEntry(key="test", data=b"hello", metadata={"a": 1})
                await storage.save("test", entry)

                # Load
                loaded = await storage.load("test")
                assert loaded is not None
                assert loaded.data == b"hello"
                assert loaded.metadata == {"a": 1}

                # Exists
                assert await storage.exists("test")
                assert not await storage.exists("nonexistent")

                # List
                keys = await storage.list()
                assert "test" in keys

                # Stat
                meta = await storage.stat("test")
                assert meta is not None
                assert meta.key == "test"
                assert meta.size > 0

                # Delete
                deleted = await storage.delete("test")
                assert deleted
                assert not await storage.exists("test")

                # Delete nonexistent
                assert not await storage.delete("nonexistent")

            asyncio.run(run())
        finally:
            storage.close()
            os.unlink(db_path)

    def test_list_with_prefix(self):
        """List with prefix filters correctly."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            storage = SqliteStorage(SqliteStorageConfig(db_path=db_path))

            async def run():
                await storage.save("config/a", StorageEntry(key="config/a", data=b"1", metadata={}))
                await storage.save("config/b", StorageEntry(key="config/b", data=b"2", metadata={}))
                await storage.save("data/x", StorageEntry(key="data/x", data=b"3", metadata={}))

                config_keys = await storage.list("config/")
                assert len(config_keys) == 2
                all_keys = await storage.list()
                assert len(all_keys) == 3

            asyncio.run(run())
        finally:
            storage.close()
            os.unlink(db_path)


# ═══════════════════════════════════════════════════════════════════════
# 9. AutoDiscovery caching and registry queries
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.connectors.discovery.auto_discovery import (
    AutoDiscovery,
    DiscoveredModel,
    DiscoveryConfig,
    ModelRegistry,
)


class TestModelRegistryQueries:
    """Test ModelRegistry query methods."""

    def _build_registry(self):
        reg = ModelRegistry()
        reg.register(DiscoveredModel(
            id="gpt-4o", provider="openai",
            capabilities=["chat"], context_window=128000,
            pricing_input=0.005, pricing_output=0.015,
        ))
        reg.register(DiscoveredModel(
            id="claude-3-5-sonnet", provider="anthropic",
            capabilities=["chat"], context_window=200000,
            pricing_input=0.003, pricing_output=0.015,
        ))
        reg.register(DiscoveredModel(
            id="llama-3-70b", provider="groq",
            capabilities=["chat"], context_window=131072,
            pricing_input=0.0, pricing_output=0.0,
        ))
        return reg

    def test_by_provider(self):
        """Filter models by provider."""
        reg = self._build_registry()
        openai_models = reg.by_provider("openai")
        assert len(openai_models) == 1
        assert openai_models[0].id == "gpt-4o"

    def test_by_capability(self):
        """Filter models by capability."""
        reg = self._build_registry()
        chat_models = reg.by_capability("chat")
        assert len(chat_models) == 3

    def test_cheapest(self):
        """Get models sorted by price (cheapest first)."""
        reg = self._build_registry()
        cheapest = reg.cheapest()
        assert len(cheapest) > 0
        # Free model should be first
        assert cheapest[0].pricing_input == 0.0

    def test_to_config(self):
        """Convert registry to config dict."""
        reg = self._build_registry()
        config = reg.to_config()
        # to_config returns a flat dict: {model_id: config_entry, ...}
        assert len(config) == 3
        assert "gpt-4o" in config


class TestAutoDiscoveryCaching:
    """Test AutoDiscovery caching behavior."""

    def test_discover_caches_results(self):
        """Repeated discover calls within TTL return cached results."""
        ad = AutoDiscovery(DiscoveryConfig(
            providers=["openai"],
            cache_ttl=60.0,
        ))
        result1 = ad.discover()
        result2 = ad.discover()
        # discover() returns list[DiscoveredModel]
        assert len(result1) == len(result2)
        assert len(result1) > 0

    def test_discover_with_exclude(self):
        """Exclude patterns filter out models."""
        ad = AutoDiscovery(DiscoveryConfig(
            providers=["openai"],
            exclude_patterns=["*"],  # exclude everything
        ))
        result = ad.discover()
        # discover() returns list[DiscoveredModel]
        assert len(result) == 0

    def test_generate_config(self):
        """generate_config produces valid config dict."""
        ad = AutoDiscovery(DiscoveryConfig(providers=["openai"]))
        config = ad.generate_config()
        assert isinstance(config, dict)
        assert "providers" in config or "models" in config


# ═══════════════════════════════════════════════════════════════════════
# 10. Rotation strategy edge cases
# ═══════════════════════════════════════════════════════════════════════

from modelmesh.connectors.rotation.round_robin import RoundRobinPolicy
from modelmesh.connectors.rotation.latency_first import LatencyFirstPolicy
from modelmesh.connectors.rotation.load_balanced import LoadBalancedConfig, LoadBalancedPolicy
from modelmesh.connectors.rotation.rate_limit_aware import RateLimitAwareConfig, RateLimitAwarePolicy
from modelmesh.interfaces.rotation import ModelState, ModelStatus
from modelmesh.interfaces.provider import CompletionRequest


class TestRoundRobinWraparound:
    """Test round-robin index wraparound."""

    def test_wraparound(self):
        """Index wraps around when exceeding candidate count."""
        policy = RoundRobinPolicy()
        sel = policy.selection

        candidates = [
            ModelState(model_id="a", status=ModelStatus.ACTIVE),
            ModelState(model_id="b", status=ModelStatus.ACTIVE),
        ]
        request = CompletionRequest(
            model="test", messages=[{"role": "user", "content": "test"}]
        )

        # Cycle through multiple times
        results = []
        for _ in range(6):
            result = sel.select(candidates, request)
            results.append(result.model_id)

        # Should alternate: a, b, a, b, a, b
        assert results[0] != results[1]
        assert results[0] == results[2]
        assert results[1] == results[3]


class TestRateLimitAwareDeactivation:
    """Test rate-limit-aware deactivation."""

    def test_quota_exhaustion(self):
        """Model is deactivated when request quota is exhausted."""
        config = RateLimitAwareConfig(model_request_limits={"gpt-4o": 10})
        policy = RateLimitAwarePolicy(config)
        deact = policy.deactivation

        state = ModelState(
            model_id="gpt-4o",
            status=ModelStatus.ACTIVE,
            total_requests=11,
        )
        result = deact.should_deactivate(state)
        assert result is True


class TestLoadBalancedWeights:
    """Test load-balanced weighted scoring."""

    def test_weight_affects_score(self):
        """Higher weight models get better scores."""
        config = LoadBalancedConfig(model_weights={"a": 2.0, "b": 1.0})
        policy = LoadBalancedPolicy(config)
        sel = policy.selection

        state_a = ModelState(model_id="a", status=ModelStatus.ACTIVE, total_requests=5)
        state_b = ModelState(model_id="b", status=ModelStatus.ACTIVE, total_requests=5)
        request = CompletionRequest(
            model="test", messages=[{"role": "user", "content": "test"}]
        )

        score_a = sel.score(state_a, request)
        score_b = sel.score(state_b, request)
        # Model 'a' has 2x weight so its score should be higher
        assert score_a > score_b


class TestLatencyFirstRecording:
    """Test latency recording and selection."""

    def test_record_latency_affects_selection(self):
        """Recording latency data changes model scores."""
        policy = LatencyFirstPolicy()
        sel = policy.selection

        state = ModelState(model_id="m1", status=ModelStatus.ACTIVE)
        request = CompletionRequest(
            model="test", messages=[{"role": "user", "content": "test"}]
        )

        # Record some latencies
        policy.record_latency("m1", 100.0)
        policy.record_latency("m1", 200.0)

        score = sel.score(state, request)
        # Score should reflect the latency (negative average = -150.0)
        assert score != 0.0
        assert score < 0  # LatencyFirstSelectionStrategy returns -avg


# ═══════════════════════════════════════════════════════════════════════
# 11. Export completeness checks
# ═══════════════════════════════════════════════════════════════════════


class TestExportCompleteness:
    """Verify key exports are accessible from public API."""

    def test_cdk_exports_resilience_mixins(self):
        """CDK package exports CircuitBreakerMixin, TimeoutMixin, StreamingCheckpointMixin."""
        from modelmesh.cdk import (
            CircuitBreakerMixin,
            CircuitOpenError,
            CircuitState,
            TimeoutMixin,
            RequestTimeoutError,
            StreamingCheckpointMixin,
            StreamCheckpoint,
        )
        assert CircuitBreakerMixin is not None
        assert TimeoutMixin is not None
        assert StreamingCheckpointMixin is not None

    def test_observability_exports_prometheus(self):
        """Observability package exports PrometheusConnector."""
        from modelmesh.connectors.observability import PrometheusConnector
        assert PrometheusConnector.CONNECTOR_ID == "modelmesh.prometheus.v1"

    def test_integrations_exports_langchain(self):
        """Integrations package exports ChatModelMesh."""
        from modelmesh.integrations import ChatModelMesh
        assert ChatModelMesh is not None

    def test_connector_registry_count(self):
        """Registry has correct connector count after all additions."""
        from modelmesh.connectors import CONNECTOR_REGISTRY
        # 47 total: 22 providers + 6 secret stores + 7 observability +
        # 8 rotation + 3 storage + 1 discovery
        assert len(CONNECTOR_REGISTRY) == 47
