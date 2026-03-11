/**
 * 07 - Testing with Mock Client
 * ==============================
 *
 * Shows how to use `mockClient()` for unit testing without live APIs.
 * The mock client behaves identically to the real MeshClient — same
 * `client.chat.completions.create()` interface — but returns
 * pre-configured responses and records all calls for assertion.
 */

import { mockClient } from '@nistrapa/modelmesh-core/testing';
import type { MockResponse } from '@nistrapa/modelmesh-core/testing';

async function testBasicResponse(): Promise<void> {
  const client = mockClient({
    responses: [{ content: 'Hello!', model: 'gpt-4o', tokens: 10 }],
  });

  const response = await client.chat.completions.create({
    model: 'text-generation',
    messages: [{ role: 'user', content: 'Hi' }],
  });

  console.assert(response.choices[0].message?.content === 'Hello!');
  console.assert(response.model === 'gpt-4o');
  console.assert(response.usage.totalTokens === 10);
  console.log('✓ Basic response works');
}

async function testCallInspection(): Promise<void> {
  const client = mockClient({ responses: [{ content: 'OK' }] });

  await client.chat.completions.create({
    model: 'my-pool',
    messages: [
      { role: 'system', content: 'You are helpful.' },
      { role: 'user', content: 'Summarize this.' },
    ],
  });

  console.assert(client.calls.length === 1);
  console.assert(client.calls[0].model === 'my-pool');
  console.assert(client.calls[0].messages.length === 2);
  console.log('✓ Call inspection works');
}

async function testMultipleResponses(): Promise<void> {
  const client = mockClient({
    responses: [
      { content: 'First' },
      { content: 'Second' },
      { content: 'Third' },
    ],
  });

  const r1 = await client.chat.completions.create({ model: 'test', messages: [] });
  const r2 = await client.chat.completions.create({ model: 'test', messages: [] });
  const r3 = await client.chat.completions.create({ model: 'test', messages: [] });

  console.assert(r1.choices[0].message?.content === 'First');
  console.assert(r2.choices[0].message?.content === 'Second');
  console.assert(r3.choices[0].message?.content === 'Third');
  console.log('✓ Multiple responses cycle correctly');
}

async function testExplainAndStatus(): Promise<void> {
  const client = mockClient();

  const explanation = client.explain();
  console.assert(explanation.poolName !== undefined);
  console.assert(explanation.selectedModel !== undefined);

  const status = client.poolStatus();
  console.assert(status['mock-pool'] !== undefined);
  console.log('✓ Explain and poolStatus work');
}

// ---------------------------------------------------------------------------
// Run all tests
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  await testBasicResponse();
  await testCallInspection();
  await testMultipleResponses();
  await testExplainAndStatus();
  console.log('\nAll tests passed!');
}

main();
