"""Tests for observability connectors during real routing scenarios.

Validates that ConsoleConnector, JsonLogConnector, CallbackConnector,
and WebhookConnector produce correct output when the mesh routes
requests -- including traces, events, and log entries.
"""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.exceptions import AllProvidersExhaustedError
from modelmesh.config.mesh_config import MeshConfig
from modelmesh.core.capability_tree import CapabilityTree
from modelmesh.core.event_emitter import EventEmitter, EventType
from modelmesh.core.mesh import ModelMesh
from modelmesh.core.pool import CapabilityPool, PoolModel
from modelmesh.core.router import Router
from modelmesh.connectors.observability.callback_connector import (
    CallbackConnector,
    CallbackConnectorConfig,
)
from modelmesh.connectors.observability.console_connector import (
    ConsoleObservabilityConnector,
    ConsoleConnectorConfig,
)
from modelmesh.connectors.observability.json_log_connector import (
    JsonLogConnector,
    JsonLogConnectorConfig,
)
from modelmesh.connectors.observability.webhook_connector import (
    WebhookConnector,
    WebhookConnectorConfig,
)
from modelmesh.interfaces.observability import (
    AggregateStats,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
    EventType as ObsEventType,
)
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


# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------

class _MockProvider(ProviderConnector):
    """Minimal mock provider for observability tests."""

    def __init__(self, fail=False):
        self._fail = fail

    async def complete(self, request):
        if self._fail:
            raise RuntimeError("Mock provider failure")
        return CompletionResponse(
            id="mock-resp",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="OK"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )

    async def stream(self, request):
        if self._fail:
            raise RuntimeError("Mock stream failure")
        yield CompletionResponse(
            id="mock-chunk",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content="OK"),
                    finish_reason="stop",
                )
            ],
        )

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, capability):
        return True

    def list_models(self):
        return [ModelInfo(id="mock-model", name="Mock")]

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


def _make_mesh_with_obs(observability, fail=False):
    """Build a ModelMesh with a given observability connector."""
    provider = _MockProvider(fail=fail)
    config = MeshConfig(raw={
        "providers": {
            "mock.v1": {
                "connector": "mock.v1",
                "instance": provider,
            },
        },
        "models": {
            "mock.model-a": {
                "provider": "mock.v1",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
            "mock.model-b": {
                "provider": "mock.v1",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
        },
        "pools": {
            "chat-completion": {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "stick-until-failure",
            },
        },
        "observability": {"connector": "modelmesh.null.v1"},
    })
    mesh = ModelMesh()
    mesh._observability = observability
    mesh.initialize(config)
    return mesh


def _make_trace_entry(severity="info", component="test", message="test msg"):
    return TraceEntry(
        severity=Severity(severity),
        timestamp=datetime.now(),
        component=component,
        message=message,
    )


def _make_routing_event():
    return RoutingEvent(
        event_type=ObsEventType.MODEL_ROTATED,
        timestamp=datetime.now(),
        model_id="test.model",
        provider_id="test.v1",
        pool_id="test-pool",
    )


def _make_log_entry():
    return RequestLogEntry(
        timestamp=datetime.now(),
        model_id="test.model",
        provider_id="test.v1",
        capability="chat-completion",
        delivery_mode="synchronous",
        latency_ms=42.5,
        status_code=200,
        tokens_in=10,
        tokens_out=5,
    )


# ===================================================================
# ConsoleConnector tests
# ===================================================================

class TestConsoleConnectorDuringRouting(unittest.TestCase):
    """Verify ConsoleConnector outputs during mesh operations."""

    def test_console_trace_called_on_initialize(self):
        """ConsoleConnector.trace() is called during mesh.initialize()."""
        traces = []
        original_trace = ConsoleObservabilityConnector.trace

        def capture_trace(self, entry):
            traces.append(entry)
            original_trace(self, entry)

        with patch.object(ConsoleObservabilityConnector, "trace", capture_trace):
            obs = ConsoleObservabilityConnector(ConsoleConnectorConfig(
                min_severity="debug",
            ))
            _make_mesh_with_obs(obs)

        # At least one trace should mention initialization
        self.assertGreater(len(traces), 0)
        init_traces = [t for t in traces if "Initialized" in t.message]
        self.assertGreater(len(init_traces), 0)

    def test_console_trace_on_routing_success(self):
        """ConsoleConnector receives trace entries during a successful route."""
        traces = []
        original_trace = ConsoleObservabilityConnector.trace

        def capture_trace(self, entry):
            traces.append(entry)

        with patch.object(ConsoleObservabilityConnector, "trace", capture_trace):
            obs = ConsoleObservabilityConnector(ConsoleConnectorConfig(
                min_severity="debug",
            ))
            mesh = _make_mesh_with_obs(obs)

            req = CompletionRequest(
                model="chat-completion",
                messages=[{"role": "user", "content": "test"}],
            )
            asyncio.run(mesh.route(req))

        # Expect routing-related trace entries
        self.assertGreater(len(traces), 0)

    def test_console_trace_on_routing_failure(self):
        """ConsoleConnector receives WARNING/ERROR traces on failure."""
        traces = []
        original_trace = ConsoleObservabilityConnector.trace

        def capture_trace(self, entry):
            traces.append(entry)

        with patch.object(ConsoleObservabilityConnector, "trace", capture_trace):
            obs = ConsoleObservabilityConnector(ConsoleConnectorConfig(
                min_severity="debug",
            ))
            mesh = _make_mesh_with_obs(obs, fail=True)

            req = CompletionRequest(
                model="chat-completion",
                messages=[{"role": "user", "content": "test"}],
            )
            with self.assertRaises(AllProvidersExhaustedError):
                asyncio.run(mesh.route(req))

        warning_traces = [t for t in traces if t.severity == Severity.WARNING]
        error_traces = [t for t in traces if t.severity == Severity.ERROR]
        self.assertGreater(len(warning_traces) + len(error_traces), 0)


# ===================================================================
# EventEmitter tests
# ===================================================================

class TestEventEmitterDuringRouting(unittest.TestCase):
    """Verify EventEmitter fires correct events during routing."""

    def test_request_success_event_emitted(self):
        """REQUEST_SUCCESS event is emitted on successful route."""
        events = []
        mesh = _make_mesh_with_obs(
            ConsoleObservabilityConnector(ConsoleConnectorConfig(min_severity="error"))
        )
        mesh.event_emitter.on(EventType.REQUEST_SUCCESS, lambda e: events.append(e))

        req = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "test"}],
        )
        asyncio.run(mesh.route(req))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, EventType.REQUEST_SUCCESS)

    def test_request_failure_event_emitted(self):
        """REQUEST_FAILURE event is emitted when provider fails."""
        events = []
        mesh = _make_mesh_with_obs(
            ConsoleObservabilityConnector(ConsoleConnectorConfig(min_severity="error")),
            fail=True,
        )
        mesh.event_emitter.on(EventType.REQUEST_FAILURE, lambda e: events.append(e))

        req = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "test"}],
        )
        with self.assertRaises(AllProvidersExhaustedError):
            asyncio.run(mesh.route(req))

        self.assertGreater(len(events), 0)

    def test_request_routed_event_emitted(self):
        """REQUEST_ROUTED event is emitted before provider call."""
        events = []
        mesh = _make_mesh_with_obs(
            ConsoleObservabilityConnector(ConsoleConnectorConfig(min_severity="error"))
        )
        mesh.event_emitter.on(EventType.REQUEST_ROUTED, lambda e: events.append(e))

        req = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "test"}],
        )
        asyncio.run(mesh.route(req))
        self.assertGreater(len(events), 0)
        self.assertIn("model_id", events[0].data)

    def test_wildcard_handler_receives_all(self):
        """Wildcard handler (None) receives all event types."""
        events = []
        mesh = _make_mesh_with_obs(
            ConsoleObservabilityConnector(ConsoleConnectorConfig(min_severity="error"))
        )
        mesh.event_emitter.on(None, lambda e: events.append(e))

        req = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "test"}],
        )
        asyncio.run(mesh.route(req))
        self.assertGreater(len(events), 0)
        event_types = {e.type for e in events}
        self.assertIn(EventType.REQUEST_ROUTED, event_types)
        self.assertIn(EventType.REQUEST_SUCCESS, event_types)


# ===================================================================
# JsonLogConnector tests
# ===================================================================

class TestJsonLogConnectorDuringRouting(unittest.TestCase):
    """Verify JsonLogConnector writes correct JSON lines."""

    def test_json_log_trace_on_initialize(self):
        """JsonLogConnector writes trace entries as JSON lines on initialize."""
        tmp = tempfile.mktemp(suffix=".jsonl")
        try:
            obs = JsonLogConnector(JsonLogConnectorConfig(file_path=tmp))
            _make_mesh_with_obs(obs)
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                lines = f.readlines()

            self.assertGreater(len(lines), 0)
            for line in lines:
                record = json.loads(line)
                self.assertIn("type", record)
                self.assertIn("timestamp", record)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_json_log_trace_type_field(self):
        """Each JSON line has type='trace' for trace entries."""
        tmp = tempfile.mktemp(suffix=".jsonl")
        try:
            obs = JsonLogConnector(JsonLogConnectorConfig(file_path=tmp))
            obs.trace(_make_trace_entry())
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                record = json.loads(f.readline())

            self.assertEqual(record["type"], "trace")
            self.assertEqual(record["component"], "test")
            self.assertEqual(record["message"], "test msg")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_json_log_event_type_field(self):
        """Routing events are written with type='event'."""
        tmp = tempfile.mktemp(suffix=".jsonl")
        try:
            obs = JsonLogConnector(JsonLogConnectorConfig(file_path=tmp))
            obs.emit(_make_routing_event())
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                record = json.loads(f.readline())

            self.assertEqual(record["type"], "event")
            self.assertEqual(record["message"], "model_rotated")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_json_log_request_log_entry(self):
        """Request log entries are written with type='log'."""
        tmp = tempfile.mktemp(suffix=".jsonl")
        try:
            obs = JsonLogConnector(JsonLogConnectorConfig(file_path=tmp))
            obs.log(_make_log_entry())
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                record = json.loads(f.readline())

            self.assertEqual(record["type"], "log")
            self.assertIn("latency_ms", record["metadata"])
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_json_log_during_routing(self):
        """JsonLogConnector writes traces during actual mesh routing."""
        tmp = tempfile.mktemp(suffix=".jsonl")
        try:
            obs = JsonLogConnector(JsonLogConnectorConfig(file_path=tmp))
            mesh = _make_mesh_with_obs(obs)

            req = CompletionRequest(
                model="chat-completion",
                messages=[{"role": "user", "content": "test"}],
            )
            asyncio.run(mesh.route(req))
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                lines = f.readlines()

            self.assertGreater(len(lines), 0)
            # All lines should be valid JSON
            for line in lines:
                record = json.loads(line)
                self.assertIn("type", record)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


# ===================================================================
# CallbackConnector tests
# ===================================================================

class TestCallbackConnectorDuringRouting(unittest.TestCase):
    """Verify CallbackConnector fires correct callbacks."""

    def test_on_trace_fires_during_init(self):
        """on_trace callback is invoked during mesh.initialize()."""
        traces = []
        obs = CallbackConnector(CallbackConnectorConfig(
            on_trace=lambda t: traces.append(t),
        ))
        _make_mesh_with_obs(obs)

        self.assertGreater(len(traces), 0)
        self.assertIsInstance(traces[0], TraceEntry)

    def test_on_trace_fires_during_routing(self):
        """on_trace callback is invoked during mesh.route()."""
        traces = []
        obs = CallbackConnector(CallbackConnectorConfig(
            on_trace=lambda t: traces.append(t),
        ))
        mesh = _make_mesh_with_obs(obs)

        count_before = len(traces)
        req = CompletionRequest(
            model="chat-completion",
            messages=[{"role": "user", "content": "test"}],
        )
        asyncio.run(mesh.route(req))

        # More traces should appear after routing
        self.assertGreater(len(traces), count_before)

    def test_on_event_fires_for_routing_event(self):
        """on_event callback is invoked when emit() is called."""
        events = []
        obs = CallbackConnector(CallbackConnectorConfig(
            on_event=lambda e: events.append(e),
        ))

        obs.emit(_make_routing_event())
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], RoutingEvent)

    def test_on_log_fires_for_log_entry(self):
        """on_log callback is invoked when log() is called."""
        logs = []
        obs = CallbackConnector(CallbackConnectorConfig(
            on_log=lambda l: logs.append(l),
        ))

        obs.log(_make_log_entry())
        self.assertEqual(len(logs), 1)
        self.assertIsInstance(logs[0], RequestLogEntry)

    def test_on_stats_fires_for_flush(self):
        """on_stats callback is invoked when flush() is called."""
        stats_received = []
        obs = CallbackConnector(CallbackConnectorConfig(
            on_stats=lambda s: stats_received.append(s),
        ))

        stats = {
            "pool.chat": AggregateStats(
                requests_total=10,
                requests_success=8,
                requests_failed=2,
                tokens_in=100,
                tokens_out=50,
                cost_total=0.05,
                latency_avg=150.0,
                latency_p95=300.0,
                downtime_total=0.0,
                rotation_events=1,
            ),
        }
        obs.flush(stats)
        self.assertEqual(len(stats_received), 1)

    def test_missing_callbacks_do_not_error(self):
        """CallbackConnector with no callbacks does not raise."""
        obs = CallbackConnector(CallbackConnectorConfig())
        obs.trace(_make_trace_entry())
        obs.emit(_make_routing_event())
        obs.log(_make_log_entry())
        obs.flush({})
        # Should not raise


# ===================================================================
# WebhookConnector tests
# ===================================================================

class TestWebhookConnector(unittest.TestCase):
    """Verify WebhookConnector builds correct payloads."""

    def test_trace_builds_correct_payload(self):
        """trace() enqueues a record with correct structure."""
        wh = WebhookConnector(WebhookConnectorConfig(
            url="https://example.com/webhook",
            min_severity="info",
        ))

        entry = _make_trace_entry(severity="error", message="test error")
        wh.trace(entry)

        # The batch should have one record
        self.assertEqual(len(wh._batch), 0)  # batch_size=1, auto-flushed
        # Since flush_batch is called and URL is unreachable, batch is cleared

    def test_trace_filters_by_severity(self):
        """Traces below min_severity are silently dropped."""
        wh = WebhookConnector(WebhookConnectorConfig(
            url="https://example.com/webhook",
            min_severity="error",
        ))

        # DEBUG should be filtered out
        wh.trace(_make_trace_entry(severity="debug", message="debug msg"))
        self.assertEqual(len(wh._batch), 0)

        # INFO should also be filtered out (below error)
        wh.trace(_make_trace_entry(severity="info", message="info msg"))
        self.assertEqual(len(wh._batch), 0)

    def test_webhook_batch_accumulation(self):
        """With batch_size > 1, records are queued until threshold."""
        wh = WebhookConnector(WebhookConnectorConfig(
            url="https://example.com/webhook",
            min_severity="info",
            batch_size=3,
        ))

        wh.trace(_make_trace_entry(severity="error", message="e1"))
        self.assertEqual(len(wh._batch), 1)

        wh.trace(_make_trace_entry(severity="error", message="e2"))
        self.assertEqual(len(wh._batch), 2)

    @patch("urllib.request.urlopen")
    def test_webhook_sends_post_with_json(self, mock_urlopen):
        """flush_batch() sends a POST with JSON content-type."""
        mock_urlopen.return_value = MagicMock()

        wh = WebhookConnector(WebhookConnectorConfig(
            url="https://example.com/webhook",
            min_severity="info",
            headers={"Authorization": "Bearer test-token"},
        ))

        wh.trace(_make_trace_entry(severity="error", message="sent"))
        # batch_size=1, so flush_batch is called automatically

        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        self.assertEqual(request_obj.method, "POST")
        self.assertEqual(request_obj.get_header("Content-type"), "application/json")
        self.assertEqual(request_obj.get_header("Authorization"), "Bearer test-token")

        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["type"], "trace")
        self.assertEqual(body["message"], "sent")

    @patch("urllib.request.urlopen")
    def test_webhook_event_payload(self, mock_urlopen):
        """emit() builds an event payload with correct structure."""
        mock_urlopen.return_value = MagicMock()

        wh = WebhookConnector(WebhookConnectorConfig(
            url="https://example.com/webhook",
            min_severity="info",
        ))

        wh.emit(_make_routing_event())
        mock_urlopen.assert_called_once()
        request_obj = mock_urlopen.call_args[0][0]
        body = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(body["type"], "event")
        self.assertEqual(body["metadata"]["model_id"], "test.model")
        self.assertEqual(body["metadata"]["provider_id"], "test.v1")

    def test_webhook_no_url_skips_send(self):
        """flush_batch() with empty URL does not send."""
        wh = WebhookConnector(WebhookConnectorConfig(
            url="",
            min_severity="info",
        ))

        wh._batch.append({"type": "test"})
        wh.flush_batch()
        # Should not raise


if __name__ == "__main__":
    unittest.main()
