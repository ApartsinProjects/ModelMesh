/**
 * 08 - Budget and Usage Tracking
 * ===============================
 *
 * Shows how to monitor costs, token usage, and budget status using the
 * UsageTracker facade. The tracker is available on every MeshClient
 * via the `client.usage` property.
 *
 * This sample uses the mock testing client for demonstration.
 */

import { mockClient } from '@nistrapa/modelmesh-core/testing';

async function main(): Promise<void> {
  // Create a mock client with some responses
  const client = mockClient({
    responses: [
      { content: 'Hello!', tokens: 50 },
      { content: 'World!', tokens: 30 },
    ],
  });

  // Make some requests
  await client.chat.completions.create({
    model: 'chat-pool',
    messages: [{ role: 'user', content: 'Hello' }],
  });
  await client.chat.completions.create({
    model: 'chat-pool',
    messages: [{ role: 'user', content: 'World' }],
  });

  console.log(`Total calls: ${client.calls.length}`);
  console.log(`Call 1 tokens: ${client.calls[0].response.usage.totalTokens}`);
  console.log(`Call 2 tokens: ${client.calls[1].response.usage.totalTokens}`);

  // --- Real client usage ---
  console.log('\n--- Real client usage pattern ---');
  console.log(`
  // With a real ModelMesh client:
  //
  //   import { create } from '@nistrapa/modelmesh-core';
  //
  //   const client = create('chat');
  //   // ... make requests ...
  //
  //   console.log('Total cost:', client.usage.totalCost);
  //   console.log('Daily cost:', client.usage.dailyCost);
  //   console.log('Monthly cost:', client.usage.monthlyCost);
  //   console.log('Total tokens:', client.usage.totalTokens);
  //
  //   // Budget status
  //   const status = client.usage.budgetStatus;
  //   if (status?.exceeded) {
  //     console.log('Budget exceeded!');
  //   }
  //
  //   // Reset counters
  //   client.usage.reset();
  `);
}

main();
