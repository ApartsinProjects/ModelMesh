"""Tests for MeshClient.describe() method."""
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


class _StubProvider(ProviderConnector):
    async def complete(self, request):
        return CompletionResponse(
            id="stub", model=request.model,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content="ok"),
                finish_reason="stop",
            )],
            usage=TokenUsage(),
        )

    async def stream(self, request):
        yield CompletionResponse(
            id="stub", model=request.model,
            choices=[CompletionChoice(
                index=0, delta=ChatMessage(role="assistant", content="ok"),
                finish_reason="stop",
            )],
            usage=TokenUsage(),
        )

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, cap):
        return cap in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="stub-model", name="Stub")]

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


def _make_client_multi():
    """Create a client with two providers and multiple models."""
    config = MeshConfig(raw={
        "providers": {
            "openai.llm.v1": {
                "connector": "openai.llm.v1", "enabled": True,
                "instance": _StubProvider(),
            },
            "anthropic.claude.v1": {
                "connector": "anthropic.claude.v1", "enabled": True,
                "instance": _StubProvider(),
            },
        },
        "models": {
            "openai.gpt-4o": {
                "provider": "openai.llm.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "openai.gpt-4o-mini": {
                "provider": "openai.llm.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "anthropic.claude-sonnet-4": {
                "provider": "anthropic.claude.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
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


def _make_client_single():
    """Create a client with a single model."""
    config = MeshConfig(raw={
        "providers": {
            "test.v1": {
                "connector": "test.v1", "enabled": True,
                "instance": _StubProvider(),
            },
        },
        "models": {
            "test.model-a": {
                "provider": "test.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
        },
        "pools": {
            "chat": {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "cost-first",
            },
        },
        "observability": {"connector": "modelmesh.null.v1"},
    })
    mesh = ModelMesh()
    mesh.initialize(config)
    return mesh.get_client()


def _make_client_multi_pool():
    """Create a client with multiple pools."""
    config = MeshConfig(raw={
        "providers": {
            "test.v1": {
                "connector": "test.v1", "enabled": True,
                "instance": _StubProvider(),
            },
        },
        "models": {
            "test.chat-model": {
                "provider": "test.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "test.embed-model": {
                "provider": "test.v1",
                "capabilities": ["representation.embeddings.text-embeddings"],
            },
        },
        "pools": {
            "chat": {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "stick-until-failure",
            },
            "embeddings": {
                "capability": "representation.embeddings.text-embeddings",
                "strategy": "round-robin",
            },
        },
        "observability": {"connector": "modelmesh.null.v1"},
    })
    mesh = ModelMesh()
    mesh.initialize(config)
    return mesh.get_client()


class TestDescribe(unittest.TestCase):
    """Test client.describe() output."""

    def test_describe_returns_string(self):
        client = _make_client_multi()
        result = client.describe()
        self.assertIsInstance(result, str)

    def test_describe_shows_pool_name(self):
        client = _make_client_multi()
        result = client.describe()
        self.assertIn('Pool "chat-completion"', result)

    def test_describe_shows_strategy(self):
        client = _make_client_multi()
        result = client.describe()
        self.assertIn("stick-until-failure", result)

    def test_describe_shows_capability(self):
        client = _make_client_multi()
        result = client.describe()
        self.assertIn("generation.text-generation.chat-completion", result)

    def test_describe_shows_model_ids(self):
        client = _make_client_multi()
        result = client.describe()
        self.assertIn("openai.gpt-4o", result)
        self.assertIn("openai.gpt-4o-mini", result)
        self.assertIn("anthropic.claude-sonnet-4", result)

    def test_describe_shows_provider_ids(self):
        client = _make_client_multi()
        result = client.describe()
        self.assertIn("openai.llm.v1", result)
        self.assertIn("anthropic.claude.v1", result)

    def test_describe_shows_active_status(self):
        client = _make_client_multi()
        result = client.describe()
        self.assertIn("active", result)

    def test_describe_shows_arrow_for_current(self):
        client = _make_client_multi()
        result = client.describe()
        self.assertIn("\u2192", result)

    def test_describe_specific_pool(self):
        client = _make_client_multi()
        result = client.describe(pool="chat-completion")
        self.assertIn("chat-completion", result)

    def test_describe_unknown_pool_raises(self):
        client = _make_client_multi()
        with self.assertRaises(KeyError):
            client.describe(pool="nonexistent")

    def test_describe_single_model(self):
        client = _make_client_single()
        result = client.describe()
        self.assertIn("test.model-a", result)
        self.assertIn("cost-first", result)

    def test_describe_multiple_pools(self):
        client = _make_client_multi_pool()
        result = client.describe()
        self.assertIn('Pool "chat"', result)
        self.assertIn('Pool "embeddings"', result)
        self.assertIn("round-robin", result)

    def test_describe_multiline(self):
        client = _make_client_multi()
        result = client.describe()
        lines = result.strip().split("\n")
        self.assertGreaterEqual(len(lines), 3)


class TestDescribeAfterRotation(unittest.TestCase):
    """Test describe() reflects state changes."""

    def test_describe_shows_standby_after_rotation(self):
        client = _make_client_multi()
        client.rotate("chat-completion")
        result = client.describe()
        self.assertIn("standby", result)


if __name__ == "__main__":
    unittest.main()
