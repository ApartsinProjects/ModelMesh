# Framework Integration Recipes

Complete, runnable integration examples for popular Python and TypeScript frameworks. Each recipe connects a web framework to ModelMesh for AI-powered endpoints. For streaming details, see the [Streaming Guide](StreamingGuide.md). For production deployment, see the [Production Guide](ProductionGuide.md).

## FastAPI (Python)

A streaming chat endpoint using FastAPI with Server-Sent Events.

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import modelmesh
import json

app = FastAPI()
client = modelmesh.create("chat-completion")


class ChatRequest(BaseModel):
    message: str
    stream: bool = False


@app.post("/chat")
async def chat(req: ChatRequest):
    messages = [{"role": "user", "content": req.message}]

    if req.stream:
        return StreamingResponse(
            stream_response(messages),
            media_type="text/event-stream",
        )

    response = client.chat.completions.create(
        model="chat-completion",
        messages=messages,
    )
    return {
        "content": response.choices[0].message.content,
        "model": response.model,
        "tokens": response.usage.total_tokens,
    }


async def stream_response(messages):
    stream = client.chat.completions.create(
        model="chat-completion",
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield f"data: {json.dumps({'content': token})}\n\n"
    yield "data: [DONE]\n\n"


@app.on_event("shutdown")
async def shutdown():
    client.close()
```

Run with:

```bash
pip install fastapi uvicorn modelmesh-lite
uvicorn app:app --host 0.0.0.0 --port 3000
```

Test:

```bash
# Non-streaming
curl -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'

# Streaming
curl -N -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "stream": true}'
```

## Flask (Python)

A simple chat endpoint using Flask.

```python
from flask import Flask, request, jsonify, Response
import modelmesh
import json

app = Flask(__name__)
client = modelmesh.create("chat-completion")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "")
    use_stream = data.get("stream", False)
    messages = [{"role": "user", "content": message}]

    if use_stream:
        def generate():
            stream = client.chat.completions.create(
                model="chat-completion",
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    yield f"data: {json.dumps({'content': token})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(generate(), mimetype="text/event-stream")

    response = client.chat.completions.create(
        model="chat-completion",
        messages=messages,
    )
    return jsonify({
        "content": response.choices[0].message.content,
        "model": response.model,
        "tokens": response.usage.total_tokens,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
```

Run with:

```bash
pip install flask modelmesh-lite
python app.py
```

## Django (Python)

A view-based chat endpoint for Django.

```python
# views.py
import json
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import modelmesh

client = modelmesh.create("chat-completion")


@csrf_exempt
@require_POST
def chat(request):
    data = json.loads(request.body)
    message = data.get("message", "")
    use_stream = data.get("stream", False)
    messages = [{"role": "user", "content": message}]

    if use_stream:
        def generate():
            stream = client.chat.completions.create(
                model="chat-completion",
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    yield f"data: {json.dumps({'content': token})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingHttpResponse(
            generate(),
            content_type="text/event-stream",
        )

    response = client.chat.completions.create(
        model="chat-completion",
        messages=messages,
    )
    return JsonResponse({
        "content": response.choices[0].message.content,
        "model": response.model,
        "tokens": response.usage.total_tokens,
    })
```

```python
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("chat", views.chat, name="chat"),
]
```

Run with:

```bash
pip install django modelmesh-lite
python manage.py runserver 0.0.0.0:3000
```

## Express.js (TypeScript)

A REST API with ModelMesh routing and streaming support.

```typescript
import express from 'express';
import { create } from '@nistrapa/modelmesh-core';

const app = express();
app.use(express.json());

const client = create('chat-completion');

app.post('/chat', async (req, res) => {
  const { message, stream: useStream } = req.body;
  const messages = [{ role: 'user' as const, content: message }];

  if (useStream) {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    const stream = await client.chat.completions.create({
      model: 'chat-completion',
      messages,
      stream: true,
    });

    for await (const chunk of stream) {
      const token = chunk.choices[0]?.delta?.content;
      if (token) {
        res.write(`data: ${JSON.stringify({ content: token })}\n\n`);
      }
    }
    res.write('data: [DONE]\n\n');
    res.end();
    return;
  }

  const response = await client.chat.completions.create({
    model: 'chat-completion',
    messages,
  });

  res.json({
    content: response.choices[0].message?.content,
    model: response.model,
    tokens: response.usage?.totalTokens,
  });
});

app.listen(3000, () => console.log('Server running on port 3000'));
```

Run with:

```bash
npm install express @nistrapa/modelmesh-core
npx tsx app.ts
```

## Next.js (TypeScript)

An API route handler plus a React chat component with streaming.

### API Route (`app/api/chat/route.ts`)

```typescript
import { NextRequest } from 'next/server';
import { create } from '@nistrapa/modelmesh-core';

const client = create('chat-completion');

export async function POST(req: NextRequest) {
  const { message, stream: useStream } = await req.json();
  const messages = [{ role: 'user' as const, content: message }];

  if (useStream) {
    const stream = await client.chat.completions.create({
      model: 'chat-completion',
      messages,
      stream: true,
    });

    const encoder = new TextEncoder();
    const readable = new ReadableStream({
      async start(controller) {
        for await (const chunk of stream) {
          const token = chunk.choices[0]?.delta?.content;
          if (token) {
            controller.enqueue(
              encoder.encode(`data: ${JSON.stringify({ content: token })}\n\n`)
            );
          }
        }
        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
        controller.close();
      },
    });

    return new Response(readable, {
      headers: { 'Content-Type': 'text/event-stream' },
    });
  }

  const response = await client.chat.completions.create({
    model: 'chat-completion',
    messages,
  });

  return Response.json({
    content: response.choices[0].message?.content,
    model: response.model,
    tokens: response.usage?.totalTokens,
  });
}
```

### Chat Component (`app/components/Chat.tsx`)

```typescript
'use client';
import { useState, FormEvent } from 'react';

export default function Chat() {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    setLoading(true);
    setOutput('');

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: input, stream: true }),
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
        if (trimmed === 'data: [DONE]') break;
        if (!trimmed.startsWith('data: ')) continue;
        const data = JSON.parse(trimmed.slice(6));
        if (data.content) setOutput(prev => prev + data.content);
      }
    }
    setLoading(false);
  }

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask anything..."
          disabled={loading}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Streaming...' : 'Send'}
        </button>
      </form>
      <pre>{output}</pre>
    </div>
  );
}
```

Run with:

```bash
npx create-next-app@latest my-app --typescript
cd my-app
npm install @nistrapa/modelmesh-core
npm run dev
```

## Recipe Comparison

| Framework | Language | Streaming | Lines of Code | Best For |
|-----------|----------|-----------|--------------|----------|
| FastAPI | Python | SSE via `StreamingResponse` | ~35 | High-performance async APIs |
| Flask | Python | SSE via `Response` generator | ~30 | Simple REST APIs, prototyping |
| Django | Python | SSE via `StreamingHttpResponse` | ~35 | Full-stack web applications |
| Express.js | TypeScript | SSE via `res.write()` | ~35 | Node.js REST services |
| Next.js | TypeScript | SSE via `ReadableStream` | ~40 (API) + ~35 (component) | Full-stack React applications |

## Error Handling Pattern

Add error handling to any recipe using the same pattern:

```python
from modelmesh.exceptions import ModelMeshError, AllProvidersExhaustedError

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": req.message}],
        )
        return {"content": response.choices[0].message.content}
    except AllProvidersExhaustedError:
        return JSONResponse(
            status_code=503,
            content={"error": "All AI providers are currently unavailable"},
        )
    except ModelMeshError as e:
        return JSONResponse(
            status_code=502,
            content={"error": f"AI routing error: {str(e)}"},
        )
```

---

See also: [Quick Start](QuickStart.md) · [Streaming Guide](StreamingGuide.md) · [Proxy Guide](ProxyGuide.md) · [Async Guide](AsyncGuide.md) · [Architecture Patterns](ArchitecturePatterns.md)
