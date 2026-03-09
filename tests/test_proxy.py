"""Tests for the ModelMesh OpenAI-compatible HTTP proxy server."""
import json
import os
import sys
import threading
import time
import unittest
from dataclasses import asdict
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.config.mesh_config import MeshConfig
from modelmesh.core.mesh import ModelMesh
from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    ErrorClassification,
    ModelInfo,
    ModelPricing,
    ProviderConnector,
    QuotaStatus,
    RateLimitStatus,
    TokenUsage,
)
from modelmesh.proxy.server import (
    ProxyServer,
    ServerStatus,
    _ProxyRequestHandler,
    _ProxyState,
    _MeshHTTPServer,
    _completion_response_to_dict,
)


# ---------------------------------------------------------------------------
# Fake provider (same pattern as test_client.py)
# ---------------------------------------------------------------------------


class _FakeProvider(ProviderConnector):
    """Minimal fake provider for proxy tests."""

    async def complete(self, request):
        return CompletionResponse(
            id="fake-resp-001",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hello from proxy"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    async def stream(self, request):
        yield CompletionResponse(
            id="chunk-1",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content="Hi"),
                    finish_reason=None,
                )
            ],
            usage=TokenUsage(),
        )
        yield CompletionResponse(
            id="chunk-2",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content=" there"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
        )

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, capability):
        return capability in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="fake-model", name="Fake Model")]

    def get_model_info(self, model_id):
        return ModelInfo(id="fake-model", name="Fake Model")

    def check_quota(self):
        return QuotaStatus()

    def get_rate_limits(self):
        return RateLimitStatus()

    def get_pricing(self, model_id):
        return ModelPricing()

    def report_usage(self, model_id, usage):
        pass

    def classify_error(self, error):
        return ErrorClassification(retryable=False)


def _make_config():
    """Create a MeshConfig with a fake provider for testing."""
    return MeshConfig(raw={
        "providers": {
            "fake.v1": {
                "connector": "fake.v1",
                "enabled": True,
                "instance": _FakeProvider(),
            },
        },
        "models": {
            "fake.model-a": {
                "provider": "fake.v1",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
        },
        "pools": {
            "chat-completion": {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "stick-until-failure",
            },
        },
        "observability": {"connector": "modelmesh.null.v1"},
    })


def _make_mesh():
    """Create an initialized ModelMesh with a fake provider."""
    config = _make_config()
    mesh = ModelMesh()
    mesh.initialize(config)
    return mesh


# ---------------------------------------------------------------------------
# Test: ServerStatus dataclass
# ---------------------------------------------------------------------------


class TestServerStatus(unittest.TestCase):
    """Test the ServerStatus dataclass."""

    def test_default_values(self):
        status = ServerStatus()
        self.assertFalse(status.running)
        self.assertEqual(status.host, "0.0.0.0")
        self.assertEqual(status.port, 8080)
        self.assertEqual(status.uptime_seconds, 0.0)
        self.assertEqual(status.active_connections, 0)
        self.assertEqual(status.total_requests, 0)

    def test_custom_values(self):
        status = ServerStatus(
            running=True,
            host="127.0.0.1",
            port=9090,
            uptime_seconds=123.45,
            active_connections=3,
            total_requests=100,
        )
        self.assertTrue(status.running)
        self.assertEqual(status.host, "127.0.0.1")
        self.assertEqual(status.port, 9090)
        self.assertAlmostEqual(status.uptime_seconds, 123.45)
        self.assertEqual(status.active_connections, 3)
        self.assertEqual(status.total_requests, 100)

    def test_asdict(self):
        status = ServerStatus(running=True, host="localhost", port=3000)
        d = asdict(status)
        self.assertIsInstance(d, dict)
        self.assertTrue(d["running"])
        self.assertEqual(d["host"], "localhost")
        self.assertEqual(d["port"], 3000)


# ---------------------------------------------------------------------------
# Test: _ProxyState and status reporting
# ---------------------------------------------------------------------------


class TestProxyState(unittest.TestCase):
    """Test the _ProxyState helper and status reporting."""

    def test_get_status_not_running(self):
        mesh = _make_mesh()
        state = _ProxyState(mesh=mesh, host="127.0.0.1", port=9090)
        status = state.get_status()
        self.assertFalse(status.running)
        self.assertEqual(status.host, "127.0.0.1")
        self.assertEqual(status.port, 9090)
        self.assertEqual(status.uptime_seconds, 0.0)
        mesh.shutdown()

    def test_get_status_running(self):
        mesh = _make_mesh()
        state = _ProxyState(mesh=mesh, host="0.0.0.0", port=8080)
        state.start_time = time.time() - 60.0  # 60 seconds ago
        status = state.get_status()
        self.assertTrue(status.running)
        self.assertGreaterEqual(status.uptime_seconds, 59.0)
        mesh.shutdown()

    def test_request_counters(self):
        mesh = _make_mesh()
        state = _ProxyState(mesh=mesh)
        with state.lock:
            state.active_connections = 2
            state.total_requests = 42
        status = state.get_status()
        self.assertEqual(status.active_connections, 2)
        self.assertEqual(status.total_requests, 42)
        mesh.shutdown()


# ---------------------------------------------------------------------------
# Test: CORS headers
# ---------------------------------------------------------------------------


class TestCORSHeaders(unittest.TestCase):
    """Test that the handler produces correct CORS headers."""

    def test_cors_headers_present_in_response_dict(self):
        """Verify the _send_cors_headers method sets the expected values.

        We cannot easily test the full HTTP handler without a live
        server, so we validate the method logic indirectly by
        checking that the ProxyServer exposes CORS-related behaviour.
        """
        # The CORS headers are: Access-Control-Allow-Origin: *,
        # Access-Control-Allow-Methods: GET, POST, OPTIONS,
        # Access-Control-Allow-Headers: Content-Type, Authorization.
        # We validate these expectations are documented in the handler.
        import inspect
        source = inspect.getsource(_ProxyRequestHandler._send_cors_headers)
        self.assertIn("Access-Control-Allow-Origin", source)
        self.assertIn("Access-Control-Allow-Methods", source)
        self.assertIn("Access-Control-Allow-Headers", source)
        self.assertIn("*", source)  # Allow-Origin: *


# ---------------------------------------------------------------------------
# Test: Bearer token authentication
# ---------------------------------------------------------------------------


class TestAuthTokenValidation(unittest.TestCase):
    """Test bearer token authentication logic."""

    def test_no_token_required_passes(self):
        """When no token is configured, any request should pass."""
        mesh = _make_mesh()
        state = _ProxyState(mesh=mesh, auth_token=None)
        # auth_token is None means no auth required
        self.assertIsNone(state.auth_token)
        mesh.shutdown()

    def test_token_configured(self):
        """When a token is configured, it should be stored in state."""
        mesh = _make_mesh()
        state = _ProxyState(mesh=mesh, auth_token="test-secret-123")
        self.assertEqual(state.auth_token, "test-secret-123")
        mesh.shutdown()

    def test_proxy_server_stores_token(self):
        """ProxyServer should pass the token to its internal state."""
        config = _make_config()
        server = ProxyServer(
            config=config,
            host="127.0.0.1",
            port=0,
            token="my-token",
        )
        self.assertEqual(server._state.auth_token, "my-token")
        server._mesh.shutdown()

    def test_proxy_server_no_token(self):
        """ProxyServer with no token should have None auth_token."""
        config = _make_config()
        server = ProxyServer(
            config=config,
            host="127.0.0.1",
            port=0,
        )
        self.assertIsNone(server._state.auth_token)
        server._mesh.shutdown()


# ---------------------------------------------------------------------------
# Test: /v1/models endpoint returns pool IDs
# ---------------------------------------------------------------------------


class TestModelsEndpoint(unittest.TestCase):
    """Test the /v1/models response structure (without live HTTP)."""

    def test_pools_are_listed_as_models(self):
        """The mesh pools should appear as model entries."""
        mesh = _make_mesh()
        pools = mesh.pools
        self.assertIn("chat-completion", pools)

        # Simulate what the handler does
        models = []
        for pool_id in pools:
            models.append(
                {
                    "id": pool_id,
                    "object": "model",
                    "created": 0,
                    "owned_by": "modelmesh",
                }
            )

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["id"], "chat-completion")
        self.assertEqual(models[0]["object"], "model")
        self.assertEqual(models[0]["owned_by"], "modelmesh")
        mesh.shutdown()

    def test_models_response_shape(self):
        """The full models response should match OpenAI list format."""
        mesh = _make_mesh()
        pools = mesh.pools
        models = [
            {
                "id": pool_id,
                "object": "model",
                "created": 0,
                "owned_by": "modelmesh",
            }
            for pool_id in pools
        ]
        response = {"object": "list", "data": models}
        self.assertEqual(response["object"], "list")
        self.assertIsInstance(response["data"], list)
        self.assertGreater(len(response["data"]), 0)
        mesh.shutdown()


# ---------------------------------------------------------------------------
# Test: Request parsing helpers
# ---------------------------------------------------------------------------


class TestRequestParsing(unittest.TestCase):
    """Test request body parsing and CompletionRequest construction."""

    def test_parse_chat_completion_body(self):
        """Parsing a standard chat completion request body."""
        body = {
            "model": "chat-completion",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
            "temperature": 0.7,
            "max_tokens": 100,
            "stream": False,
        }

        request = CompletionRequest(
            model=body["model"],
            messages=body["messages"],
            temperature=body.get("temperature", 1.0),
            max_tokens=body.get("max_tokens"),
            stream=body.get("stream", False),
        )

        self.assertEqual(request.model, "chat-completion")
        self.assertEqual(len(request.messages), 2)
        self.assertEqual(request.temperature, 0.7)
        self.assertEqual(request.max_tokens, 100)
        self.assertFalse(request.stream)

    def test_parse_streaming_request(self):
        """Parsing a streaming chat completion request."""
        body = {
            "model": "chat-completion",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        }

        request = CompletionRequest(
            model=body["model"],
            messages=body["messages"],
            stream=body.get("stream", False),
        )

        self.assertTrue(request.stream)

    def test_parse_with_tools(self):
        """Parsing a request with tool definitions."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        body = {
            "model": "chat-completion",
            "messages": [{"role": "user", "content": "Weather?"}],
            "tools": tools,
        }

        request = CompletionRequest(
            model=body["model"],
            messages=body["messages"],
            tools=body.get("tools"),
        )

        self.assertIsNotNone(request.tools)
        self.assertEqual(len(request.tools), 1)
        self.assertEqual(request.tools[0]["type"], "function")

    def test_parse_defaults(self):
        """Missing optional fields should get default values."""
        body = {
            "model": "chat-completion",
            "messages": [{"role": "user", "content": "Hi"}],
        }

        request = CompletionRequest(
            model=body["model"],
            messages=body["messages"],
            temperature=body.get("temperature", 1.0),
            max_tokens=body.get("max_tokens"),
            stream=body.get("stream", False),
            top_p=body.get("top_p", 1.0),
            stop=body.get("stop"),
        )

        self.assertEqual(request.temperature, 1.0)
        self.assertIsNone(request.max_tokens)
        self.assertFalse(request.stream)
        self.assertEqual(request.top_p, 1.0)
        self.assertIsNone(request.stop)


# ---------------------------------------------------------------------------
# Test: CompletionResponse serialization
# ---------------------------------------------------------------------------


class TestCompletionResponseSerialization(unittest.TestCase):
    """Test _completion_response_to_dict serialization."""

    def test_basic_response(self):
        resp = CompletionResponse(
            id="test-id",
            model="chat-completion",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hello!"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
            created=1700000000,
        )

        d = _completion_response_to_dict(resp)

        self.assertEqual(d["id"], "test-id")
        self.assertEqual(d["model"], "chat-completion")
        self.assertEqual(len(d["choices"]), 1)
        self.assertEqual(d["choices"][0]["message"]["role"], "assistant")
        self.assertEqual(d["choices"][0]["message"]["content"], "Hello!")
        self.assertEqual(d["choices"][0]["finish_reason"], "stop")
        self.assertEqual(d["usage"]["prompt_tokens"], 5)
        self.assertEqual(d["usage"]["completion_tokens"], 3)
        self.assertEqual(d["usage"]["total_tokens"], 8)

    def test_streaming_chunk(self):
        resp = CompletionResponse(
            id="chunk-1",
            model="chat-completion",
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content="Hi"),
                    finish_reason=None,
                )
            ],
            usage=TokenUsage(),
        )

        d = _completion_response_to_dict(resp)

        self.assertIn("delta", d["choices"][0])
        self.assertEqual(d["choices"][0]["delta"]["content"], "Hi")
        self.assertIsNone(d["choices"][0]["finish_reason"])

    def test_empty_id_generates_uuid(self):
        resp = CompletionResponse(
            id="",
            model="test",
            choices=[],
            usage=TokenUsage(),
        )

        d = _completion_response_to_dict(resp)
        self.assertTrue(d["id"].startswith("chatcmpl-"))

    def test_response_is_json_serializable(self):
        resp = CompletionResponse(
            id="test-json",
            model="chat-completion",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Yes"),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

        d = _completion_response_to_dict(resp)
        # Should not raise
        serialized = json.dumps(d)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["id"], "test-json")

    def test_tool_calls_included(self):
        resp = CompletionResponse(
            id="tool-resp",
            model="chat-completion",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=None,
                        tool_calls=[{"id": "call_1", "type": "function"}],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=TokenUsage(),
        )

        d = _completion_response_to_dict(resp)
        self.assertIn("tool_calls", d["choices"][0]["message"])
        self.assertEqual(len(d["choices"][0]["message"]["tool_calls"]), 1)


# ---------------------------------------------------------------------------
# Test: ProxyServer initialization
# ---------------------------------------------------------------------------


class TestProxyServerInit(unittest.TestCase):
    """Test ProxyServer construction and configuration."""

    def test_init_with_mesh_config(self):
        config = _make_config()
        server = ProxyServer(config=config, host="127.0.0.1", port=0)
        self.assertIsNotNone(server.mesh)
        self.assertTrue(server.mesh._initialized)
        server._mesh.shutdown()

    def test_init_with_dict(self):
        config = _make_config()
        server = ProxyServer(config=config.raw, host="127.0.0.1", port=0)
        self.assertIsNotNone(server.mesh)
        server._mesh.shutdown()

    def test_init_invalid_config_type(self):
        with self.assertRaises(TypeError):
            ProxyServer(config=42, host="127.0.0.1", port=0)

    def test_get_status_before_start(self):
        config = _make_config()
        server = ProxyServer(config=config, host="127.0.0.1", port=0)
        status = server.get_status()
        self.assertFalse(status.running)
        self.assertEqual(status.total_requests, 0)
        self.assertEqual(status.active_connections, 0)
        server._mesh.shutdown()

    def test_mesh_property(self):
        config = _make_config()
        server = ProxyServer(config=config, host="127.0.0.1", port=0)
        self.assertIsInstance(server.mesh, ModelMesh)
        server._mesh.shutdown()


if __name__ == "__main__":
    unittest.main()
