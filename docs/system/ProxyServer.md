# ProxyServer

Standalone HTTP server exposing standard OpenAI API endpoints. The proxy wraps the Router for deployment as a shared service, allowing multiple applications -- LangChain pipelines, IDE assistants, internal tools -- to connect to a single proxy with centralized configuration, credential management, and state. Authentication, CORS, and endpoint filtering are configurable.

**Depends on:** [Router](Router.md), [ModelMesh](ModelMesh.md)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


@dataclass
class ServerStatus:
    """Runtime status of the proxy server."""
    running: bool
    host: str
    port: int
    uptime_seconds: float
    active_connections: int
    total_requests: int


class ProxyServer:
    """Standalone HTTP server exposing OpenAI API endpoints.

    Wraps the Router for deployment as a shared service. Multiple
    applications connect to a single proxy with centralized configuration,
    credential management, and state.
    """

    def __init__(self, mesh: Any) -> None:
        """Initialize the proxy server with a ModelMesh instance.

        Args:
            mesh: The ModelMesh facade instance that provides the
                Router and configuration context.
        """
        ...

    async def start(self) -> None:
        """Start the HTTP server on the configured host and port.

        Binds to the address specified in configuration and begins
        accepting requests on enabled endpoints. Blocks until the
        server is fully ready to accept connections.
        """
        ...

    async def stop(self) -> None:
        """Gracefully shut down the server.

        Waits for active connections to complete, flushes state and
        statistics, and releases the bound port.
        """
        ...

    def get_status(self) -> ServerStatus:
        """Return current server status.

        Returns:
            A ServerStatus with runtime information including uptime,
            active connections, and total requests served.
        """
        ...
```

## TypeScript

```typescript
/** Runtime status of the proxy server. */
interface ServerStatus {
    running: boolean;
    host: string;
    port: number;
    uptime_seconds: number;
    active_connections: number;
    total_requests: number;
}

/** Standalone HTTP server exposing OpenAI API endpoints. */
class ProxyServer {
    /**
     * Initialize the proxy server with a ModelMesh instance.
     */
    constructor(mesh: unknown) {}

    /** Start the HTTP server on the configured host and port. */
    async start(): Promise<void> {
        throw new Error("Not implemented");
    }

    /** Gracefully shut down the server. */
    async stop(): Promise<void> {
        throw new Error("Not implemented");
    }

    /** Return current server status. */
    getStatus(): ServerStatus {
        throw new Error("Not implemented");
    }
}
```

---

## Endpoints

| Path | Method | Description |
| --- | --- | --- |
| `/v1/chat/completions` | POST | Chat completion (synchronous and streaming). |
| `/v1/embeddings` | POST | Embedding generation. |
| `/v1/audio/speech` | POST | Text-to-speech generation. |
| `/v1/audio/transcriptions` | POST | Speech-to-text transcription. |
| `/v1/images/generations` | POST | Image generation. |
| `/v1/models` | GET | List available virtual model names and their pools. |

---

## Configuration

See [SystemConfiguration.md -- Proxy](../SystemConfiguration.md#proxy) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `proxy.host` | string | Bind address (e.g., `0.0.0.0`). |
| `proxy.port` | integer | Listen port (e.g., `8080`). |
| `proxy.endpoints` | list | Enabled endpoint paths (e.g., `["/v1/chat/completions", "/v1/models"]`). |
| `proxy.auth.enabled` | boolean | Require authentication for proxy requests. |
| `proxy.auth.method` | string | Authentication method (e.g., `bearer`). |
| `proxy.auth.tokens` | list | Allowed bearer tokens for request authentication. |
| `proxy.cors.enabled` | boolean | Enable CORS headers on responses. |
| `proxy.cors.origins` | list | Allowed origins for CORS requests. |
