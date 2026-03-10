#!/usr/bin/env node
/**
 * Minimal transparent CORS proxy.
 *
 * Zero dependencies — uses only Node.js built-in `http` and `https`.
 * Forwards all requests to the target URL with CORS headers added.
 * No logic, no filtering, no caching — purely transparent relay.
 *
 * Usage:
 *   node cors-proxy.js                     # port 9090
 *   PORT=8080 node cors-proxy.js           # custom port
 *
 * Request format:
 *   POST http://localhost:9090/https://api.openai.com/v1/chat/completions
 *   The target URL is the path after the leading slash.
 *
 * How it works:
 *   Browser → http://localhost:9090/https://api.openai.com/v1/chat/completions
 *   Proxy   → https://api.openai.com/v1/chat/completions  (forwards request)
 *   Proxy   ← response from OpenAI
 *   Browser ← response + CORS headers
 */

const http = require('http');
const https = require('https');
const { URL } = require('url');

const PORT = parseInt(process.env.PORT || '9090', 10);

/**
 * Add CORS headers to a response.
 */
function setCorsHeaders(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, PATCH, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', '*');
  res.setHeader('Access-Control-Expose-Headers', '*');
  res.setHeader('Access-Control-Max-Age', '86400');
}

const server = http.createServer((req, res) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    setCorsHeaders(res);
    res.writeHead(204);
    res.end();
    return;
  }

  // Extract target URL from the request path (strip leading slash)
  const targetUrl = req.url.substring(1);

  if (!targetUrl || (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://'))) {
    setCorsHeaders(res);
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      error: 'Missing target URL. Format: http://localhost:' + PORT + '/https://api.example.com/path',
    }));
    return;
  }

  let parsed;
  try {
    parsed = new URL(targetUrl);
  } catch {
    setCorsHeaders(res);
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Invalid target URL: ' + targetUrl }));
    return;
  }

  // Forward headers, removing host (will be set by the target)
  const forwardHeaders = { ...req.headers };
  delete forwardHeaders.host;
  delete forwardHeaders.origin;
  delete forwardHeaders.referer;

  const transport = parsed.protocol === 'https:' ? https : http;

  const options = {
    hostname: parsed.hostname,
    port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
    path: parsed.pathname + parsed.search,
    method: req.method,
    headers: forwardHeaders,
  };

  const proxyReq = transport.request(options, (proxyRes) => {
    setCorsHeaders(res);

    // Forward status and headers (except hop-by-hop)
    const responseHeaders = { ...proxyRes.headers };
    delete responseHeaders['transfer-encoding']; // let Node handle chunking
    for (const [key, value] of Object.entries(responseHeaders)) {
      if (key.toLowerCase() !== 'access-control-allow-origin') {
        res.setHeader(key, value);
      }
    }

    res.writeHead(proxyRes.statusCode);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    setCorsHeaders(res);
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Proxy error: ' + err.message }));
  });

  // Pipe request body to proxy
  req.pipe(proxyReq);
});

server.listen(PORT, () => {
  console.log(`CORS proxy listening on http://localhost:${PORT}`);
  console.log(`Usage: http://localhost:${PORT}/https://api.openai.com/v1/chat/completions`);
  console.log('');
  console.log('All requests are forwarded transparently with CORS headers added.');
  console.log('Press Ctrl+C to stop.');
});
