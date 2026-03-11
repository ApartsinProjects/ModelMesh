/**
 * Tests for the enhanced MockClient and MockResponse testing utilities.
 */
import { MockClient, MockResponse, mockClient } from '@/testing';

// ---------------------------------------------------------------------------
// Enhanced MockClient
// ---------------------------------------------------------------------------

describe('Enhanced MockClient', () => {
  test('MockResponse with error throws', async () => {
    const client = mockClient({
      responses: [
        { error: new Error('API rate limit exceeded') },
      ],
    });

    await expect(
      client.chat.completions.create({
        model: 'test-pool',
        messages: [{ role: 'user', content: 'Hi' }],
      })
    ).rejects.toThrow('API rate limit exceeded');
  });

  test('MockResponse with delay adds latency', async () => {
    jest.useFakeTimers();

    const client = mockClient({
      responses: [{ content: 'Delayed response', delay: 1 }],
    });

    const promise = client.chat.completions.create({
      model: 'test-pool',
      messages: [{ role: 'user', content: 'Hi' }],
    });

    // Advance past the delay
    jest.advanceTimersByTime(1100);

    const resp = await promise;
    expect(resp.choices[0].message?.content).toBe('Delayed response');

    jest.useRealTimers();
  });

  test('error after success sequence works', async () => {
    const client = mockClient({
      responses: [
        { content: 'First OK' },
        { error: new Error('Second fails') },
      ],
    });

    // First call succeeds
    const resp1 = await client.chat.completions.create({
      model: 'test-pool',
      messages: [{ role: 'user', content: 'Hello' }],
    });
    expect(resp1.choices[0].message?.content).toBe('First OK');

    // Second call throws
    await expect(
      client.chat.completions.create({
        model: 'test-pool',
        messages: [{ role: 'user', content: 'Again' }],
      })
    ).rejects.toThrow('Second fails');
  });

  test('error with delay is delayed', async () => {
    jest.useFakeTimers();

    const client = mockClient({
      responses: [{ error: new Error('Timeout error'), delay: 2 }],
    });

    const promise = client.chat.completions.create({
      model: 'test-pool',
      messages: [{ role: 'user', content: 'Hi' }],
    });

    jest.advanceTimersByTime(2100);

    await expect(promise).rejects.toThrow('Timeout error');

    jest.useRealTimers();
  });

  test('failureRate=0 never fails', async () => {
    const client = mockClient({
      responses: [{ content: 'OK' }],
      failureRate: 0,
    });

    // Run multiple calls -- none should fail from chaos
    for (let i = 0; i < 20; i++) {
      const resp = await client.chat.completions.create({
        model: 'test-pool',
        messages: [{ role: 'user', content: 'Hi' }],
      });
      expect(resp.choices[0].message?.content).toBe('OK');
    }
  });

  test('failureRate=1 always fails', async () => {
    const client = mockClient({
      responses: [{ content: 'Should not see this' }],
      failureRate: 1.0,
    });

    await expect(
      client.chat.completions.create({
        model: 'test-pool',
        messages: [{ role: 'user', content: 'Hi' }],
      })
    ).rejects.toThrow('Simulated random failure');
  });

  // -- Backward compatibility ------------------------------------------------

  test('basic response still works', async () => {
    const client = mockClient({
      responses: [{ content: 'Hello from mock' }],
    });

    const resp = await client.chat.completions.create({
      model: 'test-pool',
      messages: [{ role: 'user', content: 'Hi' }],
    });

    expect(resp.choices[0].message?.content).toBe('Hello from mock');
    expect(resp.object).toBe('chat.completion');
    expect(client.calls.length).toBe(1);
    expect(client.calls[0].model).toBe('test-pool');
  });

  test('multiple response sequence still works', async () => {
    const client = mockClient({
      responses: [
        { content: 'First' },
        { content: 'Second' },
        { content: 'Third' },
      ],
    });

    const r1 = await client.chat.completions.create({
      model: 'test',
      messages: [{ role: 'user', content: '1' }],
    });
    const r2 = await client.chat.completions.create({
      model: 'test',
      messages: [{ role: 'user', content: '2' }],
    });
    const r3 = await client.chat.completions.create({
      model: 'test',
      messages: [{ role: 'user', content: '3' }],
    });

    expect(r1.choices[0].message?.content).toBe('First');
    expect(r2.choices[0].message?.content).toBe('Second');
    expect(r3.choices[0].message?.content).toBe('Third');
    expect(client.calls.length).toBe(3);
  });

  test('default MockResponse returns "Mock response"', async () => {
    const client = mockClient(); // no responses specified

    const resp = await client.chat.completions.create({
      model: 'test',
      messages: [{ role: 'user', content: 'Hi' }],
    });

    expect(resp.choices[0].message?.content).toBe('Mock response');
  });

  test('MockResponse with model sets model field', async () => {
    const client = mockClient({
      responses: [{ content: 'Hello', model: 'claude-3-opus' }],
    });

    const resp = await client.chat.completions.create({
      model: 'test',
      messages: [{ role: 'user', content: 'Hi' }],
    });

    expect(resp.model).toBe('claude-3-opus');
  });

  test('MockResponse with tokens sets usage', async () => {
    const client = mockClient({
      responses: [{ content: 'Hello', tokens: 30 }],
    });

    const resp = await client.chat.completions.create({
      model: 'test',
      messages: [{ role: 'user', content: 'Hi' }],
    });

    expect(resp.usage).toBeDefined();
    expect(resp.usage!.totalTokens).toBe(30);
    expect(resp.usage!.promptTokens).toBe(10); // floor(30/3)
    expect(resp.usage!.completionTokens).toBe(20); // 30 - 10
  });

  test('MockClient provides helper methods', () => {
    const client = new MockClient();

    // poolStatus
    const status = client.poolStatus();
    expect(status['mock-pool']).toBeDefined();

    // activeProviders
    const providers = client.activeProviders();
    expect(providers).toContain('mock-provider');

    // describe
    const desc = client.describe();
    expect(desc).toContain('mock-pool');

    // explain
    const explanation = client.explain();
    expect(explanation.poolName).toBe('mock-pool');
    expect(explanation.strategy).toBe('mock');

    // models
    const models = client.models.list();
    expect(models.object).toBe('list');

    // close
    expect(() => client.close()).not.toThrow();
  });

  test('calls record includes kwargs', async () => {
    const client = mockClient({
      responses: [{ content: 'OK' }],
    });

    await client.chat.completions.create({
      model: 'test',
      messages: [{ role: 'user', content: 'Hi' }],
      temperature: 0.7,
      max_tokens: 100,
    });

    expect(client.calls[0].kwargs).toEqual({
      temperature: 0.7,
      max_tokens: 100,
    });
  });

  test('exhausted responses repeat last response', async () => {
    const client = mockClient({
      responses: [
        { content: 'First' },
        { content: 'Last' },
      ],
    });

    await client.chat.completions.create({ model: 'test', messages: [] });
    await client.chat.completions.create({ model: 'test', messages: [] });
    const r3 = await client.chat.completions.create({ model: 'test', messages: [] });

    // After exhausting the list, the last response should repeat
    expect(r3.choices[0].message?.content).toBe('Last');
  });
});
