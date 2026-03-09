"""
03 - Free-Tier Aggregation
==========================

Chain free-tier quotas across three providers: Groq, Cloudflare Workers AI,
and HuggingFace.  When one provider's free quota is exhausted, ModelMesh
rotates to the next, effectively combining their individual limits into a
larger aggregate quota.

This sample demonstrates:
  - Request-count-based deactivation triggers (request_limit)
  - Quota-window-based recovery aligned to daily resets
  - Round-robin selection strategy across free-tier providers
  - How quota exhaustion on one provider triggers transparent rotation

Prerequisites:
  - Set GROQ_API_KEY, CLOUDFLARE_API_KEY, and HF_API_KEY environment variables.
  - Free-tier accounts on each provider are sufficient.
"""

import asyncio
import yaml
from modelmesh import ModelMesh, MeshConfig

CONFIG_YAML = """
secrets:
  store: modelmesh.env.v1

providers:
  groq.inference.v1:
    enabled: true
    api_key: ${secrets:GROQ_API_KEY}
    quota:
      query_remaining: true
      reset_schedule: daily

  cloudflare.workers-ai.v1:
    enabled: true
    api_key: ${secrets:CLOUDFLARE_API_KEY}
    quota:
      reset_schedule: daily

  huggingface.inference.v1:
    enabled: true
    api_key: ${secrets:HF_API_KEY}
    quota:
      reset_schedule: monthly

models:
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

  llama-3.1-8b-cloudflare:
    provider: cloudflare.workers-ai.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      system_prompt: true
    constraints:
      context_window: 8192
      max_output_tokens: 2048

  llama-3-8b-huggingface:
    provider: huggingface.inference.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      system_prompt: true
    constraints:
      context_window: 8192
      max_output_tokens: 2048

pools:
  text-generation:
    # Round-robin distributes requests evenly across providers.
    strategy: modelmesh.round-robin.v1

    # When a provider's free-tier quota is exhausted, deactivate its models.
    deactivation:
      request_limit: 200         # deactivate after 200 requests (conservative)
      error_codes: [429]         # also deactivate on rate-limit errors
      quota_window: daily        # reset counters daily

    # Reactivate when the provider's daily quota resets.
    recovery:
      on_quota_reset: true
      quota_reset_schedule: daily_utc
      cooldown: 60s              # wait before retrying after a 429

    retry:
      max_attempts: 1
      backoff: fixed
      initial_delay: 1s
      retryable_codes: [429, 502, 503]
      non_retryable_codes: [400, 401, 403]
      scope: any                 # on retry, allow rotation to a different provider

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
    print("Free-tier aggregation: Groq + Cloudflare + HuggingFace")
    print("=" * 60)
    print()
    print("Round-robin strategy distributes requests across providers.")
    print("When a provider's quota is exhausted (429 or request_limit),")
    print("its models are deactivated and traffic shifts to the remaining")
    print("providers.  Quotas reset on a daily schedule.\n")

    # Send a batch of requests to show round-robin distribution.
    prompts = [
        "Define 'machine learning' in one sentence.",
        "What is the difference between TCP and UDP?",
        "Name three sorting algorithms.",
        "What does 'REST' stand for?",
        "Explain what a hash table is.",
        "What is the time complexity of binary search?",
    ]

    for i, prompt in enumerate(prompts, start=1):
        print(f"--- Request {i}/{len(prompts)} ---")
        response = client.chat.completions.create(
            model="text-generation",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=100,
        )
        print(f"  Provider : {response.model}")
        print(f"  Model    : {response.model}")
        print(f"  Answer   : {response.choices[0].message.content[:80]}...")
        print()

    # Show aggregate quota consumption.
    print("--- Quota summary ---")
    print("Check the console output above for routing decisions showing")
    print("which provider handled each request.  Under round-robin, you")
    print("should see requests distributed across all three providers.\n")

    mesh.shutdown()
    print("ModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
