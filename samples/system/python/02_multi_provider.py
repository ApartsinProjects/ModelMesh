"""
02 - Multi-Provider with Automatic Failover
============================================

Two providers serving the same capability pool.  When one provider fails or
is rate-limited, ModelMesh automatically rotates to the other.

This sample demonstrates:
  - Configuring multiple providers in the same pool
  - Automatic failover via stick-until-failure strategy
  - Observing rotation events through console observability

Uses mock providers so it runs without API keys.
"""

import asyncio
from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


class MockProvider(ProviderConnector):
    """Mock provider that returns a canned response."""

    def __init__(self, name: str, answers: dict[str, str] | None = None):
        self._name = name
        self._answers = answers or {}
        self._default = f"Response from {name}"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        user_msg = ""
        for msg in request.messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_msg = msg.get("content", "")

        reply = self._default
        for key, val in self._answers.items():
            if key.lower() in user_msg.lower():
                reply = val
                break

        return CompletionResponse(
            id=f"resp-{self._name}",
            model=self._name,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=reply),
                finish_reason="stop",
            )],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        )

    async def stream(self, request):
        yield await self.complete(request)

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
    answers = {
        "capital of france": "The capital of France is Paris.",
        "largest ocean": "The Pacific Ocean is the largest ocean on Earth.",
        "programming paradigms": "Three programming paradigms are: imperative, functional, and object-oriented.",
    }

    config = MeshConfig(raw={
        "providers": {
            "openai.llm.v1": {
                "connector": "openai.llm.v1",
                "enabled": True,
                "instance": MockProvider("gpt-4o", answers),
            },
            "anthropic.claude.v1": {
                "connector": "anthropic.claude.v1",
                "enabled": True,
                "instance": MockProvider("claude-sonnet-4", answers),
            },
        },
        "models": {
            "gpt-4o": {
                "provider": "openai.llm.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "claude-sonnet-4": {
                "provider": "anthropic.claude.v1",
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
    print("Multi-provider failover demo")
    print("=" * 60)

    questions = [
        "What is the capital of France?",
        "What is the largest ocean on Earth?",
        "Name three programming paradigms.",
    ]

    for i, question in enumerate(questions, start=1):
        print(f"\n--- Request {i} ---")
        print(f"Question: {question}")

        response = client.chat.completions.create(
            model="text-generation",
            messages=[{"role": "user", "content": question}],
            temperature=0.3,
            max_tokens=128,
        )

        print(f"Model    : {response.model}")
        print(f"Answer   : {response.choices[0].message.content}")

    pools = mesh.list_pools()
    print(f"\n--- Pool status ---")
    for pool in pools:
        print(f"  Pool: {pool}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
