# ModelMesh CORS Proxy

A minimal, transparent CORS proxy for browser-based AI API access.

## What It Does

Adds CORS headers to any HTTP request. No logic, no filtering, no caching.

```
Browser                        CORS Proxy              AI Provider
  |                                |                        |
  |-- POST /https://api.openai... |                        |
  |                                |-- POST /v1/chat/...-->|
  |                                |<-- response -----------|
  |<-- response + CORS headers ---|                        |
```

## Quick Start

### Node.js (no dependencies)

```bash
node cors-proxy.js
# Listening on http://localhost:9090
```

### Docker

```bash
docker build -t modelmesh-cors-proxy .
docker run -p 9090:9090 modelmesh-cors-proxy
```

### Docker Compose

```bash
docker compose up
```

## Usage

Configure your `BrowserBaseProvider` with the proxy URL:

```typescript
const provider = new BrowserBaseProvider(createBrowserProviderConfig({
  baseUrl: 'https://api.openai.com',
  apiKey: 'sk-...',
  proxyUrl: 'http://localhost:9090',
}));
```

Or in the sample HTML page, set **CORS Proxy URL** to `http://localhost:9090`.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT`   | `9090`  | Proxy listen port |

## When You Don't Need This

- **Backend / Node.js**: No CORS restrictions in server-side code
- **Browser extensions**: With `host_permissions` in manifest, extensions bypass CORS
- **APIs with CORS enabled**: Some providers (OpenRouter, etc.) already send CORS headers
- **Anthropic**: Supports `anthropic-dangerous-direct-browser-access` header

## Alternatives

If you prefer a third-party solution:

- **[cors-anywhere](https://www.npmjs.com/package/cors-anywhere)**: Popular Node.js CORS proxy (`npm install cors-anywhere`)
- **[local-cors-proxy](https://www.npmjs.com/package/local-cors-proxy)**: Simple CLI proxy (`npx local-cors-proxy --proxyUrl https://api.openai.com`)
- **Nginx**: Add CORS headers in nginx config (`add_header Access-Control-Allow-Origin *;`)
- **Caddy**: Built-in CORS support via `header` directive

## Security

This proxy is for **development only**. For production:

1. Add authentication (API key or token)
2. Restrict allowed target domains
3. Deploy behind HTTPS
4. Add rate limiting
