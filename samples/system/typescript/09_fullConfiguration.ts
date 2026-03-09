/**
 * 09 - Full System Configuration
 *
 * Complete ModelMesh Lite setup demonstrating all connector types and
 * configuration sections loaded from a YAML file. This sample shows:
 *
 *   - Secret store (dotenv) for credential management
 *   - Storage (local file with periodic sync) for state persistence
 *   - Observability (console routing + file logging + file statistics)
 *   - Discovery (registry sync + health monitoring)
 *   - Multiple providers with different rotation policies per pool
 *   - YAML file configuration loaded and passed to mesh.initialize()
 *
 * This is the most comprehensive sample and represents a production-ready
 * configuration. In a real deployment, the YAML file would be managed
 * separately from the application code.
 *
 * Prerequisites:
 *   - Create a .env file with: OPENAI_API_KEY, ANTHROPIC_API_KEY,
 *     GOOGLE_API_KEY, DEEPSEEK_API_KEY
 *   - Or set these as environment variables
 */

import { ModelMesh, MeshConfig } from "modelmesh-lite";
import * as fs from "fs";
import * as path from "path";

// =========================================================================
// YAML Configuration
// =========================================================================
// In a real project this file lives at config.yaml in the project root.
// This sample writes it programmatically so the sample is self-contained.

const YAML_CONFIG = `
# ==========================================================================
# ModelMesh Lite - Full Configuration Example
# ==========================================================================
# This YAML demonstrates every top-level section. For the complete reference
# see docs/SystemConfiguration.md.

# --------------------------------------------------------------------------
# Secret Store
# --------------------------------------------------------------------------
# The dotenv store loads API keys from a .env file at startup.
# All credential references elsewhere use \${secrets:KEY_NAME} syntax.
secrets:
  store: modelmesh.dotenv.v1
  path: ./.env

# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------
providers:
  openai.llm.v1:
    enabled: true
    api_key: \${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 5.00
      monthly_limit: 50.00
    discovery:
      enumerate_models: true
      model_details: true

  anthropic.llm.v1:
    enabled: true
    api_key: \${secrets:ANTHROPIC_API_KEY}
    budget:
      daily_limit: 5.00
      monthly_limit: 50.00

  google.gemini.v1:
    enabled: true
    api_key: \${secrets:GOOGLE_API_KEY}
    quota:
      query_remaining: true
      reset_schedule: daily
    discovery:
      enumerate_models: true
      capability_query: true

  deepseek.llm.v1:
    enabled: true
    api_key: \${secrets:DEEPSEEK_API_KEY}
    budget:
      daily_limit: 1.00
      monthly_limit: 10.00

# --------------------------------------------------------------------------
# Models (explicit definitions supplement auto-discovery)
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# Pools
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
storage:
  connector: modelmesh.local-file.v1
  path: ./mesh-state.json
  sync_policy: periodic
  sync_interval: 60s

# --------------------------------------------------------------------------
# Observability
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------
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
`;

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Write the YAML config file (in a real project this already exists)
  // -----------------------------------------------------------------------
  const configPath = path.resolve(__dirname, "config.yaml");
  fs.writeFileSync(configPath, YAML_CONFIG.trim(), "utf-8");
  console.log(`Configuration written to ${configPath}\n`);

  // -----------------------------------------------------------------------
  // 2. Initialize ModelMesh from the YAML file
  // -----------------------------------------------------------------------
  // Read the YAML config, build a MeshConfig, and initialize the mesh.
  // This resolves secrets through the configured store (dotenv), registers
  // providers and connectors, builds pools, and starts background services.
  const mesh = new ModelMesh();
  const yamlContent = fs.readFileSync(configPath, "utf-8");
  await mesh.initialize({ raw: yamlContent } as any);
  console.log("ModelMesh initialized from YAML configuration.");
  console.log("Providers : OpenAI, Anthropic, Google Gemini, DeepSeek");
  console.log("Pools     : text-generation, code-generation, text-embeddings, long-context");
  console.log("Storage   : local file (periodic sync every 60s)");
  console.log("Discovery : registry sync (1h) + health monitor (60s)\n");

  const client = mesh.getClient();

  // -----------------------------------------------------------------------
  // 3. Use the cost-optimized text-generation pool
  // -----------------------------------------------------------------------
  console.log("--- Cost-Optimized Pool (text-generation) ---\n");

  const cheapResponse = await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "user", content: "What is infrastructure as code?" },
    ],
    temperature: 0.4,
    max_tokens: 150,
  });

  console.log(`Model: ${cheapResponse.model}`);
  console.log(`Reply: ${(cheapResponse.choices[0] as any).message.content}\n`);

  // -----------------------------------------------------------------------
  // 4. Use the code-generation pool (priority-based)
  // -----------------------------------------------------------------------
  console.log("--- Code Generation Pool (code-generation) ---\n");

  const codeResponse = await client.chat.completions.create({
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
    max_tokens: 300,
  });

  console.log(`Model: ${codeResponse.model}`);
  console.log(`Reply: ${(codeResponse.choices[0] as any).message.content}\n`);

  // -----------------------------------------------------------------------
  // 5. Use the embeddings pool
  // -----------------------------------------------------------------------
  console.log("--- Embeddings Pool (text-embeddings) ---\n");

  const embeddingResponse = await client.embeddings.create({
    model: "text-embeddings",
    input: "ModelMesh Lite full configuration example.",
  });

  console.log(`Model: ${embeddingResponse.model}`);
  console.log(`Dims : ${(embeddingResponse.data[0] as any).embedding.length}\n`);

  // -----------------------------------------------------------------------
  // 6. Use the long-context pool (latency-first)
  // -----------------------------------------------------------------------
  console.log("--- Long-Context Pool (long-context) ---\n");

  const longCtxResponse = await client.chat.completions.create({
    model: "long-context",
    messages: [
      { role: "user", content: "Summarize the benefits of large context windows." },
    ],
    temperature: 0.4,
    max_tokens: 200,
  });

  console.log(`Model: ${longCtxResponse.model}`);
  console.log(`Reply: ${(longCtxResponse.choices[0] as any).message.content}\n`);

  // -----------------------------------------------------------------------
  // 7. Inspect router state
  // -----------------------------------------------------------------------
  console.log("--- System Overview ---\n");
  const router = mesh.getRouter();
  const pools = router.listPools();
  console.log(`Active pools: ${pools.length}`);
  for (const pool of pools) {
    console.log(`  - ${pool}`);
  }

  // mesh.pools and mesh.providers expose the registered pools and providers
  console.log(`\nRegistered providers: ${Object.keys(mesh.providers).join(", ")}`);
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
  // 9. State persistence note
  // -----------------------------------------------------------------------
  // State is automatically persisted by the storage connector configured
  // above (modelmesh.local-file.v1 with periodic sync every 60s).
  // On restart, ModelMesh reloads state from ./mesh-state.json.

  // -----------------------------------------------------------------------
  // 10. Shut down
  // -----------------------------------------------------------------------
  await mesh.shutdown();
  // Clean up the sample config file
  if (fs.existsSync(configPath)) {
    fs.unlinkSync(configPath);
  }
  console.log(`\nModelMesh shut down.`);
  console.log(`Request log written to: ./requests.jsonl`);
  console.log(`Statistics written to : ./stats.json`);
  console.log(`State persisted to    : ./mesh-state.json`);
}

main().catch(console.error);
