"""
01 - Multi-Provider with Capabilities
======================================

Use multiple capabilities across multiple providers.  ModelMesh routes
requests according to the chosen strategy.

This sample demonstrates:
  - Requesting multiple capabilities: chat-completion and text-embeddings
  - Two providers serving different capabilities
  - Using the "cost-first" rotation strategy
  - Calling both chat and embeddings endpoints through the same client
  - Inspecting which model was used and token usage

This version uses inline mock providers so it runs without API keys.
"""

from __future__ import annotations

import random

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


class MockChatProvider(ProviderConnector):
    """Mock provider for chat completion."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            id="mock-chat-resp",
            model="mock-chat-model",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=(
                            "TCP is connection-oriented and guarantees delivery, "
                            "while UDP is connectionless and prioritizes speed."
                        ),
                    ),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=22, completion_tokens=30, total_tokens=52),
        )

    async def stream(self, request):
        yield await self.complete(request)

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, cap):
        return cap in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="mock-chat-model", name="Mock Chat")]

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


class MockEmbeddingsProvider(ProviderConnector):
    """Mock provider for text embeddings."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        # For embeddings, return a fake vector in the response content.
        dims = 128
        vector = [round(random.uniform(-1, 1), 6) for _ in range(dims)]
        import json

        return CompletionResponse(
            id="mock-embed-resp",
            model="mock-embed-model",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=json.dumps({"embedding": vector, "dimensions": dims}),
                    ),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=8, completion_tokens=0, total_tokens=8),
        )

    async def stream(self, request):
        yield await self.complete(request)

    def get_capabilities(self):
        return ["representation.embeddings.text-embeddings"]

    def supports(self, cap):
        return cap in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="mock-embed-model", name="Mock Embeddings")]

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


# Build a MeshConfig with two mock providers serving different capabilities.
config = MeshConfig(raw={
    "providers": {
        "mock-chat": {
            "connector": "mock-chat",
            "enabled": True,
            "instance": MockChatProvider(),
        },
        "mock-embed": {
            "connector": "mock-embed",
            "enabled": True,
            "instance": MockEmbeddingsProvider(),
        },
    },
    "models": {
        "chat.mock-chat-model": {
            "provider": "mock-chat",
            "capabilities": ["generation.text-generation.chat-completion"],
        },
        "embed.mock-embed-model": {
            "provider": "mock-embed",
            "capabilities": ["representation.embeddings.text-embeddings"],
        },
    },
    "pools": {
        "chat-completion": {
            "capability": "generation.text-generation.chat-completion",
            "strategy": "cost-first",
        },
        "text-embeddings": {
            "capability": "representation.embeddings.text-embeddings",
            "strategy": "cost-first",
        },
    },
})

mesh = ModelMesh()
mesh.initialize(config)
client = mesh.get_client()

# ---------------------------------------------------------------------------
# Chat completion
# ---------------------------------------------------------------------------
print("=" * 50)
print("Chat Completion")
print("=" * 50)

response = client.chat.completions.create(
    model="chat-completion",
    messages=[
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "What is the difference between TCP and UDP?"},
    ],
    max_tokens=200,
)

print(f"Model used  : {response.model}")
print(f"Prompt tkns : {response.usage.prompt_tokens}")
print(f"Compl. tkns : {response.usage.completion_tokens}")
print(f"\nAssistant:\n{response.choices[0].message.content}")

# ---------------------------------------------------------------------------
# Text embeddings (via chat completions route with embedding capability)
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print("Text Embeddings")
print("=" * 50)

embed_response = client.chat.completions.create(
    model="text-embeddings",
    messages=[
        {"role": "user", "content": "ModelMesh routes AI requests to the best provider."},
    ],
)

print(f"Model used : {embed_response.model}")
print(f"Response   : {embed_response.choices[0].message.content[:80]}...")

mesh.shutdown()


if __name__ == "__main__":
    # Already executed above; this guard is here so linters are happy.
    pass
