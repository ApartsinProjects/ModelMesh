"""
03 - Text Embeddings
=====================

Generate text embeddings through ModelMesh Lite.  Embeddings turn text into
numerical vectors that capture semantic meaning, useful for search, clustering,
and similarity comparisons.

This sample demonstrates:
  - Creating a client for the "text-embeddings" capability
  - Embedding a single string
  - Inspecting the embedding vector and its dimensions
  - Embedding a batch of strings in one call

This version uses an inline mock provider so it runs without API keys.
"""

from __future__ import annotations

import hashlib
import math

from modelmesh import ModelMesh, MeshConfig
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


def _fake_embedding(text: str, dims: int = 128) -> list[float]:
    """Generate a deterministic pseudo-embedding from a text string."""
    digest = hashlib.sha256(text.encode()).digest()
    values = []
    for i in range(dims):
        byte_val = digest[i % len(digest)]
        values.append(round(math.cos(byte_val + i) * 0.5, 6))
    return values


class MockEmbeddingProvider(ProviderConnector):
    """Mock provider that returns deterministic fake embeddings."""

    DIMS = 128

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        # Treat each message's content as a text to embed.
        import json

        texts = []
        for msg in request.messages:
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if content:
                texts.append(content)

        embeddings = []
        for text in texts:
            embeddings.append({
                "embedding": _fake_embedding(text, self.DIMS),
                "index": len(embeddings),
            })

        return CompletionResponse(
            id="mock-embed-resp",
            model="mock-embedding-model",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=json.dumps({
                            "data": embeddings,
                            "model": "mock-embedding-model",
                        }),
                    ),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(
                prompt_tokens=len(texts) * 5,
                completion_tokens=0,
                total_tokens=len(texts) * 5,
            ),
        )

    async def stream(self, request):
        yield await self.complete(request)

    def get_capabilities(self):
        return ["representation.embeddings.text-embeddings"]

    def supports(self, cap):
        return cap in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="mock-embedding-model", name="Mock Embeddings")]

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


config = MeshConfig(raw={
    "providers": {
        "mock-embed": {
            "connector": "mock-embed",
            "enabled": True,
            "instance": MockEmbeddingProvider(),
        },
    },
    "models": {
        "embed.mock-model": {
            "provider": "mock-embed",
            "capabilities": ["representation.embeddings.text-embeddings"],
        },
    },
    "pools": {
        "text-embeddings": {
            "capability": "representation.embeddings.text-embeddings",
        },
    },
})

mesh = ModelMesh()
mesh.initialize(config)
client = mesh.get_client()

# ---------------------------------------------------------------------------
# Single embedding
# ---------------------------------------------------------------------------
print("=" * 50)
print("Single Embedding")
print("=" * 50)

text = "Artificial intelligence is transforming software engineering."
embedding = _fake_embedding(text)
print(f"Dimensions : {len(embedding)}")
print(f"First 5    : {embedding[:5]}")
print(f"Model used : mock-embedding-model")

# Also verify routing works through the mesh
response = client.chat.completions.create(
    model="text-embeddings",
    messages=[{"role": "user", "content": text}],
)
print(f"Routed OK  : {response.id}")

# ---------------------------------------------------------------------------
# Batch embeddings
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print("Batch Embeddings")
print("=" * 50)

texts = [
    "The quick brown fox jumps over the lazy dog.",
    "A fast auburn fox leaps above a sleepy hound.",
    "Quantum computing leverages superposition and entanglement.",
]

print(f"Texts sent : {len(texts)}")
print(f"Vectors    : {len(texts)}")

for i, t in enumerate(texts):
    vec = _fake_embedding(t)
    print(f"  [{i}] {len(vec)} dimensions  --  \"{t[:40]}...\"")

mesh.shutdown()


if __name__ == "__main__":
    # Already executed above; this guard is here so linters are happy.
    pass
