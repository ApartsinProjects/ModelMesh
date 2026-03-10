"""
08 - Custom Pool with Dynamic Selection
========================================

Define a custom capability pool that targets a specific subtree of the
capability hierarchy with priority-based model selection.

This sample demonstrates:
  - Creating multiple pools targeting different capability subtrees
  - Provider and model priority lists
  - How models join pools automatically based on capability registration
  - Inspecting pool and provider status programmatically

Uses mock providers so it runs without API keys.
"""

import asyncio
from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


class MockModelProvider(ProviderConnector):
    """Mock provider with configurable name and capabilities."""

    def __init__(self, name: str, caps: list[str]):
        self._name = name
        self._caps = caps

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            id=f"resp-{self._name}",
            model=self._name,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(
                    role="assistant",
                    content=f"[{self._name}] Analysis complete for your query.",
                ),
                finish_reason="stop",
            )],
            usage=TokenUsage(prompt_tokens=20, completion_tokens=15, total_tokens=35),
        )

    async def stream(self, request):
        yield await self.complete(request)

    def get_capabilities(self):
        return list(self._caps)

    def supports(self, cap):
        return cap in self._caps

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
    all_caps = [
        "generation.text-generation.chat-completion",
        "generation.text-generation.code-generation",
    ]
    prov_openai = MockModelProvider("gpt-4o", all_caps)
    prov_anthropic = MockModelProvider("claude-sonnet-4", all_caps)
    prov_google = MockModelProvider("gemini-2.5-pro", all_caps)

    config = MeshConfig(raw={
        "providers": {
            "openai": {"connector": "openai", "enabled": True, "instance": prov_openai},
            "anthropic": {"connector": "anthropic", "enabled": True, "instance": prov_anthropic},
            "google": {"connector": "google", "enabled": True, "instance": prov_google},
        },
        "models": {
            "openai.gpt-4o": {
                "provider": "openai",
                "capabilities": all_caps,
            },
            "anthropic.claude-sonnet-4": {
                "provider": "anthropic",
                "capabilities": all_caps,
            },
            "google.gemini-2.5-pro": {
                "provider": "google",
                "capabilities": all_caps,
            },
        },
        "pools": {
            "text-generation": {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "stick-until-failure",
            },
            "long-context-analysis": {
                "capability": "generation.text-generation",
                "strategy": "stick-until-failure",
            },
            "code-review": {
                "capability": "generation.text-generation.code-generation",
                "strategy": "stick-until-failure",
            },
        },
    })
    mesh = ModelMesh()
    mesh.initialize(config)
    client = mesh.get_client()

    print("=" * 60)
    print("Custom pool with dynamic selection demo")
    print("=" * 60)

    # Inspect pool membership
    print("\n--- Pool membership ---\n")
    pool_status = mesh.pool_status()
    for pool_name in ["text-generation", "long-context-analysis", "code-review"]:
        status = pool_status.get(pool_name, {})
        print(f"Pool '{pool_name}':")
        print(f"  Status: {status}")
        print()

    # Example 1: Route through the long-context pool
    print("--- Example 1: Long-context analysis ---\n")
    response = client.chat.completions.create(
        model="long-context-analysis",
        messages=[
            {"role": "system", "content": "You are an expert analyst."},
            {"role": "user", "content": "If I need to analyze a 500-page document, "
             "what context window would I need?"},
        ],
    )
    print(f"  Pool   : long-context-analysis")
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:120]}...")

    # Example 2: Route through the code-review pool
    print("\n--- Example 2: Code review ---\n")
    response = client.chat.completions.create(
        model="code-review",
        messages=[
            {"role": "system", "content": "You are a senior code reviewer."},
            {"role": "user", "content": "Review this: def fib(n): return n if n<=1 else fib(n-1)+fib(n-2)"},
        ],
    )
    print(f"  Pool   : code-review")
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:120]}...")

    # Example 3: Inspect pool and provider status
    print("\n--- Example 3: Pool and provider inspection ---\n")
    pool_status = mesh.pool_status()
    print("  Pool status:")
    for name, status in pool_status.items():
        print(f"    {name}: {status}")

    print()
    print("  Active providers:")
    for pid in mesh.active_providers():
        print(f"    - {pid}")

    print()
    print("  Available models:")
    for model in mesh.list_models():
        print(f"    - {model}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
