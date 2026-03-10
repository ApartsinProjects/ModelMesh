/**
 * 03 - Free-Tier Aggregation
 *
 * Chains free-tier quotas across three providers (Groq, Cloudflare Workers AI,
 * and HuggingFace) so that when one provider's free quota is exhausted, the
 * system automatically rotates to the next. This sample demonstrates:
 *
 *   - Configuring request-count-based deactivation triggers per provider
 *   - Round-robin selection to distribute load evenly
 *   - Automatic rotation on quota exhaustion
 *   - Calendar-based recovery aligned with provider quota resets
 *
 * Free-tier aggregation is one of ModelMesh Lite's core value propositions:
 * applications combine multiple providers' free quotas into a single,
 * larger effective quota without any application-level logic.
 *
 * Prerequisites:
 *   - Set GROQ_API_KEY, CLOUDFLARE_API_TOKEN, and HF_API_KEY environment variables
 */

import { ModelMesh, MeshConfig, CompletionResponse } from "@nistrapa/modelmesh-core";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Configure three free-tier providers with request limits
  // -----------------------------------------------------------------------
  const config = new MeshConfig({
    providers: {
      // Groq: rate-limited free tier, ultra-fast inference
      "groq.api.v1": {
        enabled: true,
        api_key: "${secrets:GROQ_API_KEY}",
        quota: {
          reset_schedule: "daily",
        },
      },

      // Cloudflare Workers AI: 10,000 neurons/day free
      "cloudflare.workers-ai.v1": {
        enabled: true,
        api_key: "${secrets:CLOUDFLARE_API_TOKEN}",
        quota: {
          reset_schedule: "daily",
        },
      },

      // HuggingFace Inference: monthly free credits
      "huggingface.inference.v1": {
        enabled: true,
        api_key: "${secrets:HF_API_KEY}",
        quota: {
          reset_schedule: "monthly",
        },
      },
    },

    pools: {
      "text-generation": {
        // Round-robin distributes requests evenly across active providers,
        // maximizing the time before any single provider's quota runs out.
        strategy: "modelmesh.round-robin.v1",

        // Request-count-based deactivation triggers free-tier aggregation:
        // when one provider hits its request cap, it moves to standby and
        // the round-robin continues with the remaining providers.
        deactivation: {
          // Per-model request limit within the quota window. Adjust these
          // values to match each provider's free-tier limits.
          request_limit: 100,
          // Also deactivate on rate-limit errors (429)
          error_codes: [429, 500, 503],
          retry_limit: 2,
        },

        // Recovery is aligned with provider quota resets. When the daily
        // or monthly quota resets, the model returns to active.
        recovery: {
          on_quota_reset: true,
          quota_reset_schedule: "daily_utc",
          // Also probe periodically in case the provider resets early
          probe_interval: "600s",
        },

        // Minimal retry -- free tiers have tight rate limits
        retry: {
          max_attempts: 1,
          backoff: "fixed",
          initial_delay: "1s",
          retryable_codes: [429, 500, 503],
          scope: "same_model",
        },
      },
    },

    // Console output shows rotation events as quotas are exhausted
    observability: {
      routing: {
        connector: "modelmesh.console.v1",
      },
    },
  });

  // -----------------------------------------------------------------------
  // 2. Initialize
  // -----------------------------------------------------------------------
  const mesh = new ModelMesh();
  mesh.initialize(config);
  console.log("ModelMesh initialized with 3 free-tier providers.");
  console.log("Providers: Groq, Cloudflare Workers AI, HuggingFace\n");

  const client = mesh.getClient();

  // -----------------------------------------------------------------------
  // 3. Send a batch of requests to demonstrate round-robin and rotation
  // -----------------------------------------------------------------------
  const totalRequests = 15;
  console.log(`Sending ${totalRequests} requests across free-tier providers...\n`);

  for (let i = 1; i <= totalRequests; i++) {
    try {
      const response = (await client.chat.completions.create({
        model: "text-generation",
        messages: [
          { role: "user", content: `Request #${i}: What is ${i} * ${i}?` },
        ],
        maxTokens: 50,
      })) as CompletionResponse;

      console.log(
        `[${i}/${totalRequests}] Model: ${response.model} | ` +
        `Response: ${response.choices[0].message?.content?.trim()}`
      );
    } catch (error) {
      // This fires only if ALL three providers are exhausted
      console.error(`[${i}/${totalRequests}] All free tiers exhausted:`, error);
      break;
    }
  }

  // -----------------------------------------------------------------------
  // 4. Show aggregate statistics
  // -----------------------------------------------------------------------
  console.log("\n--- Request Distribution ---");
  const pools = mesh.listPools();
  for (const pool of pools) {
    console.log(`Pool: ${pool.poolId}`);
  }

  // -----------------------------------------------------------------------
  // 5. Shut down
  // -----------------------------------------------------------------------
  mesh.shutdown();
  console.log("\nModelMesh shut down.");
}

main().catch(console.error);
