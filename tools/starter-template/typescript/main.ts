/**
 * ModelMesh starter project — TypeScript.
 */

import { create } from "@nistrapa/modelmesh-core";

async function main() {
  // Create a client with chat completion capability
  const client = create("chat-completion");

  // Show available providers
  console.log(client.describe());
  console.log();

  // Send a request
  const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Hello! What can you help me with?" }],
  });
  console.log(response.choices[0].message.content);
}

main().catch(console.error);
