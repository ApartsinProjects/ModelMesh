/**
 * 08 - Custom Pool with Dynamic Selection Function
 *
 * Defines a custom capability pool with a dynamic selection function that
 * scores models by context window size. This sample demonstrates:
 *
 *   - Creating a custom pool targeting a specific capability subtree
 *   - Defining explicit model entries with constraint metadata
 *   - Using a dynamic selection function for model scoring
 *   - Automatic pool membership based on capability registration
 *   - Combining static pool configuration with runtime model attributes
 *
 * Dynamic pools are useful when selection logic goes beyond pre-shipped
 * strategies. The selection function receives candidate models and returns
 * scores, giving the application full control over which model is chosen.
 *
 * Prerequisites:
 *   - Set OPENAI_API_KEY, ANTHROPIC_API_KEY, and GOOGLE_API_KEY
 *     environment variables
 */

import { ModelMesh, MeshConfig, CompletionResponse } from "@modelmesh/core";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Configure providers and explicit model definitions
  // -----------------------------------------------------------------------
  const config = new MeshConfig({
    providers: {
      "openai.llm.v1": {
        enabled: true,
        api_key: "${secrets:OPENAI_API_KEY}",
      },
      "anthropic.claude.v1": {
        enabled: true,
        api_key: "${secrets:ANTHROPIC_API_KEY}",
      },
      "google.gemini.v1": {
        enabled: true,
        api_key: "${secrets:GOOGLE_API_KEY}",
      },
    },

    // Explicit model definitions with constraint metadata. The context
    // window sizes drive the dynamic selection function below.
    models: {
      "gpt-4o": {
        provider: "openai.llm.v1",
        capabilities: [
          "generation.text-generation.chat-completion",
          "interaction.tool-calling",
        ],
        delivery: { synchronous: true, streaming: true },
        features: {
          tool_calling: true,
          structured_output: true,
          system_prompt: true,
        },
        constraints: {
          context_window: 128000,
          max_output_tokens: 16384,
        },
      },
      "claude-sonnet-4": {
        provider: "anthropic.claude.v1",
        capabilities: [
          "generation.text-generation.chat-completion",
          "interaction.tool-calling",
        ],
        delivery: { synchronous: true, streaming: true },
        features: {
          tool_calling: true,
          structured_output: true,
          system_prompt: true,
        },
        constraints: {
          context_window: 200000,
          max_output_tokens: 64000,
        },
      },
      "gemini-2.5-pro": {
        provider: "google.gemini.v1",
        capabilities: [
          "generation.text-generation.chat-completion",
          "interaction.tool-calling",
        ],
        delivery: { synchronous: true, streaming: true },
        features: {
          tool_calling: true,
          structured_output: true,
          system_prompt: true,
        },
        constraints: {
          context_window: 1000000,
          max_output_tokens: 65536,
        },
      },
    },

    pools: {
      // A custom pool for "long-context-analysis" tasks. It targets the
      // chat-completion capability subtree and uses a dynamic selection
      // function that scores models by context window size.
      "long-context-analysis": {
        capability: "generation.text-generation.chat-completion",
        // Priority selection as the base strategy; the dynamic function
        // overrides the ordering at runtime.
        strategy: "modelmesh.priority-selection.v1",
        model_priority: ["gemini-2.5-pro", "claude-sonnet-4", "gpt-4o"],

        deactivation: {
          retry_limit: 3,
          error_codes: [429, 500, 503],
        },
        recovery: {
          cooldown: "60s",
        },
        retry: {
          max_attempts: 2,
          backoff: "exponential_jitter",
          initial_delay: "500ms",
          retryable_codes: [429, 500, 502, 503],
          scope: "any",
        },
      },

      // A standard text-generation pool for comparison
      "text-generation": {
        strategy: "modelmesh.cost-first.v1",
        deactivation: {
          retry_limit: 3,
        },
        recovery: {
          cooldown: "60s",
        },
      },
    },

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
  console.log("ModelMesh initialized with custom long-context-analysis pool.");
  console.log("Models: GPT-4o (128K), Claude Sonnet 4 (200K), Gemini 2.5 Pro (1M)\n");

  const client = mesh.getClient();

  // -----------------------------------------------------------------------
  // 3. Route to the long-context pool
  // -----------------------------------------------------------------------
  // Using the custom pool name as the virtual model name routes through
  // the long-context-analysis pool instead of the default text-generation.
  console.log("--- Long-Context Pool (priority: largest context window) ---\n");

  const longContextResponse = (await client.chat.completions.create({
    model: "long-context-analysis",
    messages: [
      {
        role: "system",
        content: "You are an analyst specializing in summarizing very long documents.",
      },
      {
        role: "user",
        content: "I have a 500-page legal document to analyze. What is the maximum context you can handle, and how should I approach this?",
      },
    ],
    maxTokens: 300,
  })) as CompletionResponse;

  console.log(`Selected model: ${longContextResponse.model}`);
  console.log(`Response: ${longContextResponse.choices[0].message?.content}\n`);

  // -----------------------------------------------------------------------
  // 4. Route to the standard text-generation pool for comparison
  // -----------------------------------------------------------------------
  console.log("--- Standard Text-Generation Pool (cost-first) ---\n");

  const standardResponse = (await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "user", content: "What is 2 + 2?" },
    ],
    maxTokens: 50,
  })) as CompletionResponse;

  console.log(`Selected model: ${standardResponse.model}`);
  console.log(`Response: ${standardResponse.choices[0].message?.content}\n`);

  // -----------------------------------------------------------------------
  // 5. List all pools and their membership
  // -----------------------------------------------------------------------
  console.log("--- All Pools ---");
  const pools = mesh.listPools();
  for (const pool of pools) {
    console.log(`  Pool: ${pool.poolId}, Models: ${pool.models.length}`);
  }

  // -----------------------------------------------------------------------
  // 6. Shut down
  // -----------------------------------------------------------------------
  mesh.shutdown();
  console.log("\nModelMesh shut down.");
}

main().catch(console.error);
