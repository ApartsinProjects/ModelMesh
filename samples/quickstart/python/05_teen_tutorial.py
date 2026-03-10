"""
05 - Interactive Chatbot Tutorial
==================================

A complete interactive chatbot you can run in your terminal.
Written for beginners who know basic Python (variables, functions,
print, for loops, while, input).

This sample demonstrates:
  - Setting up ModelMesh with a mock provider
  - Giving the AI a personality with a system prompt
  - Building an interactive chat loop with input()
  - Keeping conversation history so the AI remembers context
  - Streaming responses so text appears word-by-word
  - Exiting gracefully when the user types "quit" or "bye"

When run non-interactively (e.g., from a script runner), it plays a
short scripted conversation instead of waiting for terminal input.
"""

from __future__ import annotations

import sys

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


class MockTutorProvider(ProviderConnector):
    """Mock provider that returns friendly tutor-style responses."""

    _RESPONSES = {
        "what is a variable": (
            "Think of a variable like a labeled box. You write a name on "
            "the box (like 'score') and put a value inside (like 42). "
            "Whenever you need that value, you just look at the box!"
        ),
        "what is a loop": (
            "A loop is like hitting replay on your favorite song. "
            "It runs the same code over and over until you tell it to stop. "
            "A 'for' loop replays a set number of times; a 'while' loop "
            "keeps going until a condition changes."
        ),
    }

    _DEFAULT = "Great question! That's a core concept in programming."

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        user_msg = ""
        for msg in request.messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_msg = msg.get("content", "")

        reply = self._DEFAULT
        for key, val in self._RESPONSES.items():
            if key in user_msg.lower():
                reply = val
                break

        return CompletionResponse(
            id="tutor-resp",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=reply),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

    async def stream(self, request: CompletionRequest):
        resp = await self.complete(request)
        content = resp.choices[0].message.content or ""
        words = content.split(" ")
        for i, word in enumerate(words):
            token = word if i == len(words) - 1 else word + " "
            yield CompletionResponse(
                id=f"tutor-chunk-{i}",
                model=request.model,
                choices=[
                    CompletionChoice(
                        index=0,
                        delta=ChatMessage(role="assistant", content=token),
                        finish_reason="stop" if i == len(words) - 1 else None,
                    )
                ],
            )

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, cap):
        return cap in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="tutor-model", name="Mock Tutor")]

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


# --- Step 1: Create a client ---
config = MeshConfig(raw={
    "providers": {
        "tutor": {
            "connector": "tutor",
            "enabled": True,
            "instance": MockTutorProvider(),
        },
    },
    "models": {
        "tutor.model": {
            "provider": "tutor",
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
    # --- Step 2: Set a system prompt ---
    system_prompt = (
        "You are a friendly coding tutor.  Explain things simply, "
        "use analogies a teenager would understand, and keep answers short."
    )

    # --- Step 3: Start the conversation history ---
    messages = [{"role": "system", "content": system_prompt}]

    # When running non-interactively, use scripted inputs.
    # Check both isatty and whether stdin has been redirected.
    try:
        is_interactive = sys.stdin.isatty()
    except Exception:
        is_interactive = False
    scripted_inputs = [
        "What is a variable?",
        "What is a loop?",
        "bye",
    ]
    scripted_idx = 0

    print("Chatbot ready!  Type your message and press Enter.")
    print("Type 'quit' or 'bye' to exit.\n")

    # --- Step 4: The chat loop ---
    while True:
        if is_interactive:
            try:
                user_input = input("You: ")
            except EOFError:
                print("Goodbye!")
                break
        else:
            if scripted_idx >= len(scripted_inputs):
                break
            user_input = scripted_inputs[scripted_idx]
            scripted_idx += 1
            print(f"You: {user_input}")

        if user_input.lower() in ("quit", "bye", "exit"):
            print("Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        # --- Step 5: Stream the AI's response ---
        print("Bot: ", end="")
        stream = client.chat.completions.create(
            model="chat-completion",
            messages=messages,
            stream=True,
        )

        full_reply = ""
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token is not None:
                print(token, end="", flush=True)
                full_reply += token

        print("\n")

        # --- Step 6: Save the AI's reply to history ---
        messages.append({"role": "assistant", "content": full_reply})

    mesh.shutdown()


if __name__ == "__main__":
    main()
