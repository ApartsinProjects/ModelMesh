"""Tests for CDK base classes: BaseProvider, BaseRotation, BaseSecretStore, BaseStorage."""
import asyncio
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.cdk.base_provider import BaseProvider, BaseProviderConfig
from modelmesh.cdk.base_rotation import (
    BaseDeactivationPolicy,
    BaseRecoveryPolicy,
    BaseRotationConfig,
    BaseRotationPolicy,
    BaseSelectionStrategy,
)
from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig
from modelmesh.cdk.base_storage import BaseStorage, BaseStorageConfig
from modelmesh.interfaces.provider import (
    CompletionRequest,
    ErrorClassification,
    ModelInfo,
    ModelPricing,
    TokenUsage,
)
from modelmesh.interfaces.rotation import (
    DeactivationReason,
    ModelState,
    ModelStatus,
)
from modelmesh.interfaces.storage import StorageEntry


class TestBaseProvider(unittest.TestCase):
    """Test the BaseProvider class."""

    def setUp(self):
        self.config = BaseProviderConfig(
            base_url="https://api.test.com",
            api_key="test-key",
            models=[
                ModelInfo(
                    id="test-model",
                    name="Test Model",
                    capabilities=["chat"],
                    pricing=ModelPricing(
                        input_per_1k_tokens=0.01,
                        output_per_1k_tokens=0.03,
                    ),
                ),
            ],
            capabilities=["chat", "tools"],
        )
        self.provider = BaseProvider(self.config)

    def test_get_capabilities(self):
        caps = self.provider.get_capabilities()
        self.assertEqual(caps, ["chat", "tools"])

    def test_supports(self):
        self.assertTrue(self.provider.supports("chat"))
        self.assertTrue(self.provider.supports("tools"))
        self.assertFalse(self.provider.supports("embeddings"))

    def test_list_models(self):
        models = self.provider.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "test-model")

    def test_get_model_info(self):
        info = self.provider.get_model_info("test-model")
        self.assertEqual(info.id, "test-model")
        self.assertEqual(info.name, "Test Model")

    def test_get_model_info_missing_raises(self):
        with self.assertRaises(KeyError):
            self.provider.get_model_info("nonexistent")

    def test_classify_error_retryable(self):
        class FakeHTTPError(Exception):
            code = 429

        err = FakeHTTPError()
        result = self.provider.classify_error(err)
        self.assertTrue(result.retryable)
        self.assertEqual(result.category, "rate_limit")

    def test_classify_error_server_retryable(self):
        class FakeHTTPError(Exception):
            code = 500

        result = self.provider.classify_error(FakeHTTPError())
        self.assertTrue(result.retryable)
        self.assertEqual(result.category, "server")

    def test_classify_error_non_retryable(self):
        class FakeHTTPError(Exception):
            code = 401

        err = FakeHTTPError()
        result = self.provider.classify_error(err)
        self.assertFalse(result.retryable)
        self.assertEqual(result.category, "auth")

    def test_classify_error_client(self):
        class FakeHTTPError(Exception):
            code = 400

        result = self.provider.classify_error(FakeHTTPError())
        self.assertFalse(result.retryable)
        self.assertEqual(result.category, "client")

    def test_classify_error_unknown(self):
        result = self.provider.classify_error(RuntimeError("generic"))
        self.assertFalse(result.retryable)
        self.assertEqual(result.category, "unknown")

    def test_is_retryable(self):
        class FakeHTTPError(Exception):
            code = 429

        self.assertTrue(self.provider.is_retryable(FakeHTTPError()))
        self.assertFalse(self.provider.is_retryable(RuntimeError("fail")))

    def test_report_usage(self):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        self.provider.report_usage("test-model", usage)
        self.assertEqual(self.provider._request_count, 1)
        self.assertEqual(self.provider._tokens_used, 15)

    def test_build_request_payload(self):
        request = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            max_tokens=100,
        )
        payload = self.provider._build_request_payload(request)
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["messages"], request.messages)
        self.assertEqual(payload["temperature"], 0.7)
        self.assertEqual(payload["max_tokens"], 100)

    def test_parse_response(self):
        data = {
            "id": "cmpl-123",
            "model": "test-model",
            "choices": [
                {"index": 0, "finish_reason": "stop"}
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        response = self.provider._parse_response(data)
        self.assertEqual(response.id, "cmpl-123")
        self.assertEqual(response.usage.total_tokens, 15)
        self.assertEqual(len(response.choices), 1)

    def test_parse_response_extracts_message_with_role_content_tool_calls(self):
        """_parse_response creates a ChatMessage with role, content, and tool_calls."""
        data = {
            "id": "cmpl-msg-1",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "Let me call a tool.",
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city": "Paris"}',
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
            },
        }
        response = self.provider._parse_response(data)
        self.assertEqual(len(response.choices), 1)
        choice = response.choices[0]
        self.assertIsNotNone(choice.message)
        self.assertEqual(choice.message.role, "assistant")
        self.assertEqual(choice.message.content, "Let me call a tool.")
        self.assertIsNotNone(choice.message.tool_calls)
        self.assertEqual(len(choice.message.tool_calls), 1)
        self.assertEqual(choice.message.tool_calls[0]["id"], "call_abc")
        self.assertEqual(choice.finish_reason, "tool_calls")

    def test_parse_response_message_with_content_only(self):
        """_parse_response creates a ChatMessage when only role and content are present."""
        data = {
            "id": "cmpl-msg-2",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "Hello, world!",
                    },
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        response = self.provider._parse_response(data)
        choice = response.choices[0]
        self.assertIsNotNone(choice.message)
        self.assertEqual(choice.message.role, "assistant")
        self.assertEqual(choice.message.content, "Hello, world!")
        self.assertIsNone(choice.message.tool_calls)

    def test_parse_response_missing_message_null(self):
        """_parse_response handles choices where message is explicitly null."""
        data = {
            "id": "cmpl-null",
            "model": "test-model",
            "choices": [
                {"index": 0, "finish_reason": "stop", "message": None}
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        response = self.provider._parse_response(data)
        self.assertEqual(len(response.choices), 1)
        self.assertIsNone(response.choices[0].message)

    def test_parse_response_missing_message_absent(self):
        """_parse_response handles choices where message key is absent."""
        data = {
            "id": "cmpl-absent",
            "model": "test-model",
            "choices": [
                {"index": 0, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        response = self.provider._parse_response(data)
        self.assertEqual(len(response.choices), 1)
        self.assertIsNone(response.choices[0].message)

    # -- _parse_sse_chunk tests --

    def test_parse_sse_chunk_extracts_delta_with_role_content_tool_calls(self):
        """_parse_sse_chunk creates a ChatMessage delta with role, content, and tool_calls."""
        chunk_data = {
            "id": "chatcmpl-stream-1",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": None,
                    "delta": {
                        "role": "assistant",
                        "content": "Hello",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_xyz",
                                "type": "function",
                                "function": {"name": "search", "arguments": ""},
                            }
                        ],
                    },
                }
            ],
        }
        line = json.dumps(chunk_data)
        result = self.provider._parse_sse_chunk(line)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "chatcmpl-stream-1")
        self.assertEqual(len(result.choices), 1)
        delta = result.choices[0].delta
        self.assertIsNotNone(delta)
        self.assertEqual(delta.role, "assistant")
        self.assertEqual(delta.content, "Hello")
        self.assertIsNotNone(delta.tool_calls)
        self.assertEqual(len(delta.tool_calls), 1)
        self.assertEqual(delta.tool_calls[0]["id"], "call_xyz")

    def test_parse_sse_chunk_content_only(self):
        """_parse_sse_chunk extracts delta with content and default role."""
        chunk_data = {
            "id": "chatcmpl-stream-2",
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": None,
                    "delta": {"content": " world"},
                }
            ],
        }
        line = json.dumps(chunk_data)
        result = self.provider._parse_sse_chunk(line)
        self.assertIsNotNone(result)
        delta = result.choices[0].delta
        self.assertIsNotNone(delta)
        self.assertEqual(delta.content, " world")
        self.assertEqual(delta.role, "assistant")  # default role
        self.assertIsNone(delta.tool_calls)

    def test_parse_sse_chunk_missing_delta_null(self):
        """_parse_sse_chunk handles choices where delta is explicitly null."""
        chunk_data = {
            "id": "chatcmpl-stream-3",
            "model": "test-model",
            "choices": [
                {"index": 0, "finish_reason": "stop", "delta": None}
            ],
        }
        line = json.dumps(chunk_data)
        result = self.provider._parse_sse_chunk(line)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.choices), 1)
        self.assertIsNone(result.choices[0].delta)

    def test_parse_sse_chunk_missing_delta_absent(self):
        """_parse_sse_chunk handles choices where delta key is absent."""
        chunk_data = {
            "id": "chatcmpl-stream-4",
            "model": "test-model",
            "choices": [
                {"index": 0, "finish_reason": "stop"}
            ],
        }
        line = json.dumps(chunk_data)
        result = self.provider._parse_sse_chunk(line)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.choices), 1)
        self.assertIsNone(result.choices[0].delta)

    def test_parse_sse_chunk_invalid_json_returns_none(self):
        """_parse_sse_chunk returns None for invalid JSON input."""
        self.assertIsNone(self.provider._parse_sse_chunk("not valid json"))
        self.assertIsNone(self.provider._parse_sse_chunk(""))
        bad_json = '{"truncated'
        self.assertIsNone(self.provider._parse_sse_chunk(bad_json))

    def test_parse_sse_chunk_empty_choices_returns_none(self):
        """_parse_sse_chunk returns None when choices array is empty."""
        line = json.dumps({"id": "x", "model": "y", "choices": []})
        self.assertIsNone(self.provider._parse_sse_chunk(line))

    def test_build_headers(self):
        headers = self.provider._build_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Authorization"], "Bearer test-key")

    def test_build_headers_no_api_key(self):
        config = BaseProviderConfig(base_url="https://test.com", api_key="")
        provider = BaseProvider(config)
        headers = provider._build_headers()
        self.assertNotIn("Authorization", headers)

    def test_get_completion_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(
            endpoint, "https://api.test.com/v1/chat/completions"
        )

    def test_check_quota(self):
        quota = self.provider.check_quota()
        self.assertEqual(quota.used, 0)

    def test_get_rate_limits(self):
        limits = self.provider.get_rate_limits()
        self.assertIsNone(limits.requests_remaining)

    def test_get_pricing(self):
        pricing = self.provider.get_pricing("test-model")
        self.assertEqual(pricing.input_per_1k_tokens, 0.01)

    def test_get_pricing_missing(self):
        config = BaseProviderConfig(
            models=[ModelInfo(id="no-pricing", name="No Pricing")],
        )
        provider = BaseProvider(config)
        with self.assertRaises(KeyError):
            provider.get_pricing("no-pricing")


class TestBaseRotation(unittest.TestCase):
    """Test BaseRotation policy classes."""

    def setUp(self):
        self.config = BaseRotationConfig(
            failure_threshold=3,
            cooldown_seconds=60.0,
            error_rate_threshold=0.5,
        )

    def test_deactivation_policy_failure_threshold(self):
        policy = BaseDeactivationPolicy(self.config)
        state = ModelState(model_id="test", failure_count=3)
        self.assertTrue(policy.should_deactivate(state))
        self.assertEqual(
            policy.get_reason(state), DeactivationReason.ERROR_THRESHOLD
        )

    def test_deactivation_policy_below_threshold(self):
        policy = BaseDeactivationPolicy(self.config)
        state = ModelState(model_id="test", failure_count=2)
        self.assertFalse(policy.should_deactivate(state))
        self.assertIsNone(policy.get_reason(state))

    def test_deactivation_policy_error_rate(self):
        policy = BaseDeactivationPolicy(self.config)
        state = ModelState(model_id="test", failure_count=0, error_rate=0.6)
        self.assertTrue(policy.should_deactivate(state))

    def test_deactivation_policy_request_limit(self):
        config = BaseRotationConfig(request_limit=100)
        policy = BaseDeactivationPolicy(config)
        state = ModelState(model_id="test", total_requests=100)
        self.assertTrue(policy.should_deactivate(state))
        self.assertEqual(
            policy.get_reason(state), DeactivationReason.REQUEST_LIMIT
        )

    def test_deactivation_policy_token_limit(self):
        config = BaseRotationConfig(token_limit=1000)
        policy = BaseDeactivationPolicy(config)
        state = ModelState(model_id="test", total_tokens=1000)
        self.assertTrue(policy.should_deactivate(state))
        self.assertEqual(
            policy.get_reason(state), DeactivationReason.TOKEN_LIMIT
        )

    def test_deactivation_policy_budget_limit(self):
        config = BaseRotationConfig(budget_limit=10.0)
        policy = BaseDeactivationPolicy(config)
        state = ModelState(model_id="test", total_cost=10.0)
        self.assertTrue(policy.should_deactivate(state))
        self.assertEqual(
            policy.get_reason(state), DeactivationReason.BUDGET_EXCEEDED
        )

    def test_recovery_policy_no_cooldown(self):
        policy = BaseRecoveryPolicy(self.config)
        state = ModelState(model_id="test", cooldown_until=None)
        self.assertTrue(policy.should_recover(state))

    def test_recovery_policy_cooldown_expired(self):
        import time

        policy = BaseRecoveryPolicy(self.config)
        state = ModelState(model_id="test", cooldown_until=time.time() - 10)
        self.assertTrue(policy.should_recover(state))

    def test_recovery_policy_cooldown_active(self):
        import time

        policy = BaseRecoveryPolicy(self.config)
        state = ModelState(
            model_id="test", cooldown_until=time.time() + 1000
        )
        self.assertFalse(policy.should_recover(state))

    def test_recovery_schedule_for_standby(self):
        import time

        policy = BaseRecoveryPolicy(self.config)
        state = ModelState(model_id="test", status=ModelStatus.STANDBY)
        schedule = policy.get_recovery_schedule(state)
        self.assertIsNotNone(schedule)
        self.assertGreater(schedule, time.time())

    def test_recovery_schedule_for_active(self):
        policy = BaseRecoveryPolicy(self.config)
        state = ModelState(model_id="test", status=ModelStatus.ACTIVE)
        self.assertIsNone(policy.get_recovery_schedule(state))

    def test_selection_strategy(self):
        strategy = BaseSelectionStrategy(self.config)
        request = CompletionRequest(
            model="test",
            messages=[{"role": "user", "content": "hi"}],
        )
        candidates = [
            ModelState(model_id="a", error_rate=0.1),
            ModelState(model_id="b", error_rate=0.5),
        ]
        selected = strategy.select(candidates, request)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.model_id, "a")  # lower error rate

    def test_selection_strategy_empty(self):
        strategy = BaseSelectionStrategy(self.config)
        request = CompletionRequest(model="test", messages=[])
        selected = strategy.select([], request)
        self.assertIsNone(selected)

    def test_selection_strategy_priority(self):
        config = BaseRotationConfig(model_priority=["b", "a"])
        strategy = BaseSelectionStrategy(config)
        request = CompletionRequest(model="test", messages=[])
        candidates = [
            ModelState(model_id="a"),
            ModelState(model_id="b"),
        ]
        selected = strategy.select(candidates, request)
        self.assertEqual(selected.model_id, "b")

    def test_combined_rotation_policy(self):
        policy = BaseRotationPolicy(self.config)
        state = ModelState(model_id="test", failure_count=3)
        self.assertTrue(policy.should_deactivate(state))
        self.assertEqual(
            policy.get_reason(state), DeactivationReason.ERROR_THRESHOLD
        )

        state2 = ModelState(model_id="test2", cooldown_until=None)
        self.assertTrue(policy.should_recover(state2))

        request = CompletionRequest(model="test", messages=[])
        candidates = [ModelState(model_id="c")]
        selected = policy.select(candidates, request)
        self.assertIsNotNone(selected)


class TestBaseSecretStore(unittest.TestCase):
    """Test BaseSecretStore."""

    def test_resolve(self):
        config = BaseSecretStoreConfig(
            secrets={"API_KEY": "secret-value"},
        )
        store = BaseSecretStore(config)
        self.assertEqual(store.get("API_KEY"), "secret-value")

    def test_resolve_missing_raises(self):
        config = BaseSecretStoreConfig(
            secrets={},
            fail_on_missing=True,
        )
        store = BaseSecretStore(config)
        with self.assertRaises(KeyError):
            store.get("MISSING_KEY")

    def test_resolve_missing_returns_empty(self):
        config = BaseSecretStoreConfig(
            secrets={},
            fail_on_missing=False,
        )
        store = BaseSecretStore(config)
        self.assertEqual(store.get("MISSING"), "")

    def test_caching(self):
        config = BaseSecretStoreConfig(
            secrets={"KEY": "val"},
            cache_enabled=True,
            cache_ttl_ms=300000,
        )
        store = BaseSecretStore(config)
        # First call populates cache
        store.get("KEY")
        # Modify underlying secrets
        config.secrets["KEY"] = "changed"
        # Should still return cached value
        self.assertEqual(store.get("KEY"), "val")

    def test_clear_cache(self):
        config = BaseSecretStoreConfig(
            secrets={"KEY": "val"},
            cache_enabled=True,
        )
        store = BaseSecretStore(config)
        store.get("KEY")
        store.clear_cache()
        config.secrets["KEY"] = "new_val"
        self.assertEqual(store.get("KEY"), "new_val")


class TestBaseStorage(unittest.TestCase):
    """Test BaseStorage."""

    def setUp(self):
        self.config = BaseStorageConfig()
        self.storage = BaseStorage(self.config)

    def test_save_and_load(self):
        entry = StorageEntry(
            key="test-key", data=b"test-data", metadata={}
        )
        asyncio.run(self.storage.save("test-key", entry))
        loaded = asyncio.run(self.storage.load("test-key"))
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.data, b"test-data")

    def test_load_nonexistent(self):
        loaded = asyncio.run(self.storage.load("missing"))
        self.assertIsNone(loaded)

    def test_list_keys(self):
        entry = StorageEntry(key="a", data=b"", metadata={})
        asyncio.run(self.storage.save("a", entry))
        asyncio.run(self.storage.save("b", StorageEntry(key="b", data=b"", metadata={})))
        keys = asyncio.run(self.storage.list())
        self.assertIn("a", keys)
        self.assertIn("b", keys)

    def test_list_with_prefix(self):
        asyncio.run(
            self.storage.save(
                "state.model-a",
                StorageEntry(key="state.model-a", data=b"", metadata={}),
            )
        )
        asyncio.run(
            self.storage.save(
                "config.pool",
                StorageEntry(key="config.pool", data=b"", metadata={}),
            )
        )
        keys = asyncio.run(self.storage.list(prefix="state."))
        self.assertEqual(len(keys), 1)
        self.assertIn("state.model-a", keys)

    def test_delete(self):
        asyncio.run(
            self.storage.save(
                "key",
                StorageEntry(key="key", data=b"", metadata={}),
            )
        )
        result = asyncio.run(self.storage.delete("key"))
        self.assertTrue(result)
        result2 = asyncio.run(self.storage.delete("key"))
        self.assertFalse(result2)

    def test_exists(self):
        self.assertFalse(asyncio.run(self.storage.exists("key")))
        asyncio.run(
            self.storage.save(
                "key",
                StorageEntry(key="key", data=b"", metadata={}),
            )
        )
        self.assertTrue(asyncio.run(self.storage.exists("key")))

    def test_stat(self):
        asyncio.run(
            self.storage.save(
                "key",
                StorageEntry(key="key", data=b"hello", metadata={}),
            )
        )
        meta = asyncio.run(self.storage.stat("key"))
        self.assertIsNotNone(meta)
        self.assertEqual(meta.key, "key")
        self.assertEqual(meta.size, 5)

    def test_stat_nonexistent(self):
        meta = asyncio.run(self.storage.stat("missing"))
        self.assertIsNone(meta)

    def test_locking(self):
        lock = asyncio.run(self.storage.acquire("key"))
        self.assertTrue(asyncio.run(self.storage.is_locked("key")))
        asyncio.run(self.storage.release(lock))
        self.assertFalse(asyncio.run(self.storage.is_locked("key")))

    def test_locking_disabled_raises(self):
        config = BaseStorageConfig(locking_enabled=False)
        storage = BaseStorage(config)
        with self.assertRaises(RuntimeError):
            asyncio.run(storage.acquire("key"))


if __name__ == "__main__":
    unittest.main()
