# Async & Concurrency Guide

Use ModelMesh with async/await for concurrent requests, parallel processing, and high-throughput applications. This guide covers async client usage, parallel requests, connection pooling, rate limiting, streaming with async iterators, timeout handling, error handling in concurrent scenarios, and best practices. For streaming details, see the [Streaming Guide](StreamingGuide.md). For production deployment, see the [Production Guide](ProductionGuide.md).

## Async Client Usage

ModelMesh supports async context managers in Python. In TypeScript, all client methods are async by default.

### Python

```python
import asyncio
import modelmesh

async def main():
    async with modelmesh.create("chat-completion") as client:
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hello!"}],
        )
        print(response.choices[0].message.content)

asyncio.run(main())
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';

async function main() {
  const client = create('chat-completion');
  try {
    const response = await client.chat.completions.create({
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello!' }],
    });
    console.log(response.choices[0].message?.content);
  } finally {
    client.close();
  }
}

main();
```

## Parallel Requests

Send multiple requests concurrently using `asyncio.gather()` in Python or `Promise.all()` in TypeScript.

### Python

```python
import asyncio
import modelmesh

async def ask(client, question: str) -> str:
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": question}],
    )
    return response.choices[0].message.content

async def main():
    async with modelmesh.create("chat-completion") as client:
        questions = [
            "What is Python?",
            "What is TypeScript?",
            "What is Rust?",
            "What is Go?",
            "What is Java?",
        ]

        # Run all 5 requests concurrently
        results = await asyncio.gather(
            *[ask(client, q) for q in questions]
        )

        for question, answer in zip(questions, results):
            print(f"Q: {question}")
            print(f"A: {answer[:100]}...")
            print()

asyncio.run(main())
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';

async function ask(client, question: string): Promise<string> {
  const response = await client.chat.completions.create({
    model: 'chat-completion',
    messages: [{ role: 'user', content: question }],
  });
  return response.choices[0].message?.content ?? '';
}

async function main() {
  const client = create('chat-completion');

  const questions = [
    'What is Python?',
    'What is TypeScript?',
    'What is Rust?',
    'What is Go?',
    'What is Java?',
  ];

  // Run all 5 requests concurrently
  const results = await Promise.all(
    questions.map(q => ask(client, q))
  );

  questions.forEach((q, i) => {
    console.log(`Q: ${q}`);
    console.log(`A: ${results[i].slice(0, 100)}...`);
    console.log();
  });

  client.close();
}

main();
```

## Controlling Concurrency

Unbounded concurrency can overwhelm providers with rate limits. Use a semaphore to cap the number of in-flight requests.

### Python (asyncio.Semaphore)

```python
import asyncio
import modelmesh

MAX_CONCURRENT = 5

async def ask_with_limit(sem, client, question: str) -> str:
    async with sem:
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": question}],
        )
        return response.choices[0].message.content

async def main():
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    async with modelmesh.create("chat-completion") as client:
        questions = [f"Question {i}" for i in range(20)]
        results = await asyncio.gather(
            *[ask_with_limit(sem, client, q) for q in questions]
        )
        print(f"Completed {len(results)} requests")

asyncio.run(main())
```

### TypeScript (p-limit)

```typescript
import { create } from '@nistrapa/modelmesh-core';
import pLimit from 'p-limit';

const MAX_CONCURRENT = 5;

async function main() {
  const client = create('chat-completion');
  const limit = pLimit(MAX_CONCURRENT);

  const questions = Array.from({ length: 20 }, (_, i) => `Question ${i}`);

  const results = await Promise.all(
    questions.map(q =>
      limit(async () => {
        const response = await client.chat.completions.create({
          model: 'chat-completion',
          messages: [{ role: 'user', content: q }],
        });
        return response.choices[0].message?.content ?? '';
      })
    )
  );

  console.log(`Completed ${results.length} requests`);
  client.close();
}

main();
```

## Connection Pooling and Limits

Configure connection limits per provider to prevent resource exhaustion under high concurrency:

```yaml
providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    connection_pool:
      max_connections: 50
      timeout: 30s

  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}
    connection_pool:
      max_connections: 25
      timeout: 30s
```

The connection pool is shared across all concurrent requests to the same provider. When all connections are in use, new requests wait until a connection becomes available or the timeout expires.

## Rate Limiting Across Concurrent Requests

Use the `rate-limit-aware` strategy to automatically distribute concurrent requests across providers as rate limits approach:

```yaml
pools:
  chat-completion:
    strategy: modelmesh.rate-limit-aware.v1
    rate_limit:
      threshold: 0.8
      max_rpm: 60
```

With `threshold: 0.8`, ModelMesh switches to the next provider when 80% of the rate limit is consumed. This prevents rate limit errors even under bursty concurrent load.

### Python

```python
import asyncio
import modelmesh

async def burst_test():
    """Send 50 concurrent requests across rate-limited providers."""
    async with modelmesh.create("chat-completion") as client:
        tasks = []
        for i in range(50):
            tasks.append(
                client.chat.completions.create(
                    model="chat-completion",
                    messages=[{"role": "user", "content": f"Request {i}"}],
                )
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = sum(1 for r in results if isinstance(r, Exception))
        print(f"Successes: {successes}, Failures: {failures}")

asyncio.run(burst_test())
```

## Streaming with Async Iterators

Consume streaming responses asynchronously:

### Python

```python
import asyncio
import modelmesh

async def stream_chat():
    async with modelmesh.create("chat-completion") as client:
        stream = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Write a poem"}],
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                print(token, end="", flush=True)
        print()

asyncio.run(stream_chat())
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';

async function streamChat() {
  const client = create('chat-completion');

  const stream = await client.chat.completions.create({
    model: 'chat-completion',
    messages: [{ role: 'user', content: 'Write a poem' }],
    stream: true,
  });

  for await (const chunk of stream) {
    const token = chunk.choices[0]?.delta?.content;
    if (token) process.stdout.write(token);
  }
  console.log();
  client.close();
}

streamChat();
```

### Parallel Streams

Run multiple streams concurrently:

```python
import asyncio
import modelmesh

async def stream_one(client, topic: str):
    result = []
    stream = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": f"Write about {topic}"}],
        stream=True,
    )
    async for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            result.append(token)
    return "".join(result)

async def main():
    async with modelmesh.create("chat-completion") as client:
        topics = ["python", "javascript", "rust"]
        results = await asyncio.gather(
            *[stream_one(client, t) for t in topics]
        )
        for topic, text in zip(topics, results):
            print(f"--- {topic} ---")
            print(text[:200])
            print()

asyncio.run(main())
```

## Timeout Handling

Set timeouts at the pool level and handle them in application code:

```yaml
pools:
  chat-completion:
    retry:
      max_attempts: 2
      backoff: exponential_jitter
      initial_delay: 500ms
      max_delay: 10s
```

### Python

```python
import asyncio
import modelmesh
from modelmesh.exceptions import ProviderTimeoutError, ModelMeshError

async def ask_with_timeout(client, question: str, timeout: float = 30.0):
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.chat.completions.create,
                model="chat-completion",
                messages=[{"role": "user", "content": question}],
            ),
            timeout=timeout,
        )
        return response.choices[0].message.content
    except asyncio.TimeoutError:
        return f"Client timeout after {timeout}s"
    except ProviderTimeoutError:
        return "Provider timed out (ModelMesh will retry with next provider)"
    except ModelMeshError as e:
        return f"Error: {e}"

async def main():
    async with modelmesh.create("chat-completion") as client:
        result = await ask_with_timeout(client, "Hello!", timeout=15.0)
        print(result)

asyncio.run(main())
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';
import { ProviderTimeoutError, ModelMeshError } from '@nistrapa/modelmesh-core';

async function askWithTimeout(
  client,
  question: string,
  timeoutMs = 30000,
): Promise<string> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await client.chat.completions.create({
      model: 'chat-completion',
      messages: [{ role: 'user', content: question }],
    });
    return response.choices[0].message?.content ?? '';
  } catch (e) {
    if (e instanceof ProviderTimeoutError) {
      return 'Provider timed out';
    }
    if (e instanceof ModelMeshError) {
      return `Error: ${e.message}`;
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

async function main() {
  const client = create('chat-completion');
  const result = await askWithTimeout(client, 'Hello!', 15000);
  console.log(result);
  client.close();
}

main();
```

## Error Handling in Concurrent Scenarios

When running parallel requests, wrap each call in a try/except to collect errors without cancelling other requests:

### Python

```python
import asyncio
import modelmesh
from modelmesh.exceptions import ModelMeshError, RateLimitError, BudgetExceededError

async def safe_ask(client, question: str):
    try:
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": question}],
        )
        return {"status": "ok", "content": response.choices[0].message.content}
    except RateLimitError as e:
        return {"status": "rate_limited", "retry_after": e.retry_after}
    except BudgetExceededError:
        return {"status": "budget_exceeded"}
    except ModelMeshError as e:
        return {"status": "error", "message": str(e)}

async def main():
    async with modelmesh.create("chat-completion") as client:
        questions = [f"Question {i}" for i in range(10)]
        results = await asyncio.gather(*[safe_ask(client, q) for q in questions])
        ok = sum(1 for r in results if r["status"] == "ok")
        print(f"OK: {ok}, Errors: {len(results) - ok}")

asyncio.run(main())
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';
import { ModelMeshError } from '@nistrapa/modelmesh-core';

async function safeAsk(client, question: string) {
  try {
    const response = await client.chat.completions.create({
      model: 'chat-completion',
      messages: [{ role: 'user', content: question }],
    });
    return { status: 'ok', content: response.choices[0].message?.content ?? '' };
  } catch (e) {
    const msg = e instanceof ModelMeshError ? e.message : 'Unknown error';
    return { status: 'error', message: msg };
  }
}

async function main() {
  const client = create('chat-completion');
  const questions = Array.from({ length: 10 }, (_, i) => `Question ${i}`);
  const results = await Promise.allSettled(questions.map(q => safeAsk(client, q)));
  const ok = results.filter(r => r.status === 'fulfilled' && r.value.status === 'ok').length;
  console.log(`OK: ${ok}, Errors: ${results.length - ok}`);
  client.close();
}
main();
```

## Best Practices

### 1. Limit Concurrency

Cap in-flight requests with a semaphore. Unbounded concurrency causes rate limits and resource exhaustion.

```python
sem = asyncio.Semaphore(10)
async with sem:
    response = client.chat.completions.create(...)
```

### 2. Use Backpressure

Use a bounded `asyncio.Queue(maxsize=20)` with a worker pool pattern to prevent memory growth when processing large workloads. Feed items into the queue and let a fixed number of workers consume them.

### 3. Graceful Shutdown

Always use context managers (`async with modelmesh.create(...) as client:`) or explicit `client.close()` to ensure in-flight requests complete and connections are released. Register `SIGTERM` / `SIGINT` handlers to set a shutdown event.

### 4. Choose the Right Strategy for Concurrency

| Scenario | Recommended Strategy |
|----------|---------------------|
| High request volume | `rate-limit-aware` or `load-balanced` |
| Burst traffic | `rate-limit-aware` with low threshold |
| Parallel batch processing | `round-robin` with semaphore |
| Long-running sessions | `session-stickiness` |
| Mixed priorities | `priority-selection` with per-provider budgets |

---

See also: [Streaming Guide](StreamingGuide.md) · [Error Handling](ErrorHandling.md) · [Production Guide](ProductionGuide.md) · [Quick Start](QuickStart.md) · [Architecture Patterns](ArchitecturePatterns.md)
