"""Tests for MeshConfig and auto-detection."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.config.mesh_config import MeshConfig
from modelmesh.config.auto_detect import detect_providers, PROVIDER_REGISTRY


class TestMeshConfig(unittest.TestCase):
    """Test the MeshConfig class."""

    def test_from_dict(self):
        data = {
            "providers": {"openai": {"connector": "openai.llm.v1"}},
            "models": {"openai.gpt-4o": {"provider": "openai.llm.v1"}},
            "pools": {"chat": {"capability": "chat-completion"}},
        }
        config = MeshConfig.from_dict(data)
        self.assertIsInstance(config, MeshConfig)
        self.assertEqual(config.raw, data)

    def test_providers_property(self):
        config = MeshConfig(raw={
            "providers": {"test": {"connector": "test.v1"}},
        })
        self.assertEqual(config.providers, {"test": {"connector": "test.v1"}})

    def test_providers_property_default(self):
        config = MeshConfig(raw={})
        self.assertEqual(config.providers, {})

    def test_pools_property(self):
        config = MeshConfig(raw={
            "pools": {"chat": {"capability": "chat-completion"}},
        })
        self.assertEqual(config.pools, {"chat": {"capability": "chat-completion"}})

    def test_models_property(self):
        config = MeshConfig(raw={
            "models": {"openai.gpt-4o": {"provider": "openai.llm.v1"}},
        })
        self.assertIn("openai.gpt-4o", config.models)

    def test_get(self):
        config = MeshConfig(raw={"observability": {"connector": "console"}})
        self.assertEqual(config.get("observability"), {"connector": "console"})
        self.assertIsNone(config.get("nonexistent"))
        self.assertEqual(config.get("nonexistent", "default"), "default")

    def test_secrets_property(self):
        config = MeshConfig(raw={"secrets": {"store": "modelmesh.env.v1"}})
        self.assertEqual(config.secrets, {"store": "modelmesh.env.v1"})

    def test_observability_property(self):
        config = MeshConfig(raw={
            "observability": {"connector": "modelmesh.file.v1"}
        })
        self.assertEqual(
            config.observability, {"connector": "modelmesh.file.v1"}
        )

    def test_storage_property(self):
        config = MeshConfig(raw={
            "storage": {"connector": "modelmesh.local-file.v1"}
        })
        self.assertEqual(
            config.storage, {"connector": "modelmesh.local-file.v1"}
        )

    def test_merge(self):
        config = MeshConfig(raw={
            "providers": {"a": {"connector": "a.v1"}},
            "pools": {"chat": {"capability": "chat"}},
        })
        merged = config.merge({"providers": {"b": {"connector": "b.v1"}}})
        self.assertIn("a", merged.providers)
        self.assertIn("b", merged.providers)

    def test_validate_valid(self):
        config = MeshConfig(raw={
            "providers": {"test": {}},
            "models": {"test.model": {"provider": "test"}},
            "pools": {"pool": {"capability": "chat"}},
        })
        errors = config.validate()
        self.assertEqual(errors, [])

    def test_validate_invalid_providers(self):
        config = MeshConfig(raw={"providers": "not_a_dict"})
        errors = config.validate()
        self.assertIn("'providers' must be a dict", errors)

    def test_default_raw(self):
        config = MeshConfig()
        self.assertEqual(config.raw, {})


class TestAutoDetect(unittest.TestCase):
    """Test provider auto-detection."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-123"}, clear=False)
    def test_detect_with_env_var(self):
        detected = detect_providers()
        names = [d["name"] for d in detected]
        self.assertIn("openai", names)

    @patch.dict(os.environ, {}, clear=True)
    def test_detect_no_env_vars(self):
        detected = detect_providers()
        self.assertEqual(detected, [])

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test",
        "ANTHROPIC_API_KEY": "sk-ant-test",
    }, clear=True)
    def test_detect_with_names_filter(self):
        detected = detect_providers(names=["openai"])
        names = [d["name"] for d in detected]
        self.assertIn("openai", names)
        self.assertNotIn("anthropic", names)

    def test_detect_with_api_keys(self):
        detected = detect_providers(
            api_keys={"openai": "sk-test-key"}
        )
        names = [d["name"] for d in detected]
        self.assertIn("openai", names)
        found = [d for d in detected if d["name"] == "openai"][0]
        self.assertEqual(found["api_key"], "sk-test-key")

    def test_detect_with_api_keys_by_env_var_name(self):
        detected = detect_providers(
            api_keys={"OPENAI_API_KEY": "sk-test-key2"}
        )
        names = [d["name"] for d in detected]
        self.assertIn("openai", names)

    def test_provider_registry_has_expected_providers(self):
        self.assertEqual(len(PROVIDER_REGISTRY), 17)

    def test_provider_registry_entries_have_required_fields(self):
        for env_var, info in PROVIDER_REGISTRY.items():
            self.assertIn("name", info, f"Missing 'name' in {env_var}")
            self.assertIn("connector", info, f"Missing 'connector' in {env_var}")
            self.assertIn("base_url", info, f"Missing 'base_url' in {env_var}")
            self.assertIn(
                "default_models", info, f"Missing 'default_models' in {env_var}"
            )

    def test_detected_provider_has_api_key(self):
        detected = detect_providers(api_keys={"openai": "test-key"})
        for d in detected:
            self.assertIn("api_key", d)

    def test_detected_provider_has_env_var(self):
        detected = detect_providers(api_keys={"openai": "test-key"})
        for d in detected:
            self.assertIn("env_var", d)


if __name__ == "__main__":
    unittest.main()
