"""
02 - Streaming Chat Completion
===============================

Stream a chat completion response token-by-token.

This sample demonstrates:
  - Enabling streaming with the stream=True parameter
  - Iterating over response chunks
  - Accessing incremental content via chunk.choices[0].delta.content
  - Printing tokens as they arrive for a responsive user experience

This version uses an inline mock provider so it runs without API keys.
"""

from __future__ import annotations

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


class MockStreamProvider(ProviderConnector):
    """Mock provider that yields multiple streaming chunks."""

    _HAIKU_TOKENS = [
        "Nodes ",
        "whisper ",
        "in sync,\n",
        "Packets ",
        "dance ",
        "through ",
        "tangled ",
        "wires -- \n",
        "Consensus ",
        "reached.",
    ]

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            id="mock-stream-resp",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content="".join(self._HAIKU_TOKENS),
                    ),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )

    async def stream(self, request: CompletionRequest):
        for i, token in enumerate(self._HAIKU_TOKENS):
            yield CompletionResponse(
                id=f"chunk-{i}",
                model=request.model,
                choices=[
                    CompletionChoice(
                        index=0,
                        delta=ChatMessage(role="assistant", content=token),
                        finish_reason="stop" if i == len(self._HAIKU_TOKENS) - 1 else None,
                    )
                ],
            )

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, cap):
        return cap in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="mock-stream", name="Mock Stream")]

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
        "mock": {
            "connector": "mock",
            "enabled": True,
            "instance": MockStreamProvider(),
        },
    },
    "models": {
        "mock.stream-model": {
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


def main() -> None:
    print("User: Write a haiku about distributed systems.\n")
    print("Assistant: ", end="")

    # Pass stream=True to get an iterable of chunks instead of a single response.
    stream = client.chat.completions.create(
        model="chat-completion",
        messages=[
            {"role": "user", "content": "Write a haiku about distributed systems."},
        ],
        stream=True,
    )

    # Each chunk mirrors the OpenAI streaming format.
    # chunk.choices[0].delta.content holds the next piece of text (or None).
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token is not None:
            print(token, end="", flush=True)

    # Print a final newline after the stream is complete.
    print()

    mesh.shutdown()


if __name__ == "__main__":
    main()
