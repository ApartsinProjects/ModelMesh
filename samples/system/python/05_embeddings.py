"""
05 - Text Embeddings with Failover
===================================

Generate text embeddings using mock providers. The same embedding request
routes through whichever provider is currently active, with automatic
failover if one becomes unavailable.

This sample demonstrates:
  - Routing embedding requests through a capability pool
  - Failover between embedding providers
  - Inspecting usage metadata

Uses mock providers so it runs without API keys.
"""

import asyncio
import hashlib
import math

from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


def _fake_embedding(text: str, dims: int = 256) -> list[float]:
    """Generate a deterministic pseudo-embedding."""
    digest = hashlib.sha256(text.encode()).digest()
    return [round(math.sin(digest[i % len(digest)] + i) * 0.5, 6) for i in range(dims)]


class MockEmbedProvider(ProviderConnector):
    """Mock embedding provider."""

    def __init__(self, name: str, dims: int = 256):
        self._name = name
        self._dims = dims

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        import json
        texts = []
        for msg in request.messages:
            c = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if c:
                texts.append(c)
        data = [{"embedding": _fake_embedding(t, self._dims), "index": i} for i, t in enumerate(texts)]
        return CompletionResponse(
            id=f"embed-{self._name}",
            model=self._name,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=json.dumps({"data": data})),
                finish_reason="stop",
            )],
            usage=TokenUsage(prompt_tokens=len(texts) * 5, completion_tokens=0, total_tokens=len(texts) * 5),
        )

    async def stream(self, request):
        yield await self.complete(request)

    def get_capabilities(self):
        return ["representation.embeddings.text-embeddings"]

    def supports(self, cap):
        return cap in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id=self._name, name=self._name)]

    def get_model_info(self, mid):
        return ModelInfo(id=mid, name=mid)

    def check_quota(self):
        return QuotaStatus()

    def get_rate_limits(self):
        return RateLimitStatus()

    def get_pricing(self, mid):
        return ModelPricing()

    def report_usage(self, mid, usage):
        pass

    def classify_error(self, error):
        return ErrorClassification(retryable=False)


async def main() -> None:
    prov_a = MockEmbedProvider("text-embedding-3-small", 256)
    prov_b = MockEmbedProvider("embed-v3-english", 384)

    config = MeshConfig(raw={
        "providers": {
            "openai": {"connector": "openai", "enabled": True, "instance": prov_a},
            "cohere": {"connector": "cohere", "enabled": True, "instance": prov_b},
        },
        "models": {
            "openai.text-embedding-3-small": {
                "provider": "openai",
                "capabilities": ["representation.embeddings.text-embeddings"],
            },
            "cohere.embed-v3-english": {
                "provider": "cohere",
                "capabilities": ["representation.embeddings.text-embeddings"],
            },
        },
        "pools": {
            "text-embeddings": {
                "capability": "representation.embeddings.text-embeddings",
                "strategy": "stick-until-failure",
            },
        },
    })
    mesh = ModelMesh()
    mesh.initialize(config)
    client = mesh.get_client()

    print("=" * 60)
    print("Text Embeddings with Failover")
    print("=" * 60)

    # Single embedding
    print("\n--- Single embedding ---")
    text = "Artificial intelligence is transforming software engineering."
    vec = _fake_embedding(text)
    print(f"Text       : {text[:50]}...")
    print(f"Dimensions : {len(vec)}")
    print(f"First 5    : {vec[:5]}")

    # Route through mesh to verify
    response = client.chat.completions.create(
        model="text-embeddings",
        messages=[{"role": "user", "content": text}],
    )
    print(f"Model used : {response.model}")

    # Batch embeddings
    print("\n--- Batch embeddings ---")
    texts = [
        "The quick brown fox jumps over the lazy dog.",
        "A fast auburn fox leaps above a sleepy hound.",
        "Quantum computing leverages superposition.",
    ]
    for i, t in enumerate(texts):
        vec = _fake_embedding(t)
        print(f"  [{i}] {len(vec)} dims -- \"{t[:40]}...\"")

    # Show pool status
    print(f"\nPool status: {mesh.pool_status()}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
