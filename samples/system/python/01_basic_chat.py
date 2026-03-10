"""
01 - Basic Chat Completion
==========================

Simplest possible ModelMesh Lite setup: a single provider, one model,
and a chat completion request.

This sample demonstrates:
  - Initializing ModelMesh from an inline configuration dict
  - Obtaining the OpenAI-compatible client
  - Making a chat completion call using a virtual model name
  - Printing the response

The virtual model name "text-generation" maps to a capability pool.  ModelMesh
resolves it to the best (and in this case only) active real model and provider,
then forwards the request transparently.

Uses a mock provider so it runs without API keys.
"""

import asyncio
from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


class MockOpenAIProvider(ProviderConnector):
    """Mock provider simulating an OpenAI-style chat model."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            id="mock-01",
            model="gpt-4o-mini",
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(
                    role="assistant",
                    content=(
                        "An API gateway is a server that acts as a single entry "
                        "point for a set of microservices, handling request "
                        "routing, authentication, and rate limiting. It simplifies "
                        "client interaction by abstracting the complexity of the "
                        "backend architecture behind a unified interface."
                    ),
                ),
                finish_reason="stop",
            )],
            usage=TokenUsage(prompt_tokens=25, completion_tokens=45, total_tokens=70),
        )

    async def stream(self, request):
        yield await self.complete(request)

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, cap):
        return cap in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="gpt-4o-mini", name="GPT-4o Mini (mock)")]

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
    # 1. Build a MeshConfig with the mock provider.
    config = MeshConfig(raw={
        "providers": {
            "openai.llm.v1": {
                "connector": "openai.llm.v1",
                "enabled": True,
                "instance": MockOpenAIProvider(),
            },
        },
        "models": {
            "gpt-4o-mini": {
                "provider": "openai.llm.v1",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
        },
        "pools": {
            "text-generation": {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "stick-until-failure",
            },
        },
    })
    mesh = ModelMesh()
    mesh.initialize(config)

    print("ModelMesh initialized with a single provider.\n")

    # 2. Get the OpenAI-compatible client.
    client = mesh.get_client()

    # 3. Make a chat completion request.
    print("Sending chat completion request...")
    response = client.chat.completions.create(
        model="text-generation",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Explain what an API gateway is in two sentences."},
        ],
        temperature=0.7,
        max_tokens=256,
    )

    # 4. Print the result.
    print(f"\nModel used : {response.model}")
    print(f"Tokens in  : {response.usage.prompt_tokens}")
    print(f"Tokens out : {response.usage.completion_tokens}")
    print(f"\nAssistant:\n{response.choices[0].message.content}")

    # 5. Shut down gracefully.
    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
