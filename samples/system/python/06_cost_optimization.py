"""
06 - Cost Optimization with Budget Limits
==========================================

Cost-first selection strategy combined with per-provider budget limits.
ModelMesh routes each request to the cheapest active model and automatically
deactivates providers when their daily or monthly budget is exhausted.

This sample demonstrates:
  - Configuring cost-first rotation policy
  - Setting daily and monthly budget limits per provider
  - How the system routes to the cheapest models first
  - Budget-based deactivation when spend limits are reached
  - Recovery on quota/budget reset

Prerequisites:
  - Set OPENAI_API_KEY, DEEPSEEK_API_KEY, and GROQ_API_KEY environment
    variables.

Pricing note:
  DeepSeek Chat is significantly cheaper than GPT-4o.  The cost-first strategy
  will prefer DeepSeek until its budget is exhausted or it becomes unavailable,
  then fall back to Groq (free tier), and finally to OpenAI.
"""

import asyncio
import yaml
from modelmesh import ModelMesh, MeshConfig

CONFIG_YAML = """
secrets:
  store: modelmesh.env.v1

providers:
  deepseek.llm.v1:
    enabled: true
    api_key: ${secrets:DEEPSEEK_API_KEY}
    budget:
      daily_limit: 0.50           # $0.50/day -- very conservative
      monthly_limit: 5.00         # $5/month

  groq.inference.v1:
    enabled: true
    api_key: ${secrets:GROQ_API_KEY}
    # Groq free tier -- no budget limit, but has rate limits
    quota:
      query_remaining: true
      reset_schedule: daily

  openai.llm.v1:
    enabled: true
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 2.00           # $2/day
      monthly_limit: 20.00        # $20/month

models:
  deepseek-chat:
    provider: deepseek.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 64000
      max_output_tokens: 8192

  llama-3.3-70b-groq:
    provider: groq.inference.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 131072
      max_output_tokens: 8192

  gpt-4o-mini:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
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

pools:
  text-generation:
    # Cost-first: always pick the cheapest active model.
    strategy: modelmesh.cost-first.v1

    deactivation:
      retry_limit: 3
      error_codes: [429, 500, 502, 503]
      budget_limit: 0.50          # pool-level budget guard (USD)

    recovery:
      cooldown: 60s
      on_quota_reset: true
      quota_reset_schedule: daily_utc

    retry:
      max_attempts: 2
      backoff: exponential_jitter
      initial_delay: 500ms
      max_delay: 5s
      retryable_codes: [429, 500, 502, 503]
      non_retryable_codes: [400, 401, 403]
      scope: any

observability:
  routing:
    connector: modelmesh.console.v1
  statistics:
    connector: modelmesh.console.v1
    flush_interval: 30s
"""


async def main() -> None:
    config = MeshConfig(raw=yaml.safe_load(CONFIG_YAML))
    mesh = ModelMesh()
    mesh.initialize(config)

    client = mesh.get_client()

    print("=" * 60)
    print("Cost-first routing with budget limits")
    print("=" * 60)
    print()
    print("Provider cost ordering (approximate):")
    print("  1. Groq (Llama 3.3 70B) -- free tier")
    print("  2. DeepSeek Chat         -- ~$0.14/M input tokens")
    print("  3. OpenAI GPT-4o-mini    -- ~$0.15/M input tokens")
    print()
    print("The cost-first strategy selects the cheapest model for each")
    print("request.  If a provider's budget is exhausted, its models")
    print("are deactivated and traffic shifts to the next cheapest.\n")

    # Send several requests to demonstrate cost-based routing.
    tasks = [
        "Summarize the concept of microservices in two sentences.",
        "What is eventual consistency?",
        "Explain the CAP theorem briefly.",
        "Define 'idempotency' in the context of APIs.",
        "What is the difference between horizontal and vertical scaling?",
    ]

    for i, task in enumerate(tasks, start=1):
        print(f"--- Request {i}/{len(tasks)} ---")
        response = client.chat.completions.create(
            model="text-generation",
            messages=[{"role": "user", "content": task}],
            temperature=0.4,
            max_tokens=150,
        )
        print(f"  Model  : {response.model}")
        print(f"  Tokens : in={response.usage.prompt_tokens}, "
              f"out={response.usage.completion_tokens}")
        print(f"  Answer : {response.choices[0].message.content[:80]}...")
        print()

    # Show pool status through the pool_status() API.
    print("--- Pool status summary ---")
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
