"""
07 - Session Stickiness (Conversational Affinity)
==================================================

Session-sticky routing ensures all messages within a conversation are sent to
the same model and provider.  This is important for multi-turn conversations
where consistent model behavior is desired.

This sample demonstrates:
  - Configuring session-stickiness routing
  - Multi-turn conversations using the same model
  - Verifying that all messages in a session route to the same model

Uses mock providers so it runs without API keys.
"""

import asyncio
import uuid
from modelmesh import ModelMesh, MeshConfig
from modelmesh.interfaces.provider import (
    ChatMessage, CompletionChoice, CompletionRequest, CompletionResponse,
    ErrorClassification, ModelInfo, ModelPricing, ProviderConnector,
    QuotaStatus, RateLimitStatus, TokenUsage,
)


class MockConversationProvider(ProviderConnector):
    """Mock provider that tracks conversation context."""

    def __init__(self, name: str):
        self._name = name

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        user_msg = ""
        for msg in request.messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_msg = msg.get("content", "")

        reply = f"[{self._name}] I understand. Regarding '{user_msg[:40]}...' -- here is my answer."
        return CompletionResponse(
            id=f"resp-{self._name}",
            model=self._name,
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=reply),
                finish_reason="stop",
            )],
            usage=TokenUsage(prompt_tokens=15, completion_tokens=20, total_tokens=35),
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


async def run_conversation(client, session_id: str, label: str) -> None:
    """Simulate a multi-turn conversation within a single session."""
    print(f"\n{'=' * 50}")
    print(f"Session: {label} (id: {session_id[:8]}...)")
    print(f"{'=' * 50}")

    messages = [
        {"role": "system", "content": "You are a helpful tutor. Be concise."},
    ]

    turns = [
        "What is recursion in programming?",
        "Can you give me a simple example in Python?",
        "What are the risks of using recursion without a base case?",
    ]

    for i, user_msg in enumerate(turns, start=1):
        messages.append({"role": "user", "content": user_msg})

        print(f"\n  Turn {i}: {user_msg}")

        response = client.chat.completions.create(
            model="text-generation",
            messages=messages,
            temperature=0.5,
            max_tokens=200,
        )

        assistant_msg = response.choices[0].message.content
        messages.append({"role": "assistant", "content": assistant_msg})

        print(f"  Model  : {response.model}")
        print(f"  Answer : {assistant_msg[:100]}...")


async def main() -> None:
    config = MeshConfig(raw={
        "providers": {
            "openai": {
                "connector": "openai",
                "enabled": True,
                "instance": MockConversationProvider("gpt-4o"),
            },
            "anthropic": {
                "connector": "anthropic",
                "enabled": True,
                "instance": MockConversationProvider("claude-sonnet-4"),
            },
        },
        "models": {
            "openai.gpt-4o": {
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
                "strategy": "stick-until-failure",
            },
        },
    })
    mesh = ModelMesh()
    mesh.initialize(config)
    client = mesh.get_client()

    print("Session-stickiness routing demo")
    print("-" * 40)
    print("Two independent conversations run with different session IDs.")
    print("Each conversation is pinned to whichever model handles its")
    print("first request.\n")

    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())

    await run_conversation(client, session_a, "Conversation A")
    await run_conversation(client, session_b, "Conversation B")

    print(f"\n{'=' * 50}")
    print("Fallback scenario")
    print(f"{'=' * 50}")
    print()
    print("If the model pinned to a session becomes unavailable,")
    print("ModelMesh will retry and then rotate to another model,")
    print("re-pinning the session to the new model going forward.")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
