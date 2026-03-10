"""
09 - Full System Configuration
===============================

Complete ModelMesh Lite setup exercising every major subsystem: secret store,
storage, observability, discovery, multiple providers, and multiple pools with
different rotation policies.  Configuration is loaded from a YAML file.

This sample demonstrates:
  - Secret store (dotenv) for credential resolution
  - Storage (local file with periodic sync) for state persistence
  - Observability (console for routing + file for request logs + file for stats)
  - Discovery (registry sync + health monitoring)
  - Multiple providers with quota and budget settings
  - Multiple pools with different selection strategies
  - Loading configuration via MeshConfig and mesh.initialize()
  - Runtime statistics API

Prerequisites:
  - Create a .env file in the same directory with your API keys:
      OPENAI_API_KEY=sk-...
      ANTHROPIC_API_KEY=sk-ant-...
      GOOGLE_API_KEY=AI...
      DEEPSEEK_API_KEY=sk-...
  - Or set these as environment variables.

This sample writes a YAML config file to disk, then loads it with
MeshConfig to demonstrate the file-based configuration workflow.
"""

import asyncio
import os
import tempfile
import yaml
from modelmesh import ModelMesh, MeshConfig

# ---------------------------------------------------------------------------
# Full YAML configuration
# ---------------------------------------------------------------------------
# This is the most comprehensive configuration in the sample collection.
# In production, this would live in a standalone config.yaml file.

FULL_CONFIG_YAML = """
# =========================================================================
# Secrets -- resolve API keys from a .env file
# =========================================================================
secrets:
  store: modelmesh.dotenv.v1
  path: ./.env

# =========================================================================
# Providers -- four providers with quota and budget settings
# =========================================================================
providers:
  openai.llm.v1:
    enabled: true
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 5.00
      monthly_limit: 50.00
    discovery:
      enumerate_models: true
      model_details: true

  anthropic.llm.v1:
    enabled: true
    api_key: ${secrets:ANTHROPIC_API_KEY}
    budget:
      daily_limit: 5.00
      monthly_limit: 50.00

  google.gemini.v1:
    enabled: true
    api_key: ${secrets:GOOGLE_API_KEY}
    quota:
      query_remaining: true
      reset_schedule: daily
    discovery:
      enumerate_models: true
      capability_query: true

  deepseek.llm.v1:
    enabled: true
    api_key: ${secrets:DEEPSEEK_API_KEY}
    budget:
      daily_limit: 1.00
      monthly_limit: 10.00

# =========================================================================
# Models -- explicit definitions supplement auto-discovered models
# =========================================================================
models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.text-generation.code-generation
      - generation.structured-generation.json-generation
      - understanding.vision-understanding.image-captioning
      - interaction.tool-calling
    delivery:
      synchronous: true
      streaming: true
      batch: true
    batch:
      max_items: 50000
      completion_window: 24h
      cost_discount: 0.5
    features:
      tool_calling: true
      structured_output: true
      json_mode: true
      system_prompt: true
      fine_tunable: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384
      max_images: 20

  gpt-4o-mini:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.structured-generation.json-generation
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

  text-embedding-3-small:
    provider: openai.llm.v1
    capabilities:
      - representation.embeddings.text-embeddings
    delivery:
      synchronous: true
      batch: true
    constraints:
      context_window: 8191

  claude-sonnet-4:
    provider: anthropic.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.text-generation.code-generation
      - interaction.tool-calling
    delivery:
      synchronous: true
      streaming: true
      batch: true
    batch:
      max_items: 10000
      completion_window: 24h
      cost_discount: 0.5
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

  deepseek-chat:
    provider: deepseek.llm.v1
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
      context_window: 64000
      max_output_tokens: 8192

# =========================================================================
# Pools -- different strategies for different use cases
# =========================================================================
pools:
  # General text generation -- cost-first with budget deactivation
  text-generation:
    strategy: modelmesh.cost-first.v1
    deactivation:
      retry_limit: 3
      error_codes: [429, 500, 503]
      budget_limit: 2.00
    recovery:
      cooldown: 60s
      on_quota_reset: true
    retry:
      max_attempts: 2
      backoff: exponential_jitter
      initial_delay: 500ms
      max_delay: 10s
      scope: same_provider

  # Code generation -- priority-based with fallback
  code-generation:
    capability: generation.text-generation.code-generation
    strategy: modelmesh.priority-selection.v1
    model_priority:
      - claude-sonnet-4
      - gpt-4o
      - gemini-2.5-pro
      - deepseek-chat
    fallback_strategy: modelmesh.cost-first.v1
    deactivation:
      retry_limit: 2
    recovery:
      cooldown: 30s

  # Embeddings -- stick-until-failure for consistency
  text-embeddings:
    capability: representation.embeddings.text-embeddings
    strategy: modelmesh.stick-until-failure.v1
    deactivation:
      retry_limit: 2
    recovery:
      cooldown: 30s

  # Long-context tasks -- latency-first among large-context models
  long-context:
    capability: generation.text-generation
    strategy: modelmesh.latency-first.v1
    model_priority:
      - gemini-2.5-pro
      - claude-sonnet-4
      - gpt-4o
    deactivation:
      retry_limit: 2
    recovery:
      cooldown: 30s

# =========================================================================
# Storage -- persist state to a local file with periodic sync
# =========================================================================
storage:
  connector: modelmesh.local-file.v1
  path: ./mesh-state.json
  sync_policy: periodic
  sync_interval: 60s

# =========================================================================
# Observability -- console routing + file logging + file statistics
# =========================================================================
observability:
  routing:
    connector: modelmesh.console.v1
  logging:
    connector: modelmesh.local-file.v1
    level: metadata
    path: ./requests.jsonl
  statistics:
    connector: modelmesh.local-file.v1
    path: ./stats.json
    flush_interval: 30s

# =========================================================================
# Discovery -- sync model catalogue and monitor health
# =========================================================================
discovery:
  sync:
    enabled: true
    interval: 1h
    auto_register: true
    providers:
      - openai.llm.v1
      - google.gemini.v1
  health:
    enabled: true
    interval: 60s
    timeout: 10s
    failure_threshold: 3
"""


async def main() -> None:
    # Write the configuration to a temporary file to demonstrate from_yaml().
    config_dir = tempfile.mkdtemp(prefix="modelmesh_sample_")
    config_path = os.path.join(config_dir, "config.yaml")

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(FULL_CONFIG_YAML)

    print("=" * 60)
    print("Full system configuration demo")
    print("=" * 60)
    print(f"\nConfig written to: {config_path}")

    # -----------------------------------------------------------------------
    # Initialize from YAML file
    # -----------------------------------------------------------------------
    with open(config_path, "r", encoding="utf-8") as f:
        config = MeshConfig(raw=yaml.safe_load(f.read()))
    mesh = ModelMesh()
    mesh.initialize(config)
    print("ModelMesh initialized from YAML configuration.\n")

    client = mesh.get_client()

    # -----------------------------------------------------------------------
    # Show system overview
    # -----------------------------------------------------------------------
    print("--- System overview ---\n")
    pool_status = mesh.pool_status()
    print(f"Active pools: {len(pool_status)}")
    for pool_name in pool_status:
        print(f"  - {pool_name}")
    print()

    print(f"Providers : {mesh.providers}")
    print(f"Pools     : {mesh.pools}")
    print()

    # -----------------------------------------------------------------------
    # Exercise different pools
    # -----------------------------------------------------------------------

    # Pool: text-generation (cost-first)
    print("--- Pool: text-generation (cost-first) ---\n")
    response = client.chat.completions.create(
        model="text-generation",
        messages=[{"role": "user", "content": "What is infrastructure as code?"}],
        temperature=0.4,
        max_tokens=150,
    )
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:100]}...")

    # Pool: code-generation (priority-based)
    print("\n--- Pool: code-generation (priority) ---\n")
    response = client.chat.completions.create(
        model="code-generation",
        messages=[
            {"role": "system", "content": "You write clean, well-documented code."},
            {"role": "user", "content": "Write a Python function to compute the GCD of two numbers."},
        ],
        temperature=0.2,
        max_tokens=300,
    )
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:100]}...")

    # Pool: text-embeddings (stick-until-failure)
    print("\n--- Pool: text-embeddings (stick-until-failure) ---\n")
    emb_response = client.embeddings.create(
        model="text-embeddings",
        input="Full configuration example.",
    )
    print(f"  Model      : {emb_response.model}")
    print(f"  Dimensions : {len(emb_response.data[0].embedding)}")

    # Pool: long-context (latency-first)
    print("\n--- Pool: long-context (latency-first) ---\n")
    response = client.chat.completions.create(
        model="long-context",
        messages=[{"role": "user", "content": "Summarize the benefits of large context windows."}],
        temperature=0.4,
        max_tokens=200,
    )
    print(f"  Model  : {response.model}")
    print(f"  Answer : {response.choices[0].message.content[:100]}...")

    # -----------------------------------------------------------------------
    # Show runtime statistics via pool_status()
    # -----------------------------------------------------------------------
    print("\n--- Runtime statistics ---\n")
    print("Active providers:")
    for provider_id in mesh.active_providers():
        print(f"  {provider_id}")
    print()

    pool_status = mesh.pool_status()
    for pool_name, status in pool_status.items():
        print(f"  Pool '{pool_name}': {status}")

    # -----------------------------------------------------------------------
    # Demonstrate state snapshot via pool_status()
    # -----------------------------------------------------------------------
    print("\n--- State snapshot ---\n")
    import json
    snapshot = json.dumps(mesh.pool_status(), default=str)
    print(f"  State snapshot size: {len(snapshot)} chars")
    print("  (Pool status can be serialized and stored for monitoring.)")

    # -----------------------------------------------------------------------
    # Clean up
    # -----------------------------------------------------------------------
    mesh.shutdown()
    print(f"\nModelMesh shut down.")
    print(f"Request log written to: ./requests.jsonl")
    print(f"Statistics written to : ./stats.json")
    print(f"State persisted to    : ./mesh-state.json")

    # Clean up temp config file
    os.remove(config_path)
    os.rmdir(config_dir)


if __name__ == "__main__":
    asyncio.run(main())
