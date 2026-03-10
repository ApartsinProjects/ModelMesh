"""
09 - Full System Configuration
===============================

Complete ModelMesh Lite setup exercising every major subsystem: multiple
providers, multiple pools with different strategies, and runtime statistics.

This sample demonstrates:
  - Multiple providers with different capabilities
  - Multiple pools with different selection strategies
  - Runtime statistics API
  - Pool and provider inspection

Uses mock providers so it runs without API keys.
"""

import asyncio
import json
from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


class MockFullProvider(ProviderConnector):
    """Mock provider for full configuration demo."""

    def __init__(self, name: str, caps: list[str]):
        self._name = name
        self._caps = caps
        self._requests = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._requests += 1
        return CompletionResponse(
            id=f"resp-{self._name}-{self._requests}",
            model=self._name,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(
                    role="assistant",
                    content=f"[{self._name}] Full config response #{self._requests}",
                ),
                finish_reason="stop",
            )],
            usage=TokenUsage(prompt_tokens=15, completion_tokens=20, total_tokens=35),
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
    chat_cap = "generation.text-generation.chat-completion"
    code_cap = "generation.text-generation.code-generation"

    prov_openai = MockFullProvider("gpt-4o", [chat_cap, code_cap])
    prov_anthropic = MockFullProvider("claude-sonnet-4", [chat_cap, code_cap])
    prov_google = MockFullProvider("gemini-2.5-pro", [chat_cap, code_cap])
    prov_deepseek = MockFullProvider("deepseek-chat", [chat_cap, code_cap])

    config = MeshConfig(raw={
        "providers": {
            "openai": {"connector": "openai", "enabled": True, "instance": prov_openai},
            "anthropic": {"connector": "anthropic", "enabled": True, "instance": prov_anthropic},
            "google": {"connector": "google", "enabled": True, "instance": prov_google},
            "deepseek": {"connector": "deepseek", "enabled": True, "instance": prov_deepseek},
        },
        "models": {
            "openai.gpt-4o": {
                "provider": "openai",
                "capabilities": [chat_cap, code_cap],
            },
            "anthropic.claude-sonnet-4": {
                "provider": "anthropic",
                "capabilities": [chat_cap, code_cap],
            },
            "google.gemini-2.5-pro": {
                "provider": "google",
                "capabilities": [chat_cap, code_cap],
            },
            "deepseek.deepseek-chat": {
                "provider": "deepseek",
                "capabilities": [chat_cap, code_cap],
            },
        },
        "pools": {
            "text-generation": {
                "capability": chat_cap,
                "strategy": "cost-first",
            },
            "code-generation": {
                "capability": code_cap,
                "strategy": "stick-until-failure",
            },
            "long-context": {
                "capability": "generation.text-generation",
                "strategy": "stick-until-failure",
            },
        },
    })
    mesh = ModelMesh()
    mesh.initialize(config)
    client = mesh.get_client()

    print("=" * 60)
    print("Full system configuration demo")
    print("=" * 60)
    print()

    # Show system overview
    print("--- System overview ---\n")
    pool_status = mesh.pool_status()
    print(f"Active pools: {len(pool_status)}")
    for pool_name in pool_status:
        print(f"  - {pool_name}")
    print()

    # Exercise different pools
    print("--- Pool: text-generation (cost-first) ---\n")
    response = client.chat.completions.create(
        model="text-generation",
        messages=[{"role": "user", "content": "What is infrastructure as code?"}],
    )
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:100]}...")

    print("\n--- Pool: code-generation (stick-until-failure) ---\n")
    response = client.chat.completions.create(
        model="code-generation",
        messages=[
            {"role": "system", "content": "You write clean code."},
            {"role": "user", "content": "Write a Python GCD function."},
        ],
    )
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:100]}...")

    print("\n--- Pool: long-context (stick-until-failure) ---\n")
    response = client.chat.completions.create(
        model="long-context",
        messages=[{"role": "user", "content": "Benefits of large context windows."}],
    )
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:100]}...")

    # Runtime statistics
    print("\n--- Runtime statistics ---\n")
    print("Active providers:")
    for provider_id in mesh.active_providers():
        print(f"  {provider_id}")
    print()

    pool_status = mesh.pool_status()
    for pool_name, status in pool_status.items():
        print(f"  Pool '{pool_name}': {status}")

    # State snapshot
    print("\n--- State snapshot ---\n")
    snapshot = json.dumps(mesh.pool_status(), default=str)
    print(f"  State snapshot size: {len(snapshot)} chars")

    # Provider request counts
    print("\n--- Provider request counts ---")
    print(f"  OpenAI   : {prov_openai._requests}")
    print(f"  Anthropic: {prov_anthropic._requests}")
    print(f"  Google   : {prov_google._requests}")
    print(f"  DeepSeek : {prov_deepseek._requests}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
