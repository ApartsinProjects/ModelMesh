"""
04 - Streaming Chat Completion
==============================

Streaming chat completion with automatic provider failover.  The response
arrives incrementally as the model generates tokens.

This sample demonstrates:
  - Using stream=True with the OpenAI-compatible client
  - Iterating over streaming response chunks
  - Automatic fallback to the next provider on stream error

Uses mock providers so it runs without API keys.
"""

import asyncio
from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


class MockStreamProvider(ProviderConnector):
    """Mock provider that yields streaming chunks."""

    def __init__(self, name: str, tokens: list[str]):
        self._name = name
        self._tokens = tokens

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            id=f"resp-{self._name}",
            model=self._name,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content="".join(self._tokens)),
                finish_reason="stop",
            )],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=len(self._tokens), total_tokens=10 + len(self._tokens)),
        )

    async def stream(self, request: CompletionRequest):
        for i, token in enumerate(self._tokens):
            yield CompletionResponse(
                id=f"chunk-{self._name}-{i}",
                model=self._name,
                choices=[CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content=token),
                    finish_reason="stop" if i == len(self._tokens) - 1 else None,
                )],
                usage=TokenUsage(prompt_tokens=10, completion_tokens=i + 1, total_tokens=11 + i),
            )

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

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
    poem_tokens = [
        "In ", "the ", "network's ", "web ", "we ", "trust,\n",
        "Packets ", "flow ", "like ", "morning ", "dust.\n",
        "Consensus ", "reached ", "by ", "many ", "peers,\n",
        "Distributed ", "hope ", "conquers ", "fears.",
    ]
    list_tokens = [
        "1. ", "High ", "availability ", "-- ", "no ", "single ", "point ", "of ", "failure.\n",
        "2. ", "Scalability ", "-- ", "handle ", "more ", "traffic.\n",
        "3. ", "Performance ", "-- ", "reduced ", "latency.",
    ]

    prov_a = MockStreamProvider("gpt-4o", poem_tokens)
    prov_b = MockStreamProvider("gemini-flash", list_tokens)

    config = MeshConfig(raw={
        "providers": {
            "openai": {"connector": "openai", "enabled": True, "instance": prov_a},
            "google": {"connector": "google", "enabled": True, "instance": prov_b},
        },
        "models": {
            "openai.gpt-4o": {
                "provider": "openai",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "google.gemini-flash": {
                "provider": "google",
                "capabilities": ["generation.text-generation.chat-completion"],
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
    client = mesh.get_client()

    print("=" * 60)
    print("Streaming chat completion demo")
    print("=" * 60)

    # Example 1: Basic streaming
    print("\n--- Example 1: Basic streaming ---\n")
    print("User: Write a short poem about distributed systems.\n")
    print("Assistant: ", end="")

    response_stream = client.chat.completions.create(
        model="text-generation",
        messages=[
            {"role": "system", "content": "You are a creative writer."},
            {"role": "user", "content": "Write a short poem about distributed systems."},
        ],
        stream=True,
    )

    full_text = ""
    chunk = None
    for chunk in response_stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            print(token, end="", flush=True)
            full_text += token

    print("\n")
    if chunk:
        print(f"Model used: {chunk.model}")

    # Force rotation to second model for the next stream demo
    mesh.rotate("text-generation")

    # Example 2: Streaming with metadata inspection
    print("\n--- Example 2: Streaming with usage metadata ---\n")
    print("User: List three benefits of load balancing.\n")
    print("Assistant: ", end="")

    chunk_count = 0
    response_stream = client.chat.completions.create(
        model="text-generation",
        messages=[{"role": "user", "content": "List three benefits of load balancing."}],
        stream=True,
    )

    chunk = None
    for chunk in response_stream:
        chunk_count += 1
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)

    print(f"\n\nReceived {chunk_count} chunks.")
    if chunk:
        print(f"Final chunk usage: {chunk.usage}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
