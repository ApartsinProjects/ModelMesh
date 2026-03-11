/**
 * 11 - Routing Explanation & Debug
 * =================================
 *
 * Shows how to use the `explain()` method to understand routing
 * decisions without making actual API calls. Useful for debugging
 * why a specific model was selected, inspecting pool candidates,
 * and understanding rotation strategies.
 */

import { mockClient } from '@nistrapa/modelmesh-core/testing';

function main(): void {
  const client = mockClient({
    responses: [{ content: 'Hello!', model: 'gpt-4o', tokens: 25 }],
  });

  // 1. Explain routing for a model/pool
  console.log('=== Routing Explanation ===');
  const explanation = client.explain();

  console.log(`  Pool:           ${explanation.poolName}`);
  console.log(`  Strategy:       ${explanation.strategy}`);
  console.log(`  Capability:     ${explanation.capability}`);
  console.log(`  Selected Model: ${explanation.selectedModel}`);
  console.log(`  Reason:         ${explanation.reason}`);

  // 2. Inspect candidates
  console.log('\n=== Candidates ===');
  const candidates = explanation.candidates as any[];
  for (const candidate of candidates) {
    console.log(
      `  Model: ${String(candidate.modelId).padEnd(20)} ` +
        `Provider: ${String(candidate.providerId).padEnd(20)} ` +
        `Status: ${candidate.status}`
    );
  }

  // 3. Pool status
  console.log('\n=== Pool Status ===');
  const status = client.poolStatus();
  console.log(JSON.stringify(status, null, 2));

  // 4. Active providers
  console.log('\n=== Active Providers ===');
  const providers = client.activeProviders();
  for (const p of providers) {
    console.log(`  ${p}`);
  }

  // 5. Describe (human-readable)
  console.log('\n=== Describe ===');
  console.log(client.describe());
}

main();
