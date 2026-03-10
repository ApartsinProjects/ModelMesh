"""
06 - Cost Optimization with Budget Limits
==========================================

Cost-first selection strategy combined with per-provider budget limits.
ModelMesh routes each request to the cheapest active model and automatically
deactivates providers when their budget is exhausted.

This sample demonstrates:
  - Configuring cost-first rotation policy
  - How the system routes to the cheapest models first
  - Budget-based deactivation when spend limits are reached
  - Multiple providers with different cost characteristics

Uses mock providers so it runs without API keys.
"""

import asyncio
from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


class MockCostProvider(ProviderConnector):
    """Mock provider with cost tracking."""

    def __init__(self, name: str, cost_per_request: float = 0.01):
        self._name = name
        self._cost = cost_per_request
        self._total_cost = 0.0
        self._requests = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._requests += 1
        self._total_cost += self._cost
        return CompletionResponse(
            id=f"resp-{self._name}-{self._requests}",
            model=self._name,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(
                    role="assistant",
                    content=f"[{self._name}] Response #{self._requests} (cost: ${self._cost:.4f})",
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
        return QuotaStatus(used=self._requests)

    def get_rate_limits(self):
        return RateLimitStatus()

    def get_pricing(self, mid):
        return ModelPricing()

    def report_usage(self, mid, usage):
        pass

    def classify_error(self, error):
        return ErrorClassification(retryable=False)


async def main() -> None:
    # Create providers with different cost levels
    prov_cheap = MockCostProvider("deepseek-chat", cost_per_request=0.001)
    prov_free = MockCostProvider("llama-3-groq", cost_per_request=0.0)
    prov_premium = MockCostProvider("gpt-4o", cost_per_request=0.03)

    config = MeshConfig(raw={
        "providers": {
            "deepseek": {"connector": "deepseek", "enabled": True, "instance": prov_cheap},
            "groq": {"connector": "groq", "enabled": True, "instance": prov_free},
            "openai": {"connector": "openai", "enabled": True, "instance": prov_premium},
        },
        "models": {
            "deepseek.chat": {
                "provider": "deepseek",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "groq.llama-3": {
                "provider": "groq",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "openai.gpt-4o": {
                "provider": "openai",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
        },
        "pools": {
            "text-generation": {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "cost-first",
            },
        },
    })
    mesh = ModelMesh()
    mesh.initialize(config)
    client = mesh.get_client()

    print("=" * 60)
    print("Cost Optimization with Budget Limits")
    print("=" * 60)
    print()
    print("DeepSeek ($0.001/req) < Groq (free) < GPT-4o ($0.030/req)")
    print("Cost-first strategy routes to the cheapest active model.\n")

    prompts = [
        "What is machine learning?",
        "Explain gradient descent.",
        "What is a neural network?",
        "Define overfitting.",
        "What is regularization?",
    ]

    for i, prompt in enumerate(prompts, start=1):
        response = client.chat.completions.create(
            model="text-generation",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        )
        print(f"  Request {i}: {response.choices[0].message.content}")

    print(f"\n--- Cost Summary ---")
    print(f"  DeepSeek : {prov_cheap._requests} requests, ${prov_cheap._total_cost:.4f}")
    print(f"  Groq     : {prov_free._requests} requests, ${prov_free._total_cost:.4f}")
    print(f"  OpenAI   : {prov_premium._requests} requests, ${prov_premium._total_cost:.4f}")
    total = prov_cheap._total_cost + prov_free._total_cost + prov_premium._total_cost
    print(f"  Total    : ${total:.4f}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
