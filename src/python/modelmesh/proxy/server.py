"""ProxyServer -- OpenAI-compatible HTTP proxy backed by ModelMesh.

Implements a zero-dependency HTTP server (stdlib ``http.server``) that
translates incoming OpenAI REST API requests into ModelMesh routing
calls. Supports chat completions (streaming and non-streaming), models
listing, embeddings, audio speech, and audio transcriptions.

The server is intentionally synchronous at the HTTP layer (using
``http.server.HTTPServer``) while delegating to the async ModelMesh
routing pipeline via ``_run_sync``.
"""
from __future__ import annotations

import json
import logging
import signal
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from modelmesh._sync import _run_sync
from modelmesh.config.mesh_config import MeshConfig
from modelmesh.core.mesh import ModelMesh
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
)

logger = logging.getLogger("modelmesh.proxy")

__all__ = ["ProxyServer", "ServerStatus", "RateLimitConfig"]

_VERSION = "0.1.1"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


@dataclass
class RateLimitConfig:
    """Token-bucket rate limiter configuration.

    Attributes:
        requests_per_minute: Maximum sustained request rate.
        burst_size: Maximum burst size above sustained rate.
        per_ip: If True, limits are applied per client IP.
    """

    requests_per_minute: int = 60
    burst_size: int = 20
    per_ip: bool = True


class _TokenBucket:
    """Simple token-bucket rate limiter."""

    def __init__(self, rpm: int, burst: int) -> None:
        self._rate = rpm / 60.0  # tokens per second
        self._burst = burst
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        """Return True if a request is allowed."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(
                self._burst, self._tokens + elapsed * self._rate
            )
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def retry_after(self) -> float:
        """Return seconds until next token is available."""
        with self._lock:
            if self._tokens >= 1.0:
                return 0.0
            return (1.0 - self._tokens) / self._rate


class _RateLimiter:
    """Per-key rate limiter using token buckets."""

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str = "global") -> bool:
        bucket = self._get_bucket(key)
        return bucket.allow()

    def retry_after(self, key: str = "global") -> float:
        bucket = self._get_bucket(key)
        return bucket.retry_after()

    def _get_bucket(self, key: str) -> _TokenBucket:
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = _TokenBucket(
                    self._config.requests_per_minute,
                    self._config.burst_size,
                )
            return self._buckets[key]


# ---------------------------------------------------------------------------
# Status dataclass
# ---------------------------------------------------------------------------


@dataclass
class ServerStatus:
    """Snapshot of the proxy server's operational state.

    Attributes:
        running: Whether the server is currently accepting requests.
        host: The bind address.
        port: The listening port.
        uptime_seconds: Seconds since the server was started.
        active_connections: Number of requests currently in flight.
        total_requests: Total requests served since start.
    """

    running: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    uptime_seconds: float = 0.0
    active_connections: int = 0
    total_requests: int = 0


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class _ProxyRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler that translates OpenAI API calls to ModelMesh.

    Instance attributes ``server`` is the ``_MeshHTTPServer`` which
    carries a reference to the shared ``_ProxyState``.
    """

    # Suppress default stderr logging from BaseHTTPRequestHandler
    def log_message(self, format, *args):  # noqa: A002
        logger.debug(format, *args)

    # -- Lifecycle bookkeeping -----------------------------------------------

    def _begin_request(self) -> None:
        state = self.server.proxy_state  # type: ignore[attr-defined]
        # Generate or pass through request ID
        self._request_id = (
            self.headers.get("X-Request-Id") or uuid.uuid4().hex
        )
        with state.lock:
            state.active_connections += 1
            state.total_requests += 1

    def _end_request(self) -> None:
        state = self.server.proxy_state  # type: ignore[attr-defined]
        with state.lock:
            state.active_connections -= 1

    def _check_rate_limit(self) -> bool:
        """Return True if request is within rate limits."""
        state = self.server.proxy_state  # type: ignore[attr-defined]
        if state.rate_limiter is None:
            return True
        key = self.client_address[0] if state.rate_limit_config.per_ip else "global"
        if not state.rate_limiter.allow(key):
            retry = state.rate_limiter.retry_after(key)
            self.send_response(429)
            self.send_header("Retry-After", str(int(retry) + 1))
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            payload = json.dumps({
                "error": {
                    "message": "Rate limit exceeded",
                    "type": "rate_limit_error",
                    "code": 429,
                }
            }).encode()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return False
        return True

    # -- CORS helpers --------------------------------------------------------

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization",
        )

    # -- Auth ----------------------------------------------------------------

    def _check_auth(self) -> bool:
        """Validate bearer token if one is configured.

        Returns ``True`` if the request is authorized, ``False``
        otherwise (and sends a 401 response).
        """
        state = self.server.proxy_state  # type: ignore[attr-defined]
        expected = state.auth_token
        if expected is None:
            return True

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header

        if token == expected:
            return True

        self._send_json_error(401, "Invalid or missing bearer token")
        return False

    # -- Response helpers ----------------------------------------------------

    def _send_json_response(
        self, status: int, body: dict | list
    ) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Request-Id", getattr(self, "_request_id", ""))
        self._send_cors_headers()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json_error(self, status: int, message: str) -> None:
        self._send_json_response(
            status,
            {
                "error": {
                    "message": message,
                    "type": "error",
                    "code": status,
                    "request_id": getattr(self, "_request_id", ""),
                }
            },
        )

    def _read_json_body(self) -> Optional[dict]:
        """Read and parse the JSON request body.

        Returns ``None`` and sends a 400 error if parsing fails.
        """
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            self._send_json_error(400, "Empty request body")
            return None

        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_json_error(400, f"Invalid JSON: {exc}")
            return None

    # -- HTTP verbs ----------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._begin_request()
        try:
            if not self._check_rate_limit():
                return

            # Health/ready/metrics don't require auth
            if self.path == "/health":
                self._handle_health()
                return
            if self.path == "/ready":
                self._handle_ready()
                return
            if self.path == "/metrics":
                self._handle_metrics()
                return
            if self.path == "/":
                self._handle_info()
                return

            if not self._check_auth():
                return

            if self.path == "/v1/models":
                self._handle_models()
            elif self.path.startswith("/v1/models/"):
                model_id = self.path[len("/v1/models/"):]
                self._handle_model_detail(model_id)
            else:
                self._send_json_error(404, f"Not found: {self.path}")
        except Exception as exc:
            logger.exception("Unhandled error in GET %s", self.path)
            self._send_json_error(500, str(exc))
        finally:
            self._end_request()

    def do_POST(self) -> None:  # noqa: N802
        self._begin_request()
        try:
            if not self._check_rate_limit():
                return
            if not self._check_auth():
                return
            # Check body size limit (10 MB default)
            length = int(self.headers.get("Content-Length", 0))
            state = self.server.proxy_state  # type: ignore[attr-defined]
            if length > state.max_body_size:
                self._send_json_error(413, "Request body too large")
                return

            if self.path == "/v1/chat/completions":
                self._handle_chat_completions()
            elif self.path == "/v1/embeddings":
                self._handle_embeddings()
            elif self.path == "/v1/audio/speech":
                self._handle_audio_speech()
            elif self.path == "/v1/audio/transcriptions":
                self._handle_audio_transcriptions()
            else:
                self._send_json_error(404, f"Not found: {self.path}")
        except Exception as exc:
            logger.exception("Unhandled error in POST %s", self.path)
            self._send_json_error(500, str(exc))
        finally:
            self._end_request()

    # -- Endpoint handlers ---------------------------------------------------

    def _handle_health(self) -> None:
        state = self.server.proxy_state  # type: ignore[attr-defined]
        uptime = time.time() - state.start_time if state.start_time else 0
        self._send_json_response(200, {
            "status": "healthy",
            "uptime": round(uptime, 2),
            "version": _VERSION,
        })

    def _handle_ready(self) -> None:
        state = self.server.proxy_state  # type: ignore[attr-defined]
        mesh = state.mesh
        pools = mesh.pools
        providers = mesh.providers
        models = mesh.list_models()
        self._send_json_response(200, {
            "ready": True,
            "pools": len(pools),
            "providers": len(providers),
            "models": len(models),
        })

    def _handle_metrics(self) -> None:
        state = self.server.proxy_state  # type: ignore[attr-defined]
        obs = state.mesh.observability
        # Check if it's a PrometheusConnector
        if hasattr(obs, "render_metrics"):
            text = obs.render_metrics()
            payload = text.encode("utf-8")
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain; version=0.0.4; charset=utf-8",
            )
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self._send_json_response(200, {
                "message": "Prometheus connector not configured. "
                "Set observability.connector to "
                "modelmesh.prometheus.v1 for metrics."
            })

    def _handle_info(self) -> None:
        self._send_json_response(200, {
            "name": "ModelMesh Proxy",
            "version": _VERSION,
            "endpoints": [
                "GET /health",
                "GET /ready",
                "GET /metrics",
                "GET /v1/models",
                "GET /v1/models/{id}",
                "POST /v1/chat/completions",
                "POST /v1/embeddings",
                "POST /v1/audio/speech",
                "POST /v1/audio/transcriptions",
            ],
        })

    def _handle_model_detail(self, model_id: str) -> None:
        """GET /v1/models/{id} -- retrieve a single model."""
        state = self.server.proxy_state  # type: ignore[attr-defined]
        mesh = state.mesh
        models = mesh.list_models()
        for m in models:
            if m["id"] == model_id:
                m["created"] = int(state.start_time) if state.start_time else 0
                self._send_json_response(200, m)
                return
        self._send_json_error(404, f"Model '{model_id}' not found")

    def _handle_models(self) -> None:
        """GET /v1/models -- list virtual models (pool IDs)."""
        state = self.server.proxy_state  # type: ignore[attr-defined]
        mesh = state.mesh

        pools = mesh.pools
        models = []
        created_ts = int(state.start_time) if state.start_time else 0
        for pool_id in pools:
            models.append(
                {
                    "id": pool_id,
                    "object": "model",
                    "created": created_ts,
                    "owned_by": "modelmesh",
                }
            )

        self._send_json_response(
            200,
            {
                "object": "list",
                "data": models,
            },
        )

    def _handle_chat_completions(self) -> None:
        """POST /v1/chat/completions -- route through ModelMesh."""
        body = self._read_json_body()
        if body is None:
            return

        model = body.get("model", "")
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        temperature = body.get("temperature", 1.0)
        max_tokens = body.get("max_tokens")
        top_p = body.get("top_p", 1.0)
        stop = body.get("stop")
        tools = body.get("tools")

        if not model:
            self._send_json_error(400, "Missing required field: model")
            return
        if not messages:
            self._send_json_error(400, "Missing required field: messages")
            return

        state = self.server.proxy_state  # type: ignore[attr-defined]
        mesh = state.mesh

        request = CompletionRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            tools=tools,
            top_p=top_p,
            stop=stop,
        )

        if stream:
            self._stream_chat_response(mesh, request)
        else:
            self._non_stream_chat_response(mesh, request)

    def _non_stream_chat_response(
        self, mesh: ModelMesh, request: CompletionRequest
    ) -> None:
        """Route a non-streaming chat request and return the response."""
        try:
            response: CompletionResponse = _run_sync(mesh.route(request))
        except RuntimeError as exc:
            self._send_json_error(502, f"Routing error: {exc}")
            return

        resp_dict = _completion_response_to_dict(response)
        self._send_json_response(200, resp_dict)

    def _stream_chat_response(
        self, mesh: ModelMesh, request: CompletionRequest
    ) -> None:
        """Route a streaming chat request and emit SSE chunks.

        Writes each chunk to the wire as it arrives from the async
        generator, providing true real-time streaming to the client.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self._send_cors_headers()
        self.end_headers()

        wfile = self.wfile

        def _write_chunk(data: bytes) -> None:
            """Write a single chunk using HTTP chunked transfer encoding."""
            wfile.write(f"{len(data):x}\r\n".encode("utf-8"))
            wfile.write(data)
            wfile.write(b"\r\n")
            wfile.flush()

        try:
            async def _stream_and_write():
                async for chunk in mesh.route_stream(request):
                    chunk_dict = _completion_response_to_dict(chunk)
                    chunk_dict["object"] = "chat.completion.chunk"
                    data_line = f"data: {json.dumps(chunk_dict)}\n\n"
                    _write_chunk(data_line.encode("utf-8"))

            _run_sync(_stream_and_write())

            # Send [DONE] marker
            _write_chunk(b"data: [DONE]\n\n")

            # Chunked transfer terminator
            wfile.write(b"0\r\n\r\n")
            wfile.flush()

        except Exception as exc:
            logger.exception("Streaming error")
            # Attempt to send an error chunk
            try:
                err = json.dumps({"error": {"message": str(exc)}})
                err_line = f"data: {err}\n\n".encode("utf-8")
                _write_chunk(err_line)
                wfile.write(b"0\r\n\r\n")
                wfile.flush()
            except Exception:
                pass

    def _handle_embeddings(self) -> None:
        """POST /v1/embeddings -- route through ModelMesh."""
        body = self._read_json_body()
        if body is None:
            return

        model = body.get("model", "")
        input_data = body.get("input", "")

        if not model:
            self._send_json_error(400, "Missing required field: model")
            return

        # Normalize input
        if isinstance(input_data, str):
            input_data = [input_data]

        state = self.server.proxy_state  # type: ignore[attr-defined]
        mesh = state.mesh

        request = CompletionRequest(
            model=model,
            messages=[
                {"role": "user", "content": text} for text in input_data
            ],
            temperature=0.0,
        )

        try:
            response = _run_sync(mesh.route(request))
        except RuntimeError as exc:
            self._send_json_error(502, f"Routing error: {exc}")
            return

        resp_dict = _completion_response_to_dict(response)
        self._send_json_response(200, resp_dict)

    def _handle_audio_speech(self) -> None:
        """POST /v1/audio/speech -- route through ModelMesh."""
        body = self._read_json_body()
        if body is None:
            return

        model = body.get("model", "")
        text_input = body.get("input", "")

        if not model:
            self._send_json_error(400, "Missing required field: model")
            return

        state = self.server.proxy_state  # type: ignore[attr-defined]
        mesh = state.mesh

        request = CompletionRequest(
            model=model,
            messages=[{"role": "user", "content": text_input}],
        )

        try:
            response = _run_sync(mesh.route(request))
        except RuntimeError as exc:
            self._send_json_error(502, f"Routing error: {exc}")
            return

        resp_dict = _completion_response_to_dict(response)
        self._send_json_response(200, resp_dict)

    def _handle_audio_transcriptions(self) -> None:
        """POST /v1/audio/transcriptions -- route through ModelMesh."""
        body = self._read_json_body()
        if body is None:
            return

        model = body.get("model", "")

        if not model:
            self._send_json_error(400, "Missing required field: model")
            return

        state = self.server.proxy_state  # type: ignore[attr-defined]
        mesh = state.mesh

        request = CompletionRequest(
            model=model,
            messages=[{"role": "user", "content": body.get("text", "")}],
        )

        try:
            response = _run_sync(mesh.route(request))
        except RuntimeError as exc:
            self._send_json_error(502, f"Routing error: {exc}")
            return

        resp_dict = _completion_response_to_dict(response)
        self._send_json_response(200, resp_dict)


# ---------------------------------------------------------------------------
# Shared server state
# ---------------------------------------------------------------------------


@dataclass
class _ProxyState:
    """Mutable state shared between the request handler and ProxyServer."""

    mesh: ModelMesh
    auth_token: Optional[str] = None
    host: str = "0.0.0.0"
    port: int = 8080
    start_time: Optional[float] = None
    active_connections: int = 0
    total_requests: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    rate_limiter: Optional[_RateLimiter] = None
    rate_limit_config: Optional[RateLimitConfig] = None
    max_body_size: int = 10 * 1024 * 1024  # 10 MB

    def get_status(self) -> ServerStatus:
        uptime = (
            time.time() - self.start_time
            if self.start_time is not None
            else 0.0
        )
        with self.lock:
            return ServerStatus(
                running=self.start_time is not None,
                host=self.host,
                port=self.port,
                uptime_seconds=round(uptime, 2),
                active_connections=self.active_connections,
                total_requests=self.total_requests,
            )


# ---------------------------------------------------------------------------
# Custom HTTPServer subclass to carry state
# ---------------------------------------------------------------------------


class _MeshHTTPServer(HTTPServer):
    """HTTPServer subclass that carries the shared proxy state."""

    def __init__(
        self,
        server_address: tuple,
        handler_class: type,
        proxy_state: _ProxyState,
    ) -> None:
        self.proxy_state = proxy_state
        super().__init__(server_address, handler_class)


# ---------------------------------------------------------------------------
# ProxyServer
# ---------------------------------------------------------------------------


class ProxyServer:
    """OpenAI-compatible HTTP proxy server backed by ModelMesh.

    Wraps a stdlib ``HTTPServer`` and translates OpenAI REST API
    requests into ModelMesh routing calls. Zero external dependencies.

    Args:
        config: A ``MeshConfig`` instance, a raw dict, or a path to a
            YAML configuration file.
        host: Bind address. Default ``"0.0.0.0"``.
        port: Listen port. Default ``8080``.
        token: Optional bearer token for authentication. When set,
            all requests must include ``Authorization: Bearer <token>``.

    Usage::

        server = ProxyServer(config="modelmesh.yaml", port=8080)
        server.start()          # blocks
        # or
        server.start(block=False)  # runs in background thread
        server.stop()
    """

    def __init__(
        self,
        config: MeshConfig | dict | str,
        host: str = "0.0.0.0",
        port: int = 8080,
        token: Optional[str] = None,
        rate_limit: Optional[RateLimitConfig] = None,
        max_body_size: int = 10 * 1024 * 1024,
    ) -> None:
        # Resolve config
        if isinstance(config, str):
            mesh_config = MeshConfig.from_yaml(config)
        elif isinstance(config, dict):
            mesh_config = MeshConfig.from_dict(config)
        elif isinstance(config, MeshConfig):
            mesh_config = config
        else:
            raise TypeError(
                f"config must be str, dict, or MeshConfig, got "
                f"{type(config).__name__}"
            )

        # Initialize ModelMesh
        self._mesh = ModelMesh()
        self._mesh.initialize(mesh_config)

        self._host = host
        self._port = port
        self._token = token

        rl = _RateLimiter(rate_limit) if rate_limit else None
        self._state = _ProxyState(
            mesh=self._mesh,
            auth_token=token,
            host=host,
            port=port,
            rate_limiter=rl,
            rate_limit_config=rate_limit,
            max_body_size=max_body_size,
        )
        self._httpd: Optional[_MeshHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._shutting_down = False

    @property
    def mesh(self) -> ModelMesh:
        """The underlying ModelMesh instance."""
        return self._mesh

    def start(self, block: bool = True) -> None:
        """Start the HTTP server.

        Args:
            block: If ``True`` (default), block the calling thread.
                If ``False``, run in a daemon background thread.
        """
        self._httpd = _MeshHTTPServer(
            (self._host, self._port),
            _ProxyRequestHandler,
            self._state,
        )
        self._state.start_time = time.time()

        logger.info(
            "ModelMesh proxy listening on %s:%d", self._host, self._port
        )

        # Register signal handlers for graceful shutdown
        def _graceful_shutdown(signum, frame):
            logger.info("Received signal %d, initiating graceful shutdown", signum)
            self._shutting_down = True
            threading.Thread(target=self.stop, daemon=True).start()

        signal.signal(signal.SIGTERM, _graceful_shutdown)

        if block:
            try:
                self._httpd.serve_forever()
            except KeyboardInterrupt:
                logger.info("Shutting down proxy server")
            finally:
                self.stop()
        else:
            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 30.0) -> None:
        """Stop the HTTP server and shut down the mesh.

        Waits up to *timeout* seconds for in-flight requests to
        complete before forcing shutdown.
        """
        self._shutting_down = True
        logger.info("Stopping proxy server (waiting for in-flight requests)...")

        # Wait for in-flight requests
        deadline = time.time() + timeout
        while self._state.active_connections > 0 and time.time() < deadline:
            time.sleep(0.1)

        if self._state.active_connections > 0:
            logger.warning(
                "Forcing shutdown with %d in-flight requests",
                self._state.active_connections,
            )

        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        self._state.start_time = None
        self._mesh.shutdown()
        logger.info("ModelMesh proxy stopped")

    def get_status(self) -> ServerStatus:
        """Return a snapshot of the server's operational state."""
        return self._state.get_status()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _completion_response_to_dict(resp: CompletionResponse) -> dict:
    """Convert a CompletionResponse dataclass to an OpenAI-compatible dict."""
    choices = []
    for choice in resp.choices:
        c: dict = {"index": choice.index, "finish_reason": choice.finish_reason}
        if choice.message is not None:
            c["message"] = {
                "role": choice.message.role,
                "content": choice.message.content,
            }
            if choice.message.tool_calls is not None:
                c["message"]["tool_calls"] = choice.message.tool_calls
        if choice.delta is not None:
            c["delta"] = {
                "role": choice.delta.role,
                "content": choice.delta.content,
            }
            if choice.delta.tool_calls is not None:
                c["delta"]["tool_calls"] = choice.delta.tool_calls
        choices.append(c)

    return {
        "id": resp.id or f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": resp.object,
        "created": resp.created or int(time.time()),
        "model": resp.model,
        "choices": choices,
        "usage": {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        },
    }
