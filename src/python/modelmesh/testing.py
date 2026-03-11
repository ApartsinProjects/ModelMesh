"""Testing utilities for ModelMesh.

Provides a mock client that behaves like the real ``MeshClient`` but
returns pre-configured responses instead of calling live APIs.
Designed for unit testing applications that use ModelMesh.

Usage::

    from modelmesh.testing import mock_client, MockResponse

    client = mock_client(responses=[
        MockResponse(content="Hello!", model="gpt-4o", tokens=10),
        MockResponse(content="World!", model="claude-3", tokens=15),
    ])

    resp = client.chat.completions.create(
        messages=[{"role": "user", "content": "Hi"}],
        model="test-pool",
    )
    assert resp.choices[0].message.content == "Hello!"
    assert len(client.calls) == 1
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionResponse,
    TokenUsage,
)


@dataclass
class MockResponse:
    """Pre-configured response for the mock client.

    Attributes:
        content: The text content of the assistant's reply.
        model: Model identifier to include in the response.
        tokens: Total token count to simulate.
        prompt_tokens: Prompt token count (defaults to tokens // 3).
        completion_tokens: Completion token count (auto-calculated).
        finish_reason: Stop reason (default: "stop").
    """

    content: str = "Mock response"
    model: str = "mock-model"
    tokens: int = 10
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    finish_reason: str = "stop"

    def to_completion_response(self) -> CompletionResponse:
        """Convert to a ``CompletionResponse``."""
        prompt = self.prompt_tokens if self.prompt_tokens is not None else self.tokens // 3
        completion = (
            self.completion_tokens
            if self.completion_tokens is not None
            else self.tokens - prompt
        )
        return CompletionResponse(
            id=f"mock-{uuid.uuid4().hex[:8]}",
            model=self.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=self.content,
                    ),
                    finish_reason=self.finish_reason,
                )
            ],
            usage=TokenUsage(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=prompt + completion,
            ),
            created=int(time.time()),
            object="chat.completion",
        )


@dataclass
class MockCall:
    """Record of a call made to the mock client.

    Attributes:
        model: The model / pool name requested.
        messages: The messages sent.
        kwargs: Additional parameters.
        response: The response that was returned.
    """

    model: str = ""
    messages: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    response: Optional[CompletionResponse] = None


class _MockChatCompletions:
    """Mock chat.completions namespace."""

    def __init__(self, responses: list[MockResponse], calls: list[MockCall]) -> None:
        self._responses = responses
        self._calls = calls
        self._index = 0

    def create(
        self,
        *,
        model: str = "test",
        messages: list[dict] | None = None,
        stream: bool = False,
        **kwargs,
    ) -> CompletionResponse:
        """Return the next pre-configured response."""
        messages = messages or []

        if self._index < len(self._responses):
            response = self._responses[self._index].to_completion_response()
            self._index += 1
        else:
            # Cycle back to last response if exhausted
            response = self._responses[-1].to_completion_response() if self._responses else MockResponse().to_completion_response()

        call = MockCall(
            model=model,
            messages=messages,
            kwargs=kwargs,
            response=response,
        )
        self._calls.append(call)
        return response


class _MockChatNamespace:
    """Mock chat namespace."""

    def __init__(self, responses: list[MockResponse], calls: list[MockCall]) -> None:
        self.completions = _MockChatCompletions(responses, calls)


class _MockModelsNamespace:
    """Mock models namespace."""

    def list(self):
        return type("ModelList", (), {"data": [], "object": "list"})()


class MockClient:
    """A mock MeshClient for testing.

    Behaves like the real ``MeshClient`` but returns pre-configured
    responses. Records all calls for assertion.

    Attributes:
        calls: List of :class:`MockCall` records.
        chat: Chat namespace with ``completions.create()``.
        models: Models namespace with ``list()``.
    """

    def __init__(self, responses: list[MockResponse] | None = None) -> None:
        self.calls: list[MockCall] = []
        self._responses = responses or [MockResponse()]
        self.chat = _MockChatNamespace(self._responses, self.calls)
        self.models = _MockModelsNamespace()

    def __enter__(self) -> MockClient:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    async def __aenter__(self) -> MockClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    def pool_status(self, pool: str | None = None) -> dict:
        """Return mock pool status."""
        return {"mock-pool": {"active": 1, "standby": 0, "total": 1, "current_model": "mock-model"}}

    def active_providers(self) -> list[str]:
        """Return mock provider list."""
        return ["mock-provider"]

    def describe(self, pool: str | None = None) -> str:
        """Return mock description."""
        return 'Pool "mock-pool" (strategy: mock)\n  -> mock-model [mock-provider] (active)'

    def explain(self, *, model: str = "test", **kwargs) -> dict:
        """Return mock routing explanation."""
        return {
            "pool_name": "mock-pool",
            "strategy": "mock",
            "capability": "mock",
            "selected_model": "mock-model",
            "candidates": [{"model_id": "mock-model", "provider_id": "mock-provider", "status": "active"}],
            "reason": "Mock selection",
        }


def mock_client(
    responses: list[MockResponse] | None = None,
) -> MockClient:
    """Create a mock MeshClient for testing.

    Args:
        responses: Pre-configured responses to cycle through.
            Each call to ``chat.completions.create()`` returns
            the next response in the list.

    Returns:
        A ``MockClient`` that can be used in place of a real
        ``MeshClient``.

    Example::

        client = mock_client(responses=[
            MockResponse(content="Hello!"),
            MockResponse(content="Goodbye!"),
        ])
        resp = client.chat.completions.create(model="test", messages=[...])
        assert resp.choices[0].message.content == "Hello!"
    """
    return MockClient(responses=responses)


__all__ = [
    "MockCall",
    "MockClient",
    "MockResponse",
    "mock_client",
]
