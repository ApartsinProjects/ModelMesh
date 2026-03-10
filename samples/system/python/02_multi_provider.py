"""
02 - Multi-Provider with Automatic Failover
============================================

Two providers (OpenAI and Anthropic) serving the same capability pool.  When
one provider fails or is rate-limited, ModelMesh automatically rotates to the
other.

This sample demonstrates:
  - Configuring multiple providers with secret references
  - Registering models from different providers in the same pool
  - Automatic failover via stick-until-failure strategy
  - Observing rotation events through console observability

Prerequisites:
  - Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables.
"""

import asyncio
import yaml
from modelmesh import ModelMesh, MeshConfig

CONFIG_YAML = """
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    enabled: true
    api_key: ${secrets:OPENAI_API_KEY}

  anthropic.claude.v1:
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
      batch: true
    features:
      tool_calling: true
      structured_output: true
      system_prompt: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384

  claude-sonnet-4:
    provider: anthropic.claude.v1
    capabilities:
      - generation.text-generation.chat-completion
      - interaction.tool-calling
    delivery:
      synchronous: true
      streaming: true
      batch: true
    features:
      tool_calling: true
      structured_output: true
      system_prompt: true
    constraints:
      context_window: 200000
      max_output_tokens: 16384

pools:
  text-generation:
    # Stick to the first working model; rotate only on failure.
    strategy: modelmesh.stick-until-failure.v1
    deactivation:
      retry_limit: 2
      error_codes: [429, 500, 502, 503]
    recovery:
      cooldown: 30s
      probe_interval: 120s
    retry:
      max_attempts: 1
      backoff: exponential_jitter
      initial_delay: 500ms
      max_delay: 5s
      retryable_codes: [429, 500, 502, 503]
      non_retryable_codes: [400, 401, 403]
      scope: same_provider

observability:
  routing:
    connector: modelmesh.console.v1   # rotation events appear here
"""


async def main() -> None:
    config = MeshConfig(raw=yaml.safe_load(CONFIG_YAML))
    mesh = ModelMesh()
    mesh.initialize(config)

    client = mesh.get_client()

    print("=" * 60)
    print("Multi-provider failover demo")
    print("=" * 60)

    # Send three requests.  Under normal conditions all three go to the same
    # model (stick-until-failure).  If that model's provider returns a 429 or
    # 5xx, ModelMesh rotates to the other provider transparently.
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

    # Demonstrate explicit routing inspection through the mesh.
    pools = mesh.list_pools()
    print(f"\n--- Pool status ---")
    for pool in pools:
        print(f"  Pool: {pool}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
