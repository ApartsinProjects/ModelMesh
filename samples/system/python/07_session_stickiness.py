"""
07 - Session Stickiness (Conversational Affinity)
==================================================

Session-sticky routing ensures all messages within a conversation are sent to
the same model and provider.  This is important for multi-turn conversations
where the provider maintains context or where consistent model behavior is
desired.

This sample demonstrates:
  - Configuring session-stickiness rotation policy
  - Passing a session_id through routing options / kwargs
  - Verifying that all messages in a session route to the same model
  - Fallback behavior when the session's model becomes unavailable

Prerequisites:
  - Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables.
"""

import asyncio
import uuid
import yaml
from modelmesh import ModelMesh, MeshConfig

CONFIG_YAML = """
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    enabled: true
    api_key: ${secrets:OPENAI_API_KEY}

  anthropic.llm.v1:
    enabled: true
    api_key: ${secrets:ANTHROPIC_API_KEY}

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - interaction.tool-calling
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384

  claude-sonnet-4:
    provider: anthropic.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - interaction.tool-calling
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 200000
      max_output_tokens: 16384

pools:
  text-generation:
    # Session-stickiness: route all requests with the same session_id
    # to the same model.  First request in a session picks the model
    # via normal selection; subsequent requests are pinned.
    strategy: modelmesh.session-stickiness.v1

    deactivation:
      retry_limit: 3
      error_codes: [429, 500, 502, 503]

    recovery:
      cooldown: 30s
      probe_interval: 120s

    retry:
      max_attempts: 1
      backoff: exponential_jitter
      initial_delay: 500ms
      retryable_codes: [429, 500, 502, 503]
      scope: same_model         # retry on the same model before rotating

observability:
  routing:
    connector: modelmesh.console.v1
"""


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

        # The session_id is passed as a keyword argument.  The OpenAIClient
        # forwards it to the Router as part of RoutingOptions.
        response = client.chat.completions.create(
            model="text-generation",
            messages=messages,
            temperature=0.5,
            max_tokens=200,
            session_id=session_id,    # <-- session affinity key
        )

        assistant_msg = response.choices[0].message.content
        messages.append({"role": "assistant", "content": assistant_msg})

        print(f"  Model  : {response.model}")
        print(f"  Answer : {assistant_msg[:100]}...")


async def main() -> None:
    config = MeshConfig(raw=yaml.safe_load(CONFIG_YAML))
    mesh = ModelMesh()
    mesh.initialize(config)

    client = mesh.get_client()

    print("Session-stickiness routing demo")
    print("-" * 40)
    print("Two independent conversations run with different session IDs.")
    print("Each conversation is pinned to whichever model handles its")
    print("first request.  The routing console output confirms that all")
    print("turns within a session use the same model.\n")

    # Create two independent sessions.
    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())

    # Run both conversations.  In a real application these could be
    # concurrent users or separate conversation threads.
    await run_conversation(client, session_a, "Conversation A")
    await run_conversation(client, session_b, "Conversation B")

    # -----------------------------------------------------------------------
    # Demonstrate what happens when a session's model becomes unavailable.
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 50}")
    print("Fallback scenario")
    print(f"{'=' * 50}")
    print()
    print("If the model pinned to a session becomes unavailable (e.g., the")
    print("provider returns a 503), ModelMesh will:")
    print("  1. Retry on the same model (per retry config)")
    print("  2. If retries are exhausted, rotate to another model")
    print("  3. Re-pin the session to the new model going forward")
    print()
    print("This ensures conversations are not permanently stuck on a")
    print("failing provider while still maximizing session consistency.")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
