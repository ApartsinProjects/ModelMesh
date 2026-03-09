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

import ModelMesh from "modelmesh";

// Create a client for the "text-embeddings" capability.
const client = ModelMesh.create("text-embeddings");

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

  // response.data is a list of embedding objects; we want the first one.
  const vector = response.data[0].embedding;
  console.log(`Dimensions : ${vector.length}`);
  console.log(`First 5    : [${vector.slice(0, 5).join(", ")}]`);
  console.log(`Model used : ${response.model}`);

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
  console.log(`Vectors    : ${batchResponse.data.length}`);

  // Show the dimension of each returned vector.
  for (let i = 0; i < batchResponse.data.length; i++) {
    const dims = batchResponse.data[i].embedding.length;
    const preview = texts[i].substring(0, 40);
    console.log(`  [${i}] ${dims} dimensions  —  "${preview}..."`);
  }
}

main();
