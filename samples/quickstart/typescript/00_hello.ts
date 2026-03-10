/**
 * 00 - Hello World Chat Completion
 * =================================
 *
 * Simplest possible ModelMesh Lite usage: specify a capability, get an
 * OpenAI-compatible client, make a chat completion call.
 *
 * This sample is nearly identical to using the OpenAI SDK directly.
 * The only differences: the import, the create() call, and the model parameter.
 *
 * Prerequisites:
 *   - Set at least one provider API key (e.g., OPENAI_API_KEY).
 */

import { create, CompletionResponse } from "@modelmesh/core";

// Create a client for the "chat-completion" capability.
// Providers are auto-detected from environment variables.
const client = create("chat-completion");

async function main(): Promise<void> {
  // Standard OpenAI-compatible call — virtual model name = capability name.
  const response = (await client.chat.completions.create({
    model: "chat-completion",
    messages: [
      { role: "user", content: "Explain what an API is in two sentences." },
    ],
  })) as CompletionResponse;

  console.log(response.choices[0].message?.content);
}

main();
