/**
 * 05 - Text Embeddings with Failover
 *
 * Generates text embeddings using OpenAI and Cohere as providers, with
 * automatic failover between them. This sample demonstrates:
 *
 *   - Using the embeddings API through the OpenAI-compatible client
 *   - Configuring providers that support the text-embeddings capability
 *   - Routing embedding requests through the same pool/failover system
 *
 * The "text-embeddings" virtual model name maps to the predefined
 * representation.embeddings.text-embeddings capability pool. Any provider with models
 * registered at that capability leaf is eligible for selection.
 *
 * Prerequisites:
 *   - Set OPENAI_API_KEY and COHERE_API_KEY environment variables
 */

import { ModelMesh, MeshConfig } from "@modelmesh/core";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Configure two embedding providers
  // -----------------------------------------------------------------------
  const config = new MeshConfig({
    providers: {
      // OpenAI offers text-embedding-3-small and text-embedding-3-large
      "openai.llm.v1": {
        enabled: true,
        api_key: "${secrets:OPENAI_API_KEY}",
      },
      // Cohere offers Embed v4 and Embed v3 (English/Multilingual)
      "cohere.nlp.v1": {
        enabled: true,
        api_key: "${secrets:COHERE_API_KEY}",
      },
    },

    // Explicit model definitions for embedding models. These supplement
    // auto-discovered models and ensure the pool has the right entries.
    models: {
      "text-embedding-3-small": {
        provider: "openai.llm.v1",
        capabilities: ["representation.embeddings.text-embeddings"],
        delivery: { synchronous: true },
        constraints: { contextWindow: 8191 },
      },
      "embed-v4": {
        provider: "cohere.nlp.v1",
        capabilities: ["representation.embeddings.text-embeddings"],
        delivery: { synchronous: true },
        constraints: { contextWindow: 128000 },
      },
    },

    pools: {
      "text-embeddings": {
        capability: "representation.embeddings.text-embeddings",
        strategy: "modelmesh.stick-until-failure.v1",
        provider_priority: ["openai.llm.v1", "cohere.nlp.v1"],

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
          initial_delay: "300ms",
          retryable_codes: [429, 500, 502, 503],
          scope: "same_provider",
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
  console.log("ModelMesh initialized with OpenAI + Cohere embedding providers.\n");

  const client = mesh.getClient();

  // -----------------------------------------------------------------------
  // 3. Generate embeddings for a single text
  // -----------------------------------------------------------------------
  console.log("--- Single Text Embedding ---");
  const singleResult = await client.embeddings.create({
    model: "text-embeddings",
    input: "ModelMesh Lite provides capability-driven AI routing.",
  });

  console.log(`Model used    : ${singleResult.model}`);
  console.log(`Tokens used   : ${singleResult.usage.totalTokens}`);
  console.log(`Choices       : ${singleResult.choices.length}`);

  // -----------------------------------------------------------------------
  // 4. Generate embeddings for a batch of texts
  // -----------------------------------------------------------------------
  console.log("\n--- Batch Text Embeddings ---");
  const texts = [
    "Automatic failover between providers.",
    "Free-tier quota aggregation across multiple services.",
    "Capability-based model pools with rotation policies.",
    "OpenAI-compatible drop-in replacement interface.",
  ];

  const batchResult = await client.embeddings.create({
    model: "text-embeddings",
    input: texts,
  });

  console.log(`Model used : ${batchResult.model}`);
  console.log(`Texts count: ${texts.length}`);
  console.log(`Tokens used: ${batchResult.usage.totalTokens}`);

  // -----------------------------------------------------------------------
  // 5. Shut down
  // -----------------------------------------------------------------------
  mesh.shutdown();
  console.log("\nModelMesh shut down.");
}

main().catch(console.error);
