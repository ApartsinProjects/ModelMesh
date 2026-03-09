/**
 * 04 - Streaming Chat Completion
 *
 * Demonstrates streaming responses with failover between OpenAI and Google
 * Gemini providers. This sample shows:
 *
 *   - Using the OpenAI client with stream=true for incremental output
 *   - Iterating over response chunks as they arrive
 *   - Automatic fallback to the next provider when a stream errors mid-flight
 *   - Delivery mode filtering (only stream-capable models are selected)
 *
 * Streaming is a delivery mode orthogonal to capabilities. When stream=true
 * is set, the routing pipeline filters for models that support streaming
 * delivery before applying the selection strategy.
 *
 * Prerequisites:
 *   - Set OPENAI_API_KEY and GOOGLE_API_KEY environment variables
 */

import { ModelMesh, MeshConfig } from "modelmesh-lite";

async function main(): Promise<void> {
  // -----------------------------------------------------------------------
  // 1. Configure two streaming-capable providers
  // -----------------------------------------------------------------------
  const config: MeshConfig = {
    raw: {
      providers: {
        "openai.llm.v1": {
          enabled: true,
          api_key: "${secrets:OPENAI_API_KEY}",
        },
        "google.gemini.v1": {
          enabled: true,
          api_key: "${secrets:GOOGLE_API_KEY}",
        },
      },

      pools: {
        "text-generation": {
          strategy: "modelmesh.stick-until-failure.v1",
          provider_priority: ["openai.llm.v1", "google.gemini.v1"],

          deactivation: {
            retry_limit: 2,
            error_codes: [429, 500, 502, 503],
          },
          recovery: {
            cooldown: "30s",
          },
          retry: {
            max_attempts: 1,
            backoff: "fixed",
            initial_delay: "500ms",
            retryable_codes: [429, 500, 502, 503],
            scope: "any",
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
  console.log("ModelMesh initialized with OpenAI + Gemini (streaming mode).\n");

  const client = mesh.getClient();

  // -----------------------------------------------------------------------
  // 3. Streaming chat completion
  // -----------------------------------------------------------------------
  console.log("--- Streaming Response ---");
  console.log("Prompt: Write a short story about a robot learning to paint.\n");

  // When stream=true, the client returns an AsyncIterable of chunks.
  // Each chunk contains incremental content from the selected model.
  const stream = await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "system", content: "You are a creative storyteller." },
      { role: "user", content: "Write a short story about a robot learning to paint. Keep it under 200 words." },
    ],
    temperature: 0.8,
    max_tokens: 300,
    stream: true,
  });

  // The stream object is an AsyncIterable. If the underlying provider
  // errors mid-stream, ModelMesh transparently retries or rotates to
  // the fallback provider and continues streaming.
  let fullContent = "";
  let chunkCount = 0;

  for await (const chunk of stream as AsyncIterable<any>) {
    const delta = chunk.choices?.[0]?.delta?.content ?? "";
    if (delta) {
      process.stdout.write(delta);
      fullContent += delta;
      chunkCount++;
    }
  }

  console.log("\n\n--- Stream Complete ---");
  console.log(`Total chunks received: ${chunkCount}`);
  console.log(`Total characters: ${fullContent.length}`);

  // -----------------------------------------------------------------------
  // 4. Second streaming request (demonstrates continued routing)
  // -----------------------------------------------------------------------
  console.log("\n--- Second Streaming Request ---");
  console.log("Prompt: Continue the story.\n");

  const stream2 = await client.chat.completions.create({
    model: "text-generation",
    messages: [
      { role: "system", content: "You are a creative storyteller." },
      { role: "user", content: "Write a short story about a robot learning to paint." },
      { role: "assistant", content: fullContent },
      { role: "user", content: "Continue the story in 100 words." },
    ],
    temperature: 0.8,
    max_tokens: 200,
    stream: true,
  });

  for await (const chunk of stream2 as AsyncIterable<any>) {
    const delta = chunk.choices?.[0]?.delta?.content ?? "";
    if (delta) {
      process.stdout.write(delta);
    }
  }

  console.log("\n\n--- Done ---");

  // -----------------------------------------------------------------------
  // 5. Shut down
  // -----------------------------------------------------------------------
  await mesh.shutdown();
  console.log("ModelMesh shut down.");
}

main().catch(console.error);
