/**
 * 09 - Full System Configuration
 *
 * Complete ModelMesh Lite setup demonstrating all connector types and
 * configuration sections loaded from a JSON config object. This sample shows:
 *
 *   - Secret store (dotenv) for credential management
 *   - Storage (local file with periodic sync) for state persistence
 *   - Observability (console routing + file logging + file statistics)
 *   - Discovery (registry sync + health monitoring)
 *   - Multiple providers with different rotation policies per pool
 *   - Programmatic configuration passed to mesh.initialize()
 *
 * This is the most comprehensive sample and represents a production-ready
 * configuration.
 *
 * Prerequisites:
 *   - Create a .env file with: OPENAI_API_KEY, ANTHROPIC_API_KEY,
 *     GOOGLE_API_KEY, DEEPSEEK_API_KEY
 *   - Or set these as environment variables
 */

import { ModelMesh, MeshConfig, CompletionResponse } from "@modelmesh/core";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Define the full configuration inline
  // -----------------------------------------------------------------------
  const config = new MeshConfig({
    // Secret Store
    secrets: {
      store: "modelmesh.dotenv.v1",
      path: "./.env",
    },

    // Providers
    providers: {
      "openai.llm.v1": {
        enabled: true,
        api_key: "${secrets:OPENAI_API_KEY}",
        budget: { daily_limit: 5.00, monthly_limit: 50.00 },
        discovery: { enumerate_models: true, model_details: true },
      },
      "anthropic.llm.v1": {
        enabled: true,
        api_key: "${secrets:ANTHROPIC_API_KEY}",
        budget: { daily_limit: 5.00, monthly_limit: 50.00 },
      },
      "google.gemini.v1": {
        enabled: true,
        api_key: "${secrets:GOOGLE_API_KEY}",
        quota: { query_remaining: true, reset_schedule: "daily" },
        discovery: { enumerate_models: true, capability_query: true },
      },
      "deepseek.llm.v1": {
        enabled: true,
        api_key: "${secrets:DEEPSEEK_API_KEY}",
        budget: { daily_limit: 1.00, monthly_limit: 10.00 },
      },
    },

    // Models (explicit definitions supplement auto-discovery)
    models: {
      "gpt-4o": {
        provider: "openai.llm.v1",
        capabilities: [
          "generation.text-generation.chat-completion",
          "generation.text-generation.code-generation",
          "generation.structured-generation.json-generation",
          "understanding.vision-understanding.image-captioning",
          "interaction.tool-calling",
        ],
      },
      "gpt-4o-mini": {
        provider: "openai.llm.v1",
        capabilities: [
          "generation.text-generation.chat-completion",
          "generation.structured-generation.json-generation",
        ],
      },
      "text-embedding-3-small": {
        provider: "openai.llm.v1",
        capabilities: ["representation.embeddings.text-embeddings"],
      },
      "claude-sonnet-4": {
        provider: "anthropic.llm.v1",
        capabilities: [
          "generation.text-generation.chat-completion",
          "generation.text-generation.code-generation",
          "interaction.tool-calling",
        ],
      },
      "gemini-2.5-pro": {
        provider: "google.gemini.v1",
        capabilities: [
          "generation.text-generation.chat-completion",
          "generation.text-generation.code-generation",
          "generation.structured-generation.json-generation",
          "interaction.tool-calling",
        ],
      },
      "deepseek-chat": {
        provider: "deepseek.llm.v1",
        capabilities: [
          "generation.text-generation.chat-completion",
          "generation.text-generation.code-generation",
        ],
      },
    },

    // Pools
    pools: {
      "text-generation": {
        strategy: "modelmesh.cost-first.v1",
        deactivation: {
          retry_limit: 3,
          error_codes: [429, 500, 503],
          budget_limit: 2.00,
        },
        recovery: { cooldown: "60s", on_quota_reset: true },
        retry: {
          max_attempts: 2,
          backoff: "exponential_jitter",
          initial_delay: "500ms",
          max_delay: "10s",
          scope: "same_provider",
        },
      },
      "code-generation": {
        capability: "generation.text-generation.code-generation",
        strategy: "modelmesh.priority-selection.v1",
        model_priority: ["claude-sonnet-4", "gpt-4o", "gemini-2.5-pro", "deepseek-chat"],
        fallback_strategy: "modelmesh.cost-first.v1",
        deactivation: { retry_limit: 2 },
        recovery: { cooldown: "30s" },
      },
      "text-embeddings": {
        capability: "representation.embeddings.text-embeddings",
        strategy: "modelmesh.stick-until-failure.v1",
        deactivation: { retry_limit: 2 },
        recovery: { cooldown: "30s" },
      },
      "long-context": {
        capability: "generation.text-generation",
        strategy: "modelmesh.latency-first.v1",
        model_priority: ["gemini-2.5-pro", "claude-sonnet-4", "gpt-4o"],
        deactivation: { retry_limit: 2 },
        recovery: { cooldown: "30s" },
      },
    },

    // Storage
    storage: {
      connector: "modelmesh.local-file.v1",
      path: "./mesh-state.json",
      sync_policy: "periodic",
      sync_interval: "60s",
    },

    // Observability
    observability: {
      routing: { connector: "modelmesh.console.v1" },
      logging: {
        connector: "modelmesh.local-file.v1",
        level: "metadata",
        path: "./requests.jsonl",
      },
      statistics: {
        connector: "modelmesh.local-file.v1",
        path: "./stats.json",
        flush_interval: "30s",
      },
    },

    // Discovery
    discovery: {
      sync: {
        enabled: true,
        interval: "1h",
        auto_register: true,
        providers: ["openai.llm.v1", "google.gemini.v1"],
      },
      health: {
        enabled: true,
        interval: "60s",
        timeout: "10s",
        failure_threshold: 3,
      },
    },
  });

  // -----------------------------------------------------------------------
  // 2. Initialize ModelMesh
  // -----------------------------------------------------------------------
  const mesh = new ModelMesh();
  mesh.initialize(config);
  console.log("ModelMesh initialized from full configuration.");
  console.log("Providers : OpenAI, Anthropic, Google Gemini, DeepSeek");
  console.log("Pools     : text-generation, code-generation, text-embeddings, long-context");
  console.log("Storage   : local file (periodic sync every 60s)");
  console.log("Discovery : registry sync (1h) + health monitor (60s)\n");

  const client = mesh.getClient();

  // -----------------------------------------------------------------------
  // 3. Use the cost-optimized text-generation pool
  // -----------------------------------------------------------------------
  console.log("--- Cost-Optimized Pool (text-generation) ---\n");

  const cheapResponse = (await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "user", content: "What is infrastructure as code?" },
    ],
    temperature: 0.4,
    maxTokens: 150,
  })) as CompletionResponse;

  console.log(`Model: ${cheapResponse.model}`);
  console.log(`Reply: ${cheapResponse.choices[0].message?.content}\n`);

  // -----------------------------------------------------------------------
  // 4. Use the code-generation pool (priority-based)
  // -----------------------------------------------------------------------
  console.log("--- Code Generation Pool (code-generation) ---\n");

  const codeResponse = (await client.chat.completions.create({
    model: "code-generation",
    messages: [
      {
        role: "system",
        content: "You write clean, well-documented code.",
      },
      {
        role: "user",
        content: "Write a Python function to compute the GCD of two numbers.",
      },
    ],
    temperature: 0.2,
    maxTokens: 300,
  })) as CompletionResponse;

  console.log(`Model: ${codeResponse.model}`);
  console.log(`Reply: ${codeResponse.choices[0].message?.content}\n`);

  // -----------------------------------------------------------------------
  // 5. Use the embeddings pool
  // -----------------------------------------------------------------------
  console.log("--- Embeddings Pool (text-embeddings) ---\n");

  const embeddingResponse = await client.embeddings.create({
    model: "text-embeddings",
    input: "ModelMesh Lite full configuration example.",
  });

  console.log(`Model: ${embeddingResponse.model}`);
  console.log(`Usage: ${embeddingResponse.usage.totalTokens} tokens\n`);

  // -----------------------------------------------------------------------
  // 6. Use the long-context pool (latency-first)
  // -----------------------------------------------------------------------
  console.log("--- Long-Context Pool (long-context) ---\n");

  const longCtxResponse = (await client.chat.completions.create({
    model: "long-context",
    messages: [
      { role: "user", content: "Summarize the benefits of large context windows." },
    ],
    temperature: 0.4,
    maxTokens: 200,
  })) as CompletionResponse;

  console.log(`Model: ${longCtxResponse.model}`);
  console.log(`Reply: ${longCtxResponse.choices[0].message?.content}\n`);

  // -----------------------------------------------------------------------
  // 7. Inspect system state
  // -----------------------------------------------------------------------
  console.log("--- System Overview ---\n");

  // mesh.pools and mesh.providers expose the registered pools and providers
  console.log(`Registered providers: ${Object.keys(mesh.providers).join(", ")}`);
  console.log(`Registered pools   : ${Object.keys(mesh.pools).join(", ")}\n`);

  // -----------------------------------------------------------------------
  // 8. Show pool status
  // -----------------------------------------------------------------------
  console.log("--- Pool Status ---\n");
  const poolStatus = mesh.poolStatus();
  for (const [poolName, status] of Object.entries(poolStatus)) {
    console.log(`  Pool '${poolName}': active=${status.active}, standby=${status.standby}`);
  }

  // -----------------------------------------------------------------------
  // 9. Shut down
  // -----------------------------------------------------------------------
  mesh.shutdown();
  console.log(`\nModelMesh shut down.`);
  console.log(`Request log written to: ./requests.jsonl`);
  console.log(`Statistics written to : ./stats.json`);
  console.log(`State persisted to    : ./mesh-state.json`);
}

main().catch(console.error);
