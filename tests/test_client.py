"""Tests for the MeshClient class."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.client.mesh_client import MeshClient
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


class _FakeProvider(ProviderConnector):
    """Minimal fake provider for MeshClient tests."""

    async def complete(self, request):
        return CompletionResponse(
            id="fake-resp",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hello"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )

    async def stream(self, request):
        yield CompletionResponse(
            id="chunk-1",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content="Hi"),
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
        return [ModelInfo(id="fake-model", name="Fake")]

    def get_model_info(self, model_id):
        return ModelInfo(id="fake-model", name="Fake")

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


def _make_client():
    """Create an initialized MeshClient backed by a fake provider."""
    config = MeshConfig(raw={
        "providers": {
            "fake.v1": {
                "connector": "fake.v1",
                "enabled": True,
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
    mesh.initialize(config)
    return mesh.get_client()


class TestMeshClient(unittest.TestCase):
    """Test the MeshClient class."""

    def setUp(self):
        self.client = _make_client()

    def test_has_chat_namespace(self):
        self.assertTrue(hasattr(self.client, "chat"))
        self.assertTrue(hasattr(self.client.chat, "completions"))

    def test_has_embeddings_namespace(self):
        self.assertTrue(hasattr(self.client, "embeddings"))

    def test_has_models_namespace(self):
        self.assertTrue(hasattr(self.client, "models"))

    def test_pool_status(self):
        status = self.client.pool_status()
        self.assertIn("chat-completion", status)
        self.assertIsInstance(status["chat-completion"], dict)

    def test_pool_status_specific_pool(self):
        status = self.client.pool_status(pool="chat-completion")
        self.assertIn("active", status)
        self.assertIn("total", status)

    def test_pool_status_unknown_pool_raises(self):
        with self.assertRaises(KeyError):
            self.client.pool_status(pool="nonexistent")

    def test_active_providers(self):
        active = self.client.active_providers()
        self.assertIsInstance(active, list)
        self.assertIn("fake.v1", active)

    def test_mesh_property(self):
        self.assertIsInstance(self.client.mesh, ModelMesh)

    def test_models_list(self):
        model_list = self.client.models.list()
        self.assertTrue(hasattr(model_list, "data"))
        self.assertIsInstance(model_list.data, list)
        self.assertGreater(len(model_list.data), 0)
        self.assertEqual(model_list.data[0].id, "fake.model-a")
        self.assertEqual(model_list.object, "list")

    def test_models_list_entry_shape(self):
        model_list = self.client.models.list()
        entry = model_list.data[0]
        self.assertTrue(hasattr(entry, "id"))
        self.assertTrue(hasattr(entry, "object"))
        self.assertTrue(hasattr(entry, "owned_by"))
        self.assertEqual(entry.object, "model")

    def test_chat_completion_create(self):
        response = self.client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hello"}],
        )
        self.assertIsInstance(response, CompletionResponse)
        self.assertEqual(response.choices[0].message.content, "Hello")

    def test_rotate(self):
        # Should not raise -- even though there is only one model,
        # rotate returns None when no alternative
        result = self.client.rotate("chat-completion")
        # With only one model, after rotate the model goes to standby
        # and result will be None
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
