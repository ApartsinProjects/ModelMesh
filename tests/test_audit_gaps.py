"""Tests for previously untested modules: BaseDiscovery, MetricsMixin,
HttpApiProvider, HttpHealthDiscovery, and FileObservabilityConnector."""
import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.cdk.base_discovery import BaseDiscovery, BaseDiscoveryConfig
from modelmesh.cdk.mixins.metrics import MetricsMixin, MetricSnapshot
from modelmesh.cdk.specialized.http_api_provider import (
    HttpApiProvider,
    HttpApiProviderConfig,
)
from modelmesh.cdk.specialized.http_health_discovery import (
    HttpHealthDiscovery,
    HttpHealthDiscoveryConfig,
)
from modelmesh.connectors.observability.file_connector import (
    FileConnectorConfig,
    FileObservabilityConnector,
)
from modelmesh.interfaces.discovery import (
    HealthReport,
    ProbeResult,
    SyncResult,
    SyncStatus,
)
from modelmesh.interfaces.observability import (
    AggregateStats,
    EventType,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
    ModelInfo,
    TokenUsage,
)


# =====================================================================
# 1. BaseDiscovery
# =====================================================================


class TestBaseDiscoveryConfig(unittest.TestCase):
    """Test BaseDiscoveryConfig defaults and customization."""

    def test_default_config(self):
        config = BaseDiscoveryConfig()
        self.assertEqual(config.providers, [])
        self.assertEqual(config.sync_interval_seconds, 3600.0)
        self.assertEqual(config.health_interval_seconds, 60.0)
        self.assertEqual(config.health_timeout_seconds, 10.0)
        self.assertEqual(config.failure_threshold, 3)
        self.assertEqual(config.on_new_model, "register")
        self.assertEqual(config.on_deprecated_model, "notify")

    def test_custom_config(self):
        config = BaseDiscoveryConfig(
            providers=["openai", "anthropic"],
            sync_interval_seconds=1800.0,
            failure_threshold=5,
        )
        self.assertEqual(config.providers, ["openai", "anthropic"])
        self.assertEqual(config.sync_interval_seconds, 1800.0)
        self.assertEqual(config.failure_threshold, 5)


class TestBaseDiscoveryInit(unittest.TestCase):
    """Test BaseDiscovery construction."""

    def test_default_init(self):
        discovery = BaseDiscovery()
        self.assertIsNotNone(discovery._config)
        self.assertEqual(discovery._known_models, {})
        self.assertIsNone(discovery._last_sync)
        self.assertEqual(discovery._models_synced, 0)
        self.assertEqual(discovery._health_history, {})
        self.assertEqual(discovery._failure_counts, {})

    def test_init_with_config(self):
        config = BaseDiscoveryConfig(
            providers=["p1"], failure_threshold=5
        )
        discovery = BaseDiscovery(config)
        self.assertEqual(discovery._config.providers, ["p1"])
        self.assertEqual(discovery._config.failure_threshold, 5)


class TestBaseDiscoverySync(unittest.TestCase):
    """Test BaseDiscovery.sync() method."""

    def test_sync_empty_providers(self):
        discovery = BaseDiscovery(BaseDiscoveryConfig(providers=[]))
        result = asyncio.run(discovery.sync())
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.new_models, [])
        self.assertEqual(result.deprecated_models, [])
        self.assertEqual(result.updated_models, [])
        self.assertEqual(result.errors, [])

    def test_sync_discovers_new_models(self):
        """When _discover_provider_models returns new models they appear in new_models."""

        class TestDiscovery(BaseDiscovery):
            async def _discover_provider_models(self, provider_id):
                return ["model-a", "model-b"]

        discovery = TestDiscovery(BaseDiscoveryConfig(providers=["prov1"]))
        result = asyncio.run(discovery.sync())
        self.assertEqual(len(result.new_models), 2)
        self.assertIn("prov1/model-a", result.new_models)
        self.assertIn("prov1/model-b", result.new_models)
        self.assertEqual(result.deprecated_models, [])

    def test_sync_detects_deprecated_models(self):
        """Models in known catalogue but not in discovery are deprecated."""

        class ShrinkingDiscovery(BaseDiscovery):
            async def _discover_provider_models(self, provider_id):
                return ["model-a"]

        discovery = ShrinkingDiscovery(
            BaseDiscoveryConfig(providers=["prov1"])
        )
        discovery._known_models["prov1"] = ["model-a", "model-b"]

        result = asyncio.run(discovery.sync())
        self.assertIn("prov1/model-b", result.deprecated_models)
        self.assertNotIn("prov1/model-a", result.deprecated_models)

    def test_sync_detects_updated_models(self):
        """Models present in both known and discovered are updated."""

        class StableDiscovery(BaseDiscovery):
            async def _discover_provider_models(self, provider_id):
                return ["model-a"]

        discovery = StableDiscovery(
            BaseDiscoveryConfig(providers=["prov1"])
        )
        discovery._known_models["prov1"] = ["model-a"]

        result = asyncio.run(discovery.sync())
        self.assertIn("prov1/model-a", result.updated_models)

    def test_sync_handles_provider_errors(self):
        """Errors during discovery are captured in result.errors."""

        class FailingDiscovery(BaseDiscovery):
            async def _discover_provider_models(self, provider_id):
                raise ConnectionError("unreachable")

        discovery = FailingDiscovery(
            BaseDiscoveryConfig(providers=["broken"])
        )
        result = asyncio.run(discovery.sync())
        self.assertEqual(len(result.errors), 1)
        self.assertIn("broken", result.errors[0])
        self.assertIn("unreachable", result.errors[0])

    def test_sync_updates_last_sync_and_count(self):
        discovery = BaseDiscovery(BaseDiscoveryConfig(providers=[]))
        self.assertIsNone(discovery._last_sync)
        asyncio.run(discovery.sync())
        self.assertIsNotNone(discovery._last_sync)

    def test_sync_with_explicit_providers_list(self):
        """Passing providers to sync() overrides config.providers."""

        class TestDiscovery(BaseDiscovery):
            async def _discover_provider_models(self, provider_id):
                return [f"{provider_id}-model"]

        discovery = TestDiscovery(
            BaseDiscoveryConfig(providers=["default"])
        )
        result = asyncio.run(discovery.sync(providers=["custom"]))
        self.assertIn("custom/custom-model", result.new_models)
        self.assertNotIn("default/default-model", result.new_models)

    def test_sync_multiple_providers(self):
        """Sync across multiple providers tracks models independently."""

        class MultiDiscovery(BaseDiscovery):
            async def _discover_provider_models(self, provider_id):
                if provider_id == "a":
                    return ["m1"]
                return ["m2", "m3"]

        discovery = MultiDiscovery(
            BaseDiscoveryConfig(providers=["a", "b"])
        )
        result = asyncio.run(discovery.sync())
        self.assertEqual(len(result.new_models), 3)
        self.assertEqual(discovery._models_synced, 3)


class TestBaseDiscoverySyncStatus(unittest.TestCase):
    """Test BaseDiscovery.get_sync_status()."""

    def test_status_before_sync(self):
        discovery = BaseDiscovery()
        status = asyncio.run(discovery.get_sync_status())
        self.assertIsInstance(status, SyncStatus)
        self.assertIsNone(status.last_sync)
        self.assertIsNone(status.next_sync)
        self.assertEqual(status.models_synced, 0)
        self.assertEqual(status.status, "pending")

    def test_status_after_sync(self):
        discovery = BaseDiscovery(BaseDiscoveryConfig(providers=[]))
        asyncio.run(discovery.sync())
        status = asyncio.run(discovery.get_sync_status())
        self.assertIsNotNone(status.last_sync)
        self.assertIsNotNone(status.next_sync)
        self.assertEqual(status.status, "idle")
        # next_sync should be last_sync + sync_interval
        diff = (status.next_sync - status.last_sync).total_seconds()
        self.assertAlmostEqual(diff, 3600.0, places=0)


class TestBaseDiscoveryHealth(unittest.TestCase):
    """Test BaseDiscovery health monitoring methods."""

    def test_default_probe_succeeds(self):
        discovery = BaseDiscovery()
        result = asyncio.run(discovery.probe("any-provider"))
        self.assertIsInstance(result, ProbeResult)
        self.assertTrue(result.success)
        self.assertEqual(result.provider_id, "any-provider")

    def test_get_health_report_single_provider(self):
        discovery = BaseDiscovery(
            BaseDiscoveryConfig(providers=["prov1"])
        )
        reports = asyncio.run(discovery.get_health_report("prov1"))
        self.assertEqual(len(reports), 1)
        self.assertTrue(reports[0].available)
        self.assertEqual(reports[0].provider_id, "prov1")

    def test_get_health_report_all_providers(self):
        discovery = BaseDiscovery(
            BaseDiscoveryConfig(providers=["a", "b"])
        )
        reports = asyncio.run(discovery.get_health_report())
        self.assertEqual(len(reports), 2)

    def test_health_report_resets_failure_count_on_success(self):
        discovery = BaseDiscovery()
        discovery._failure_counts["prov1"] = 5
        asyncio.run(discovery.get_health_report("prov1"))
        self.assertEqual(discovery._failure_counts["prov1"], 0)

    def test_health_report_increments_failure_count(self):
        """When probe fails, failure count increments."""

        class FailProbe(BaseDiscovery):
            async def probe(self, provider_id):
                return ProbeResult(
                    provider_id=provider_id,
                    success=False,
                    error="timeout",
                )

        discovery = FailProbe(BaseDiscoveryConfig(providers=["bad"]))
        asyncio.run(discovery.get_health_report("bad"))
        self.assertEqual(discovery._failure_counts["bad"], 1)
        asyncio.run(discovery.get_health_report("bad"))
        self.assertEqual(discovery._failure_counts["bad"], 2)

    def test_health_history_capped_at_100(self):
        discovery = BaseDiscovery(
            BaseDiscoveryConfig(providers=["prov1"])
        )
        for _ in range(110):
            asyncio.run(discovery.get_health_report("prov1"))
        self.assertEqual(len(discovery._health_history["prov1"]), 100)

    def test_availability_score_calculation(self):
        """Availability score reflects ratio of successful probes."""

        class AlternatingProbe(BaseDiscovery):
            def __init__(self, config):
                super().__init__(config)
                self._call_count = 0

            async def probe(self, provider_id):
                self._call_count += 1
                return ProbeResult(
                    provider_id=provider_id,
                    success=(self._call_count % 2 == 1),
                )

        discovery = AlternatingProbe(
            BaseDiscoveryConfig(providers=["prov1"])
        )
        # First probe: success
        reports = asyncio.run(discovery.get_health_report("prov1"))
        self.assertAlmostEqual(reports[0].availability_score, 1.0)
        # Second probe: failure -> 1 success / 2 total = 0.5
        reports = asyncio.run(discovery.get_health_report("prov1"))
        self.assertAlmostEqual(reports[0].availability_score, 0.5)


class TestBaseDiscoveryDegraded(unittest.TestCase):
    """Test BaseDiscovery.is_provider_degraded()."""

    def test_not_degraded_by_default(self):
        discovery = BaseDiscovery(
            BaseDiscoveryConfig(failure_threshold=3)
        )
        self.assertFalse(discovery.is_provider_degraded("prov1"))

    def test_degraded_when_threshold_reached(self):
        discovery = BaseDiscovery(
            BaseDiscoveryConfig(failure_threshold=3)
        )
        discovery._failure_counts["prov1"] = 3
        self.assertTrue(discovery.is_provider_degraded("prov1"))

    def test_degraded_when_threshold_exceeded(self):
        discovery = BaseDiscovery(
            BaseDiscoveryConfig(failure_threshold=2)
        )
        discovery._failure_counts["prov1"] = 5
        self.assertTrue(discovery.is_provider_degraded("prov1"))

    def test_not_degraded_below_threshold(self):
        discovery = BaseDiscovery(
            BaseDiscoveryConfig(failure_threshold=3)
        )
        discovery._failure_counts["prov1"] = 2
        self.assertFalse(discovery.is_provider_degraded("prov1"))


class TestBaseDiscoveryDiscoverProviderModels(unittest.TestCase):
    """Test BaseDiscovery._discover_provider_models() default."""

    def test_default_returns_known_models(self):
        discovery = BaseDiscovery()
        discovery._known_models["prov1"] = ["m1", "m2"]
        result = asyncio.run(discovery._discover_provider_models("prov1"))
        self.assertEqual(result, ["m1", "m2"])

    def test_default_returns_empty_for_unknown_provider(self):
        discovery = BaseDiscovery()
        result = asyncio.run(discovery._discover_provider_models("unknown"))
        self.assertEqual(result, [])


# =====================================================================
# 2. MetricsMixin
# =====================================================================


class MetricsHost(MetricsMixin):
    """Concrete host class for MetricsMixin testing."""

    def __init__(self):
        self.__init_metrics__()


class TestMetricsMixinInit(unittest.TestCase):
    """Test MetricsMixin initialization."""

    def test_init_metrics_sets_defaults(self):
        host = MetricsHost()
        self.assertEqual(host._metrics_latencies, [])
        self.assertEqual(host._metrics_total_requests, 0)
        self.assertEqual(host._metrics_successful, 0)
        self.assertEqual(host._metrics_failed, 0)
        self.assertEqual(host._metrics_total_tokens, 0)
        self.assertAlmostEqual(host._metrics_total_cost, 0.0)
        self.assertGreater(host._metrics_start_time, 0)


class TestMetricsTrackRequest(unittest.TestCase):
    """Test MetricsMixin._metrics_track_request() context manager."""

    def test_successful_request_counted(self):
        host = MetricsHost()
        with host._metrics_track_request():
            pass  # simulate successful request
        self.assertEqual(host._metrics_total_requests, 1)
        self.assertEqual(host._metrics_successful, 1)
        self.assertEqual(host._metrics_failed, 0)
        self.assertEqual(len(host._metrics_latencies), 1)

    def test_failed_request_counted(self):
        host = MetricsHost()
        with self.assertRaises(ValueError):
            with host._metrics_track_request():
                raise ValueError("API error")
        self.assertEqual(host._metrics_total_requests, 1)
        self.assertEqual(host._metrics_successful, 0)
        self.assertEqual(host._metrics_failed, 1)
        self.assertEqual(len(host._metrics_latencies), 1)

    def test_latency_recorded_in_milliseconds(self):
        host = MetricsHost()
        with host._metrics_track_request():
            time.sleep(0.01)  # 10ms
        self.assertGreater(host._metrics_latencies[0], 0)
        # Should be roughly 10ms or more
        self.assertGreater(host._metrics_latencies[0], 5)

    def test_multiple_requests_accumulated(self):
        host = MetricsHost()
        for _ in range(5):
            with host._metrics_track_request():
                pass
        self.assertEqual(host._metrics_total_requests, 5)
        self.assertEqual(host._metrics_successful, 5)
        self.assertEqual(len(host._metrics_latencies), 5)

    def test_mixed_success_and_failure(self):
        host = MetricsHost()
        with host._metrics_track_request():
            pass
        try:
            with host._metrics_track_request():
                raise RuntimeError("fail")
        except RuntimeError:
            pass
        with host._metrics_track_request():
            pass
        self.assertEqual(host._metrics_total_requests, 3)
        self.assertEqual(host._metrics_successful, 2)
        self.assertEqual(host._metrics_failed, 1)


class TestMetricsRecordTokens(unittest.TestCase):
    """Test MetricsMixin._metrics_record_tokens()."""

    def test_record_tokens_basic(self):
        host = MetricsHost()
        host._metrics_record_tokens(100)
        self.assertEqual(host._metrics_total_tokens, 100)
        self.assertAlmostEqual(host._metrics_total_cost, 0.0)

    def test_record_tokens_with_cost(self):
        host = MetricsHost()
        host._metrics_record_tokens(500, cost=0.05)
        self.assertEqual(host._metrics_total_tokens, 500)
        self.assertAlmostEqual(host._metrics_total_cost, 0.05)

    def test_record_tokens_accumulates(self):
        host = MetricsHost()
        host._metrics_record_tokens(100, cost=0.01)
        host._metrics_record_tokens(200, cost=0.02)
        host._metrics_record_tokens(300, cost=0.03)
        self.assertEqual(host._metrics_total_tokens, 600)
        self.assertAlmostEqual(host._metrics_total_cost, 0.06)


class TestMetricsSnapshot(unittest.TestCase):
    """Test MetricsMixin._metrics_snapshot()."""

    def test_snapshot_empty(self):
        host = MetricsHost()
        snap = host._metrics_snapshot()
        self.assertIsInstance(snap, MetricSnapshot)
        self.assertEqual(snap.total_requests, 0)
        self.assertEqual(snap.successful_requests, 0)
        self.assertEqual(snap.failed_requests, 0)
        self.assertAlmostEqual(snap.error_rate, 0.0)

    def test_snapshot_after_requests(self):
        host = MetricsHost()
        for _ in range(3):
            with host._metrics_track_request():
                pass
        try:
            with host._metrics_track_request():
                raise RuntimeError("err")
        except RuntimeError:
            pass
        host._metrics_record_tokens(1000, cost=0.10)

        snap = host._metrics_snapshot()
        self.assertEqual(snap.total_requests, 4)
        self.assertEqual(snap.successful_requests, 3)
        self.assertEqual(snap.failed_requests, 1)
        self.assertEqual(snap.total_tokens, 1000)
        self.assertAlmostEqual(snap.total_cost, 0.10)
        self.assertAlmostEqual(snap.error_rate, 0.25)
        self.assertGreater(snap.avg_latency_ms, 0)
        self.assertGreater(snap.requests_per_minute, 0)

    def test_snapshot_percentiles(self):
        host = MetricsHost()
        # Inject known latencies
        host._metrics_latencies = [float(i) for i in range(1, 101)]
        host._metrics_total_requests = 100
        host._metrics_successful = 100

        snap = host._metrics_snapshot()
        self.assertAlmostEqual(snap.p50_latency_ms, 51.0)
        self.assertAlmostEqual(snap.p95_latency_ms, 96.0)
        self.assertAlmostEqual(snap.p99_latency_ms, 100.0)


class TestMetricsReset(unittest.TestCase):
    """Test MetricsMixin._metrics_reset()."""

    def test_reset_clears_all(self):
        host = MetricsHost()
        with host._metrics_track_request():
            pass
        host._metrics_record_tokens(500, cost=0.05)
        self.assertEqual(host._metrics_total_requests, 1)

        host._metrics_reset()
        self.assertEqual(host._metrics_latencies, [])
        self.assertEqual(host._metrics_total_requests, 0)
        self.assertEqual(host._metrics_successful, 0)
        self.assertEqual(host._metrics_failed, 0)
        self.assertEqual(host._metrics_total_tokens, 0)
        self.assertAlmostEqual(host._metrics_total_cost, 0.0)

    def test_reset_resets_start_time(self):
        host = MetricsHost()
        old_start = host._metrics_start_time
        time.sleep(0.01)
        host._metrics_reset()
        self.assertGreater(host._metrics_start_time, old_start)


# =====================================================================
# 3. HttpApiProvider
# =====================================================================


class TestHttpApiProviderConfig(unittest.TestCase):
    """Test HttpApiProviderConfig defaults and customization."""

    def test_default_config(self):
        config = HttpApiProviderConfig(
            base_url="https://api.example.com",
            api_key="key",
        )
        self.assertEqual(config.method, "POST")
        self.assertEqual(config.content_type, "application/json")

    def test_custom_config(self):
        config = HttpApiProviderConfig(
            base_url="https://api.example.com",
            api_key="key",
            method="PUT",
            content_type="text/plain",
        )
        self.assertEqual(config.method, "PUT")
        self.assertEqual(config.content_type, "text/plain")


class ConcreteHttpApiProvider(HttpApiProvider):
    """Concrete subclass for testing HttpApiProvider."""

    def _translate_request(self, request):
        return {"prompt": request.messages[-1]["content"]}

    def _translate_response(self, data):
        return CompletionResponse(
            id=data.get("id", "resp-1"),
            model=data.get("model", "test-model"),
            choices=[],
            usage=TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0
            ),
        )


class TestHttpApiProviderInit(unittest.TestCase):
    """Test HttpApiProvider construction."""

    def test_instantiation(self):
        config = HttpApiProviderConfig(
            base_url="https://api.example.com",
            api_key="key",
        )
        provider = ConcreteHttpApiProvider(config)
        self.assertIsNotNone(provider)
        self.assertEqual(provider._http_config.method, "POST")

    def test_is_base_provider(self):
        from modelmesh.cdk.base_provider import BaseProvider

        config = HttpApiProviderConfig(
            base_url="https://api.example.com", api_key="key"
        )
        provider = ConcreteHttpApiProvider(config)
        self.assertIsInstance(provider, BaseProvider)


class TestHttpApiProviderAbstractMethods(unittest.TestCase):
    """Test that HttpApiProvider base raises NotImplementedError."""

    def test_translate_request_raises(self):
        config = HttpApiProviderConfig(
            base_url="https://api.example.com", api_key="key"
        )
        provider = HttpApiProvider(config)
        request = CompletionRequest(
            model="test",
            messages=[{"role": "user", "content": "hi"}],
        )
        with self.assertRaises(NotImplementedError):
            provider._translate_request(request)

    def test_translate_response_raises(self):
        config = HttpApiProviderConfig(
            base_url="https://api.example.com", api_key="key"
        )
        provider = HttpApiProvider(config)
        with self.assertRaises(NotImplementedError):
            provider._translate_response({"id": "1"})


class TestHttpApiProviderDelegation(unittest.TestCase):
    """Test that _build_request_payload and _parse_response delegate."""

    def setUp(self):
        self.config = HttpApiProviderConfig(
            base_url="https://api.example.com", api_key="key"
        )
        self.provider = ConcreteHttpApiProvider(self.config)

    def test_build_request_payload_delegates(self):
        request = CompletionRequest(
            model="test",
            messages=[{"role": "user", "content": "Hello"}],
        )
        payload = self.provider._build_request_payload(request)
        self.assertEqual(payload, {"prompt": "Hello"})

    def test_parse_response_delegates(self):
        data = {"id": "resp-42", "model": "custom"}
        response = self.provider._parse_response(data)
        self.assertIsInstance(response, CompletionResponse)
        self.assertEqual(response.id, "resp-42")
        self.assertEqual(response.model, "custom")


class TestHttpApiProviderHeaders(unittest.TestCase):
    """Test HttpApiProvider._build_headers() with custom content type."""

    def test_headers_use_configured_content_type(self):
        config = HttpApiProviderConfig(
            base_url="https://api.example.com",
            api_key="my-key",
            content_type="application/xml",
        )
        provider = ConcreteHttpApiProvider(config)
        headers = provider._build_headers()
        self.assertEqual(headers["Content-Type"], "application/xml")
        self.assertEqual(headers["Authorization"], "Bearer my-key")

    def test_headers_default_json_content_type(self):
        config = HttpApiProviderConfig(
            base_url="https://api.example.com", api_key="key"
        )
        provider = ConcreteHttpApiProvider(config)
        headers = provider._build_headers()
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_headers_no_auth_when_empty_api_key(self):
        config = HttpApiProviderConfig(
            base_url="https://api.example.com", api_key=""
        )
        provider = ConcreteHttpApiProvider(config)
        headers = provider._build_headers()
        self.assertNotIn("Authorization", headers)


# =====================================================================
# 4. HttpHealthDiscovery
# =====================================================================


class TestHttpHealthDiscoveryConfig(unittest.TestCase):
    """Test HttpHealthDiscoveryConfig defaults and inheritance."""

    def test_default_config(self):
        config = HttpHealthDiscoveryConfig()
        self.assertEqual(config.health_path, "/health")
        self.assertEqual(config.expected_status, 200)
        # Inherited from BaseDiscoveryConfig
        self.assertEqual(config.failure_threshold, 3)

    def test_custom_config(self):
        config = HttpHealthDiscoveryConfig(
            health_path="/v1/models",
            expected_status=200,
            providers=["openai"],
            failure_threshold=5,
        )
        self.assertEqual(config.health_path, "/v1/models")
        self.assertEqual(config.providers, ["openai"])


class TestHttpHealthDiscoveryInit(unittest.TestCase):
    """Test HttpHealthDiscovery construction."""

    def test_default_init(self):
        discovery = HttpHealthDiscovery()
        self.assertIsNotNone(discovery._http_config)
        self.assertEqual(discovery._provider_urls, {})

    def test_init_with_config(self):
        config = HttpHealthDiscoveryConfig(
            health_path="/status",
            providers=["prov1"],
        )
        discovery = HttpHealthDiscovery(config)
        self.assertEqual(discovery._http_config.health_path, "/status")

    def test_inherits_base_discovery(self):
        discovery = HttpHealthDiscovery()
        self.assertIsInstance(discovery, BaseDiscovery)


class TestHttpHealthDiscoveryRegister(unittest.TestCase):
    """Test HttpHealthDiscovery.register_provider_url()."""

    def test_register_provider_url(self):
        discovery = HttpHealthDiscovery()
        discovery.register_provider_url("openai", "https://api.openai.com")
        self.assertEqual(
            discovery._provider_urls["openai"], "https://api.openai.com"
        )

    def test_register_strips_trailing_slash(self):
        discovery = HttpHealthDiscovery()
        discovery.register_provider_url("prov", "https://api.example.com/")
        self.assertEqual(
            discovery._provider_urls["prov"], "https://api.example.com"
        )

    def test_register_multiple_providers(self):
        discovery = HttpHealthDiscovery()
        discovery.register_provider_url("a", "https://a.com")
        discovery.register_provider_url("b", "https://b.com")
        self.assertEqual(len(discovery._provider_urls), 2)

    def test_register_overwrites_existing(self):
        discovery = HttpHealthDiscovery()
        discovery.register_provider_url("prov", "https://old.com")
        discovery.register_provider_url("prov", "https://new.com")
        self.assertEqual(discovery._provider_urls["prov"], "https://new.com")


class TestHttpHealthDiscoveryProbe(unittest.TestCase):
    """Test HttpHealthDiscovery.probe() method."""

    def test_probe_no_url_registered(self):
        discovery = HttpHealthDiscovery()
        result = asyncio.run(discovery.probe("unknown"))
        self.assertIsInstance(result, ProbeResult)
        self.assertFalse(result.success)
        self.assertIn("No URL registered", result.error)

    @patch("modelmesh.cdk.specialized.http_health_discovery.urllib.request.urlopen")
    def test_probe_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        discovery = HttpHealthDiscovery(
            HttpHealthDiscoveryConfig(expected_status=200)
        )
        discovery.register_provider_url("prov", "https://api.example.com")
        result = asyncio.run(discovery.probe("prov"))

        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(result.error)
        self.assertGreaterEqual(result.latency_ms, 0)

    @patch("modelmesh.cdk.specialized.http_health_discovery.urllib.request.urlopen")
    def test_probe_unexpected_status(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 503
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        discovery = HttpHealthDiscovery(
            HttpHealthDiscoveryConfig(expected_status=200)
        )
        discovery.register_provider_url("prov", "https://api.example.com")
        result = asyncio.run(discovery.probe("prov"))

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 503)
        self.assertIn("Unexpected status", result.error)

    @patch("modelmesh.cdk.specialized.http_health_discovery.urllib.request.urlopen")
    def test_probe_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.example.com/health",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        discovery = HttpHealthDiscovery()
        discovery.register_provider_url("prov", "https://api.example.com")
        result = asyncio.run(discovery.probe("prov"))

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 500)
        self.assertIn("HTTP 500", result.error)

    @patch("modelmesh.cdk.specialized.http_health_discovery.urllib.request.urlopen")
    def test_probe_connection_error(self, mock_urlopen):
        mock_urlopen.side_effect = ConnectionError("Connection refused")

        discovery = HttpHealthDiscovery()
        discovery.register_provider_url("prov", "https://api.example.com")
        result = asyncio.run(discovery.probe("prov"))

        self.assertFalse(result.success)
        self.assertIn("Connection refused", result.error)
        self.assertGreaterEqual(result.latency_ms, 0)

    @patch("modelmesh.cdk.specialized.http_health_discovery.urllib.request.urlopen")
    def test_probe_uses_configured_health_path(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        config = HttpHealthDiscoveryConfig(health_path="/v1/status")
        discovery = HttpHealthDiscovery(config)
        discovery.register_provider_url("prov", "https://api.example.com")
        asyncio.run(discovery.probe("prov"))

        # Verify the URL used includes the health path
        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertIn("/v1/status", request_obj.full_url)


class TestHttpHealthDiscoverySyncProbe(unittest.TestCase):
    """Test HttpHealthDiscovery._sync_probe() directly."""

    @patch("modelmesh.cdk.specialized.http_health_discovery.urllib.request.urlopen")
    def test_sync_probe_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        discovery = HttpHealthDiscovery()
        result = discovery._sync_probe("prov", "https://api.example.com/health")
        self.assertTrue(result.success)
        self.assertEqual(result.provider_id, "prov")

    @patch("modelmesh.cdk.specialized.http_health_discovery.urllib.request.urlopen")
    def test_sync_probe_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")

        discovery = HttpHealthDiscovery()
        result = discovery._sync_probe("prov", "https://api.example.com/health")
        self.assertFalse(result.success)
        self.assertIn("timed out", result.error)


# =====================================================================
# 5. FileObservabilityConnector
# =====================================================================


class TestFileConnectorConfig(unittest.TestCase):
    """Test FileConnectorConfig defaults."""

    def test_inherits_file_observability_config(self):
        from modelmesh.cdk.specialized.file_observability import (
            FileObservabilityConfig,
        )

        config = FileConnectorConfig()
        self.assertIsInstance(config, FileObservabilityConfig)

    def test_default_values(self):
        config = FileConnectorConfig()
        self.assertEqual(config.file_path, "modelmesh.log")
        self.assertTrue(config.append)
        self.assertTrue(config.flush_each_line)
        self.assertEqual(config.max_file_size_bytes, 0)


class TestFileObservabilityConnectorInit(unittest.TestCase):
    """Test FileObservabilityConnector construction."""

    def test_connector_id(self):
        self.assertEqual(
            FileObservabilityConnector.CONNECTOR_ID, "modelmesh.file.v1"
        )

    def test_default_init(self):
        connector = FileObservabilityConnector()
        self.assertIsNotNone(connector)

    def test_init_with_config(self):
        tmp = tempfile.mktemp(suffix=".log")
        try:
            config = FileConnectorConfig(file_path=tmp)
            connector = FileObservabilityConnector(config)
            self.assertIsNotNone(connector)
            connector.close()
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_inherits_file_observability(self):
        from modelmesh.cdk.specialized.file_observability import FileObservability

        connector = FileObservabilityConnector()
        self.assertIsInstance(connector, FileObservability)
        connector.close()


class TestFileObservabilityConnectorFunctionality(unittest.TestCase):
    """Test FileObservabilityConnector trace/emit/log/flush operations."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix=".log")
        self.connector = FileObservabilityConnector(
            FileConnectorConfig(file_path=self.tmp, min_severity="debug")
        )

    def tearDown(self):
        try:
            self.connector.close()
        except Exception:
            pass
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_trace_writes_to_file(self):
        entry = TraceEntry(
            severity=Severity.INFO,
            timestamp=datetime.now(),
            component="test",
            message="hello from connector",
        )
        self.connector.trace(entry)
        self.connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertEqual(data["type"], "trace")
        self.assertEqual(data["message"], "hello from connector")

    def test_emit_writes_event(self):
        event = RoutingEvent(
            event_type=EventType.MODEL_ACTIVATED,
            timestamp=datetime.now(),
            model_id="test.model",
        )
        self.connector.emit(event)
        self.connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())
        self.assertEqual(data["type"], "event")
        self.assertEqual(data["event_type"], "model_activated")

    def test_log_writes_request_entry(self):
        self.connector.close()
        self.connector = FileObservabilityConnector(
            FileConnectorConfig(
                file_path=self.tmp, log_level="full", min_severity="debug"
            )
        )

        entry = RequestLogEntry(
            timestamp=datetime.now(),
            model_id="test.model",
            provider_id="test.v1",
            capability="chat",
            delivery_mode="synchronous",
            latency_ms=100.0,
            status_code=200,
            tokens_in=10,
            tokens_out=5,
        )
        self.connector.log(entry)
        self.connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())
        self.assertEqual(data["type"], "log")
        self.assertEqual(data["model_id"], "test.model")

    def test_flush_writes_stats(self):
        stats = {
            "pool.chat": AggregateStats(
                requests_total=50,
                requests_success=48,
                requests_failed=2,
                tokens_in=5000,
                tokens_out=2500,
                cost_total=0.75,
                latency_avg=100.0,
                latency_p95=200.0,
                downtime_total=1.0,
                rotation_events=1,
            )
        }
        self.connector.flush(stats)
        self.connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())
        self.assertEqual(data["type"], "stats")
        self.assertEqual(data["requests_total"], 50)

    def test_close_closes_file(self):
        self.connector.trace(
            TraceEntry(
                severity=Severity.INFO,
                timestamp=datetime.now(),
                component="test",
                message="before close",
            )
        )
        self.connector.close()
        self.assertTrue(self.connector._file.closed)

    def test_secret_redaction(self):
        self.connector.close()
        self.connector = FileObservabilityConnector(
            FileConnectorConfig(
                file_path=self.tmp,
                redact_secrets=True,
                min_severity="debug",
            )
        )
        event = RoutingEvent(
            event_type=EventType.MODEL_ACTIVATED,
            timestamp=datetime.now(),
            metadata={"api_key": "sk-secret-value-123"},
        )
        self.connector.emit(event)
        self.connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("***REDACTED***", content)
        self.assertNotIn("sk-secret-value-123", content)

    def test_append_mode(self):
        # Write initial content
        with open(self.tmp, "w", encoding="utf-8") as f:
            f.write('{"existing": true}\n')

        self.connector.close()
        self.connector = FileObservabilityConnector(
            FileConnectorConfig(
                file_path=self.tmp, append=True, min_severity="debug"
            )
        )
        self.connector.trace(
            TraceEntry(
                severity=Severity.INFO,
                timestamp=datetime.now(),
                component="test",
                message="appended line",
            )
        )
        self.connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
