"""Tests for the ModelMesh facade class."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from typing import AsyncIterator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

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
from modelmesh.interfaces.rotation import ModelStatus
from modelmesh.connectors.observability.null_connector import NullObservabilityConnector


class _FakeProvider(ProviderConnector):
    """Minimal fake provider for testing."""

    async def complete(self, request):
        return CompletionResponse(
            id="fake-resp",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Fake response"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )

    async def stream(self, request):
        yield CompletionResponse(
            id="fake-chunk",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content="Fake"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(),
        )

    def get_capabilities(self):
        return ["chat"]

    def supports(self, capability):
        return capability == "chat"

    def list_models(self):
        return [ModelInfo(id="fake-model", name="Fake Model")]

    def get_model_info(self, model_id):
        return ModelInfo(id="fake-model", name="Fake Model")

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


def _make_config(observability_connector="modelmesh.null.v1"):
    """Build a minimal MeshConfig for testing."""
    return MeshConfig(raw={
        "providers": {
            "fake.v1": {
                "connector": "fake.v1",
                "enabled": True,
                "instance": _FakeProvider(),
                "config": {},
            },
        },
        "models": {
            "fake.model-a": {
                "provider": "fake.v1",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
            "fake.model-b": {
                "provider": "fake.v1",
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
        "observability": {
            "connector": observability_connector,
        },
    })


class TestModelMesh(unittest.TestCase):
    """Test the ModelMesh class."""

    def test_initialize(self):
        mesh = ModelMesh()
        config = _make_config()
        mesh.initialize(config)
        self.assertTrue(mesh._initialized)

    def test_get_client_before_init_raises(self):
        mesh = ModelMesh()
        with self.assertRaises(RuntimeError) as ctx:
            mesh.get_client()
        self.assertIn("not initialized", str(ctx.exception))

    def test_get_client_returns_mesh_client(self):
        from modelmesh.client.mesh_client import MeshClient

        mesh = ModelMesh()
        mesh.initialize(_make_config())
        client = mesh.get_client()
        self.assertIsInstance(client, MeshClient)

    def test_pool_status(self):
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        status = mesh.pool_status()
        self.assertIn("chat-completion", status)
        pool_info = status["chat-completion"]
        self.assertIn("active", pool_info)
        self.assertIn("standby", pool_info)
        self.assertIn("total", pool_info)
        self.assertEqual(pool_info["total"], 2)

    def test_active_providers(self):
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        active = mesh.active_providers()
        self.assertIsInstance(active, list)
        self.assertIn("fake.v1", active)

    def test_list_models(self):
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        models = mesh.list_models()
        self.assertIsInstance(models, list)
        self.assertGreater(len(models), 0)
        model_ids = [m["id"] for m in models]
        self.assertIn("fake.model-a", model_ids)

    def test_rotate(self):
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        new_model_id = mesh.rotate("chat-completion")
        self.assertIsNotNone(new_model_id)

    def test_rotate_unknown_pool_raises(self):
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        with self.assertRaises(KeyError):
            mesh.rotate("nonexistent-pool")

    def test_shutdown(self):
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        mesh.shutdown()
        self.assertFalse(mesh._initialized)
        with self.assertRaises(RuntimeError):
            mesh.get_client()

    def test_pools_property(self):
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        pools = mesh.pools
        self.assertIn("chat-completion", pools)

    def test_providers_property(self):
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        providers = mesh.providers
        self.assertIn("fake.v1", providers)

    def test_event_emitter_property(self):
        from modelmesh.core.event_emitter import EventEmitter

        mesh = ModelMesh()
        self.assertIsInstance(mesh.event_emitter, EventEmitter)

    def test_state_manager_property(self):
        from modelmesh.core.state_manager import StateManager

        mesh = ModelMesh()
        self.assertIsInstance(mesh.state_manager, StateManager)

    def test_capability_tree_property(self):
        from modelmesh.core.capability_tree import CapabilityTree

        mesh = ModelMesh()
        self.assertIsInstance(mesh.capability_tree, CapabilityTree)

    # -- WITH OBSERVABILITY --

    def test_initialize_emits_trace(self):
        """Verify that initializing the mesh emits trace entries."""
        from modelmesh.cdk.specialized.file_observability import (
            FileObservability,
            FileObservabilityConfig,
        )

        tmp = tempfile.mktemp(suffix=".log")
        try:
            obs = FileObservability(
                FileObservabilityConfig(file_path=tmp, min_severity="debug")
            )
            mesh = ModelMesh()
            mesh._observability = obs
            config = _make_config()
            mesh.initialize(config)
            obs.close()

            with open(tmp, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("Initialized", content)
            self.assertIn('"type": "trace"', content)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_null_observability_default(self):
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        self.assertIsInstance(mesh.observability, NullObservabilityConnector)

    def test_file_observability_config(self):
        """Verify that mesh can be initialized with a file observability config."""
        from modelmesh.cdk.specialized.file_observability import (
            FileObservability,
            FileObservabilityConfig,
        )

        tmp = tempfile.mktemp(suffix=".log")
        try:
            obs = FileObservability(
                FileObservabilityConfig(file_path=tmp, min_severity="info")
            )
            mesh = ModelMesh()
            # Inject observability before initialize
            mesh._observability = obs
            config = _make_config()
            mesh.initialize(config)
            obs.close()

            self.assertTrue(os.path.exists(tmp))
            with open(tmp, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertGreater(len(lines), 0)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


class TestPoolStatus(unittest.TestCase):
    """Tests for CapabilityPool.status() method."""

    def test_status_returns_current_model_key(self):
        """Pool status() uses snake_case 'current_model' key, not camelCase."""
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        pool = mesh.pools["chat-completion"]
        status = pool.status()
        self.assertIn("current_model", status)
        self.assertNotIn("currentModel", status)

    def test_status_shows_correct_model_when_active(self):
        """Pool status() shows the first active model's ID as current_model."""
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        pool = mesh.pools["chat-completion"]
        status = pool.status()
        # With two models both active, current_model should be the first one
        active = pool.active_models
        self.assertGreater(len(active), 0)
        self.assertEqual(status["current_model"], active[0].model_id)
        self.assertGreater(status["active"], 0)
        self.assertEqual(status["total"], 2)

    def test_status_shows_none_when_all_standby(self):
        """Pool status() shows current_model=None when all models are standby."""
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        pool = mesh.pools["chat-completion"]
        # Move all models to standby
        for model in pool.models:
            model.status = ModelStatus.STANDBY
        status = pool.status()
        self.assertIsNone(status["current_model"])
        self.assertEqual(status["active"], 0)
        self.assertEqual(status["standby"], 2)
        self.assertEqual(status["total"], 2)

    def test_status_keys_complete(self):
        """Pool status() returns all expected keys."""
        mesh = ModelMesh()
        mesh.initialize(_make_config())
        pool = mesh.pools["chat-completion"]
        status = pool.status()
        expected_keys = {"active", "standby", "total", "current_model"}
        self.assertEqual(set(status.keys()), expected_keys)


class _ProviderWithDotCaps(_FakeProvider):
    """Fake provider that returns dot-notation capabilities in ModelInfo."""

    def list_models(self):
        return [
            ModelInfo(
                id="gpt-4o",
                name="GPT-4o",
                capabilities=["generation.text-generation.chat-completion"],
            ),
            ModelInfo(
                id="text-embedding-3-small",
                name="Text Embedding 3 Small",
                capabilities=["representation.embeddings.text-embeddings"],
            ),
        ]

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]


class TestCapabilityAutoDiscovery(unittest.TestCase):
    """Tests for capability auto-discovery from provider connectors."""

    def test_capabilities_from_provider_when_config_omits(self):
        """Config model has no 'capabilities' → resolved from provider."""
        provider = _ProviderWithDotCaps()
        config = MeshConfig(raw={
            "providers": {
                "test.v1": {
                    "connector": "test.v1",
                    "instance": provider,
                },
            },
            "models": {
                "test.gpt-4o": {
                    "provider": "test.v1",
                    # No capabilities declared — should come from provider
                },
            },
            "pools": {
                "chat-completion": {
                    "capability": "generation.text-generation.chat-completion",
                },
            },
        })
        mesh = ModelMesh()
        mesh.initialize(config)

        pool = mesh.pools["chat-completion"]
        model_ids = [m.model_id for m in pool.models]
        self.assertIn("test.gpt-4o", model_ids)

    def test_config_capabilities_override_provider(self):
        """Config-declared capabilities win over provider's."""
        provider = _ProviderWithDotCaps()
        config = MeshConfig(raw={
            "providers": {
                "test.v1": {
                    "connector": "test.v1",
                    "instance": provider,
                },
            },
            "models": {
                "test.gpt-4o": {
                    "provider": "test.v1",
                    # Explicitly override with different capability
                    "capabilities": [
                        "representation.embeddings.text-embeddings",
                    ],
                },
            },
            "pools": {
                "chat-completion": {
                    "capability": "generation.text-generation.chat-completion",
                },
                "embeddings": {
                    "capability": "representation.embeddings.text-embeddings",
                },
            },
        })
        mesh = ModelMesh()
        mesh.initialize(config)

        # Model should be in embeddings pool (config override), not chat
        chat_ids = [m.model_id for m in mesh.pools["chat-completion"].models]
        emb_ids = [m.model_id for m in mesh.pools["embeddings"].models]
        self.assertNotIn("test.gpt-4o", chat_ids)
        self.assertIn("test.gpt-4o", emb_ids)

    def test_provider_caps_register_in_tree(self):
        """Provider dot-notation capabilities register in the capability tree."""
        provider = _ProviderWithDotCaps()
        config = MeshConfig(raw={
            "providers": {
                "test.v1": {
                    "connector": "test.v1",
                    "instance": provider,
                },
            },
            "models": {
                "test.gpt-4o": {
                    "provider": "test.v1",
                },
            },
            "pools": {
                "chat-completion": {
                    "capability": "generation.text-generation.chat-completion",
                },
            },
        })
        mesh = ModelMesh()
        mesh.initialize(config)

        self.assertTrue(
            mesh.capability_tree.contains(
                "generation.text-generation.chat-completion"
            )
        )

    def test_no_provider_instance_yields_empty_caps(self):
        """Config model references a stub provider (no instance) → empty caps."""
        config = MeshConfig(raw={
            "providers": {
                "stub.v1": {
                    "connector": "stub.v1",
                    "enabled": True,
                    # No "instance" key — provider is a stub
                },
            },
            "models": {
                "stub.model-a": {
                    "provider": "stub.v1",
                    # No capabilities declared, no provider instance to query
                },
            },
            "pools": {
                "chat-completion": {
                    "capability": "generation.text-generation.chat-completion",
                },
            },
        })
        mesh = ModelMesh()
        mesh.initialize(config)

        # Model should NOT be in the pool (no capabilities to match)
        pool = mesh.pools["chat-completion"]
        model_ids = [m.model_id for m in pool.models]
        self.assertNotIn("stub.model-a", model_ids)

    def test_explicit_models_in_pool(self):
        """Pool with explicit 'models' list adds models by ID."""
        config = MeshConfig(raw={
            "providers": {
                "fake.v1": {
                    "connector": "fake.v1",
                    "instance": _FakeProvider(),
                },
            },
            "models": {
                "fake.model-x": {
                    "provider": "fake.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
                "fake.model-y": {
                    "provider": "fake.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
            },
            "pools": {
                "my-pool": {
                    "models": ["fake.model-x"],
                },
            },
        })
        mesh = ModelMesh()
        mesh.initialize(config)

        pool = mesh.pools["my-pool"]
        model_ids = [m.model_id for m in pool.models]
        self.assertIn("fake.model-x", model_ids)
        self.assertNotIn("fake.model-y", model_ids)

    def test_hybrid_pool_capability_plus_explicit(self):
        """Pool with both 'capability' and 'models' merges both."""
        config = MeshConfig(raw={
            "providers": {
                "fake.v1": {
                    "connector": "fake.v1",
                    "instance": _FakeProvider(),
                },
            },
            "models": {
                "fake.model-a": {
                    "provider": "fake.v1",
                    "capabilities": [
                        "generation.text-generation.chat-completion",
                    ],
                },
                "fake.model-b": {
                    "provider": "fake.v1",
                    "capabilities": [
                        "representation.embeddings.text-embeddings",
                    ],
                },
            },
            "pools": {
                "hybrid-pool": {
                    "capability": "generation.text-generation.chat-completion",
                    "models": ["fake.model-b"],
                },
            },
        })
        mesh = ModelMesh()
        mesh.initialize(config)

        pool = mesh.pools["hybrid-pool"]
        model_ids = [m.model_id for m in pool.models]
        # model-a matched by capability, model-b added explicitly
        self.assertIn("fake.model-a", model_ids)
        self.assertIn("fake.model-b", model_ids)


if __name__ == "__main__":
    unittest.main()
