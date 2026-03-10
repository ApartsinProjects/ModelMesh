/**
 * 01 - Basic Chat Completion
 *
 * Simplest possible ModelMesh Lite setup: a single OpenAI provider, one model,
 * and a chat completion request. This sample demonstrates:
 *
 *   - Initializing ModelMesh from an inline configuration object
 *   - Obtaining the OpenAI-compatible client
 *   - Making a chat completion call using a virtual model name
 *   - Printing the response
 *
 * The virtual model name "text-generation" maps to the predefined capability
 * pool. ModelMesh resolves it to the best active real model (here, the only
 * configured model from OpenAI) and routes the request transparently.
 *
 * Prerequisites:
 *   - Set the OPENAI_API_KEY environment variable
 */

import { ModelMesh, MeshConfig, CompletionResponse } from "@nistrapa/modelmesh-core";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Define inline configuration
  // -----------------------------------------------------------------------
  // Secrets are read from environment variables by default
  // (secret-store.modelmesh.env.v1). The provider connector ID follows the
  // naming convention: vendor.service.version (the "provider." prefix is
  // omitted inside the providers section).
  const config = new MeshConfig({
    providers: {
      "openai.llm.v1": {
        enabled: true,
        api_key: "${secrets:OPENAI_API_KEY}",
      },
    },
    // No explicit pool configuration needed -- the predefined
    // "text-generation" pool automatically includes all models registered
    // at the generation.text-generation capability node or its descendants.
    // The default selection strategy is stick-until-failure.
  });

  // -----------------------------------------------------------------------
  // 2. Initialize ModelMesh
  // -----------------------------------------------------------------------
  const mesh = new ModelMesh();
  mesh.initialize(config);
  console.log("ModelMesh initialized with OpenAI provider.");

  // -----------------------------------------------------------------------
  // 3. Get the OpenAI-compatible client
  // -----------------------------------------------------------------------
  // The client exposes the same interface as the official OpenAI SDK.
  // Applications use it as a drop-in replacement.
  const client = mesh.getClient();

  // -----------------------------------------------------------------------
  // 4. Make a chat completion request
  // -----------------------------------------------------------------------
  // The model parameter is a *virtual model name* that maps to a capability
  // pool. "text-generation" resolves to the best active model in the
  // text-generation pool (in this case, a GPT model from OpenAI).
  console.log("Sending chat completion request...");

  const response = (await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "Explain what ModelMesh Lite does in one sentence." },
    ],
    temperature: 0.7,
    maxTokens: 150,
  })) as CompletionResponse;

  // -----------------------------------------------------------------------
  // 5. Print the response
  // -----------------------------------------------------------------------
  console.log("\n--- Response ---");
  console.log(`Model used : ${response.model}`);
  console.log(`Response ID: ${response.id}`);
  console.log(`Content    : ${response.choices[0].message?.content}`);
  console.log(`Tokens     : prompt=${response.usage.promptTokens}, completion=${response.usage.completionTokens}`);

  // -----------------------------------------------------------------------
  // 6. Shut down gracefully
  // -----------------------------------------------------------------------
  mesh.shutdown();
  console.log("\nModelMesh shut down.");
}

main().catch(console.error);
