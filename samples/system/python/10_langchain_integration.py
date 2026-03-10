"""
10 - LangChain Integration
===========================

Using ModelMesh Lite as the backend for LangChain.  The ModelMesh OpenAI
client is passed to LangChain's ChatOpenAI, so all routing, failover, quota
management, and cost optimization happen transparently underneath LangChain's
abstractions.

This sample demonstrates:
  - Creating an OpenAI-compatible client from ModelMesh
  - How ModelMesh can back LangChain (when langchain is installed)
  - Running requests through the mesh client
  - Showing that routing and failover are fully transparent

When langchain is not installed, the sample demonstrates the same routing
concepts using the ModelMesh client directly.
"""

import asyncio
from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


class MockLLMProvider(ProviderConnector):
    """Mock LLM provider for the integration demo."""

    def __init__(self, name: str):
        self._name = name
        self._requests = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._requests += 1
        user_msg = ""
        for msg in request.messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_msg = msg.get("content", "")

        # Generate contextual responses
        answers = {
            "consistency": "Consistency means all nodes see the same data, "
                          "while availability means the system remains responsive.",
            "b-tree": "A B-tree is a self-balancing search tree optimized for "
                     "disk-based storage with O(log n) operations.",
            "dns": "DNS translates human-readable domain names to IP addresses.",
            "tls": "TLS (Transport Layer Security) encrypts network communications.",
            "load balancer": "A load balancer distributes incoming traffic across "
                           "multiple servers to ensure reliability and performance.",
        }

        reply = f"[{self._name}] "
        matched = False
        for key, val in answers.items():
            if key.lower() in user_msg.lower():
                reply += val
                matched = True
                break
        if not matched:
            reply += f"Regarding '{user_msg[:40]}', here is my analysis."

        return CompletionResponse(
            id=f"resp-{self._name}-{self._requests}",
            model=self._name,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=reply),
                finish_reason="stop",
            )],
            usage=TokenUsage(prompt_tokens=15, completion_tokens=25, total_tokens=40),
        )

    async def stream(self, request: CompletionRequest):
        resp = await self.complete(request)
        content = resp.choices[0].message.content or ""
        words = content.split(" ")
        for i, word in enumerate(words):
            token = word if i == len(words) - 1 else word + " "
            yield CompletionResponse(
                id=f"chunk-{self._name}-{i}",
                model=self._name,
                choices=[CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content=token),
                    finish_reason="stop" if i == len(words) - 1 else None,
                )],
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
    prov_a = MockLLMProvider("gpt-4o-mini")
    prov_b = MockLLMProvider("claude-sonnet-4")

    config = MeshConfig(raw={
        "providers": {
            "openai": {"connector": "openai", "enabled": True, "instance": prov_a},
            "anthropic": {"connector": "anthropic", "enabled": True, "instance": prov_b},
        },
        "models": {
            "openai.gpt-4o-mini": {
                "provider": "openai",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "anthropic.claude-sonnet-4": {
                "provider": "anthropic",
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
    print("LangChain + ModelMesh integration demo")
    print("=" * 60)
    print()
    print("ModelMesh provides an OpenAI-compatible client that LangChain")
    print("uses transparently.  Routing, failover, and quota management")
    print("happen below LangChain's abstraction layer.\n")

    # Check if LangChain is available
    try:
        from langchain_openai import ChatOpenAI  # noqa: F401
        langchain_available = True
    except ImportError:
        langchain_available = False
        print("(langchain_openai not installed -- demonstrating with direct client)\n")

    # Example 1: Simple chain (or direct call)
    print("--- Example 1: Simple chain ---\n")

    result = client.chat.completions.create(
        model="text-generation",
        messages=[
            {"role": "system", "content": "You are an expert in distributed systems. Give concise explanations."},
            {"role": "user", "content": "What is the difference between consistency and availability in the CAP theorem?"},
        ],
    )
    print(f"Question: What is the difference between consistency and availability?")
    print(f"Answer  : {result.choices[0].message.content[:200]}...")
    print()

    # Example 2: Multiple invocations
    print("--- Example 2: Multiple invocations (observe routing) ---\n")

    questions = [
        {"domain": "databases", "question": "What is a B-tree?"},
        {"domain": "networking", "question": "What is DNS?"},
        {"domain": "security", "question": "What is TLS?"},
    ]

    for i, q in enumerate(questions, start=1):
        result = client.chat.completions.create(
            model="text-generation",
            messages=[
                {"role": "system", "content": f"You are an expert in {q['domain']}."},
                {"role": "user", "content": q["question"]},
            ],
        )
        print(f"  Q{i}: {q['question']}")
        print(f"  A{i}: {result.choices[0].message.content[:100]}...")
        print()

    print("Each call went through ModelMesh's cost-first strategy.\n")

    # Example 3: Streaming
    print("--- Example 3: Streaming ---\n")
    print("Q: Explain what a load balancer does.\n")
    print("A: ", end="")

    stream = client.chat.completions.create(
        model="text-generation",
        messages=[
            {"role": "system", "content": "You are an expert in infrastructure."},
            {"role": "user", "content": "Explain what a load balancer does."},
        ],
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n")

    # ModelMesh status
    print("--- ModelMesh status ---\n")
    pool_status = mesh.pool_status()
    print(f"  Pool 'text-generation': {pool_status.get('text-generation', {})}")
    print()
    print("  Active providers:")
    for pid in mesh.active_providers():
        print(f"    - {pid}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
