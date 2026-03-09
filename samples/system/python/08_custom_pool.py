"""
08 - Custom Pool with Dynamic Selection
========================================

Define a custom capability pool that targets a specific subtree of the
capability hierarchy, and use a dynamic selection function to score
candidates by context window size.

This sample demonstrates:
  - Creating a custom pool targeting a hierarchy node
  - Using a dynamic selection function for scoring models
  - Provider and model priority lists
  - How models join pools automatically based on capability registration
  - Inspecting pool and provider status programmatically

Prerequisites:
  - Set OPENAI_API_KEY, ANTHROPIC_API_KEY, and GOOGLE_API_KEY environment
    variables.
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

  anthropic.llm.v1:
    enabled: true
    api_key: ${secrets:ANTHROPIC_API_KEY}

  google.gemini.v1:
    enabled: true
    api_key: ${secrets:GOOGLE_API_KEY}

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.text-generation.code-generation
      - generation.structured-generation.json-generation
      - interaction.tool-calling
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      structured_output: true
      system_prompt: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384

  claude-sonnet-4:
    provider: anthropic.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.text-generation.code-generation
      - interaction.tool-calling
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      structured_output: true
      system_prompt: true
    constraints:
      context_window: 200000
      max_output_tokens: 16384

  gemini-2.5-pro:
    provider: google.gemini.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.text-generation.code-generation
      - generation.structured-generation.json-generation
      - interaction.tool-calling
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      structured_output: true
      system_prompt: true
    constraints:
      context_window: 1048576
      max_output_tokens: 65536

  gemini-2.5-flash:
    provider: google.gemini.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.text-generation.code-generation
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 1048576
      max_output_tokens: 8192

pools:
  # -------------------------------------------------------------------
  # Pool 1: Standard text generation (for comparison).
  # -------------------------------------------------------------------
  text-generation:
    strategy: modelmesh.stick-until-failure.v1

  # -------------------------------------------------------------------
  # Pool 2: Custom "long-context" pool.
  # Targets the text-generation subtree but applies a dynamic selection
  # function that favors models with the largest context window.
  # -------------------------------------------------------------------
  long-context-analysis:
    capability: generation.text-generation
    strategy: modelmesh.priority-selection.v1
    model_priority:
      - gemini-2.5-pro             # 1M context
      - claude-sonnet-4            # 200K context
      - gpt-4o                     # 128K context
    fallback_strategy: modelmesh.cost-first.v1
    deactivation:
      retry_limit: 2
    recovery:
      cooldown: 30s

  # -------------------------------------------------------------------
  # Pool 3: Custom "code-review" pool.
  # Targets the code-generation leaf with provider restrictions.
  # -------------------------------------------------------------------
  code-review:
    capability: generation.text-generation.code-generation
    strategy: modelmesh.priority-selection.v1
    model_priority:
      - claude-sonnet-4
      - gpt-4o
    excluded_providers:
      - google.gemini.v1           # exclude Gemini from code review
    deactivation:
      retry_limit: 2
    recovery:
      cooldown: 30s

observability:
  routing:
    connector: modelmesh.console.v1
"""


async def main() -> None:
    config = MeshConfig(raw=yaml.safe_load(CONFIG_YAML))
    mesh = ModelMesh()
    mesh.initialize(config)

    client = mesh.get_client()

    print("=" * 60)
    print("Custom pool with dynamic selection demo")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Inspect pool membership
    # -----------------------------------------------------------------------
    print("\n--- Pool membership ---\n")
    pool_status = mesh.pool_status()
    for pool_name in ["text-generation", "long-context-analysis", "code-review"]:
        status = pool_status.get(pool_name, {})
        print(f"Pool '{pool_name}':")
        print(f"  Status: {status}")
        print()

    # -----------------------------------------------------------------------
    # Example 1: Route through the long-context pool
    # -----------------------------------------------------------------------
    print("--- Example 1: Long-context analysis ---\n")

    # The model name "long-context-analysis" is the pool name, used as a
    # virtual model name.  ModelMesh resolves it to the highest-priority
    # model in that pool (gemini-2.5-pro with 1M context).
    response = client.chat.completions.create(
        model="long-context-analysis",
        messages=[
            {"role": "system", "content": "You are an expert analyst."},
            {"role": "user", "content": "If I need to analyze a 500-page document, "
             "what context window would I need? Estimate in tokens."},
        ],
        temperature=0.3,
        max_tokens=200,
    )

    print(f"  Pool   : long-context-analysis")
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:120]}...")

    # -----------------------------------------------------------------------
    # Example 2: Route through the code-review pool
    # -----------------------------------------------------------------------
    print("\n--- Example 2: Code review (Gemini excluded) ---\n")

    response = client.chat.completions.create(
        model="code-review",
        messages=[
            {"role": "system", "content": "You are a senior code reviewer."},
            {"role": "user", "content": "Review this function:\n\n"
             "def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)"},
        ],
        temperature=0.2,
        max_tokens=300,
    )

    print(f"  Pool   : code-review")
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:120]}...")

    # -----------------------------------------------------------------------
    # Example 3: Inspect pool and provider status programmatically
    # -----------------------------------------------------------------------
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
