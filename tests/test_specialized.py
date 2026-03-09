"""Tests for CDK specialized classes, mixins, and connector implementations."""
import asyncio
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.cdk.enums import (
    AuthMethod,
    ConnectorType,
    DeactivationReason,
    EventType,
    LogLevel,
    ModelStatus,
    RecoveryTrigger,
    SyncAction,
    SyncPolicy,
    SerializationFormat,
)
from modelmesh.cdk.helpers import (
    ConnectorTestHarness,
    MockHttpClient,
    MockHttpResponse,
    mock_completion_request,
    mock_model_snapshot,
)
from modelmesh.cdk.mixins.cache import CacheMixin, CacheStats
from modelmesh.cdk.mixins.rate_limiter import RateLimiterMixin
from modelmesh.cdk.mixins.retry import RetryMixin
from modelmesh.cdk.specialized.file_secret_store import (
    FileSecretStore,
    FileSecretStoreConfig,
)
from modelmesh.cdk.specialized.kv_storage import (
    KeyValueStorage,
    KeyValueStorageConfig,
)
from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.cdk.specialized.quick_provider import (
    QuickProvider,
    QuickProviderConfig,
)
from modelmesh.cdk.specialized.threshold_rotation import (
    ThresholdRotationConfig,
    ThresholdRotationPolicy,
)
from modelmesh.cdk.base_provider import BaseProvider
from modelmesh.connectors.rotation.stick_until_failure import (
    StickUntilFailureConfig,
    StickUntilFailurePolicy,
)
from modelmesh.connectors.storage.local_file import (
    LocalFileStorage,
    LocalFileStorageConfig,
)
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
    ModelInfo,
)
from modelmesh.interfaces.rotation import ModelState, ModelStatus as MS
from modelmesh.interfaces.storage import StorageEntry


# ---------------------------------------------------------------------------
# 1. OpenAICompatibleProvider
# ---------------------------------------------------------------------------

class TestOpenAICompatibleProvider(unittest.TestCase):
    """Test the OpenAICompatibleProvider class."""

    def setUp(self):
        self.config = OpenAICompatibleConfig(
            base_url="https://api.openai.com",
            api_key="sk-test-key-123",
            models=[
                ModelInfo(id="gpt-4o", name="GPT-4o", capabilities=["chat", "tools"]),
            ],
        )
        self.provider = OpenAICompatibleProvider(self.config)

    def test_instantiation(self):
        self.assertIsNotNone(self.provider)
        self.assertIsInstance(self.provider, BaseProvider)

    def test_default_base_url(self):
        """When base_url is empty, it defaults to https://api.openai.com."""
        config = OpenAICompatibleConfig(api_key="sk-test")
        provider = OpenAICompatibleProvider(config)
        endpoint = provider._get_completion_endpoint()
        self.assertTrue(endpoint.startswith("https://api.openai.com"))

    def test_get_completion_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(endpoint, "https://api.openai.com/v1/chat/completions")

    def test_build_headers_includes_bearer(self):
        headers = self.provider._build_headers()
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer sk-test-key-123")

    def test_build_headers_with_organization(self):
        config = OpenAICompatibleConfig(
            base_url="https://api.openai.com",
            api_key="sk-test",
            organization="org-abc",
        )
        provider = OpenAICompatibleProvider(config)
        headers = provider._build_headers()
        self.assertEqual(headers["OpenAI-Organization"], "org-abc")

    def test_build_headers_with_api_version(self):
        config = OpenAICompatibleConfig(
            base_url="https://api.openai.com",
            api_key="sk-test",
            api_version="2024-01-01",
        )
        provider = OpenAICompatibleProvider(config)
        headers = provider._build_headers()
        self.assertEqual(headers["OpenAI-Version"], "2024-01-01")

    def test_build_request_payload(self):
        request = CompletionRequest(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello, world!"}],
            temperature=0.7,
        )
        payload = self.provider._build_request_payload(request)
        self.assertEqual(payload["model"], "gpt-4o")
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0]["content"], "Hello, world!")
        self.assertEqual(payload["temperature"], 0.7)

    def test_parse_response(self):
        data = {
            "id": "chatcmpl-abc123",
            "model": "gpt-4o",
            "choices": [
                {"index": 0, "finish_reason": "stop"}
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }
        response = self.provider._parse_response(data)
        self.assertIsInstance(response, CompletionResponse)
        self.assertEqual(response.id, "chatcmpl-abc123")
        self.assertEqual(response.model, "gpt-4o")
        self.assertEqual(len(response.choices), 1)
        self.assertEqual(response.usage.prompt_tokens, 10)
        self.assertEqual(response.usage.completion_tokens, 20)
        self.assertEqual(response.usage.total_tokens, 30)

    def test_list_models(self):
        models = self.provider.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "gpt-4o")


# ---------------------------------------------------------------------------
# 2. QuickProvider
# ---------------------------------------------------------------------------

class TestQuickProvider(unittest.TestCase):
    """Test the QuickProvider class."""

    def test_instantiation(self):
        config = QuickProviderConfig(
            base_url="https://api.example.com",
            api_key="sk-quick-123",
        )
        provider = QuickProvider(config)
        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, BaseProvider)

    def test_inherits_base_provider(self):
        config = QuickProviderConfig(
            base_url="https://api.example.com",
            api_key="sk-quick",
        )
        provider = QuickProvider(config)
        self.assertIsInstance(provider, BaseProvider)

    def test_list_models_with_preconfigured(self):
        config = QuickProviderConfig(
            base_url="https://api.example.com",
            api_key="sk-quick",
            models=[ModelInfo(id="model-a", name="Model A")],
        )
        provider = QuickProvider(config)
        models = provider.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "model-a")

    def test_discovered_flag_set_when_models_provided(self):
        config = QuickProviderConfig(
            base_url="https://api.example.com",
            api_key="sk-quick",
            models=[ModelInfo(id="m1", name="M1")],
        )
        provider = QuickProvider(config)
        self.assertTrue(provider._discovered)

    def test_discovered_flag_unset_when_no_models(self):
        config = QuickProviderConfig(
            base_url="https://api.example.com",
            api_key="sk-quick",
        )
        provider = QuickProvider(config)
        self.assertFalse(provider._discovered)

    def test_build_headers(self):
        config = QuickProviderConfig(
            base_url="https://api.example.com",
            api_key="sk-quick-key",
        )
        provider = QuickProvider(config)
        headers = provider._build_headers()
        self.assertEqual(headers["Authorization"], "Bearer sk-quick-key")


# ---------------------------------------------------------------------------
# 3. ThresholdRotationPolicy
# ---------------------------------------------------------------------------

class TestThresholdRotationPolicy(unittest.TestCase):
    """Test the ThresholdRotationPolicy class."""

    def test_default_config_thresholds(self):
        config = ThresholdRotationConfig()
        self.assertEqual(config.failure_count_threshold, 3)
        self.assertEqual(config.error_rate_threshold, 0.5)
        self.assertIsNone(config.quota_threshold)
        self.assertIsNone(config.budget_threshold)
        self.assertIsNone(config.token_limit_threshold)
        self.assertIsNone(config.request_limit_threshold)
        self.assertEqual(config.cooldown_seconds, 60.0)

    def test_should_deactivate_failure_count_exceeded(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            failure_count_threshold=3,
        ))
        state = ModelState(model_id="test", failure_count=3)
        self.assertTrue(policy.should_deactivate(state))

    def test_should_deactivate_failure_count_below(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            failure_count_threshold=3,
        ))
        state = ModelState(model_id="test", failure_count=2)
        self.assertFalse(policy.should_deactivate(state))

    def test_should_deactivate_error_rate_exceeded(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            failure_count_threshold=None,
            error_rate_threshold=0.5,
        ))
        state = ModelState(model_id="test", error_rate=0.6)
        self.assertTrue(policy.should_deactivate(state))

    def test_should_deactivate_error_rate_below(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            failure_count_threshold=None,
            error_rate_threshold=0.5,
        ))
        state = ModelState(model_id="test", error_rate=0.3)
        self.assertFalse(policy.should_deactivate(state))

    def test_get_reason_quota_exhausted(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            failure_count_threshold=None,
            error_rate_threshold=None,
            quota_threshold=100,
        ))
        state = ModelState(model_id="test", total_requests=100)
        reason = policy.get_reason(state)
        self.assertEqual(reason, DeactivationReason.QUOTA_EXHAUSTED)

    def test_get_reason_budget_exceeded(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            failure_count_threshold=None,
            error_rate_threshold=None,
            budget_threshold=50.0,
        ))
        state = ModelState(model_id="test", total_cost=55.0)
        reason = policy.get_reason(state)
        self.assertEqual(reason, DeactivationReason.BUDGET_EXCEEDED)

    def test_get_reason_token_limit(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            failure_count_threshold=None,
            error_rate_threshold=None,
            token_limit_threshold=10000,
        ))
        state = ModelState(model_id="test", total_tokens=10001)
        reason = policy.get_reason(state)
        self.assertEqual(reason, DeactivationReason.TOKEN_LIMIT)

    def test_get_reason_request_limit(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            failure_count_threshold=None,
            error_rate_threshold=None,
            request_limit_threshold=500,
        ))
        state = ModelState(model_id="test", total_requests=500)
        reason = policy.get_reason(state)
        self.assertEqual(reason, DeactivationReason.REQUEST_LIMIT)

    def test_get_reason_none_when_healthy(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig())
        state = ModelState(model_id="test", failure_count=0, error_rate=0.0)
        self.assertIsNone(policy.get_reason(state))

    def test_should_recover_no_cooldown(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig())
        state = ModelState(model_id="test", cooldown_until=None)
        self.assertTrue(policy.should_recover(state))

    def test_should_recover_cooldown_expired(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig())
        state = ModelState(model_id="test", cooldown_until=time.time() - 10)
        self.assertTrue(policy.should_recover(state))

    def test_should_not_recover_cooldown_active(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig())
        state = ModelState(
            model_id="test", cooldown_until=time.time() + 1000
        )
        self.assertFalse(policy.should_recover(state))

    def test_select_with_candidates(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig())
        request = CompletionRequest(
            model="test", messages=[{"role": "user", "content": "hi"}]
        )
        candidates = [
            ModelState(model_id="a", error_rate=0.1),
            ModelState(model_id="b", error_rate=0.4),
        ]
        selected = policy.select(candidates, request)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.model_id, "a")

    def test_select_empty_candidates(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig())
        request = CompletionRequest(model="test", messages=[])
        self.assertIsNone(policy.select([], request))

    def test_select_stick_until_failure(self):
        policy = ThresholdRotationPolicy(ThresholdRotationConfig(
            stick_until_failure=True,
        ))
        request = CompletionRequest(
            model="test", messages=[{"role": "user", "content": "hi"}]
        )
        candidates = [
            ModelState(model_id="a", error_rate=0.1),
            ModelState(model_id="b", error_rate=0.2),
        ]
        # First selection picks best candidate
        selected1 = policy.select(candidates, request)
        self.assertEqual(selected1.model_id, "a")
        # Second call should stick to same model
        selected2 = policy.select(candidates, request)
        self.assertEqual(selected2.model_id, "a")


# ---------------------------------------------------------------------------
# 4. FileSecretStore
# ---------------------------------------------------------------------------

class TestFileSecretStore(unittest.TestCase):
    """Test the FileSecretStore class."""

    def test_instantiation_with_config(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("API_KEY=my-secret\n")
            f.flush()
            config = FileSecretStoreConfig(
                file_path=f.name, format="env"
            )
            store = FileSecretStore(config)
            self.assertIsNotNone(store)
        os.unlink(f.name)

    def test_resolve_env_format(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("API_KEY=my-secret-value\n")
            f.write("DB_HOST=localhost\n")
            f.flush()
            config = FileSecretStoreConfig(
                file_path=f.name, format="env"
            )
            store = FileSecretStore(config)
        self.assertEqual(store.get("API_KEY"), "my-secret-value")
        self.assertEqual(store.get("DB_HOST"), "localhost")
        os.unlink(f.name)

    def test_resolve_json_format(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"API_KEY": "json-secret", "OTHER": "value"}, f)
            f.flush()
            config = FileSecretStoreConfig(
                file_path=f.name, format="json"
            )
            store = FileSecretStore(config)
        self.assertEqual(store.get("API_KEY"), "json-secret")
        self.assertEqual(store.get("OTHER"), "value")
        os.unlink(f.name)

    def test_resolve_missing_key_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("KEY=val\n")
            f.flush()
            config = FileSecretStoreConfig(
                file_path=f.name,
                format="env",
                fail_on_missing=True,
            )
            store = FileSecretStore(config)
        with self.assertRaises(KeyError):
            store.get("NONEXISTENT")
        os.unlink(f.name)

    def test_resolve_missing_key_returns_empty(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write("KEY=val\n")
            f.flush()
            config = FileSecretStoreConfig(
                file_path=f.name,
                format="env",
                fail_on_missing=False,
            )
            store = FileSecretStore(config)
        result = store.get("NONEXISTENT")
        self.assertEqual(result, "")
        os.unlink(f.name)

    def test_resolve_env_with_quoted_values(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False
        ) as f:
            f.write('QUOTED="hello world"\n')
            f.write("SINGLE='single quoted'\n")
            f.flush()
            config = FileSecretStoreConfig(
                file_path=f.name, format="env"
            )
            store = FileSecretStore(config)
        self.assertEqual(store.get("QUOTED"), "hello world")
        self.assertEqual(store.get("SINGLE"), "single quoted")
        os.unlink(f.name)

    def test_missing_file_does_not_error(self):
        config = FileSecretStoreConfig(
            file_path="/nonexistent/path/secrets.env",
            format="env",
            fail_on_missing=False,
        )
        store = FileSecretStore(config)
        result = store.get("ANY_KEY")
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# 5. KeyValueStorage
# ---------------------------------------------------------------------------

class TestKeyValueStorage(unittest.TestCase):
    """Test the KeyValueStorage class."""

    def test_instantiation_memory_backend(self):
        config = KeyValueStorageConfig(backend="memory")
        storage = KeyValueStorage(config)
        self.assertIsNotNone(storage)

    def test_save_and_load_roundtrip(self):
        config = KeyValueStorageConfig(backend="memory")
        storage = KeyValueStorage(config)
        entry = StorageEntry(key="test-key", data=b"test-data", metadata={"tag": "v1"})
        asyncio.run(storage.save("test-key", entry))
        loaded = asyncio.run(storage.load("test-key"))
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.data, b"test-data")
        self.assertEqual(loaded.metadata["tag"], "v1")

    def test_load_nonexistent_returns_none(self):
        config = KeyValueStorageConfig(backend="memory")
        storage = KeyValueStorage(config)
        result = asyncio.run(storage.load("missing"))
        self.assertIsNone(result)

    def test_delete_removes_key(self):
        config = KeyValueStorageConfig(backend="memory")
        storage = KeyValueStorage(config)
        entry = StorageEntry(key="del-key", data=b"data", metadata={})
        asyncio.run(storage.save("del-key", entry))
        result = asyncio.run(storage.delete("del-key"))
        self.assertTrue(result)
        loaded = asyncio.run(storage.load("del-key"))
        self.assertIsNone(loaded)

    def test_delete_nonexistent_returns_false(self):
        config = KeyValueStorageConfig(backend="memory")
        storage = KeyValueStorage(config)
        result = asyncio.run(storage.delete("nope"))
        self.assertFalse(result)

    def test_list_keys(self):
        config = KeyValueStorageConfig(backend="memory")
        storage = KeyValueStorage(config)
        asyncio.run(storage.save("a", StorageEntry(key="a", data=b"1", metadata={})))
        asyncio.run(storage.save("b", StorageEntry(key="b", data=b"2", metadata={})))
        keys = asyncio.run(storage.list())
        self.assertIn("a", keys)
        self.assertIn("b", keys)
        self.assertEqual(len(keys), 2)

    def test_file_backend_roundtrip(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            tmp_path = f.name

        try:
            config = KeyValueStorageConfig(backend="file", file_path=tmp_path)
            storage = KeyValueStorage(config)
            entry = StorageEntry(
                key="persist", data=b"persistent-data", metadata={"ver": "1"}
            )
            asyncio.run(storage.save("persist", entry))

            # Load in a new storage instance from the same file
            config2 = KeyValueStorageConfig(backend="file", file_path=tmp_path)
            storage2 = KeyValueStorage(config2)
            loaded = asyncio.run(storage2.load("persist"))
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.data, b"persistent-data")
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 6. CDK Enums
# ---------------------------------------------------------------------------

class TestCDKEnums(unittest.TestCase):
    """Test CDK enums from modelmesh.cdk.enums."""

    def test_auth_method_values(self):
        self.assertEqual(AuthMethod.API_KEY.value, "api_key")
        self.assertEqual(AuthMethod.OAUTH.value, "oauth")
        self.assertEqual(AuthMethod.SERVICE_ACCOUNT.value, "service_account")

    def test_connector_type_values(self):
        self.assertEqual(ConnectorType.PROVIDER.value, "provider")
        self.assertEqual(ConnectorType.ROTATION.value, "rotation")
        self.assertEqual(ConnectorType.SECRET_STORE.value, "secret_store")
        self.assertEqual(ConnectorType.STORAGE.value, "storage")
        self.assertEqual(ConnectorType.OBSERVABILITY.value, "observability")
        self.assertEqual(ConnectorType.DISCOVERY.value, "discovery")

    def test_connector_type_all_members(self):
        expected = {
            "PROVIDER", "ROTATION", "SECRET_STORE",
            "STORAGE", "OBSERVABILITY", "DISCOVERY",
        }
        actual = {m.name for m in ConnectorType}
        self.assertEqual(actual, expected)

    def test_model_status_reexport(self):
        self.assertEqual(ModelStatus.ACTIVE.value, "active")
        self.assertEqual(ModelStatus.STANDBY.value, "standby")

    def test_deactivation_reason_reexport(self):
        self.assertIn("error_threshold", DeactivationReason.ERROR_THRESHOLD.value)

    def test_recovery_trigger_reexport(self):
        self.assertEqual(RecoveryTrigger.COOLDOWN_EXPIRED.value, "cooldown_expired")
        self.assertEqual(RecoveryTrigger.QUOTA_RESET.value, "quota_reset")
        self.assertEqual(RecoveryTrigger.PROBE_SUCCESS.value, "probe_success")
        self.assertEqual(RecoveryTrigger.MANUAL.value, "manual")

    def test_sync_policy_values(self):
        self.assertEqual(SyncPolicy.IN_MEMORY.value, "in-memory")
        self.assertEqual(SyncPolicy.IMMEDIATE.value, "immediate")

    def test_serialization_format_values(self):
        self.assertEqual(SerializationFormat.JSON.value, "json")
        self.assertEqual(SerializationFormat.YAML.value, "yaml")
        self.assertEqual(SerializationFormat.MSGPACK.value, "msgpack")


# ---------------------------------------------------------------------------
# 7. CDK Helpers
# ---------------------------------------------------------------------------

class TestCDKHelpers(unittest.TestCase):
    """Test CDK testing helpers."""

    def test_mock_completion_request_defaults(self):
        req = mock_completion_request()
        self.assertEqual(req.model, "test-model")
        self.assertEqual(len(req.messages), 1)
        self.assertEqual(req.messages[0]["role"], "user")
        self.assertEqual(req.messages[0]["content"], "Hello")

    def test_mock_completion_request_custom(self):
        req = mock_completion_request(model="gpt-4o", content="Test prompt")
        self.assertEqual(req.model, "gpt-4o")
        self.assertEqual(req.messages[0]["content"], "Test prompt")

    def test_mock_completion_request_is_completion_request(self):
        req = mock_completion_request()
        self.assertIsInstance(req, CompletionRequest)

    def test_mock_model_snapshot_raises_due_to_provider_id(self):
        """mock_model_snapshot passes provider_id which ModelState does not accept.

        This documents a known issue in the helper: ModelState does not have
        a provider_id field, so the default call raises TypeError.
        """
        with self.assertRaises(TypeError):
            mock_model_snapshot()

    def test_mock_http_client_records_post_calls(self):
        client = MockHttpClient()
        response = asyncio.run(client.post(
            "https://api.example.com/v1/chat",
            headers={"Authorization": "Bearer key"},
            json={"model": "gpt-4o"},
        ))
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["method"], "POST")
        self.assertEqual(client.calls[0]["url"], "https://api.example.com/v1/chat")
        self.assertEqual(client.calls[0]["json"]["model"], "gpt-4o")

    def test_mock_http_client_records_get_calls(self):
        client = MockHttpClient()
        asyncio.run(client.get("https://api.example.com/v1/models"))
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["method"], "GET")

    def test_mock_http_client_returns_canned_response(self):
        client = MockHttpClient()
        client.add_response(MockHttpResponse(
            status_code=200,
            body='{"ok": true}',
        ))
        response = asyncio.run(client.post("https://api.example.com/test"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

    def test_mock_http_client_default_response(self):
        client = MockHttpClient()
        response = asyncio.run(client.post("https://example.com/api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, "{}")

    def test_mock_http_response_json(self):
        resp = MockHttpResponse(body='{"key": "value"}')
        self.assertEqual(resp.json(), {"key": "value"})

    def test_connector_test_harness_wraps_connector(self):
        config = OpenAICompatibleConfig(
            base_url="https://api.test.com",
            api_key="key",
            models=[ModelInfo(id="m1", name="M1")],
        )
        provider = OpenAICompatibleProvider(config)
        harness = ConnectorTestHarness(provider)
        self.assertIs(harness.connector, provider)
        self.assertEqual(len(harness.calls), 0)


# ---------------------------------------------------------------------------
# 8. RetryMixin, CacheMixin, RateLimiterMixin
# ---------------------------------------------------------------------------

class TestRetryMixin(unittest.TestCase):
    """Test the RetryMixin class."""

    def test_default_attributes(self):
        mixin = RetryMixin()
        self.assertEqual(mixin._retry_max_attempts, 3)
        self.assertEqual(mixin._retry_base_delay, 1.0)
        self.assertEqual(mixin._retry_max_delay, 30.0)
        self.assertEqual(mixin._retry_exponential_base, 2.0)
        self.assertTrue(mixin._retry_jitter)

    def test_custom_attributes(self):
        class CustomRetry(RetryMixin):
            _retry_max_attempts = 5
            _retry_base_delay = 0.5
            _retry_max_delay = 10.0

        mixin = CustomRetry()
        self.assertEqual(mixin._retry_max_attempts, 5)
        self.assertEqual(mixin._retry_base_delay, 0.5)
        self.assertEqual(mixin._retry_max_delay, 10.0)

    def test_is_retryable_error_default(self):
        mixin = RetryMixin()
        self.assertTrue(mixin._is_retryable_error(RuntimeError("test")))

    def test_calculate_delay(self):
        mixin = RetryMixin()
        mixin._retry_jitter = False
        delay0 = mixin._calculate_delay(0)
        self.assertAlmostEqual(delay0, 1.0)
        delay1 = mixin._calculate_delay(1)
        self.assertAlmostEqual(delay1, 2.0)
        delay2 = mixin._calculate_delay(2)
        self.assertAlmostEqual(delay2, 4.0)

    def test_calculate_delay_capped(self):
        mixin = RetryMixin()
        mixin._retry_jitter = False
        mixin._retry_max_delay = 5.0
        delay = mixin._calculate_delay(10)
        self.assertLessEqual(delay, 5.0)

    def test_retry_succeeds_on_first_attempt(self):
        mixin = RetryMixin()

        async def succeed():
            return "ok"

        result = asyncio.run(mixin._retry(succeed))
        self.assertEqual(result, "ok")

    def test_retry_retries_and_succeeds(self):
        mixin = RetryMixin()
        mixin._retry_base_delay = 0.01  # fast for tests
        mixin._retry_jitter = False
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient")
            return "recovered"

        result = asyncio.run(mixin._retry(fail_then_succeed))
        self.assertEqual(result, "recovered")
        self.assertEqual(call_count, 3)

    def test_retry_exhausts_attempts(self):
        mixin = RetryMixin()
        mixin._retry_max_attempts = 2
        mixin._retry_base_delay = 0.01
        mixin._retry_jitter = False

        async def always_fail():
            raise RuntimeError("permanent")

        with self.assertRaises(RuntimeError):
            asyncio.run(mixin._retry(always_fail))


class TestCacheMixin(unittest.TestCase):
    """Test the CacheMixin class."""

    def _make_cache(self, ttl_ms=60000, max_entries=1024):
        obj = CacheMixin()
        obj._init_cache(ttl_ms=ttl_ms, max_entries=max_entries)
        return obj

    def test_init_cache(self):
        cache = self._make_cache()
        self.assertEqual(cache._cache_ttl_ms, 60000)
        self.assertEqual(cache._cache_max_entries, 1024)

    def test_cache_set_and_get(self):
        cache = self._make_cache()
        cache._cache_set("key1", "value1")
        result = cache._cache_get("key1")
        self.assertEqual(result, "value1")

    def test_cache_get_miss(self):
        cache = self._make_cache()
        result = cache._cache_get("nonexistent")
        self.assertIsNone(result)

    def test_cache_invalidate(self):
        cache = self._make_cache()
        cache._cache_set("key1", "value1")
        cache._cache_invalidate("key1")
        result = cache._cache_get("key1")
        self.assertIsNone(result)

    def test_cache_clear(self):
        cache = self._make_cache()
        cache._cache_set("a", 1)
        cache._cache_set("b", 2)
        cache._cache_clear()
        self.assertIsNone(cache._cache_get("a"))
        self.assertIsNone(cache._cache_get("b"))

    def test_cache_stats(self):
        cache = self._make_cache()
        cache._cache_set("k", "v")
        cache._cache_get("k")  # hit
        cache._cache_get("missing")  # miss
        stats = cache._cache_stats()
        self.assertIsInstance(stats, CacheStats)
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.size, 1)

    def test_cache_lru_eviction(self):
        cache = self._make_cache(max_entries=2)
        cache._cache_set("a", 1)
        cache._cache_set("b", 2)
        # Access "a" to make it recently used
        cache._cache_get("a")
        # Adding "c" should evict "b" (least recently accessed)
        cache._cache_set("c", 3)
        self.assertIsNone(cache._cache_get("b"))
        self.assertEqual(cache._cache_get("a"), 1)
        self.assertEqual(cache._cache_get("c"), 3)


class TestRateLimiterMixin(unittest.TestCase):
    """Test the RateLimiterMixin class."""

    def test_default_attributes(self):
        mixin = RateLimiterMixin()
        self.assertEqual(mixin._rate_limit_rpm, 60)
        self.assertEqual(mixin._rate_limit_tpm, 100_000)
        self.assertEqual(mixin._rate_limit_min_delay, 0)

    def test_init_rate_limiter(self):
        mixin = RateLimiterMixin()
        mixin.__init_rate_limiter__()
        self.assertEqual(mixin._request_timestamps, [])
        self.assertEqual(mixin._token_counts, [])
        self.assertEqual(mixin._last_request_at, 0)

    def test_record_tokens(self):
        mixin = RateLimiterMixin()
        mixin.__init_rate_limiter__()
        mixin._rate_limit_record_tokens(500)
        self.assertEqual(len(mixin._token_counts), 1)
        self.assertEqual(mixin._token_counts[0][1], 500)

    def test_acquire_basic(self):
        mixin = RateLimiterMixin()
        mixin.__init_rate_limiter__()
        asyncio.run(mixin._rate_limit_acquire(estimated_tokens=100))
        self.assertEqual(len(mixin._request_timestamps), 1)


# ---------------------------------------------------------------------------
# 9. StickUntilFailurePolicy
# ---------------------------------------------------------------------------

class TestStickUntilFailurePolicy(unittest.TestCase):
    """Test the StickUntilFailurePolicy connector."""

    def test_connector_id(self):
        policy = StickUntilFailurePolicy()
        self.assertEqual(policy.CONNECTOR_ID, "modelmesh.stick-until-failure.v1")

    def test_default_instantiation(self):
        policy = StickUntilFailurePolicy()
        self.assertIsNotNone(policy.deactivation)
        self.assertIsNotNone(policy.recovery)
        self.assertIsNotNone(policy.selection)

    def test_custom_config(self):
        config = StickUntilFailureConfig(failure_threshold=5, cooldown_seconds=120.0)
        policy = StickUntilFailurePolicy(config)
        self.assertIsNotNone(policy)

    def test_deactivation_threshold(self):
        policy = StickUntilFailurePolicy(StickUntilFailureConfig(failure_threshold=3))
        state = ModelState(model_id="test", failure_count=3)
        self.assertTrue(policy.deactivation.should_deactivate(state))

    def test_deactivation_below_threshold(self):
        policy = StickUntilFailurePolicy(StickUntilFailureConfig(failure_threshold=3))
        state = ModelState(model_id="test", failure_count=1)
        self.assertFalse(policy.deactivation.should_deactivate(state))

    def test_select_returns_first_active_model(self):
        policy = StickUntilFailurePolicy()
        request = CompletionRequest(
            model="test", messages=[{"role": "user", "content": "hi"}]
        )
        candidates = [
            ModelState(model_id="a", error_rate=0.0),
            ModelState(model_id="b", error_rate=0.1),
        ]
        selected = policy.selection.select(candidates, request)
        self.assertIsNotNone(selected)
        # Should pick the one with lowest error rate (highest score)
        self.assertEqual(selected.model_id, "a")

    def test_select_empty_returns_none(self):
        policy = StickUntilFailurePolicy()
        request = CompletionRequest(model="test", messages=[])
        self.assertIsNone(policy.selection.select([], request))

    def test_on_failure_rotates_to_next(self):
        config = StickUntilFailureConfig(failure_threshold=2)
        policy = StickUntilFailurePolicy(config)
        request = CompletionRequest(
            model="test", messages=[{"role": "user", "content": "hi"}]
        )
        # Model A has exceeded failure threshold
        model_a = ModelState(model_id="a", failure_count=2, error_rate=0.8)
        model_b = ModelState(model_id="b", failure_count=0, error_rate=0.0)

        # Deactivation should trigger for model A
        self.assertTrue(policy.deactivation.should_deactivate(model_a))
        self.assertFalse(policy.deactivation.should_deactivate(model_b))

        # Only model B remains as a candidate
        selected = policy.selection.select([model_b], request)
        self.assertEqual(selected.model_id, "b")

    def test_recovery_after_cooldown(self):
        config = StickUntilFailureConfig(cooldown_seconds=60.0)
        policy = StickUntilFailurePolicy(config)
        # Cooldown expired
        state = ModelState(model_id="test", cooldown_until=time.time() - 10)
        self.assertTrue(policy.recovery.should_recover(state))
        # Cooldown still active
        state2 = ModelState(model_id="test2", cooldown_until=time.time() + 1000)
        self.assertFalse(policy.recovery.should_recover(state2))


# ---------------------------------------------------------------------------
# 10. LocalFileStorage
# ---------------------------------------------------------------------------

class TestLocalFileStorage(unittest.TestCase):
    """Test the LocalFileStorage connector."""

    def test_connector_id(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            tmp_path = f.name
        try:
            config = LocalFileStorageConfig(file_path=tmp_path)
            storage = LocalFileStorage(config)
            self.assertEqual(storage.CONNECTOR_ID, "modelmesh.local-file.v1")
        finally:
            os.unlink(tmp_path)

    def test_default_config(self):
        config = LocalFileStorageConfig()
        self.assertEqual(config.backend, "file")
        self.assertEqual(config.file_path, "modelmesh_state.json")

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "state.json")
            config = LocalFileStorageConfig(file_path=file_path)
            storage = LocalFileStorage(config)

            entry = StorageEntry(
                key="model.state",
                data=b"model-state-data",
                metadata={"version": "1"},
            )
            asyncio.run(storage.save("model.state", entry))
            loaded = asyncio.run(storage.load("model.state"))
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.data, b"model-state-data")
            self.assertEqual(loaded.metadata["version"], "1")

    def test_list_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "state.json")
            config = LocalFileStorageConfig(file_path=file_path)
            storage = LocalFileStorage(config)

            asyncio.run(storage.save(
                "a", StorageEntry(key="a", data=b"1", metadata={})
            ))
            asyncio.run(storage.save(
                "b", StorageEntry(key="b", data=b"2", metadata={})
            ))
            keys = asyncio.run(storage.list())
            self.assertIn("a", keys)
            self.assertIn("b", keys)

    def test_delete_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "state.json")
            config = LocalFileStorageConfig(file_path=file_path)
            storage = LocalFileStorage(config)

            asyncio.run(storage.save(
                "key", StorageEntry(key="key", data=b"data", metadata={})
            ))
            result = asyncio.run(storage.delete("key"))
            self.assertTrue(result)
            loaded = asyncio.run(storage.load("key"))
            self.assertIsNone(loaded)

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "state.json")

            # Write with first instance
            config1 = LocalFileStorageConfig(file_path=file_path)
            storage1 = LocalFileStorage(config1)
            asyncio.run(storage1.save(
                "persist",
                StorageEntry(key="persist", data=b"durable", metadata={}),
            ))

            # Read with second instance
            config2 = LocalFileStorageConfig(file_path=file_path)
            storage2 = LocalFileStorage(config2)
            loaded = asyncio.run(storage2.load("persist"))
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.data, b"durable")


if __name__ == "__main__":
    unittest.main()
