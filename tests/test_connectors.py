"""Tests for pre-shipped connectors: OpenAI, Anthropic, EnvSecretStore, Registry."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.connectors.providers.openai_provider import (
    OpenAIProvider,
    OpenAIProviderConfig,
)
from modelmesh.connectors.providers.anthropic_provider import (
    AnthropicProvider,
    AnthropicProviderConfig,
)
from modelmesh.connectors.secret_stores.env_store import (
    EnvSecretStore,
    EnvSecretStoreConfig,
)
from modelmesh.connectors import CONNECTOR_REGISTRY
from modelmesh.interfaces.provider import CompletionRequest


class TestOpenAIProvider(unittest.TestCase):
    """Test the OpenAI provider connector."""

    def setUp(self):
        self.config = OpenAIProviderConfig(api_key="sk-test-key")
        self.provider = OpenAIProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(OpenAIProvider.CONNECTOR_ID, "openai.llm.v1")

    def test_default_models(self):
        models = self.provider.list_models()
        self.assertGreater(len(models), 0)
        model_ids = [m.id for m in models]
        self.assertIn("gpt-4o", model_ids)
        self.assertIn("gpt-4o-mini", model_ids)

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.openai.com")

    def test_headers(self):
        headers = self.provider._build_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Authorization"], "Bearer sk-test-key")

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(
            endpoint, "https://api.openai.com/v1/chat/completions"
        )

    def test_supports_chat_completion(self):
        self.assertTrue(
            self.provider.supports("generation.text-generation.chat-completion")
        )

    def test_default_config_no_args(self):
        provider = OpenAIProvider()
        models = provider.list_models()
        self.assertGreater(len(models), 0)


class TestAnthropicProvider(unittest.TestCase):
    """Test the Anthropic provider connector."""

    def setUp(self):
        self.config = AnthropicProviderConfig(api_key="sk-ant-test-key")
        self.provider = AnthropicProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(
            AnthropicProvider.CONNECTOR_ID, "anthropic.claude.v1"
        )

    def test_headers_use_x_api_key(self):
        headers = self.provider._build_headers()
        self.assertIn("x-api-key", headers)
        self.assertEqual(headers["x-api-key"], "sk-ant-test-key")
        self.assertNotIn("Authorization", headers)

    def test_headers_anthropic_version(self):
        headers = self.provider._build_headers()
        self.assertIn("anthropic-version", headers)
        self.assertEqual(headers["anthropic-version"], "2023-06-01")

    def test_build_payload_separates_system(self):
        request = CompletionRequest(
            model="claude-sonnet-4-20250514",
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
        )
        payload = self.provider._build_request_payload(request)
        self.assertIn("system", payload)
        self.assertEqual(payload["system"], "You are helpful.")
        # User message should be in messages array without system
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0]["role"], "user")

    def test_build_payload_no_system(self):
        request = CompletionRequest(
            model="claude-sonnet-4-20250514",
            messages=[
                {"role": "user", "content": "Hello"},
            ],
        )
        payload = self.provider._build_request_payload(request)
        self.assertNotIn("system", payload)

    def test_build_payload_max_tokens_default(self):
        request = CompletionRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hi"}],
        )
        payload = self.provider._build_request_payload(request)
        self.assertIn("max_tokens", payload)
        # Should use the model's max_output_tokens or 4096 fallback
        self.assertGreater(payload["max_tokens"], 0)

    def test_parse_response(self):
        data = {
            "id": "msg_123",
            "type": "message",
            "model": "claude-sonnet-4-20250514",
            "content": [
                {"type": "text", "text": "Hello from Claude!"}
            ],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
            },
        }
        response = self.provider._parse_response(data)
        self.assertEqual(response.id, "msg_123")
        self.assertEqual(response.choices[0].message.content, "Hello from Claude!")
        self.assertEqual(response.choices[0].finish_reason, "stop")
        self.assertEqual(response.usage.prompt_tokens, 10)
        self.assertEqual(response.usage.completion_tokens, 5)
        self.assertEqual(response.usage.total_tokens, 15)

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(
            endpoint, "https://api.anthropic.com/v1/messages"
        )

    def test_default_models(self):
        models = self.provider.list_models()
        self.assertGreater(len(models), 0)

    def test_default_config_no_args(self):
        provider = AnthropicProvider()
        models = provider.list_models()
        self.assertGreater(len(models), 0)


class TestEnvSecretStore(unittest.TestCase):
    """Test the environment variable secret store."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real-key"}, clear=False)
    def test_resolve_existing_var(self):
        store = EnvSecretStore()
        value = store.get("OPENAI_API_KEY")
        self.assertEqual(value, "sk-real-key")

    def test_resolve_missing_var(self):
        config = EnvSecretStoreConfig(fail_on_missing=True)
        store = EnvSecretStore(config)
        # Ensure the var doesn't exist
        env_key = "MODELMESH_TEST_NONEXISTENT_VAR_12345"
        if env_key in os.environ:
            del os.environ[env_key]
        with self.assertRaises(KeyError):
            store.get(env_key)

    @patch.dict(
        os.environ,
        {"MODELMESH_OPENAI_KEY": "sk-prefixed"},
        clear=False,
    )
    def test_resolve_with_prefix(self):
        config = EnvSecretStoreConfig(prefix="MODELMESH_")
        store = EnvSecretStore(config)
        value = store.get("OPENAI_KEY")
        self.assertEqual(value, "sk-prefixed")

    def test_connector_id(self):
        self.assertEqual(EnvSecretStore.CONNECTOR_ID, "modelmesh.env.v1")

    def test_default_config(self):
        store = EnvSecretStore()
        self.assertEqual(store._env_config.prefix, "")


class TestConnectorRegistry(unittest.TestCase):
    """Test the connector registry."""

    def test_has_expected_connectors(self):
        self.assertEqual(len(CONNECTOR_REGISTRY), 16)

    def test_all_have_connector_id(self):
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

    def test_registry_contains_openai(self):
        self.assertIn("openai.llm.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_anthropic(self):
        self.assertIn("anthropic.claude.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_null_obs(self):
        self.assertIn("modelmesh.null.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_file_obs(self):
        self.assertIn("modelmesh.file.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_console_obs(self):
        self.assertIn("modelmesh.console.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_env_store(self):
        self.assertIn("modelmesh.env.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_rotation(self):
        self.assertIn("modelmesh.stick-until-failure.v1", CONNECTOR_REGISTRY)

    def test_registry_contains_storage(self):
        self.assertIn("modelmesh.local-file.v1", CONNECTOR_REGISTRY)


if __name__ == "__main__":
    unittest.main()
