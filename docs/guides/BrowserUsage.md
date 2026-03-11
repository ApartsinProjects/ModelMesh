# Browser Usage Guide

ModelMesh TypeScript works in browsers, calling AI provider APIs directly from client-side JavaScript. This guide covers setup, CORS handling, and security. For the full list of browser-compatible connectors (storage, secret stores, providers), see the [Connector Catalogue](../ConnectorCatalogue.html). For the CORS proxy deployment, see the [Proxy Guide](ProxyGuide.html).

## Architecture

```
┌──────────────────────────────────────────────┐
│  Browser                                     │
│                                              │
│  Your App  ──→  BrowserBaseProvider          │
│                    │                         │
│                    ├── proxyUrl set?          │
│                    │   YES → CORS Proxy ──→ API│
│                    │   NO  → Direct    ──→ API│
└──────────────────────────────────────────────┘
```

## Two Modes

### 1. Direct Access (No CORS Proxy)

Works when:
- The AI provider sends CORS headers (e.g., Anthropic with `anthropic-dangerous-direct-browser-access` header)
- You're in a browser extension with `host_permissions`
- You're in a non-browser runtime (Node.js, Deno, Bun, Workers)

```typescript
import { BrowserBaseProvider, createBrowserProviderConfig } from '@nistrapa/modelmesh-core';

const provider = new BrowserBaseProvider(createBrowserProviderConfig({
  baseUrl: 'https://api.openai.com',
  apiKey: userApiKey,
  // No proxyUrl — direct connection
}));
```

### 2. CORS Proxy

Works everywhere. The proxy adds CORS headers so the browser allows the request.

```typescript
const provider = new BrowserBaseProvider(createBrowserProviderConfig({
  baseUrl: 'https://api.openai.com',
  apiKey: userApiKey,
  proxyUrl: 'http://localhost:9090',  // CORS proxy
}));
```

## Quick Start

### Step 1: Start the CORS Proxy

```bash
# Option A: Node.js (zero dependencies)
node tools/cors-proxy/cors-proxy.js

# Option B: Docker
cd tools/cors-proxy
docker compose up

# Option C: Third-party
npx local-cors-proxy --proxyUrl https://api.openai.com --port 9090
```

### Step 2: Open the Sample Page

Open `samples/browser/index.html` in your browser. Configure:

1. **Provider**: Select your AI provider
2. **Model**: Model name (auto-filled for common providers)
3. **API Key**: Your provider API key
4. **CORS Proxy URL**: `http://localhost:9090` (or leave empty for direct access)

### Step 3: Chat

Type a message and click Send. Responses stream in real-time.

## What is CORS?

**CORS (Cross-Origin Resource Sharing)** is a browser security feature. When JavaScript on `yoursite.com` tries to call `api.openai.com`, the browser blocks it unless the API server explicitly allows it with response headers like:

```
Access-Control-Allow-Origin: *
```

Most AI provider APIs do **not** send these headers, so browsers block the requests. The CORS proxy sits between the browser and the API, adding these headers.

**Important**: CORS only applies in web browsers. Node.js, browser extensions (with permissions), and server-side code are not affected.

## BrowserBaseProvider vs BaseProvider

| Feature | BaseProvider | BrowserBaseProvider |
|---------|-------------|-------------------|
| HTTP transport | Node.js `http`/`https` | Fetch API |
| Streaming | Node.js streams | ReadableStream |
| Timeout | `req.destroy()` | AbortController |
| CORS proxy | N/A | `proxyUrl` config |
| Environment | Node.js only | Browser, Deno, Bun, Workers |
| API interface | Identical | Identical |

Both classes share the same protected hooks for subclassing:
- `_buildHeaders()` — Customize request headers
- `_buildRequestPayload()` — Transform request body
- `_parseResponse()` — Parse completion response
- `_parseSseChunk()` — Parse SSE stream chunks
- `_getCompletionEndpoint()` — Override API endpoint

## Browser Entry Point

For bundlers, import from the browser entry point to exclude Node.js-specific modules:

```typescript
import {
  BrowserBaseProvider,
  createBrowserProviderConfig,
  ModelMesh,
  MeshClient,
  createBrowser,
  // Storage connectors
  MemoryStorage,
  LocalStorageStorage,
  SessionStorageStorage,
  IndexedDBStorage,
  // Secret stores
  MemorySecretStore,
  BrowserSecretStore,
  // Runtime metadata
  RuntimeEnvironment,
} from '@nistrapa/modelmesh-core/browser';
```

The browser entry point excludes: `ProxyServer`, `MeshConfig.fromFile()`, `FileSecretStore`, `HttpHealthDiscovery`, `KeyValueStorage` (file backend), and all Node.js-dependent connectors (providers using `http`/`https`, file-based storage, env/dotenv/json/encrypted/keyring secret stores).

## Security Considerations

### API Keys in Browser Code

API keys in client-side JavaScript are visible to users. This is acceptable for:
- **Personal tools**: You're the only user
- **Development/testing**: Local development with test keys
- **User-provided keys**: Users enter their own API keys

For production apps with shared API keys, use a backend proxy that holds the keys.

### CORS Proxy Security

The included CORS proxy is for **development only**. For production:
1. Add authentication to the proxy
2. Restrict allowed target domains (whitelist)
3. Deploy behind HTTPS
4. Add rate limiting

### Browser Extensions

Browser extensions with `host_permissions` in `manifest.json` bypass CORS entirely:

```json
{
  "host_permissions": [
    "https://api.openai.com/*",
    "https://api.anthropic.com/*"
  ]
}
```

No CORS proxy needed. Use `BrowserBaseProvider` without `proxyUrl`.

## Provider-Specific Notes

### OpenAI
- Requires CORS proxy for browser access
- Standard Bearer token authentication

### Anthropic
- Supports direct browser access with special header:
  ```
  anthropic-dangerous-direct-browser-access: true
  ```
- Uses `x-api-key` header instead of Bearer token

### Groq / DeepSeek / Mistral
- Require CORS proxy for browser access
- Standard OpenAI-compatible API format

### OpenRouter
- May support CORS headers natively
- Standard OpenAI-compatible API format

## Audio over Browser

TTS and STT providers (ElevenLabs, AssemblyAI) can be accessed from the browser through the same `BrowserBaseProvider` and CORS proxy setup. Key considerations:

### TTS Streaming

TTS responses are binary audio data, not JSON. The `BrowserBaseProvider` returns audio bytes in the response `extra.audio` field. For streaming TTS, the response is a `ReadableStream` of audio chunks that can be fed directly to the Web Audio API or an `<audio>` element via `MediaSource`:

```typescript
const response = await client.audio.speech.create({
    model: "text-to-speech",
    input: "Hello from the browser!",
    voice: "alloy",
});
// response.extra.audio is a Blob or ReadableStream
const audioUrl = URL.createObjectURL(response.extra.audio);
const audio = new Audio(audioUrl);
audio.play();
```

### STT from Browser

Speech-to-text requests send audio data (from a microphone or file upload) to the STT provider. The browser `MediaRecorder` API captures audio, which is sent as the `file` parameter:

```typescript
const transcript = await client.audio.transcriptions.create({
    model: "speech-to-text",
    file: audioBlob,  // from MediaRecorder or file input
});
console.log(transcript.text);
```

### CORS Proxy for Audio

Audio API endpoints require the same CORS proxy as text endpoints. The proxy handles binary response bodies transparently. Ensure the proxy does not set a response size limit that would truncate large audio files.

## Browser Storage Connectors

ModelMesh provides three persistent storage connectors for browser environments, plus a browser-compatible secret store. All use the standard `StorageConnector` interface.

### localStorage Storage

Persists state across page reloads and browser restarts. Subject to ~5-10 MB limit per origin.

```typescript
import { LocalStorageStorage } from '@nistrapa/modelmesh-core/browser';

const storage = new LocalStorageStorage({ prefix: 'myapp:' });
await storage.save('model-state', {
  key: 'model-state',
  data: new Uint8Array([1, 2, 3]),
  metadata: { version: 1 },
});
const entry = await storage.load('model-state');
```

### sessionStorage Storage

Identical API to localStorage, but data is cleared when the browser tab closes. Useful for ephemeral per-session state.

```typescript
import { SessionStorageStorage } from '@nistrapa/modelmesh-core/browser';

const storage = new SessionStorageStorage({ prefix: 'session:' });
```

### IndexedDB Storage

Natively async storage with no practical size limit. Stores binary data directly (no base64 overhead). Recommended for apps with large state.

```typescript
import { IndexedDBStorage } from '@nistrapa/modelmesh-core/browser';

const storage = new IndexedDBStorage({
  dbName: 'myapp',
  storeName: 'mesh-state',
  version: 1,
});
await storage.save('large-data', {
  key: 'large-data',
  data: new Uint8Array(1024 * 1024), // 1 MB
  metadata: {},
});
// When done, release the connection
storage.close();
```

### Browser Secret Store

Persists API keys and secrets in localStorage. Supports the full `SecretManagement` interface.

```typescript
import { BrowserSecretStore } from '@nistrapa/modelmesh-core/browser';

const secrets = new BrowserSecretStore({
  prefix: 'myapp-secrets:',
  failOnMissing: false,
});
secrets.set('OPENAI_API_KEY', userProvidedKey);
const key = secrets.get('OPENAI_API_KEY');
```

> **Security note:** localStorage is not encrypted. Secrets are visible in browser DevTools. This is suitable for user-provided API keys in personal tools, not for shared production deployments with server-managed keys.

### Choosing a Browser Storage Backend

| Requirement | Use |
|-------------|-----|
| Small state, simple persistence | `LocalStorageStorage` |
| Large binary data, no size limit | `IndexedDBStorage` |
| State that expires with the tab | `SessionStorageStorage` |
| Testing without browser APIs | `MemoryStorage` (universal) |
| Storing API keys in browser | `BrowserSecretStore` |

## Runtime Environment Metadata

Every TypeScript connector class declares a `static readonly RUNTIME` property using the `RuntimeEnvironment` enum. This metadata enables:

- **Build-time tree-shaking**: Bundlers can exclude Node.js-only connectors from browser builds
- **Runtime compatibility checks**: `assertRuntimeCompatible()` throws a clear error if a connector is used in the wrong environment
- **Discoverability**: Inspect any connector's runtime requirement programmatically

### RuntimeEnvironment Values

| Value | Constant | Runs In | Connector Examples |
|-------|----------|---------|-------------------|
| `'node'` | `RuntimeEnvironment.NODE_ONLY` | Node.js, Bun, Deno (server) | All providers (OpenAI, Anthropic, Ollama, etc.), file storage, env/dotenv/json secret stores |
| `'browser'` | `RuntimeEnvironment.BROWSER_ONLY` | Browsers | LocalStorageStorage, SessionStorageStorage, IndexedDBStorage, BrowserSecretStore |
| `'universal'` | `RuntimeEnvironment.UNIVERSAL` | Anywhere | MemoryStorage, MemorySecretStore, BrowserBaseProvider, rotation policies, ConsoleObservability |

### Runtime Guard

Use `detectRuntime()` and `assertRuntimeCompatible()` to validate connector compatibility:

```typescript
import { detectRuntime, assertRuntimeCompatible, RuntimeEnvironment } from '@nistrapa/modelmesh-core';

// Check current environment
const env = detectRuntime(); // 'node' or 'browser'

// Guard against incompatible usage (throws on mismatch)
assertRuntimeCompatible('modelmesh.localstorage.v1', RuntimeEnvironment.BROWSER_ONLY);
```

The runtime guard checks `typeof window !== 'undefined'` and `typeof document !== 'undefined'` to distinguish browser from Node.js environments.

## CORS Proxy Advanced Configuration

The Docker CORS proxy accepts a `PORT` environment variable (default: `9090`):

```bash
# Custom port
PORT=8080 node tools/cors-proxy/cors-proxy.js

# Docker with custom port
docker compose -f tools/cors-proxy/docker-compose.yml up
# Modify the ports mapping in docker-compose.yml for non-default ports
```

For production deployments, replace the development proxy with a production-grade reverse proxy (nginx, Caddy) that adds CORS headers. See [Security Considerations](#security-considerations) above.

---

See also: [FAQ](FAQ.html) · [Quick Start](QuickStart.html) · [Proxy Guide](ProxyGuide.html)
