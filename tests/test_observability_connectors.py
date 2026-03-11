"""Tests for webhook, JSON log, and callback observability connectors."""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from datetime import datetime, timezone

from modelmesh.interfaces.observability import (
    AggregateStats,
    EventType,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)
from modelmesh.connectors.observability.webhook_connector import (
    WebhookConnector,
    WebhookConnectorConfig,
)
from modelmesh.connectors.observability.json_log_connector import (
    JsonLogConnector,
    JsonLogConnectorConfig,
)
from modelmesh.connectors.observability.callback_connector import (
    CallbackConnector,
    CallbackConnectorConfig,
)


def _make_trace(severity=Severity.ERROR, message="test trace"):
    """Create a TraceEntry for testing."""
    return TraceEntry(
        severity=severity,
        timestamp=datetime.now(tz=timezone.utc),
        component="test.component",
        message=message,
    )


def _make_event():
    """Create a RoutingEvent for testing."""
    return RoutingEvent(
        event_type=EventType.MODEL_ACTIVATED,
        timestamp=datetime.now(tz=timezone.utc),
        model_id="test.model",
        provider_id="test.v1",
        pool_id="chat-completion",
    )


def _make_log_entry(error=None):
    """Create a RequestLogEntry for testing."""
    return RequestLogEntry(
        timestamp=datetime.now(tz=timezone.utc),
        model_id="test.model",
        provider_id="test.v1",
        capability="chat",
        delivery_mode="synchronous",
        latency_ms=150.0,
        status_code=200,
        tokens_in=100,
        tokens_out=50,
        cost=0.01,
        error=error,
    )


def _make_stats():
    """Create an AggregateStats dict for testing."""
    return {
        "pool.chat": AggregateStats(
            requests_total=100,
            requests_success=95,
            requests_failed=5,
            tokens_in=10000,
            tokens_out=5000,
            cost_total=1.50,
            latency_avg=120.0,
            latency_p95=250.0,
            downtime_total=5.0,
            rotation_events=2,
        )
    }


class TestWebhookObservabilityConnector:
    """Test webhook observability connector."""

    def test_connector_id(self):
        """Connector ID matches expected pattern."""
        assert WebhookConnector.CONNECTOR_ID == "modelmesh.webhook.v1"

    def test_creates_with_config(self):
        """Can instantiate with url and optional headers."""
        config = WebhookConnectorConfig(
            url="https://hooks.example.com/webhook",
            headers={"Authorization": "Bearer token"},
        )
        connector = WebhookConnector(config)
        assert connector._config.url == "https://hooks.example.com/webhook"
        assert connector._config.headers["Authorization"] == "Bearer token"

    def test_creates_with_default_config(self):
        """Default config has empty URL and POST method."""
        connector = WebhookConnector()
        assert connector._config.url == ""
        assert connector._config.method == "POST"

    def test_on_event_queues_event(self):
        """Events are queued for batch delivery when batch_size > 1."""
        config = WebhookConnectorConfig(
            url="https://hooks.example.com/webhook",
            batch_size=10,
            min_severity="debug",
        )
        connector = WebhookConnector(config)
        trace = _make_trace(severity=Severity.ERROR)
        connector.trace(trace)

        # The record should be in the batch queue
        assert len(connector._batch) == 1

    def test_event_format(self):
        """Events are formatted as expected JSON structure."""
        config = WebhookConnectorConfig(
            url="https://hooks.example.com/webhook",
            batch_size=10,
            min_severity="debug",
        )
        connector = WebhookConnector(config)
        trace = _make_trace(severity=Severity.ERROR, message="error occurred")
        connector.trace(trace)

        record = connector._batch[0]
        assert record["type"] == "trace"
        assert record["severity"] == "error"
        assert record["component"] == "test.component"
        assert record["message"] == "error occurred"
        assert "timestamp" in record

    def test_severity_filtering(self):
        """Events below min_severity are dropped."""
        config = WebhookConnectorConfig(
            url="https://hooks.example.com/webhook",
            batch_size=10,
            min_severity="error",
        )
        connector = WebhookConnector(config)

        # DEBUG and INFO should be filtered out
        connector.trace(_make_trace(severity=Severity.DEBUG))
        connector.trace(_make_trace(severity=Severity.INFO))
        assert len(connector._batch) == 0

        # ERROR and CRITICAL should pass through
        connector.trace(_make_trace(severity=Severity.ERROR))
        connector.trace(_make_trace(severity=Severity.CRITICAL))
        assert len(connector._batch) == 2

    def test_flush_batch_with_empty_url(self):
        """flush_batch does nothing when URL is empty."""
        connector = WebhookConnector(WebhookConnectorConfig(url=""))
        connector._batch = [{"type": "test"}]
        connector.flush_batch()
        # Batch should remain (no URL to send to, so nothing happens
        # except the batch being cleared... actually checking the code:
        # flush_batch returns early if not self._batch or not self._config.url
        # Since url is empty, it returns early, batch stays
        assert len(connector._batch) == 1

    def test_log_entry_with_error(self):
        """Log entries with errors use error severity."""
        config = WebhookConnectorConfig(
            url="https://hooks.example.com/webhook",
            batch_size=10,
            min_severity="error",
        )
        connector = WebhookConnector(config)
        entry = _make_log_entry(error="Connection refused")
        connector.log(entry)
        assert len(connector._batch) == 1
        assert connector._batch[0]["severity"] == "error"

    def test_flush_writes_stats(self):
        """Stats are queued properly."""
        config = WebhookConnectorConfig(
            url="https://hooks.example.com/webhook",
            batch_size=100,
            min_severity="debug",
        )
        connector = WebhookConnector(config)
        connector.flush(_make_stats())
        assert len(connector._batch) == 1
        assert connector._batch[0]["type"] == "stats"


class TestJsonLogObservabilityConnector:
    """Test JSON log observability connector."""

    def setup_method(self):
        """Create a temporary file for each test."""
        self.tmp = tempfile.mktemp(suffix=".jsonl")

    def teardown_method(self):
        """Clean up temporary files."""
        for path in [self.tmp, self.tmp + ".1"]:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def test_connector_id(self):
        """Connector ID is modelmesh.json-log.v1."""
        assert JsonLogConnector.CONNECTOR_ID == "modelmesh.json-log.v1"

    def test_creates_with_defaults(self):
        """Default config uses default file path."""
        config = JsonLogConnectorConfig(file_path=self.tmp)
        connector = JsonLogConnector(config)
        assert connector._config.file_path == self.tmp
        connector.close()

    def test_formats_event_as_json(self):
        """Events are written as JSON lines."""
        config = JsonLogConnectorConfig(file_path=self.tmp)
        connector = JsonLogConnector(config)
        connector.trace(_make_trace(severity=Severity.ERROR, message="json test"))
        connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            line = f.readline().strip()
        data = json.loads(line)
        assert data["type"] == "trace"
        assert data["message"] == "json test"

    def test_includes_timestamp(self):
        """Events include ISO timestamp."""
        config = JsonLogConnectorConfig(file_path=self.tmp)
        connector = JsonLogConnector(config)
        connector.trace(_make_trace())
        connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())
        assert "timestamp" in data
        # Verify it's parseable as ISO format
        datetime.fromisoformat(data["timestamp"])

    def test_writes_multiple_lines(self):
        """Multiple events produce multiple JSON lines."""
        config = JsonLogConnectorConfig(file_path=self.tmp)
        connector = JsonLogConnector(config)
        connector.trace(_make_trace(message="line 1"))
        connector.trace(_make_trace(message="line 2"))
        connector.trace(_make_trace(message="line 3"))
        connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        assert len(lines) == 3

    def test_emit_writes_routing_event(self):
        """Routing events are written as JSON lines."""
        config = JsonLogConnectorConfig(file_path=self.tmp)
        connector = JsonLogConnector(config)
        connector.emit(_make_event())
        connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())
        assert data["type"] == "event"
        assert data["message"] == "model_activated"

    def test_log_writes_request_entry(self):
        """Request log entries are written as JSON lines."""
        config = JsonLogConnectorConfig(file_path=self.tmp)
        connector = JsonLogConnector(config)
        connector.log(_make_log_entry())
        connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())
        assert data["type"] == "log"
        assert data["metadata"]["model_id"] == "test.model"

    def test_flush_writes_stats(self):
        """Aggregate stats are written as JSON lines."""
        config = JsonLogConnectorConfig(file_path=self.tmp)
        connector = JsonLogConnector(config)
        connector.flush(_make_stats())
        connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())
        assert data["type"] == "stats"
        assert data["metadata"]["requests_total"] == 100

    def test_append_mode(self):
        """Append mode adds to existing file."""
        with open(self.tmp, "w", encoding="utf-8") as f:
            f.write('{"existing": true}\n')

        config = JsonLogConnectorConfig(file_path=self.tmp, append=True)
        connector = JsonLogConnector(config)
        connector.trace(_make_trace())
        connector.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_close(self):
        """close() closes the output file."""
        config = JsonLogConnectorConfig(file_path=self.tmp)
        connector = JsonLogConnector(config)
        connector.close()
        assert connector._file.closed


class TestCallbackObservabilityConnector:
    """Test callback-based observability."""

    def test_connector_id(self):
        """Connector ID matches."""
        assert CallbackConnector.CONNECTOR_ID == "modelmesh.callback.v1"

    def test_callback_invoked_on_trace(self):
        """Registered on_trace callback is called for each trace."""
        traces = []
        connector = CallbackConnector(CallbackConnectorConfig(
            on_trace=lambda t: traces.append(t),
        ))
        trace = _make_trace()
        connector.trace(trace)
        assert len(traces) == 1
        assert traces[0] is trace

    def test_callback_invoked_on_event(self):
        """Registered on_event callback is called for each event."""
        events = []
        connector = CallbackConnector(CallbackConnectorConfig(
            on_event=lambda e: events.append(e),
        ))
        event = _make_event()
        connector.emit(event)
        assert len(events) == 1
        assert events[0] is event

    def test_callback_invoked_on_log(self):
        """Registered on_log callback is called for each log entry."""
        logs = []
        connector = CallbackConnector(CallbackConnectorConfig(
            on_log=lambda l: logs.append(l),
        ))
        entry = _make_log_entry()
        connector.log(entry)
        assert len(logs) == 1
        assert logs[0] is entry

    def test_callback_invoked_on_stats(self):
        """Registered on_stats callback is called for stats flushes."""
        stats_list = []
        connector = CallbackConnector(CallbackConnectorConfig(
            on_stats=lambda s: stats_list.append(s),
        ))
        stats = _make_stats()
        connector.flush(stats)
        assert len(stats_list) == 1
        assert stats_list[0] is stats

    def test_multiple_callbacks(self):
        """Multiple callback types all receive events independently."""
        traces = []
        events = []
        logs = []
        connector = CallbackConnector(CallbackConnectorConfig(
            on_trace=lambda t: traces.append(t),
            on_event=lambda e: events.append(e),
            on_log=lambda l: logs.append(l),
        ))

        connector.trace(_make_trace())
        connector.emit(_make_event())
        connector.log(_make_log_entry())

        assert len(traces) == 1
        assert len(events) == 1
        assert len(logs) == 1

    def test_no_callback_is_noop(self):
        """When no callback is registered, methods are no-ops."""
        connector = CallbackConnector(CallbackConnectorConfig())
        # These should all execute without error
        connector.trace(_make_trace())
        connector.emit(_make_event())
        connector.log(_make_log_entry())
        connector.flush(_make_stats())

    def test_default_config(self):
        """Default config has all callbacks as None."""
        connector = CallbackConnector()
        # Should not raise
        connector.trace(_make_trace())
        connector.emit(_make_event())
        connector.log(_make_log_entry())
        connector.flush(_make_stats())
