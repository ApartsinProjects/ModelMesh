/**
 * 06 - Cost Optimization with Budget Limits
 *
 * Configures a cost-first selection policy with daily and monthly budget
 * limits per provider. This sample demonstrates:
 *
 *   - Cost-first rotation policy: cheapest active model is always selected
 *   - Per-provider budget limits (daily and monthly)
 *   - Budget-based deactivation: when a provider's spend cap is reached,
 *     its models move to standby and the next cheapest provider takes over
 *   - Multiple providers with different cost profiles
 *
 * This pattern is ideal for applications that need to minimize spend while
 * maintaining service availability. The system exhausts cheap providers
 * before falling back to more expensive ones.
 *
 * Prerequisites:
 *   - Set DEEPSEEK_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, and
 *     ANTHROPIC_API_KEY environment variables
 */

import { ModelMesh, MeshConfig } from "modelmesh-lite";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Configure providers ordered by cost (cheapest first)
  // -----------------------------------------------------------------------
  // DeepSeek and Groq offer the lowest per-token pricing. OpenAI and
  // Anthropic are more expensive but have higher rate limits and broader
  // capability support. The cost-first policy routes to the cheapest
  // active model regardless of declaration order.
  const config: MeshConfig = {
    raw: {
      providers: {
        // DeepSeek: ultra-low-cost chat and reasoning
        "deepseek.llm.v1": {
          enabled: true,
          api_key: "${secrets:DEEPSEEK_API_KEY}",
          budget: {
            daily_limit: 0.50,
            monthly_limit: 5.00,
          },
        },

        // Groq: fast free-tier inference
        "groq.inference.v1": {
          enabled: true,
          api_key: "${secrets:GROQ_API_KEY}",
          budget: {
            daily_limit: 0.00, // Free tier only
            monthly_limit: 0.00,
          },
        },

        // OpenAI: moderate cost, broad capabilities
        "openai.llm.v1": {
          enabled: true,
          api_key: "${secrets:OPENAI_API_KEY}",
          budget: {
            daily_limit: 2.00,
            monthly_limit: 20.00,
          },
        },

        // Anthropic: premium tier, strongest reasoning
        "anthropic.llm.v1": {
          enabled: true,
          api_key: "${secrets:ANTHROPIC_API_KEY}",
          budget: {
            daily_limit: 5.00,
            monthly_limit: 50.00,
          },
        },
      },

      pools: {
        "text-generation": {
          // Cost-first selects the cheapest active model for each request.
          // Provider pricing metadata is used to rank models by cost per
          // token. When a provider's budget limit is reached, its models
          // move to standby and the next cheapest active model takes over.
          strategy: "modelmesh.cost-first.v1",

          deactivation: {
            retry_limit: 3,
            error_codes: [429, 500, 503],
            // Budget-based deactivation: when cumulative spend reaches
            // the budget_limit, the model is deactivated for the period.
            budget_limit: 2.00,
          },

          recovery: {
            cooldown: "60s",
            on_quota_reset: true,
            quota_reset_schedule: "daily_utc",
          },

          retry: {
            max_attempts: 2,
            backoff: "exponential_jitter",
            initial_delay: "500ms",
            retryable_codes: [429, 500, 502, 503],
            scope: "same_provider",
          },
        },
      },

      observability: {
        routing: {
          connector: "modelmesh.console.v1",
        },
        // Track cost statistics to a file for analysis
        statistics: {
          connector: "modelmesh.local-file.v1",
          path: "./cost-stats.json",
          flush_interval: "30s",
        },
      },
    },
  };

  // -----------------------------------------------------------------------
  // 2. Initialize
  // -----------------------------------------------------------------------
  const mesh = new ModelMesh();
  await mesh.initialize(config);
  console.log("ModelMesh initialized with cost-first routing.");
  console.log("Providers (cheapest first): DeepSeek, Groq, OpenAI, Anthropic\n");

  const client = mesh.getClient();

  // -----------------------------------------------------------------------
  // 3. Send requests and observe cost-driven routing
  // -----------------------------------------------------------------------
  const prompts = [
    "Summarize the benefits of renewable energy in 2 sentences.",
    "What are the main programming paradigms?",
    "Explain the difference between TCP and UDP.",
    "Name three famous mathematicians and their contributions.",
    "What is the time complexity of quicksort?",
  ];

  console.log("--- Sending Requests (Cost-First Routing) ---\n");

  for (let i = 0; i < prompts.length; i++) {
    const response = await client.chat.completions.create({
      model: "text-generation",
      messages: [{ role: "user", content: prompts[i] }],
      max_tokens: 100,
    });

    console.log(`[${i + 1}] Prompt : ${prompts[i].substring(0, 50)}...`);
    console.log(`    Model : ${response.model}`);
    console.log(`    Tokens: in=${response.usage.prompt_tokens}, out=${response.usage.completion_tokens}`);
    console.log(`    Answer: ${(response.choices[0] as any).message.content.substring(0, 80)}...\n`);
  }

  // -----------------------------------------------------------------------
  // 4. Check cost statistics
  // -----------------------------------------------------------------------
  console.log("--- Cost Summary ---");
  // The stats() API provides per-provider cost totals.
  // In a real application, you would query mesh.stats() here.
  // For this sample, the statistics are flushed to cost-stats.json
  // by the observability connector.
  const pools = mesh.listPools();
  console.log(`Active pools: ${pools.length}`);
  console.log("Cost data written to ./cost-stats.json");

  // -----------------------------------------------------------------------
  // 5. Shut down
  // -----------------------------------------------------------------------
  await mesh.shutdown();
  console.log("\nModelMesh shut down.");
}

main().catch(console.error);
