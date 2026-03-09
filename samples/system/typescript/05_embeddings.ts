/**
 * 05 - Text Embeddings with Failover
 *
 * Generates text embeddings using OpenAI and Cohere as providers, with
 * automatic failover between them. This sample demonstrates:
 *
 *   - Using the embeddings API through the OpenAI-compatible client
 *   - Configuring providers that support the text-embeddings capability
 *   - Routing embedding requests through the same pool/failover system
 *   - Comparing embedding dimensions across providers
 *
 * The "text-embeddings" virtual model name maps to the predefined
 * representation.embeddings.text-embeddings capability pool. Any provider with models
 * registered at that capability leaf is eligible for selection.
 *
 * Prerequisites:
 *   - Set OPENAI_API_KEY and COHERE_API_KEY environment variables
 */

import { ModelMesh, MeshConfig } from "modelmesh-lite";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Configure two embedding providers
  // -----------------------------------------------------------------------
  const config: MeshConfig = {
    raw: {
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
          constraints: { context_window: 8191 },
        },
        "embed-v4": {
          provider: "cohere.nlp.v1",
          capabilities: ["representation.embeddings.text-embeddings"],
          delivery: { synchronous: true },
          constraints: { context_window: 128000 },
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
    },
  };

  // -----------------------------------------------------------------------
  // 2. Initialize
  // -----------------------------------------------------------------------
  const mesh = new ModelMesh();
  await mesh.initialize(config);
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
  console.log(`Dimensions    : ${(singleResult.data[0] as any).embedding.length}`);
  console.log(`Tokens used   : ${singleResult.usage.total_tokens}`);
  console.log(`First 5 values: [${(singleResult.data[0] as any).embedding.slice(0, 5).join(", ")}]`);

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
  console.log(`Tokens used: ${batchResult.usage.total_tokens}`);

  for (let i = 0; i < texts.length; i++) {
    const embedding = (batchResult.data[i] as any).embedding;
    console.log(`  [${i}] "${texts[i].substring(0, 40)}..." -> ${embedding.length} dims`);
  }

  // -----------------------------------------------------------------------
  // 5. Demonstrate cosine similarity (application-level usage)
  // -----------------------------------------------------------------------
  console.log("\n--- Cosine Similarity ---");
  const embA = (batchResult.data[0] as any).embedding as number[];
  const embB = (batchResult.data[1] as any).embedding as number[];
  const embC = (batchResult.data[2] as any).embedding as number[];

  console.log(`Similarity(0, 1): ${cosineSimilarity(embA, embB).toFixed(4)}`);
  console.log(`Similarity(0, 2): ${cosineSimilarity(embA, embC).toFixed(4)}`);
  console.log(`Similarity(1, 2): ${cosineSimilarity(embB, embC).toFixed(4)}`);

  // -----------------------------------------------------------------------
  // 6. Shut down
  // -----------------------------------------------------------------------
  await mesh.shutdown();
  console.log("\nModelMesh shut down.");
}

/** Compute cosine similarity between two vectors. */
function cosineSimilarity(a: number[], b: number[]): number {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

main().catch(console.error);
