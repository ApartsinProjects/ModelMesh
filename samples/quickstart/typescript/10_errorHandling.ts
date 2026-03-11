/**
 * 10 - Error Handling Patterns
 * =============================
 *
 * Shows how to handle different error types with ModelMesh's structured
 * exception hierarchy. Each exception carries metadata like providerId,
 * retry hints, and budget details.
 */

import {
  ModelMeshError,
  RoutingError,
  NoActiveModelError,
  AllProvidersExhaustedError,
  ProviderError,
  AuthenticationError,
  RateLimitError,
  ProviderTimeoutError,
  ConfigurationError,
  BudgetExceededError,
} from '@nistrapa/modelmesh-core';
import { mockClient } from '@nistrapa/modelmesh-core/testing';

function demoBasicErrorHandling(): void {
  console.log('=== Basic Error Handling ===');

  const client = mockClient({
    responses: [{ content: 'Success!', tokens: 20 }],
  });

  client.chat.completions
    .create({
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
    })
    .then((response) => {
      console.log(`  Response: ${response.choices[0].message?.content}`);
    })
    .catch((e) => {
      if (e instanceof ModelMeshError) {
        console.log(`  Error: ${e.message}`);
      }
    });
}

function demoExceptionHierarchy(): void {
  console.log('\n=== Exception Hierarchy ===');

  const errors: ModelMeshError[] = [
    new NoActiveModelError("No models in pool 'chat'", { poolName: 'chat' }),
    new AllProvidersExhaustedError('3 attempts failed', {
      poolName: 'chat',
      attempts: 3,
      lastError: new Error('Connection timed out'),
    }),
    new AuthenticationError('Invalid API key', { providerId: 'openai' }),
    new RateLimitError('Rate limited', { providerId: 'anthropic', retryAfter: 30 }),
    new ProviderTimeoutError('Timed out', { timeoutSeconds: 60 }),
    new ConfigurationError('Missing provider config'),
    new BudgetExceededError('Daily limit exceeded', {
      limitType: 'daily',
      limitValue: 10.0,
      actualValue: 12.5,
    }),
  ];

  for (const err of errors) {
    const hint = err.retryable ? 'retryable' : 'permanent';
    console.log(`  ${err.name.padEnd(35)} [${hint}] ${err.message}`);
  }
}

function demoGranularCatching(): void {
  console.log('\n=== Granular Catching ===');

  const scenarios: [string, ModelMeshError][] = [
    ['Rate limit', new RateLimitError('Too many requests', { providerId: 'openai', retryAfter: 5 })],
    ['Auth failure', new AuthenticationError('Bad key', { providerId: 'anthropic' })],
    ['No models', new NoActiveModelError('Pool empty', { poolName: 'embeddings' })],
    ['All exhausted', new AllProvidersExhaustedError('Failed', { attempts: 3 })],
    ['Over budget', new BudgetExceededError('Over limit', { limitType: 'daily', limitValue: 10.0 })],
  ];

  for (const [name, error] of scenarios) {
    console.log(`\n  Scenario: ${name}`);
    try {
      throw error;
    } catch (e) {
      if (e instanceof RateLimitError) {
        console.log(`    → Rate limited by ${e.providerId}, retry in ${e.retryAfter}s`);
      } else if (e instanceof AuthenticationError) {
        console.log(`    → Auth failed for ${e.providerId} — check credentials`);
      } else if (e instanceof NoActiveModelError) {
        console.log(`    → No models in pool '${e.poolName}' — wait and retry`);
      } else if (e instanceof AllProvidersExhaustedError) {
        console.log(`    → All ${e.attempts} attempts failed`);
      } else if (e instanceof BudgetExceededError) {
        console.log(`    → ${e.limitType} budget exceeded: $${e.limitValue}`);
      } else if (e instanceof ModelMeshError) {
        console.log(`    → Generic error: ${(e as Error).message}`);
      }
    }
  }
}

function demoRetryableCheck(): void {
  console.log('\n=== Retryable Check ===');

  const errors: ModelMeshError[] = [
    new NoActiveModelError('Pool empty'),
    new RateLimitError('Rate limited', { retryAfter: 10 }),
    new ProviderTimeoutError('Timeout', { timeoutSeconds: 30 }),
    new AuthenticationError('Bad key'),
    new AllProvidersExhaustedError('Exhausted'),
    new BudgetExceededError('Over budget'),
  ];

  for (const err of errors) {
    const action = err.retryable ? 'RETRY' : 'FAIL';
    console.log(`  ${err.name.padEnd(35)} → ${action}`);
  }
}

demoBasicErrorHandling();
demoExceptionHierarchy();
demoGranularCatching();
demoRetryableCheck();
console.log('\nDone!');
