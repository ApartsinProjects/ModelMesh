/**
 * 02 - Multi-Provider with Automatic Failover
 *
 * Configures two providers (OpenAI and Anthropic) behind the same capability
 * pool and demonstrates automatic failover. This sample shows:
 *
 *   - Registering multiple providers with API keys from environment variables
 *   - Setting up a chat-completion pool with provider priority
 *   - Automatic rotation when the primary provider fails
 *   - Observing rotation events through console observability
 *
 * When the primary provider (OpenAI) encounters an error -- rate limit,
 * outage, or authentication failure -- ModelMesh automatically rotates to the
 * next available provider (Anthropic) without application code changes.
 *
 * Prerequisites:
 *   - Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables
 */

import { ModelMesh, MeshConfig } from "modelmesh-lite";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Define configuration with two providers
  // -----------------------------------------------------------------------
  const config: MeshConfig = {
    raw: {
      // Use environment variables for secret resolution (default store)
      providers: {
        "openai.llm.v1": {
          enabled: true,
          api_key: "${secrets:OPENAI_API_KEY}",
        },
        "anthropic.llm.v1": {
          enabled: true,
          api_key: "${secrets:ANTHROPIC_API_KEY}",
        },
      },

      // Configure the text-generation pool with priority ordering and retry
      pools: {
        "text-generation": {
          // Priority selection tries providers in the given order. When the
          // first provider fails beyond the retry limit, it moves to standby
          // and the next provider takes over.
          strategy: "modelmesh.priority-selection.v1",
          provider_priority: ["openai.llm.v1", "anthropic.llm.v1"],

          // Deactivation: move a model to standby after 3 consecutive failures
          deactivation: {
            retry_limit: 3,
            error_codes: [429, 500, 502, 503],
          },

          // Recovery: try the standby model again after 60 seconds
          recovery: {
            cooldown: "60s",
            probe_interval: "300s",
          },

          // Retry: attempt the same model up to 2 times before rotating
          retry: {
            max_attempts: 2,
            backoff: "exponential_jitter",
            initial_delay: "500ms",
            max_delay: "5s",
            retryable_codes: [429, 500, 502, 503],
            non_retryable_codes: [400, 401, 403],
            scope: "same_provider",
          },
        },
      },

      // Console observability prints routing decisions to stdout so you can
      // see which provider was selected and any rotation events.
      observability: {
        routing: {
          connector: "modelmesh.console.v1",
        },
      },
    },
  };

  // -----------------------------------------------------------------------
  // 2. Initialize and obtain the client
  // -----------------------------------------------------------------------
  const mesh = new ModelMesh();
  await mesh.initialize(config);
  console.log("ModelMesh initialized with OpenAI + Anthropic providers.\n");

  const client = mesh.getClient();

  // -----------------------------------------------------------------------
  // 3. Send requests -- observe routing and failover
  // -----------------------------------------------------------------------
  const questions = [
    "What is the capital of France?",
    "Explain quantum computing in simple terms.",
    "Write a haiku about programming.",
  ];

  for (const question of questions) {
    console.log(`\n--- Question: "${question}" ---`);

    try {
      const response = await client.chat.completions.create({
        model: "text-generation",
        messages: [
          { role: "user", content: question },
        ],
        temperature: 0.5,
        max_tokens: 200,
      });

      // The response includes the *real* model name that served the request,
      // letting you see which provider was selected.
      console.log(`Routed to  : ${response.model}`);
      console.log(`Response   : ${response.choices[0].message.content}`);
      console.log(`Tokens used: ${response.usage.prompt_tokens + response.usage.completion_tokens}`);
    } catch (error) {
      // If all providers are exhausted, the error propagates to the caller.
      console.error("All providers failed:", error);
    }
  }

  // -----------------------------------------------------------------------
  // 4. Inspect routing state (optional)
  // -----------------------------------------------------------------------
  const router = mesh.getRouter();
  const pool = router.getPool("text-generation");
  console.log("\n--- Pool State ---");
  console.log(`Pool: text-generation`);
  console.log(`Active models:`, pool);

  // -----------------------------------------------------------------------
  // 5. Shut down
  // -----------------------------------------------------------------------
  await mesh.shutdown();
  console.log("\nModelMesh shut down.");
}

main().catch(console.error);
