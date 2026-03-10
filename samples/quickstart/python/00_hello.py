"""
00 - Hello World Chat Completion
=================================

Simplest possible ModelMesh Lite usage: specify a capability, get an
OpenAI-compatible client, make a chat completion call.

This sample is nearly identical to using the OpenAI SDK directly.
The only differences: the import, the create() call, and the model parameter.

This version uses an inline mock provider so it runs without API keys.
"""

from __future__ import annotations

import modelmesh
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


class MockProvider(ProviderConnector):
    """Minimal mock provider that returns a canned response."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            id="mock-resp-00",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=(
                            "An API (Application Programming Interface) is a set of "
                            "rules that lets different software programs talk to each "
                            "other. It defines how to request data or actions and what "
                            "responses to expect, like a menu at a restaurant."
                        ),
                    ),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=14, completion_tokens=42, total_tokens=56),
        )

    async def stream(self, request):
        yield await self.complete(request)

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, capability):
        return capability in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="mock-model", name="Mock Model")]

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


# Build a MeshConfig with the mock provider.
config = MeshConfig(raw={
    "providers": {
        "mock": {
            "connector": "mock",
            "enabled": True,
            "instance": MockProvider(),
        },
    },
    "models": {
        "mock.chat-model": {
            "provider": "mock",
            "capabilities": ["generation.text-generation.chat-completion"],
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
client = mesh.get_client()

# Standard OpenAI-compatible call -- virtual model name = capability name.
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Explain what an API is in two sentences."}],
)

print(response.choices[0].message.content)
mesh.shutdown()
