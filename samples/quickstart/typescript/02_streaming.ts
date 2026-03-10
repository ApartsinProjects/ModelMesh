/**
 * 02 - Streaming Chat Completion
 * ===============================
 *
 * Stream a chat completion response token-by-token.  The setup is the same
 * as 00_hello.ts; the only addition is `stream: true` and iterating over
 * the returned chunks.
 *
 * This sample demonstrates:
 *   - Enabling streaming with the stream: true parameter
 *   - Iterating over response chunks with for-await-of
 *   - Accessing incremental content via chunk.choices[0].delta.content
 *   - Printing tokens as they arrive for a responsive user experience
 *
 * Prerequisites:
 *   - Set at least one provider API key (e.g., OPENAI_API_KEY).
 */

import { create, CompletionResponse } from "@nistrapa/modelmesh-core";

// Same one-liner setup as the hello-world sample.
const client = create("chat-completion");

async function main(): Promise<void> {
  process.stdout.write("User: Write a haiku about distributed systems.\n\n");
  process.stdout.write("Assistant: ");

  // Pass stream: true to get an async iterable of chunks instead of a single response.
  const stream = (await client.chat.completions.create({
    model: "chat-completion",
    messages: [
      { role: "user", content: "Write a haiku about distributed systems." },
    ],
    stream: true,
  })) as AsyncIterableIterator<CompletionResponse>;

  // Each chunk mirrors the OpenAI streaming format.
  // chunk.choices[0].delta.content holds the next piece of text (or null/undefined).
  for await (const chunk of stream) {
    const token = chunk.choices[0].delta?.content;
    if (token != null) {
      process.stdout.write(token);
    }
  }

  // Print a final newline after the stream is complete.
  process.stdout.write("\n");
}

main();
