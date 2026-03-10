#!/usr/bin/env node
/**
 * Convenience launcher for the ModelMesh CORS proxy.
 *
 * Run this script alongside `index.html` to enable browser-based chat
 * with AI providers that don't send CORS headers (most of them).
 *
 * Usage:
 *   node proxy-server.js            # starts on port 9090
 *   PORT=8080 node proxy-server.js  # custom port
 *
 * Then open index.html in your browser and set the CORS Proxy URL
 * field to http://localhost:9090 (or your custom port).
 *
 * How it works:
 *   Browser  POST http://localhost:9090/https://api.openai.com/v1/chat/completions
 *     └──→  Proxy forwards to https://api.openai.com/v1/chat/completions
 *     ←──   Proxy relays the response with CORS headers added
 *
 * This is a development-only proxy. For production deployments, see
 * docs/guides/BrowserUsage.md.
 */

const path = require('path');

// Resolve the shared CORS proxy script relative to this sample
const corsProxyPath = path.resolve(__dirname, '../../tools/cors-proxy/cors-proxy.js');

try {
  require(corsProxyPath);
} catch (err) {
  console.error('Failed to start CORS proxy.');
  console.error(`Expected script at: ${corsProxyPath}`);
  console.error('');
  console.error('Make sure you are running from the ModelMesh repository root');
  console.error('or that tools/cors-proxy/cors-proxy.js exists.');
  console.error('');
  console.error('Original error:', err.message);
  process.exit(1);
}
