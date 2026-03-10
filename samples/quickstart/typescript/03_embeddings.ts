/**
 * 03 - Text Embeddings
 * =====================
 *
 * Generate text embeddings through ModelMesh Lite.  Embeddings turn text into
 * numerical vectors that capture semantic meaning, useful for search, clustering,
 * and similarity comparisons.
 *
 * This sample demonstrates:
 *   - Creating a client for the "text-embeddings" capability
 *   - Embedding a single string
 *   - Inspecting the embedding vector and its dimensions
 *   - Embedding a batch of strings in one call
 *
 * Prerequisites:
 *   - Set at least one provider API key that supports embeddings
 *     (e.g., OPENAI_API_KEY).
 */

import { create } from "@nistrapa/modelmesh-core";

// Create a client for the "text-embeddings" capability.
const client = create("text-embeddings");

async function main(): Promise<void> {
  // ---------------------------------------------------------------------------
  // Single embedding
  // ---------------------------------------------------------------------------
  console.log("=".repeat(50));
  console.log("Single Embedding");
  console.log("=".repeat(50));

  const response = await client.embeddings.create({
    model: "text-embeddings",
    input: "Artificial intelligence is transforming software engineering.",
  });

  // The embeddings response uses the CompletionResponse shape.
  // Access model and usage directly.
  console.log(`Model used : ${response.model}`);
  console.log(`Tokens     : ${response.usage.totalTokens}`);
  console.log(`Choices    : ${response.choices.length}`);

  // ---------------------------------------------------------------------------
  // Batch embeddings
  // ---------------------------------------------------------------------------
  console.log("\n" + "=".repeat(50));
  console.log("Batch Embeddings");
  console.log("=".repeat(50));

  const texts = [
    "The quick brown fox jumps over the lazy dog.",
    "A fast auburn fox leaps above a sleepy hound.",
    "Quantum computing leverages superposition and entanglement.",
  ];

  const batchResponse = await client.embeddings.create({
    model: "text-embeddings",
    input: texts,
  });

  console.log(`Texts sent : ${texts.length}`);
  console.log(`Model used : ${batchResponse.model}`);
  console.log(`Tokens     : ${batchResponse.usage.totalTokens}`);
}

main();
