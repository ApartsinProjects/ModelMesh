"""
03 - Free-Tier Aggregation
==========================

Chain free-tier quotas across three providers.  When one provider's quota is
exhausted, ModelMesh rotates to the next, combining their individual limits
into a larger aggregate quota.

This sample demonstrates:
  - Round-robin selection strategy across providers
  - How quota exhaustion on one provider triggers transparent rotation
  - Multiple providers serving the same capability

Uses mock providers so it runs without API keys.
"""

import asyncio
from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


class MockFreeTierProvider(ProviderConnector):
    """Mock provider that simulates free-tier responses."""

    def __init__(self, name: str):
        self._name = name
        self._request_count = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._request_count += 1
        user_msg = ""
        for msg in request.messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_msg = msg.get("content", "")

        return CompletionResponse(
            id=f"resp-{self._name}-{self._request_count}",
            model=self._name,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(
                    role="assistant",
                    content=f"[{self._name}] Response to: {user_msg[:50]}",
                ),
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
        return QuotaStatus(used=self._request_count)

    def get_rate_limits(self):
        return RateLimitStatus()

    def get_pricing(self, mid):
        return ModelPricing()

    def report_usage(self, mid, usage):
        pass

    def classify_error(self, error):
        return ErrorClassification(retryable=False)


async def main() -> None:
    prov_a = MockFreeTierProvider("llama-3.3-70b-groq")
    prov_b = MockFreeTierProvider("llama-3.1-8b-cloudflare")
    prov_c = MockFreeTierProvider("llama-3-8b-huggingface")

    config = MeshConfig(raw={
        "providers": {
            "groq": {"connector": "groq", "enabled": True, "instance": prov_a},
            "cloudflare": {"connector": "cloudflare", "enabled": True, "instance": prov_b},
            "huggingface": {"connector": "huggingface", "enabled": True, "instance": prov_c},
        },
        "models": {
            "groq.llama-70b": {
                "provider": "groq",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "cf.llama-8b": {
                "provider": "cloudflare",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "hf.llama-8b": {
                "provider": "huggingface",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
        },
        "pools": {
            "text-generation": {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "round-robin",
            },
        },
    })
    mesh = ModelMesh()
    mesh.initialize(config)
    client = mesh.get_client()

    print("=" * 60)
    print("Free-tier aggregation: Groq + Cloudflare + HuggingFace")
    print("=" * 60)
    print()
    print("Round-robin strategy distributes requests across providers.")
    print("When a provider's quota is exhausted, its models are deactivated")
    print("and traffic shifts to the remaining providers.\n")

    prompts = [
        "Define 'machine learning' in one sentence.",
        "What is the difference between TCP and UDP?",
        "Name three sorting algorithms.",
        "What does 'REST' stand for?",
        "Explain what a hash table is.",
        "What is the time complexity of binary search?",
    ]

    for i, prompt in enumerate(prompts, start=1):
        print(f"--- Request {i}/{len(prompts)} ---")
        response = client.chat.completions.create(
            model="text-generation",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=100,
        )
        print(f"  Model    : {response.model}")
        print(f"  Answer   : {response.choices[0].message.content[:80]}...")
        print()

    print("--- Quota summary ---")
    print(f"  Groq requests      : {prov_a._request_count}")
    print(f"  Cloudflare requests: {prov_b._request_count}")
    print(f"  HuggingFace requests: {prov_c._request_count}")
    print()

    mesh.shutdown()
    print("ModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
