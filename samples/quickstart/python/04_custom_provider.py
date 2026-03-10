"""
04 - Custom Provider Endpoint
==============================

Use QuickProvider to connect to a custom or internal API endpoint.
QuickProvider works with just a base_url and api_key -- it auto-discovers
models from the ``GET /v1/models`` endpoint.

This sample demonstrates:
  - Creating a QuickProvider with QuickProviderConfig
  - Registering it with ModelMesh using the ``instance`` key
  - Verifying the provider is functional through the mesh

Since there is no real endpoint, this sample uses a mock provider that
simulates the same pattern.
"""

from __future__ import annotations

from modelmesh import ModelMesh, MeshConfig
from modelmesh.cdk import QuickProvider
from modelmesh.cdk.specialized.quick_provider import QuickProviderConfig
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


class MockInternalProvider(ProviderConnector):
    """Simulates a custom internal API endpoint."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            id="internal-resp",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="Hello from the internal API! (mock response)",
                    ),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=8, completion_tokens=10, total_tokens=18),
        )

    async def stream(self, request):
        yield await self.complete(request)

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, cap):
        return cap in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="internal-model", name="Internal Model")]

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


# Show that QuickProviderConfig is the proper way to construct a QuickProvider:
print("QuickProvider construction pattern:")
print("  provider = QuickProvider(QuickProviderConfig(")
print("      base_url='https://my-internal-api.company.com/v1',")
print("      api_key='sk-internal-key',")
print("  ))")
print()

# For this demo, we use a mock provider since there is no real endpoint.
provider = MockInternalProvider()

# Register with ModelMesh using the "instance" key in the providers config.
config = MeshConfig(raw={
    "providers": {
        "internal": {
            "connector": "internal",
            "enabled": True,
            "instance": provider,
        },
    },
    "models": {
        "internal.model": {
            "provider": "internal",
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

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello from internal API!"}],
)
print(response.choices[0].message.content)
mesh.shutdown()
