/**
 * 06 - Middleware: Request/Response Logging
 * ==========================================
 *
 * Shows how to add a logging middleware that prints every request and
 * response flowing through ModelMesh. Middleware can also transform
 * requests, enrich responses, or provide error fallbacks.
 *
 * This sample uses the mock testing client so it runs without API keys.
 */

import { Middleware, MiddlewareStack } from '@nistrapa/modelmesh-core';
import type { MiddlewareContext } from '@nistrapa/modelmesh-core';
import type {
  CompletionRequest,
  CompletionResponse,
} from '@nistrapa/modelmesh-core';
import { mockClient, MockResponse } from '@nistrapa/modelmesh-core/testing';

// ---------------------------------------------------------------------------
// 1. Define a middleware by extending Middleware
// ---------------------------------------------------------------------------

class LoggingMiddleware extends Middleware {
  async beforeRequest(
    request: CompletionRequest,
    context: MiddlewareContext
  ): Promise<CompletionRequest> {
    console.log(`[LOG] >>> Sending request to ${context.modelId}`);
    console.log(`         Provider: ${context.providerId}`);
    console.log(`         Pool:     ${context.poolName}`);
    console.log(`         Attempt:  ${context.attempt}`);
    return request; // pass through unchanged
  }

  async afterResponse(
    response: CompletionResponse,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    const tokens = response.usage?.totalTokens ?? 0;
    console.log(`[LOG] <<< Response from ${context.modelId}: ${tokens} tokens`);
    return response;
  }

  async onError(
    error: Error,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    console.log(`[LOG] !!! Error from ${context.modelId}: ${error.message}`);
    throw error; // re-raise so the router can retry
  }
}

// ---------------------------------------------------------------------------
// 2. Use the mock client for demonstration
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const client = mockClient({
    responses: [
      { content: 'Hello from middleware demo!', model: 'gpt-4o', tokens: 25 },
      { content: 'Second response.', model: 'claude-3', tokens: 15 },
    ],
  });

  const response = await client.chat.completions.create({
    model: 'chat-pool',
    messages: [{ role: 'user', content: 'Hi!' }],
  });

  console.log(`\nAssistant: ${response.choices[0].message?.content}`);
  console.log(`Total calls recorded: ${client.calls.length}`);

  // ---------------------------------------------------------------------------
  // 3. Real client usage pattern
  // ---------------------------------------------------------------------------
  console.log('\n--- Real client usage ---');
  console.log(`
  // With a real ModelMesh client:
  //
  //   import { create, Middleware } from '@nistrapa/modelmesh-core';
  //
  //   const client = create('chat', {
  //     middleware: [new LoggingMiddleware()],
  //   });
  //
  //   const response = await client.chat.completions.create({
  //     model: 'chat-completion',
  //     messages: [{ role: 'user', content: 'Hello' }],
  //   });
  `);
}

main();
