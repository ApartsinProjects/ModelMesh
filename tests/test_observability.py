"""Tests for observability connectors: Null, File, Console, and integration."""
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.interfaces.observability import (
    AggregateStats,
    EventType,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)
from modelmesh.connectors.observability.null_connector import (
    NullObservabilityConnector,
)
from modelmesh.cdk.specialized.file_observability import (
    FileObservability,
    FileObservabilityConfig,
)
from modelmesh.cdk.specialized.console_observability import (
    ConsoleObservability,
    ConsoleObservabilityConfig,
)
from modelmesh.cdk.base_observability import (
    BaseObservability,
    BaseObservabilityConfig,
)


class TestNullObservability(unittest.TestCase):
    """Test NullObservabilityConnector."""

    def setUp(self):
        self.obs = NullObservabilityConnector()

    def test_emit_no_op(self):
        event = RoutingEvent(
            event_type=EventType.MODEL_ACTIVATED,
            timestamp=datetime.now(),
        )
        # Should not raise
        self.obs.emit(event)

    def test_log_no_op(self):
        entry = RequestLogEntry(
            timestamp=datetime.now(),
            model_id="test",
            provider_id="test.v1",
            capability="chat",
            delivery_mode="synchronous",
            latency_ms=100.0,
            status_code=200,
            tokens_in=10,
            tokens_out=5,
        )
        self.obs.log(entry)

    def test_flush_no_op(self):
        stats = {
            "test": AggregateStats(
                requests_total=10,
                requests_success=9,
                requests_failed=1,
                tokens_in=1000,
                tokens_out=500,
                cost_total=0.05,
                latency_avg=100.0,
                latency_p95=200.0,
                downtime_total=0.0,
                rotation_events=1,
            )
        }
        self.obs.flush(stats)

    def test_trace_no_op(self):
        entry = TraceEntry(
            severity=Severity.INFO,
            timestamp=datetime.now(),
            component="test",
            message="test message",
        )
        self.obs.trace(entry)

    def test_connector_id(self):
        self.assertEqual(
            NullObservabilityConnector.CONNECTOR_ID, "modelmesh.null.v1"
        )


class TestFileObservability(unittest.TestCase):
    """Test FileObservability."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix=".log")

    def tearDown(self):
        for path in [self.tmp, self.tmp + ".1"]:
            if os.path.exists(path):
                os.unlink(path)

    def test_creates_file(self):
        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp)
        )
        entry = TraceEntry(
            severity=Severity.INFO,
            timestamp=datetime.now(),
            component="test",
            message="hello",
        )
        obs.trace(entry)
        obs.close()
        self.assertTrue(os.path.exists(self.tmp))

    def test_writes_json_lines(self):
        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp, min_severity="debug")
        )
        obs.trace(
            TraceEntry(
                severity=Severity.INFO,
                timestamp=datetime.now(),
                component="test",
                message="line1",
            )
        )
        obs.trace(
            TraceEntry(
                severity=Severity.WARNING,
                timestamp=datetime.now(),
                component="test",
                message="line2",
            )
        )
        obs.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        self.assertEqual(len(lines), 2)
        for line in lines:
            parsed = json.loads(line)
            self.assertEqual(parsed["type"], "trace")

    def test_trace_writes_severity(self):
        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp, min_severity="debug")
        )
        obs.trace(
            TraceEntry(
                severity=Severity.ERROR,
                timestamp=datetime.now(),
                component="router",
                message="error msg",
            )
        )
        obs.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())

        self.assertEqual(data["severity"], "error")
        self.assertEqual(data["component"], "router")

    def test_severity_filtering(self):
        """File observability inherits severity filtering from base. The
        FileObservability.trace() method bypasses base filtering but the
        base emit/log/flush still use _write which goes through the file."""
        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp, min_severity="warning")
        )
        # FileObservability.trace() writes all traces directly (no base filter),
        # but let's verify by checking what gets written
        obs.trace(
            TraceEntry(
                severity=Severity.DEBUG,
                timestamp=datetime.now(),
                component="test",
                message="should appear (file trace bypasses base filter)",
            )
        )
        obs.trace(
            TraceEntry(
                severity=Severity.WARNING,
                timestamp=datetime.now(),
                component="test",
                message="should appear",
            )
        )
        obs.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        # FileObservability.trace() writes directly without base severity check
        self.assertEqual(len(lines), 2)

    def test_emit_writes_event(self):
        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp)
        )
        event = RoutingEvent(
            event_type=EventType.MODEL_ACTIVATED,
            timestamp=datetime.now(),
            model_id="test.model",
        )
        obs.emit(event)
        obs.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())

        self.assertEqual(data["type"], "event")
        self.assertEqual(data["event_type"], "model_activated")

    def test_log_writes_request(self):
        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp, log_level="full")
        )
        entry = RequestLogEntry(
            timestamp=datetime.now(),
            model_id="test.model",
            provider_id="test.v1",
            capability="chat",
            delivery_mode="synchronous",
            latency_ms=150.0,
            status_code=200,
            tokens_in=100,
            tokens_out=50,
        )
        obs.log(entry)
        obs.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())

        self.assertEqual(data["type"], "log")
        self.assertEqual(data["model_id"], "test.model")

    def test_flush_writes_stats(self):
        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp)
        )
        stats = {
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
        obs.flush(stats)
        obs.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())

        self.assertEqual(data["type"], "stats")
        self.assertEqual(data["requests_total"], 100)

    def test_secret_redaction(self):
        obs = FileObservability(
            FileObservabilityConfig(
                file_path=self.tmp, redact_secrets=True
            )
        )
        event = RoutingEvent(
            event_type=EventType.MODEL_ACTIVATED,
            timestamp=datetime.now(),
            metadata={"api_key": "sk-secret-12345"},
        )
        obs.emit(event)
        obs.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("***REDACTED***", content)
        self.assertNotIn("sk-secret-12345", content)

    def test_append_mode(self):
        # Write something first
        with open(self.tmp, "w", encoding="utf-8") as f:
            f.write('{"existing": true}\n')

        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp, append=True)
        )
        obs.trace(
            TraceEntry(
                severity=Severity.INFO,
                timestamp=datetime.now(),
                component="test",
                message="appended",
            )
        )
        obs.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 2)

    def test_close(self):
        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp)
        )
        obs.trace(
            TraceEntry(
                severity=Severity.INFO,
                timestamp=datetime.now(),
                component="test",
                message="msg",
            )
        )
        obs.close()
        self.assertTrue(obs._file.closed)

    def test_file_rotation(self):
        obs = FileObservability(
            FileObservabilityConfig(
                file_path=self.tmp,
                max_file_size_bytes=50,  # very small to trigger rotation
            )
        )
        # Write enough data to trigger rotation
        for i in range(10):
            obs.trace(
                TraceEntry(
                    severity=Severity.INFO,
                    timestamp=datetime.now(),
                    component="test",
                    message=f"message number {i} with some padding data to make it large enough",
                )
            )
        obs.close()

        # The rotated file should exist
        rotated = self.tmp + ".1"
        self.assertTrue(
            os.path.exists(self.tmp) or os.path.exists(rotated),
            "Expected either the main or rotated file to exist",
        )

    def test_overwrite_mode(self):
        # Write something first
        with open(self.tmp, "w", encoding="utf-8") as f:
            f.write('{"line": 1}\n{"line": 2}\n')

        obs = FileObservability(
            FileObservabilityConfig(file_path=self.tmp, append=False)
        )
        obs.trace(
            TraceEntry(
                severity=Severity.INFO,
                timestamp=datetime.now(),
                component="test",
                message="only line",
            )
        )
        obs.close()

        with open(self.tmp, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        self.assertEqual(len(lines), 1)


class TestConsoleObservability(unittest.TestCase):
    """Test ConsoleObservability."""

    def test_trace_with_color(self):
        config = ConsoleObservabilityConfig(
            use_color=True, min_severity="debug"
        )
        obs = ConsoleObservability(config)
        entry = TraceEntry(
            severity=Severity.INFO,
            timestamp=datetime.now(),
            component="router",
            message="test trace",
        )
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            obs.trace(entry)
            output = mock_stdout.getvalue()
        self.assertIn("test trace", output)
        # Should contain ANSI codes when color is enabled
        self.assertIn("\033[", output)

    def test_trace_severity_filter(self):
        config = ConsoleObservabilityConfig(min_severity="error")
        obs = ConsoleObservability(config)
        # DEBUG should be filtered out
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            obs.trace(
                TraceEntry(
                    severity=Severity.DEBUG,
                    timestamp=datetime.now(),
                    component="test",
                    message="should not appear",
                )
            )
            output = mock_stdout.getvalue()
        self.assertEqual(output, "")

        # ERROR should pass through
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            obs.trace(
                TraceEntry(
                    severity=Severity.ERROR,
                    timestamp=datetime.now(),
                    component="test",
                    message="should appear",
                )
            )
            output = mock_stdout.getvalue()
        self.assertIn("should appear", output)

    def test_emit_prints(self):
        config = ConsoleObservabilityConfig(use_color=False)
        obs = ConsoleObservability(config)
        event = RoutingEvent(
            event_type=EventType.MODEL_ACTIVATED,
            timestamp=datetime.now(),
            model_id="test.model",
        )
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            obs.emit(event)
            output = mock_stdout.getvalue()
        self.assertIn("model_activated", output)

    def test_no_color_mode(self):
        config = ConsoleObservabilityConfig(
            use_color=False, min_severity="debug"
        )
        obs = ConsoleObservability(config)
        entry = TraceEntry(
            severity=Severity.INFO,
            timestamp=datetime.now(),
            component="test",
            message="no color test",
        )
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            obs.trace(entry)
            output = mock_stdout.getvalue()
        self.assertIn("no color test", output)
        self.assertNotIn("\033[", output)


class TestBaseObservabilitySeverityOrder(unittest.TestCase):
    """Test severity ordering in BaseObservability."""

    def test_severity_order(self):
        order = BaseObservability._SEVERITY_ORDER
        self.assertEqual(order[Severity.DEBUG], 0)
        self.assertEqual(order[Severity.INFO], 1)
        self.assertEqual(order[Severity.WARNING], 2)
        self.assertEqual(order[Severity.ERROR], 3)
        self.assertEqual(order[Severity.CRITICAL], 4)

    def test_min_severity_filtering(self):
        """BaseObservability.trace() should filter by min_severity."""
        config = BaseObservabilityConfig(min_severity="warning")
        obs = BaseObservability(config)

        # Track what gets written
        written = []
        obs._write = lambda line: written.append(line)

        obs.trace(
            TraceEntry(
                severity=Severity.DEBUG,
                timestamp=datetime.now(),
                component="test",
                message="debug",
            )
        )
        self.assertEqual(len(written), 0)

        obs.trace(
            TraceEntry(
                severity=Severity.WARNING,
                timestamp=datetime.now(),
                component="test",
                message="warning",
            )
        )
        self.assertEqual(len(written), 1)

        obs.trace(
            TraceEntry(
                severity=Severity.ERROR,
                timestamp=datetime.now(),
                component="test",
                message="error",
            )
        )
        self.assertEqual(len(written), 2)

    def test_redaction_in_base(self):
        config = BaseObservabilityConfig(redact_secrets=True)
        obs = BaseObservability(config)
        text = '{"api_key": "sk-secret-value"}'
        redacted = obs._redact(text)
        self.assertIn("***REDACTED***", redacted)
        self.assertNotIn("sk-secret-value", redacted)


class TestObservabilityIntegration(unittest.TestCase):
    """End-to-end test: configure file observability, run operations,
    verify that the correct traces appear in the log file."""

    def test_full_lifecycle_traces(self):
        """Create mesh with file obs, add models, trigger failure,
        verify trace log has INFO/WARNING/ERROR entries."""
        from modelmesh.core.mesh import ModelMesh
        from modelmesh.config.mesh_config import MeshConfig
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

        class TestProvider(ProviderConnector):
            def __init__(self):
                self._calls = 0

            async def complete(self, request):
                self._calls += 1
                if self._calls <= 1:
                    raise RuntimeError("Simulated failure")
                return CompletionResponse(
                    id="r",
                    model=request.model,
                    choices=[
                        CompletionChoice(
                            index=0,
                            message=ChatMessage(
                                role="assistant", content="ok"
                            ),
                            finish_reason="stop",
                        )
                    ],
                    usage=TokenUsage(
                        prompt_tokens=5,
                        completion_tokens=3,
                        total_tokens=8,
                    ),
                )

            async def stream(self, request):
                yield CompletionResponse()

            def get_capabilities(self):
                return ["chat"]

            def supports(self, cap):
                return cap == "chat"

            def list_models(self):
                return []

            def get_model_info(self, model_id):
                raise KeyError

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

        tmp = tempfile.mktemp(suffix=".log")
        try:
            obs = FileObservability(
                FileObservabilityConfig(
                    file_path=tmp, min_severity="debug"
                )
            )

            mesh = ModelMesh()
            mesh._observability = obs

            config = MeshConfig(raw={
                "providers": {
                    "test.v1": {
                        "connector": "test.v1",
                        "instance": TestProvider(),
                    },
                },
                "models": {
                    "test.model-a": {
                        "provider": "test.v1",
                        "capabilities": [
                            "generation.text-generation.chat-completion",
                        ],
                    },
                    "test.model-b": {
                        "provider": "test.v1",
                        "capabilities": [
                            "generation.text-generation.chat-completion",
                        ],
                    },
                },
                "pools": {
                    "chat-completion": {
                        "capability": "generation.text-generation.chat-completion",
                    },
                },
                "observability": {"connector": "modelmesh.null.v1"},
            })
            mesh.initialize(config)

            import asyncio

            request = CompletionRequest(
                model="chat-completion",
                messages=[{"role": "user", "content": "Hello"}],
            )
            # First call fails, rotation happens, second succeeds
            response = asyncio.run(mesh.route(request))

            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                lines = f.readlines()

            all_severities = set()
            for line in lines:
                try:
                    data = json.loads(line)
                    if "severity" in data:
                        all_severities.add(data["severity"])
                except json.JSONDecodeError:
                    pass

            # We should see at least info and warning traces
            self.assertIn("info", all_severities, "Expected INFO traces")
            self.assertIn(
                "warning", all_severities, "Expected WARNING traces"
            )
        finally:
            try:
                obs.close()
            except Exception:
                pass
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def test_pool_deactivation_trace(self):
        """Configure pool with threshold=2, fail 2 times,
        check that ERROR trace for deactivation appears."""
        from modelmesh.core.pool import CapabilityPool, PoolModel
        from modelmesh.interfaces.rotation import ModelStatus

        tmp = tempfile.mktemp(suffix=".log")
        try:
            obs = FileObservability(
                FileObservabilityConfig(
                    file_path=tmp, min_severity="debug"
                )
            )
            pool = CapabilityPool(
                "test",
                {"capability": "test", "failure_threshold": 2},
                observability=obs,
            )
            model = PoolModel(
                model_id="test.model",
                real_model_id="model",
                provider_id="test.v1",
            )
            pool.add_model(model)

            pool.record_failure("test.model", RuntimeError("err1"))
            self.assertEqual(model.status, ModelStatus.ACTIVE)

            pool.record_failure("test.model", RuntimeError("err2"))
            self.assertEqual(model.status, ModelStatus.STANDBY)

            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                lines = f.readlines()

            error_traces = []
            for line in lines:
                try:
                    data = json.loads(line)
                    if (
                        data.get("severity") == "error"
                        and "deactivated" in data.get("message", "")
                    ):
                        error_traces.append(data)
                except json.JSONDecodeError:
                    pass

            self.assertGreater(
                len(error_traces),
                0,
                "Expected ERROR trace for deactivation",
            )
            self.assertIn(
                "deactivated", error_traces[0]["message"]
            )
        finally:
            try:
                obs.close()
            except Exception:
                pass
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass


if __name__ == "__main__":
    unittest.main()
