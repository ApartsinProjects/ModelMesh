"""Tests for newly added connectors: secret stores, observability, and storage.

Covers all 8 new connectors:
  - DotenvSecretStore (modelmesh.dotenv.v1)
  - JsonSecretStore (modelmesh.json-secrets.v1)
  - KeyringSecretStore (modelmesh.keyring.v1)
  - JsonLogConnector (modelmesh.json-log.v1)
  - WebhookConnector (modelmesh.webhook.v1)
  - CallbackConnector (modelmesh.callback.v1)
  - SqliteStorage (modelmesh.sqlite.v1)
  - MemoryStorage (modelmesh.memory.v1)
"""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.connectors import CONNECTOR_REGISTRY

# Secret stores
from modelmesh.connectors.secret_stores.dotenv_store import (
    DotenvSecretStore,
    DotenvSecretStoreConfig,
)
from modelmesh.connectors.secret_stores.json_store import (
    JsonSecretStore,
    JsonSecretStoreConfig,
)
from modelmesh.connectors.secret_stores.keyring_store import (
    KeyringSecretStore,
    KeyringSecretStoreConfig,
)

# Observability
from modelmesh.connectors.observability.json_log_connector import (
    JsonLogConnector,
    JsonLogConnectorConfig,
)
from modelmesh.connectors.observability.webhook_connector import (
    WebhookConnector,
    WebhookConnectorConfig,
)
from modelmesh.connectors.observability.callback_connector import (
    CallbackConnector,
    CallbackConnectorConfig,
)

# Storage
from modelmesh.connectors.storage.sqlite_storage import (
    SqliteStorage,
    SqliteStorageConfig,
)
from modelmesh.connectors.storage.memory_storage import MemoryStorage

# Data types
from modelmesh.interfaces.observability import (
    AggregateStats,
    EventType,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)
from modelmesh.interfaces.storage import StorageEntry


def _run(coro):
    """Helper to run async coroutines in sync tests."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_trace(
    severity=Severity.ERROR,
    component="test",
    message="test trace",
) -> TraceEntry:
    return TraceEntry(
        severity=severity,
        timestamp=datetime(2025, 1, 15, 12, 0, 0),
        component=component,
        message=message,
        metadata={"key": "value"},
    )


def _make_event() -> RoutingEvent:
    return RoutingEvent(
        event_type=EventType.MODEL_ACTIVATED,
        timestamp=datetime(2025, 1, 15, 12, 0, 0),
        model_id="gpt-4o",
        provider_id="openai",
    )


def _make_log_entry(error=None) -> RequestLogEntry:
    return RequestLogEntry(
        timestamp=datetime(2025, 1, 15, 12, 0, 0),
        model_id="gpt-4o",
        provider_id="openai",
        capability="chat-completion",
        delivery_mode="sync",
        latency_ms=123.4,
        status_code=200,
        tokens_in=10,
        tokens_out=20,
        error=error,
    )


def _make_stats() -> dict[str, AggregateStats]:
    return {
        "openai": AggregateStats(
            requests_total=100,
            requests_success=95,
            requests_failed=5,
            tokens_in=1000,
            tokens_out=2000,
            cost_total=1.50,
            latency_avg=120.0,
            latency_p95=250.0,
            downtime_total=0.0,
            rotation_events=2,
        )
    }


def _make_storage_entry(key="test-key", data=b"hello world"):
    return StorageEntry(key=key, data=data, metadata={"format": "raw"})


# ===================================================================
# Secret Store Tests
# ===================================================================


class TestDotenvSecretStore(unittest.TestCase):
    """Tests for the dotenv file secret store."""

    def test_connector_id(self):
        self.assertEqual(DotenvSecretStore.CONNECTOR_ID, "modelmesh.dotenv.v1")

    def test_default_config(self):
        config = DotenvSecretStoreConfig()
        self.assertEqual(config.file_path, ".env")
        self.assertFalse(config.override_env)

    def test_parse_simple_values(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("API_KEY=sk-test-123\n")
            f.write("DB_HOST=localhost\n")
            f.write("DB_PORT=5432\n")
            f.name
        try:
            config = DotenvSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = DotenvSecretStore(config)
            self.assertEqual(store.get("API_KEY"), "sk-test-123")
            self.assertEqual(store.get("DB_HOST"), "localhost")
            self.assertEqual(store.get("DB_PORT"), "5432")
        finally:
            os.unlink(f.name)

    def test_parse_comments_and_blank_lines(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("# This is a comment\n")
            f.write("\n")
            f.write("KEY1=value1\n")
            f.write("  # Indented comment\n")
            f.write("KEY2=value2\n")
        try:
            config = DotenvSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = DotenvSecretStore(config)
            self.assertEqual(store.get("KEY1"), "value1")
            self.assertEqual(store.get("KEY2"), "value2")
        finally:
            os.unlink(f.name)

    def test_parse_quoted_values(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write('DOUBLE="hello world"\n')
            f.write("SINGLE='goodbye world'\n")
        try:
            config = DotenvSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = DotenvSecretStore(config)
            self.assertEqual(store.get("DOUBLE"), "hello world")
            self.assertEqual(store.get("SINGLE"), "goodbye world")
        finally:
            os.unlink(f.name)

    def test_parse_multiline_backslash(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("MULTI=line1\\\n")
            f.write("line2\n")
            f.write("OTHER=simple\n")
        try:
            config = DotenvSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = DotenvSecretStore(config)
            self.assertEqual(store.get("MULTI"), "line1line2")
            self.assertEqual(store.get("OTHER"), "simple")
        finally:
            os.unlink(f.name)

    def test_parse_inline_comment(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("KEY=value # this is a comment\n")
        try:
            config = DotenvSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = DotenvSecretStore(config)
            self.assertEqual(store.get("KEY"), "value")
        finally:
            os.unlink(f.name)

    @patch.dict(os.environ, {"MY_VAR": "from_env"}, clear=False)
    def test_env_takes_precedence_by_default(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("MY_VAR=from_file\n")
        try:
            config = DotenvSecretStoreConfig(
                file_path=f.name, override_env=False
            )
            store = DotenvSecretStore(config)
            self.assertEqual(store.get("MY_VAR"), "from_env")
        finally:
            os.unlink(f.name)

    @patch.dict(os.environ, {"MY_VAR": "from_env"}, clear=False)
    def test_override_env(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("MY_VAR=from_file\n")
        try:
            config = DotenvSecretStoreConfig(
                file_path=f.name, override_env=True
            )
            store = DotenvSecretStore(config)
            self.assertEqual(store.get("MY_VAR"), "from_file")
        finally:
            os.unlink(f.name)

    def test_missing_file_returns_empty(self):
        config = DotenvSecretStoreConfig(
            file_path="/nonexistent/.env", fail_on_missing=False
        )
        store = DotenvSecretStore(config)
        self.assertEqual(store.get("ANY_KEY"), "")

    def test_missing_key_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("EXISTING=yes\n")
        try:
            config = DotenvSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = DotenvSecretStore(config)
            with self.assertRaises(KeyError):
                store.get("NONEXISTENT")
        finally:
            os.unlink(f.name)


class TestJsonSecretStore(unittest.TestCase):
    """Tests for the JSON file secret store."""

    def test_connector_id(self):
        self.assertEqual(
            JsonSecretStore.CONNECTOR_ID, "modelmesh.json-secrets.v1"
        )

    def test_default_config(self):
        config = JsonSecretStoreConfig()
        self.assertEqual(config.file_path, "")
        self.assertEqual(config.json_path, "")

    def test_simple_lookup(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"api_key": "sk-123", "db_pass": "secret"}, f)
        try:
            config = JsonSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = JsonSecretStore(config)
            self.assertEqual(store.get("api_key"), "sk-123")
            self.assertEqual(store.get("db_pass"), "secret")
        finally:
            os.unlink(f.name)

    def test_nested_dot_notation(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "providers": {
                        "openai": {"api_key": "sk-openai"},
                        "anthropic": {"api_key": "sk-anthropic"},
                    }
                },
                f,
            )
        try:
            config = JsonSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = JsonSecretStore(config)
            self.assertEqual(
                store.get("providers.openai.api_key"), "sk-openai"
            )
            self.assertEqual(
                store.get("providers.anthropic.api_key"), "sk-anthropic"
            )
        finally:
            os.unlink(f.name)

    def test_json_path_scoping(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "prod": {"api_key": "sk-prod"},
                    "dev": {"api_key": "sk-dev"},
                },
                f,
            )
        try:
            config = JsonSecretStoreConfig(
                file_path=f.name,
                json_path="prod",
                fail_on_missing=True,
            )
            store = JsonSecretStore(config)
            self.assertEqual(store.get("api_key"), "sk-prod")
        finally:
            os.unlink(f.name)

    def test_numeric_value_to_string(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"port": 5432, "retries": 3}, f)
        try:
            config = JsonSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = JsonSecretStore(config)
            self.assertEqual(store.get("port"), "5432")
        finally:
            os.unlink(f.name)

    def test_missing_key_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"existing": "yes"}, f)
        try:
            config = JsonSecretStoreConfig(
                file_path=f.name, fail_on_missing=True
            )
            store = JsonSecretStore(config)
            with self.assertRaises(KeyError):
                store.get("nonexistent")
        finally:
            os.unlink(f.name)

    def test_missing_file_returns_empty(self):
        config = JsonSecretStoreConfig(
            file_path="/nonexistent/secrets.json",
            fail_on_missing=False,
        )
        store = JsonSecretStore(config)
        self.assertEqual(store.get("any_key"), "")


class TestKeyringSecretStore(unittest.TestCase):
    """Tests for the OS keyring secret store."""

    def test_connector_id(self):
        self.assertEqual(
            KeyringSecretStore.CONNECTOR_ID, "modelmesh.keyring.v1"
        )

    def test_default_config(self):
        config = KeyringSecretStoreConfig()
        self.assertEqual(config.service_name, "modelmesh")

    def test_keyring_available_property(self):
        store = KeyringSecretStore()
        # keyring_available should be a boolean
        self.assertIsInstance(store.keyring_available, bool)

    def test_missing_keyring_returns_none(self):
        """When keyring is not available, _resolve returns None."""
        store = KeyringSecretStore(
            KeyringSecretStoreConfig(fail_on_missing=False)
        )
        # Mock the module-level flag to simulate missing keyring
        import modelmesh.connectors.secret_stores.keyring_store as ks_mod

        original = ks_mod._KEYRING_AVAILABLE
        try:
            ks_mod._KEYRING_AVAILABLE = False
            self.assertEqual(store.get("ANY_KEY"), "")
        finally:
            ks_mod._KEYRING_AVAILABLE = original

    def test_missing_keyring_raises_if_fail_on_missing(self):
        store = KeyringSecretStore(
            KeyringSecretStoreConfig(fail_on_missing=True)
        )
        import modelmesh.connectors.secret_stores.keyring_store as ks_mod

        original = ks_mod._KEYRING_AVAILABLE
        try:
            ks_mod._KEYRING_AVAILABLE = False
            with self.assertRaises(KeyError):
                store.get("ANY_KEY")
        finally:
            ks_mod._KEYRING_AVAILABLE = original

    def test_keyring_resolve_with_mock(self):
        """Simulate a working keyring backend with a mock."""
        import modelmesh.connectors.secret_stores.keyring_store as ks_mod

        original_avail = ks_mod._KEYRING_AVAILABLE
        original_keyring = ks_mod._keyring
        try:
            mock_keyring = MagicMock()
            mock_keyring.get_password.return_value = "mocked-secret"
            ks_mod._KEYRING_AVAILABLE = True
            ks_mod._keyring = mock_keyring

            store = KeyringSecretStore(
                KeyringSecretStoreConfig(service_name="test-svc")
            )
            value = store.get("MY_SECRET")
            self.assertEqual(value, "mocked-secret")
            mock_keyring.get_password.assert_called_once_with(
                "test-svc", "MY_SECRET"
            )
        finally:
            ks_mod._KEYRING_AVAILABLE = original_avail
            ks_mod._keyring = original_keyring


# ===================================================================
# Observability Connector Tests
# ===================================================================


class TestJsonLogConnector(unittest.TestCase):
    """Tests for the JSON Lines observability connector."""

    def test_connector_id(self):
        self.assertEqual(JsonLogConnector.CONNECTOR_ID, "modelmesh.json-log.v1")

    def test_default_config(self):
        config = JsonLogConnectorConfig()
        self.assertEqual(config.file_path, "modelmesh_events.jsonl")
        self.assertTrue(config.append)
        self.assertEqual(config.max_size_mb, 0)

    def test_trace_writes_json_line(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = f.name
        try:
            conn = JsonLogConnector(
                JsonLogConnectorConfig(file_path=path, append=False)
            )
            conn.trace(_make_trace())
            conn.close()

            with open(path, "r") as fh:
                line = fh.readline()
            record = json.loads(line)
            self.assertEqual(record["type"], "trace")
            self.assertEqual(record["severity"], "error")
            self.assertEqual(record["component"], "test")
            self.assertEqual(record["message"], "test trace")
            self.assertIn("timestamp", record)
            self.assertIn("metadata", record)
        finally:
            os.unlink(path)

    def test_emit_writes_event(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = f.name
        try:
            conn = JsonLogConnector(
                JsonLogConnectorConfig(file_path=path, append=False)
            )
            conn.emit(_make_event())
            conn.close()

            with open(path, "r") as fh:
                record = json.loads(fh.readline())
            self.assertEqual(record["type"], "event")
            self.assertEqual(record["message"], "model_activated")
            self.assertEqual(record["metadata"]["model_id"], "gpt-4o")
        finally:
            os.unlink(path)

    def test_log_writes_request_entry(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = f.name
        try:
            conn = JsonLogConnector(
                JsonLogConnectorConfig(file_path=path, append=False)
            )
            conn.log(_make_log_entry())
            conn.close()

            with open(path, "r") as fh:
                record = json.loads(fh.readline())
            self.assertEqual(record["type"], "log")
            self.assertEqual(record["severity"], "info")
            self.assertIn("123", record["message"])
        finally:
            os.unlink(path)

    def test_log_error_severity(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = f.name
        try:
            conn = JsonLogConnector(
                JsonLogConnectorConfig(file_path=path, append=False)
            )
            conn.log(_make_log_entry(error="timeout"))
            conn.close()

            with open(path, "r") as fh:
                record = json.loads(fh.readline())
            self.assertEqual(record["severity"], "error")
        finally:
            os.unlink(path)

    def test_flush_writes_stats(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = f.name
        try:
            conn = JsonLogConnector(
                JsonLogConnectorConfig(file_path=path, append=False)
            )
            conn.flush(_make_stats())
            conn.close()

            with open(path, "r") as fh:
                record = json.loads(fh.readline())
            self.assertEqual(record["type"], "stats")
            self.assertEqual(record["metadata"]["requests_total"], 100)
        finally:
            os.unlink(path)

    def test_multiple_lines(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = f.name
        try:
            conn = JsonLogConnector(
                JsonLogConnectorConfig(file_path=path, append=False)
            )
            conn.trace(_make_trace())
            conn.emit(_make_event())
            conn.log(_make_log_entry())
            conn.close()

            with open(path, "r") as fh:
                lines = fh.readlines()
            self.assertEqual(len(lines), 3)
            # Each line should be valid JSON
            for line in lines:
                json.loads(line)
        finally:
            os.unlink(path)


class TestWebhookConnector(unittest.TestCase):
    """Tests for the webhook observability connector."""

    def test_connector_id(self):
        self.assertEqual(WebhookConnector.CONNECTOR_ID, "modelmesh.webhook.v1")

    def test_default_config(self):
        config = WebhookConnectorConfig()
        self.assertEqual(config.url, "")
        self.assertEqual(config.method, "POST")
        self.assertEqual(config.min_severity, "error")
        self.assertEqual(config.batch_size, 1)

    def test_severity_filter_drops_low_severity(self):
        """Events below min_severity should be silently dropped."""
        conn = WebhookConnector(
            WebhookConnectorConfig(url="http://example.com", min_severity="error")
        )
        # INFO trace should be dropped
        conn.trace(_make_trace(severity=Severity.INFO))
        self.assertEqual(len(conn._batch), 0)

    def test_severity_filter_passes_matching(self):
        """Events at or above min_severity should be queued."""
        conn = WebhookConnector(
            WebhookConnectorConfig(
                url="http://example.com",
                min_severity="error",
                batch_size=100,  # large batch so we don't auto-flush
            )
        )
        conn.trace(_make_trace(severity=Severity.ERROR))
        self.assertEqual(len(conn._batch), 1)

    def test_severity_filter_passes_critical(self):
        conn = WebhookConnector(
            WebhookConnectorConfig(
                url="http://example.com",
                min_severity="error",
                batch_size=100,
            )
        )
        conn.trace(_make_trace(severity=Severity.CRITICAL))
        self.assertEqual(len(conn._batch), 1)

    def test_batch_accumulation(self):
        conn = WebhookConnector(
            WebhookConnectorConfig(
                url="http://example.com",
                min_severity="debug",
                batch_size=3,
            )
        )
        conn.trace(_make_trace(severity=Severity.ERROR))
        conn.trace(_make_trace(severity=Severity.ERROR))
        self.assertEqual(len(conn._batch), 2)

    @patch("modelmesh.connectors.observability.webhook_connector.urllib.request.urlopen")
    def test_flush_batch_sends_http(self, mock_urlopen):
        """flush_batch should send queued records via HTTP."""
        mock_urlopen.return_value = MagicMock()
        conn = WebhookConnector(
            WebhookConnectorConfig(
                url="http://example.com/hook",
                min_severity="debug",
                batch_size=100,
            )
        )
        conn.trace(_make_trace(severity=Severity.ERROR))
        conn.flush_batch()
        self.assertTrue(mock_urlopen.called)
        self.assertEqual(len(conn._batch), 0)

    @patch("modelmesh.connectors.observability.webhook_connector.urllib.request.urlopen")
    def test_auto_flush_at_batch_size(self, mock_urlopen):
        """Batch should auto-flush when reaching batch_size."""
        mock_urlopen.return_value = MagicMock()
        conn = WebhookConnector(
            WebhookConnectorConfig(
                url="http://example.com/hook",
                min_severity="debug",
                batch_size=2,
            )
        )
        conn.trace(_make_trace(severity=Severity.ERROR))
        self.assertEqual(len(conn._batch), 1)
        conn.trace(_make_trace(severity=Severity.ERROR))
        # Should have flushed
        self.assertEqual(len(conn._batch), 0)
        self.assertTrue(mock_urlopen.called)

    def test_emit_filtered_by_severity(self):
        conn = WebhookConnector(
            WebhookConnectorConfig(
                url="http://example.com",
                min_severity="error",
                batch_size=100,
            )
        )
        # Events are INFO by default
        conn.emit(_make_event())
        self.assertEqual(len(conn._batch), 0)

    def test_log_with_error_passes_filter(self):
        conn = WebhookConnector(
            WebhookConnectorConfig(
                url="http://example.com",
                min_severity="error",
                batch_size=100,
            )
        )
        conn.log(_make_log_entry(error="timeout"))
        self.assertEqual(len(conn._batch), 1)

    def test_no_url_flush_is_noop(self):
        """flush_batch should be a no-op when url is empty."""
        conn = WebhookConnector(WebhookConnectorConfig(url=""))
        conn._batch = [{"test": True}]
        conn.flush_batch()
        # Batch should remain since we couldn't send
        # Actually the implementation clears batch before sending -- let's verify
        # the implementation: batch is cleared, but no HTTP call is made
        # Re-reading: if not self._batch or not self._config.url: return
        # So batch is NOT cleared (early return)
        self.assertEqual(len(conn._batch), 1)


class TestCallbackConnector(unittest.TestCase):
    """Tests for the callback observability connector."""

    def test_connector_id(self):
        self.assertEqual(
            CallbackConnector.CONNECTOR_ID, "modelmesh.callback.v1"
        )

    def test_default_config_all_none(self):
        config = CallbackConnectorConfig()
        self.assertIsNone(config.on_trace)
        self.assertIsNone(config.on_event)
        self.assertIsNone(config.on_log)
        self.assertIsNone(config.on_stats)

    def test_trace_callback(self):
        traces = []
        conn = CallbackConnector(
            CallbackConnectorConfig(on_trace=traces.append)
        )
        entry = _make_trace()
        conn.trace(entry)
        self.assertEqual(len(traces), 1)
        self.assertIs(traces[0], entry)

    def test_event_callback(self):
        events = []
        conn = CallbackConnector(
            CallbackConnectorConfig(on_event=events.append)
        )
        event = _make_event()
        conn.emit(event)
        self.assertEqual(len(events), 1)
        self.assertIs(events[0], event)

    def test_log_callback(self):
        logs = []
        conn = CallbackConnector(
            CallbackConnectorConfig(on_log=logs.append)
        )
        entry = _make_log_entry()
        conn.log(entry)
        self.assertEqual(len(logs), 1)
        self.assertIs(logs[0], entry)

    def test_stats_callback(self):
        flushed = []
        conn = CallbackConnector(
            CallbackConnectorConfig(on_stats=flushed.append)
        )
        stats = _make_stats()
        conn.flush(stats)
        self.assertEqual(len(flushed), 1)
        self.assertIs(flushed[0], stats)

    def test_noop_without_callbacks(self):
        """All methods should silently succeed when no callbacks set."""
        conn = CallbackConnector()
        conn.trace(_make_trace())
        conn.emit(_make_event())
        conn.log(_make_log_entry())
        conn.flush(_make_stats())

    def test_multiple_callbacks(self):
        traces = []
        events = []
        conn = CallbackConnector(
            CallbackConnectorConfig(
                on_trace=traces.append,
                on_event=events.append,
            )
        )
        conn.trace(_make_trace())
        conn.trace(_make_trace())
        conn.emit(_make_event())
        self.assertEqual(len(traces), 2)
        self.assertEqual(len(events), 1)


# ===================================================================
# Storage Connector Tests
# ===================================================================


class TestSqliteStorage(unittest.TestCase):
    """Tests for the SQLite storage connector."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            suffix=".db", delete=False
        )
        self.tmp.close()
        self.storage = SqliteStorage(
            SqliteStorageConfig(db_path=self.tmp.name)
        )

    def tearDown(self):
        self.storage.close()
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_connector_id(self):
        self.assertEqual(SqliteStorage.CONNECTOR_ID, "modelmesh.sqlite.v1")

    def test_default_config(self):
        config = SqliteStorageConfig()
        self.assertEqual(config.db_path, "modelmesh_state.db")
        self.assertEqual(config.table_name, "kv_store")

    def test_save_and_load(self):
        entry = _make_storage_entry()
        _run(self.storage.save("k1", entry))
        loaded = _run(self.storage.load("k1"))
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.key, "k1")
        self.assertEqual(loaded.data, b"hello world")
        self.assertEqual(loaded.metadata, {"format": "raw"})

    def test_load_missing_returns_none(self):
        result = _run(self.storage.load("nonexistent"))
        self.assertIsNone(result)

    def test_delete_existing(self):
        _run(self.storage.save("k1", _make_storage_entry()))
        deleted = _run(self.storage.delete("k1"))
        self.assertTrue(deleted)
        self.assertIsNone(_run(self.storage.load("k1")))

    def test_delete_nonexistent(self):
        deleted = _run(self.storage.delete("ghost"))
        self.assertFalse(deleted)

    def test_list_all_keys(self):
        _run(self.storage.save("a1", _make_storage_entry(key="a1")))
        _run(self.storage.save("b2", _make_storage_entry(key="b2")))
        _run(self.storage.save("a3", _make_storage_entry(key="a3")))
        keys = _run(self.storage.list())
        self.assertEqual(sorted(keys), ["a1", "a3", "b2"])

    def test_list_with_prefix(self):
        _run(self.storage.save("prefix.x", _make_storage_entry(key="prefix.x")))
        _run(self.storage.save("prefix.y", _make_storage_entry(key="prefix.y")))
        _run(self.storage.save("other.z", _make_storage_entry(key="other.z")))
        keys = _run(self.storage.list(prefix="prefix."))
        self.assertEqual(sorted(keys), ["prefix.x", "prefix.y"])

    def test_exists(self):
        _run(self.storage.save("k1", _make_storage_entry()))
        self.assertTrue(_run(self.storage.exists("k1")))
        self.assertFalse(_run(self.storage.exists("k2")))

    def test_stat(self):
        data = b"some binary data"
        entry = StorageEntry(key="k1", data=data, metadata={})
        _run(self.storage.save("k1", entry))
        meta = _run(self.storage.stat("k1"))
        self.assertIsNotNone(meta)
        self.assertEqual(meta.key, "k1")
        self.assertEqual(meta.size, len(data))
        self.assertIsInstance(meta.last_modified, datetime)

    def test_stat_missing(self):
        meta = _run(self.storage.stat("ghost"))
        self.assertIsNone(meta)

    def test_overwrite(self):
        _run(self.storage.save("k1", _make_storage_entry(data=b"v1")))
        _run(self.storage.save("k1", _make_storage_entry(data=b"v2")))
        loaded = _run(self.storage.load("k1"))
        self.assertEqual(loaded.data, b"v2")


class TestMemoryStorage(unittest.TestCase):
    """Tests for the in-memory storage connector."""

    def setUp(self):
        self.storage = MemoryStorage()

    def test_connector_id(self):
        self.assertEqual(MemoryStorage.CONNECTOR_ID, "modelmesh.memory.v1")

    def test_save_and_load(self):
        entry = _make_storage_entry()
        _run(self.storage.save("k1", entry))
        loaded = _run(self.storage.load("k1"))
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.data, b"hello world")

    def test_load_missing_returns_none(self):
        result = _run(self.storage.load("nonexistent"))
        self.assertIsNone(result)

    def test_delete_existing(self):
        _run(self.storage.save("k1", _make_storage_entry()))
        self.assertTrue(_run(self.storage.delete("k1")))
        self.assertIsNone(_run(self.storage.load("k1")))

    def test_delete_nonexistent(self):
        self.assertFalse(_run(self.storage.delete("ghost")))

    def test_list_all_keys(self):
        _run(self.storage.save("x", _make_storage_entry(key="x")))
        _run(self.storage.save("y", _make_storage_entry(key="y")))
        keys = _run(self.storage.list())
        self.assertEqual(sorted(keys), ["x", "y"])

    def test_list_with_prefix(self):
        _run(self.storage.save("ab.1", _make_storage_entry(key="ab.1")))
        _run(self.storage.save("ab.2", _make_storage_entry(key="ab.2")))
        _run(self.storage.save("cd.3", _make_storage_entry(key="cd.3")))
        keys = _run(self.storage.list(prefix="ab."))
        self.assertEqual(sorted(keys), ["ab.1", "ab.2"])

    def test_exists(self):
        _run(self.storage.save("k1", _make_storage_entry()))
        self.assertTrue(_run(self.storage.exists("k1")))
        self.assertFalse(_run(self.storage.exists("k2")))

    def test_stat(self):
        data = b"test data"
        entry = StorageEntry(key="k1", data=data, metadata={})
        _run(self.storage.save("k1", entry))
        meta = _run(self.storage.stat("k1"))
        self.assertIsNotNone(meta)
        self.assertEqual(meta.key, "k1")
        self.assertEqual(meta.size, len(data))
        self.assertIsInstance(meta.last_modified, datetime)

    def test_stat_missing(self):
        self.assertIsNone(_run(self.storage.stat("ghost")))

    def test_overwrite(self):
        _run(self.storage.save("k1", _make_storage_entry(data=b"v1")))
        _run(self.storage.save("k1", _make_storage_entry(data=b"v2")))
        loaded = _run(self.storage.load("k1"))
        self.assertEqual(loaded.data, b"v2")

    def test_no_config_needed(self):
        """MemoryStorage takes no configuration arguments."""
        storage = MemoryStorage()
        self.assertIsNotNone(storage)


# ===================================================================
# Registry Integration Tests
# ===================================================================


class TestUpdatedConnectorRegistry(unittest.TestCase):
    """Verify all new connectors are registered in CONNECTOR_REGISTRY."""

    def test_registry_has_38_connectors(self):
        """34 previous + 4 local providers (Ollama, LM Studio, vLLM, LocalAI) = 38 total connectors."""
        self.assertEqual(len(CONNECTOR_REGISTRY), 38)

    def test_all_have_matching_connector_id(self):
        for connector_id, cls in CONNECTOR_REGISTRY.items():
            self.assertTrue(
                hasattr(cls, "CONNECTOR_ID"),
                f"{cls.__name__} missing CONNECTOR_ID",
            )
            self.assertEqual(
                cls.CONNECTOR_ID,
                connector_id,
                f"Mismatch: {cls.__name__}.CONNECTOR_ID "
                f"= {cls.CONNECTOR_ID} != {connector_id}",
            )

    # New secret stores
    def test_registry_contains_dotenv(self):
        self.assertIn("modelmesh.dotenv.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_json_secrets(self):
        self.assertIn("modelmesh.json-secrets.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_keyring(self):
        self.assertIn("modelmesh.keyring.v1", CONNECTOR_REGISTRY)

    # New observability
    def test_registry_contains_json_log(self):
        self.assertIn("modelmesh.json-log.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_webhook(self):
        self.assertIn("modelmesh.webhook.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_callback(self):
        self.assertIn("modelmesh.callback.v1", CONNECTOR_REGISTRY)

    # New storage
    def test_registry_contains_sqlite(self):
        self.assertIn("modelmesh.sqlite.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_memory(self):
        self.assertIn("modelmesh.memory.v1", CONNECTOR_REGISTRY)

    # Original connectors still present
    def test_registry_still_contains_originals(self):
        originals = [
            "openai.llm.v1",
            "anthropic.claude.v1",
            "modelmesh.env.v1",
            "modelmesh.console.v1",
            "modelmesh.null.v1",
            "modelmesh.file.v1",
            "modelmesh.stick-until-failure.v1",
            "modelmesh.local-file.v1",
        ]
        for cid in originals:
            self.assertIn(cid, CONNECTOR_REGISTRY, f"Missing original: {cid}")


if __name__ == "__main__":
    unittest.main()
