# ModelMesh Integrate Skill

## Purpose
Replace existing AI SDK calls in the user's project with ModelMesh routing. This enables automatic failover, multi-provider support, and free-tier aggregation.

## Decision Steps

1. **Scan the project** for existing AI SDK usage:
   - Python: `from openai import OpenAI`, `import anthropic`, `import google.generativeai`
   - TypeScript: `import OpenAI from 'openai'`, `import Anthropic from '@anthropic-ai/sdk'`
   - REST API calls to `api.openai.com`, `api.anthropic.com`, etc.

2. **Determine integration approach:**
   - **Drop-in replacement** (recommended): Replace SDK client instantiation only
   - **Proxy mode**: Keep existing SDK, point `base_url` to ModelMesh proxy
   - **Full migration**: Replace all provider-specific code with ModelMesh API

## Approach A: Drop-In Replacement (Recommended)

ModelMesh's `create()` returns an OpenAI-compatible client. Replace client instantiation only.

### Python

**Before:**
```python
from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
```

**After:**
```python
import modelmesh
client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",              # use pool name instead of model name
    messages=[{"role": "user", "content": "Hello"}],
)
```

**Key changes:**
1. Replace `from openai import OpenAI` with `import modelmesh`
2. Replace `OpenAI()` with `modelmesh.create("chat-completion")`
3. Change `model="gpt-4o-mini"` to `model="chat-completion"` (capability pool)
4. Everything else stays the same — same API, same response format

### TypeScript

**Before:**
```typescript
import OpenAI from 'openai';
const client = new OpenAI();

const response = await client.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [{ role: 'user', content: 'Hello' }],
});
```

**After:**
```typescript
import { create } from '@modelmesh/core';
const client = create('chat-completion');

const response = await client.chat.completions.create({
    model: 'chat-completion',
    messages: [{ role: 'user', content: 'Hello' }],
});
```

## Approach B: Proxy Mode (Minimal Code Change)

Keep the existing OpenAI SDK, just point it at the ModelMesh proxy. Requires Docker proxy running.

**Python:**
```python
from openai import OpenAI
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="unused",    # proxy handles auth
)
# All existing code stays unchanged
```

**TypeScript:**
```typescript
import OpenAI from 'openai';
const client = new OpenAI({
    baseURL: 'http://localhost:8080/v1',
    apiKey: 'unused',
});
// All existing code stays unchanged
```

**Advantage:** Zero code changes beyond client config. Existing tests keep working.
**Requirement:** Docker proxy must be running (`docker compose up`).

## Approach C: Anthropic/Gemini Migration

If the project uses a non-OpenAI SDK, the migration is more involved since ModelMesh uses the OpenAI-compatible interface.

### From Anthropic SDK

**Before:**
```python
import anthropic
client = anthropic.Anthropic()
message = client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
print(message.content[0].text)
```

**After:**
```python
import modelmesh
client = modelmesh.create("chat-completion")
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=1024,
)
print(response.choices[0].message.content)
```

**Key changes:**
- `anthropic.Anthropic()` → `modelmesh.create("chat-completion")`
- `client.messages.create()` → `client.chat.completions.create()`
- `message.content[0].text` → `response.choices[0].message.content`
- Model name → pool name

## Streaming Migration

### Python Streaming

**Before:**
```python
stream = client.chat.completions.create(model="gpt-4o", ..., stream=True)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

**After (identical — same interface):**
```python
stream = client.chat.completions.create(model="chat-completion", ..., stream=True)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

### TypeScript Streaming

Same pattern — just change the model name to the pool name.

## Checklist

After integration, verify:

- [ ] ModelMesh package is installed (`pip install modelmesh-lite` or `npm install @modelmesh/core`)
- [ ] At least one API key env var is set
- [ ] All `OpenAI()` / `Anthropic()` calls replaced with `modelmesh.create()`
- [ ] All `model="specific-model"` changed to `model="pool-name"` (e.g., `"chat-completion"`)
- [ ] Streaming works (if used)
- [ ] Error handling works (ModelMesh raises compatible exceptions)
- [ ] Tests pass with the new client

## Common Gotchas

1. **Model name must be a pool name**: Use `"chat-completion"` or `"text-generation"`, not `"gpt-4o-mini"`.
2. **Environment variables**: At least one provider key must be set.
3. **Async**: ModelMesh client supports both sync and async patterns.
4. **Type checking**: ModelMesh provides `py.typed` (Python) and `.d.ts` (TypeScript) for full type support.
