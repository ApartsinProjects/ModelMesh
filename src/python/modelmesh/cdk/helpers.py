"""CDK testing helpers.

Provides factory functions and test doubles for writing connector unit
tests without real HTTP traffic or live AI providers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)
from modelmesh.interfaces.rotation import ModelState, ModelStatus

__all__ = [
    "ConnectorTestHarness",
    "MockHttpClient",
    "mock_completion_request",
    "mock_model_snapshot",
]


def mock_completion_request(
    model: str = "test-model",
    content: str = "Hello",
    **kwargs: Any,
) -> CompletionRequest:
    """Create a minimal ``CompletionRequest`` for testing.

    Args:
        model: Virtual model name.
        content: User message content.
        **kwargs: Additional fields forwarded to ``CompletionRequest``.

    Returns:
        A ready-to-use ``CompletionRequest``.
    """
    return CompletionRequest(
        model=model,
        messages=[{"role": "user", "content": content}],
        **kwargs,
    )


def mock_model_snapshot(
    model_id: str = "test.model-a",
    provider_id: str = "test.v1",
    status: ModelStatus = ModelStatus.ACTIVE,
    failure_count: int = 0,
    success_count: int = 0,
) -> ModelState:
    """Create a ``ModelState`` snapshot for rotation policy testing.

    Args:
        model_id: Dot-notated model identifier.
        provider_id: Provider connector ID.
        status: Current lifecycle status.
        failure_count: Consecutive failures.
        success_count: Lifetime successes.

    Returns:
        A ``ModelState`` instance.
    """
    return ModelState(
        model_id=model_id,
        provider_id=provider_id,
        status=status,
        failure_count=failure_count,
        success_count=success_count,
    )


@dataclass
class MockHttpResponse:
    """Simulated HTTP response for ``MockHttpClient``."""

    status_code: int = 200
    headers: dict = field(default_factory=dict)
    body: str = "{}"

    def json(self) -> Any:
        import json
        return json.loads(self.body)


class MockHttpClient:
    """HTTP client double that records calls and returns canned responses.

    Usage::

        client = MockHttpClient()
        client.add_response(MockHttpResponse(status_code=200, body='{"ok":true}'))
        response = await client.post("https://api.example.com/v1/chat", ...)
    """

    def __init__(self) -> None:
        self._responses: list[MockHttpResponse] = []
        self.calls: list[dict] = []

    def add_response(self, response: MockHttpResponse) -> None:
        """Queue a canned response."""
        self._responses.append(response)

    async def post(self, url: str, *, headers: dict | None = None,
                   json: Any = None, **kwargs: Any) -> MockHttpResponse:
        """Simulate an HTTP POST, recording the call."""
        self.calls.append({
            "method": "POST",
            "url": url,
            "headers": headers,
            "json": json,
        })
        if self._responses:
            return self._responses.pop(0)
        return MockHttpResponse()

    async def get(self, url: str, *, headers: dict | None = None,
                  **kwargs: Any) -> MockHttpResponse:
        """Simulate an HTTP GET, recording the call."""
        self.calls.append({
            "method": "GET",
            "url": url,
            "headers": headers,
        })
        if self._responses:
            return self._responses.pop(0)
        return MockHttpResponse()


class ConnectorTestHarness:
    """Lightweight test harness for connector instances.

    Wraps a connector and provides convenience methods for exercising
    its lifecycle (initialize, call, shutdown) without a full ModelMesh
    setup.

    Usage::

        harness = ConnectorTestHarness(MyProvider(config))
        response = await harness.complete(mock_completion_request())
        assert response.choices
    """

    def __init__(self, connector: Any) -> None:
        self.connector = connector
        self.calls: list[dict] = []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Route a request through the connector's ``complete`` method."""
        self.calls.append({"method": "complete", "request": request})
        return await self.connector.complete(request)

    async def stream(self, request: CompletionRequest):
        """Route a request through the connector's ``stream`` method."""
        self.calls.append({"method": "stream", "request": request})
        async for chunk in self.connector.stream(request):
            yield chunk
