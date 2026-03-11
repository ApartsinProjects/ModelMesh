# Streaming Deep Dive

Stream responses token-by-token from ModelMesh. This guide covers basic streaming, SSE format, proxy streaming, error handling, middleware integration, budget tracking, token counting, and browser patterns. For proxy-specific streaming details, see the [Proxy Guide](ProxyGuide.md). For error handling, see [Error Handling](ErrorHandling.md).

## Basic Streaming

Enable streaming by passing `stream=True` to `chat.completions.create()`. The response is an iterator that yields chunks as they arrive from the provider.

### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

stream = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Write a haiku about code"}],
    stream=True,
)

for chunk in stream:
    token = chunk.choices[0].delta.content
    if token:
        print(token, end="", flush=True)
print()
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';

const client = create('chat-completion');

const stream = await client.chat.completions.create({
  model: 'chat-completion',
  messages: [{ role: 'user', content: 'Write a haiku about code' }],
  stream: true,
});

for await (const chunk of stream) {
  const token = chunk.choices[0]?.delta?.content;
  if (token) process.stdout.write(token);
}
console.log();
```

## SSE Format

ModelMesh streaming uses the Server-Sent Events (SSE) format, identical to the OpenAI API. Each event is a `data:` line followed by a JSON object, with events separated by blank lines.

```
data: {"id":"chatcmpl-abc","choices":[{"delta":{"content":"Hello"},"index":0}]}

data: {"id":"chatcmpl-abc","choices":[{"delta":{"content":" world"},"index":0}]}

data: {"id":"chatcmpl-abc","choices":[{"delta":{},"finish_reason":"stop","index":0}]}

data: [DONE]
```

The final chunk has `finish_reason: "stop"` and an empty `delta`. The stream terminates with `data: [DONE]`.

## Streaming with the Proxy

When using the ModelMesh proxy, any HTTP client can consume the SSE stream.

### curl

```bash
curl -N -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chat-completion",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

The `-N` flag disables output buffering so chunks print as they arrive.

### JavaScript fetch

```javascript
const response = await fetch('http://localhost:8080/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'chat-completion',
    messages: [{ role: 'user', content: 'Hello!' }],
    stream: true,
  }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });

  const lines = buffer.split('\n');
  buffer = lines.pop();

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed === 'data: [DONE]') return;
    if (!trimmed.startsWith('data: ')) continue;
    const chunk = JSON.parse(trimmed.slice(6));
    const token = chunk.choices?.[0]?.delta?.content;
    if (token) document.getElementById('output').textContent += token;
  }
}
```

### OpenAI SDK (Pointing at Proxy)

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="not-needed")

stream = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)

for chunk in stream:
    token = chunk.choices[0].delta.content or ""
    print(token, end="", flush=True)
```

## Error Handling During Streaming

Errors can occur before the stream starts (routing failure, budget exceeded) or mid-stream (provider disconnect, timeout). Handle both cases.

### Python

```python
from modelmesh.exceptions import (
    AllProvidersExhaustedError,
    BudgetExceededError,
    ProviderTimeoutError,
    ModelMeshError,
)

try:
    stream = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello!"}],
        stream=True,
    )
    collected_text = ""
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            collected_text += token
            print(token, end="", flush=True)
except BudgetExceededError as e:
    print(f"\nStream aborted: budget exceeded ({e.limit_type})")
except ProviderTimeoutError:
    print(f"\nStream interrupted: provider timed out")
    print(f"Partial response: {collected_text}")
except AllProvidersExhaustedError:
    print("\nAll providers failed during streaming")
except ModelMeshError as e:
    print(f"\nStream error: {e}")
```

### TypeScript

```typescript
import {
  BudgetExceededError,
  ProviderTimeoutError,
  ModelMeshError,
} from '@nistrapa/modelmesh-core';

try {
  const stream = await client.chat.completions.create({
    model: 'chat-completion',
    messages: [{ role: 'user', content: 'Hello!' }],
    stream: true,
  });

  let collectedText = '';
  for await (const chunk of stream) {
    const token = chunk.choices[0]?.delta?.content;
    if (token) {
      collectedText += token;
      process.stdout.write(token);
    }
  }
} catch (e) {
  if (e instanceof BudgetExceededError) {
    console.error('\nBudget exceeded during streaming');
  } else if (e instanceof ProviderTimeoutError) {
    console.error('\nProvider timed out during streaming');
  } else if (e instanceof ModelMeshError) {
    console.error(`\nStream error: ${e.message}`);
  }
}
```

## Streaming with Middleware

Middleware hooks run before the stream starts and after it completes. Use `before_request` to intercept the request and `after_response` to process the final aggregated response.

### Python

```python
import time
from modelmesh import Middleware

class StreamTimingMiddleware(Middleware):
    async def before_request(self, request, context):
        context.metadata["stream_start"] = time.time()
        print(f"Streaming from {context.model_id} via {context.provider_id}")
        return request

    async def after_response(self, response, context):
        elapsed = time.time() - context.metadata["stream_start"]
        print(f"\nStream completed in {elapsed:.2f}s")
        return response

client = modelmesh.create("chat-completion", middleware=[StreamTimingMiddleware()])

stream = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)
for chunk in stream:
    token = chunk.choices[0].delta.content
    if token:
        print(token, end="", flush=True)
```

### TypeScript

```typescript
import { Middleware, create } from '@nistrapa/modelmesh-core';

class StreamTimingMiddleware extends Middleware {
  async beforeRequest(request, context) {
    context.metadata.streamStart = Date.now();
    console.log(`Streaming from ${context.modelId} via ${context.providerId}`);
    return request;
  }

  async afterResponse(response, context) {
    const elapsed = (Date.now() - context.metadata.streamStart) / 1000;
    console.log(`\nStream completed in ${elapsed.toFixed(2)}s`);
    return response;
  }
}

const client = create('chat-completion', {
  middleware: [new StreamTimingMiddleware()],
});
```

## Streaming with Budget Tracking

Budget tracking works during streaming. ModelMesh estimates token cost as chunks arrive and enforces limits in real time.

```yaml
providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 5.00
```

```python
client = modelmesh.create("chat-completion")

stream = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Write a long essay about AI"}],
    stream=True,
)

for chunk in stream:
    token = chunk.choices[0].delta.content
    if token:
        print(token, end="", flush=True)

# Check cost after stream completes
print(f"\nCost: ${client.usage.total_cost:.6f}")
```

If the budget is exceeded mid-stream, the stream raises `BudgetExceededError`. Handle it to capture partial output (see error handling section above).

## Token Counting During Streaming

Count tokens as they arrive to display progress or implement client-side limits:

### Python

```python
client = modelmesh.create("chat-completion")

stream = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)

token_count = 0
for chunk in stream:
    token = chunk.choices[0].delta.content
    if token:
        token_count += 1
        print(token, end="", flush=True)

    # Access usage on the final chunk when available
    if chunk.usage:
        print(f"\nServer-reported tokens: {chunk.usage.total_tokens}")
        break

print(f"\nClient-counted chunks: {token_count}")
```

### TypeScript

```typescript
const stream = await client.chat.completions.create({
  model: 'chat-completion',
  messages: [{ role: 'user', content: 'Hello!' }],
  stream: true,
});

let tokenCount = 0;
for await (const chunk of stream) {
  const token = chunk.choices[0]?.delta?.content;
  if (token) {
    tokenCount++;
    process.stdout.write(token);
  }
  if (chunk.usage) {
    console.log(`\nServer-reported tokens: ${chunk.usage.totalTokens}`);
  }
}
console.log(`Client-counted chunks: ${tokenCount}`);
```

## Browser Streaming Patterns

### ReadableStream with React

```typescript
import { useState } from 'react';

function ChatStream() {
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSend(message: string) {
    setLoading(true);
    setOutput('');

    const response = await fetch('http://localhost:8080/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'chat-completion',
        messages: [{ role: 'user', content: message }],
        stream: true,
      }),
    });

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop()!;

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed === 'data: [DONE]') { setLoading(false); return; }
        if (!trimmed.startsWith('data: ')) continue;
        const chunk = JSON.parse(trimmed.slice(6));
        const token = chunk.choices?.[0]?.delta?.content;
        if (token) setOutput(prev => prev + token);
      }
    }
    setLoading(false);
  }

  return (
    <div>
      <button onClick={() => handleSend('Hello!')} disabled={loading}>
        {loading ? 'Streaming...' : 'Send'}
      </button>
      <pre>{output}</pre>
    </div>
  );
}
```

### EventSource (SSE Native API)

The native `EventSource` API does not support POST requests, so use the `fetch` + `ReadableStream` pattern shown above for chat completions. `EventSource` works only for GET-based SSE endpoints.

### AbortController (Cancel Streaming)

Cancel a stream mid-response using `AbortController`:

```typescript
const controller = new AbortController();

const response = await fetch('http://localhost:8080/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'chat-completion',
    messages: [{ role: 'user', content: 'Write a long story' }],
    stream: true,
  }),
  signal: controller.signal,
});

// Cancel after 5 seconds
setTimeout(() => controller.abort(), 5000);

const reader = response.body!.getReader();
try {
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // process chunks...
  }
} catch (e) {
  if (e.name === 'AbortError') {
    console.log('Stream cancelled by user');
  }
}
```

## Streaming Checklist

1. Always handle both pre-stream and mid-stream errors
2. Use `flush=True` (Python) or unbuffered writes for real-time display
3. Buffer partial SSE lines when parsing raw responses
4. Look for `data: [DONE]` to detect stream completion
5. Check `chunk.usage` on the final chunk for server-side token counts
6. Use `AbortController` in browsers to let users cancel streams
7. Budget enforcement works during streaming; catch `BudgetExceededError` to handle partial responses

---

See also: [Quick Start](QuickStart.md) · [Proxy Guide](ProxyGuide.md) · [Error Handling](ErrorHandling.md) · [Async Guide](AsyncGuide.md) · [Integration Recipes](IntegrationRecipes.md)
