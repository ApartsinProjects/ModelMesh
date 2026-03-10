/**
 * 01 - Multi-Provider with Capabilities
 * ======================================
 *
 * Use multiple capabilities across multiple providers.  ModelMesh auto-detects
 * providers from environment variables and routes requests according to the
 * chosen strategy.
 *
 * This sample demonstrates:
 *   - Requesting multiple capabilities: generation.chat-completion and representation.text-embeddings
 *   - Restricting providers explicitly
 *   - Using the "cost-first" rotation strategy
 *   - Calling both chat and embeddings endpoints through the same client
 *   - Inspecting which model was used and token usage
 *
 * Prerequisites:
 *   - Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables.
 */

import { create, CompletionResponse } from "@modelmesh/core";

// Create a client with two capabilities across two providers.
// "cost-first" picks the cheapest available model for each request.
const client = create(
  "chat-completion",
  "text-embeddings",
  {
    providers: ["openai", "anthropic"],
    strategy: "cost-first",
  },
);

async function main(): Promise<void> {
  // ---------------------------------------------------------------------------
  // Chat completion
  // ---------------------------------------------------------------------------
  console.log("=".repeat(50));
  console.log("Chat Completion");
  console.log("=".repeat(50));

  const response = (await client.chat.completions.create({
    model: "chat-completion",
    messages: [
      { role: "system", content: "You are a concise assistant." },
      { role: "user", content: "What is the difference between TCP and UDP?" },
    ],
    maxTokens: 200,
  })) as CompletionResponse;

  console.log(`Model used  : ${response.model}`);
  console.log(`Prompt tkns : ${response.usage.promptTokens}`);
  console.log(`Compl. tkns : ${response.usage.completionTokens}`);
  console.log(`\nAssistant:\n${response.choices[0].message?.content}`);

  // ---------------------------------------------------------------------------
  // Text embeddings
  // ---------------------------------------------------------------------------
  console.log("\n" + "=".repeat(50));
  console.log("Text Embeddings");
  console.log("=".repeat(50));

  const embedResponse = await client.embeddings.create({
    model: "text-embeddings",
    input: "ModelMesh routes AI requests to the best provider.",
  });

  // The embeddings response uses the CompletionResponse shape; the raw
  // embedding data is provider-dependent.  Access the model and usage
  // fields directly.
  console.log(`Model used : ${embedResponse.model}`);
  console.log(`Usage      : ${embedResponse.usage.totalTokens} tokens`);
  console.log(`Response   : ${embedResponse.choices.length} choice(s)`);
}

main();
