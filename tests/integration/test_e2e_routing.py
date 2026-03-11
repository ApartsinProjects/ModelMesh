"""
Integration tests for end-to-end routing scenarios.

These tests use mock providers to verify the full request lifecycle:
  create() → Router → Pool → Model → Provider → Response

Run with: pytest tests/integration/ -v
"""

import pytest
from modelmesh.testing import mock_client, MockResponse
from modelmesh.exceptions import NoActiveModelError


class TestEndToEndRouting:
    """Test the full routing lifecycle with multiple providers."""

    def test_single_provider_happy_path(self):
        """Request flows through a single provider successfully."""
        client = mock_client(responses=[MockResponse(content="Hello from mock!")])
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert response.choices[0].message.content == "Hello from mock!"

    def test_multi_response_sequence(self):
        """Multiple sequential requests return different responses."""
        client = mock_client(responses=[
            MockResponse(content="First"),
            MockResponse(content="Second"),
            MockResponse(content="Third"),
        ])
        results = []
        for _ in range(3):
            response = client.chat.completions.create(
                model="chat-completion",
                messages=[{"role": "user", "content": "Hi"}],
            )
            results.append(response.choices[0].message.content)
        assert results == ["First", "Second", "Third"]

    def test_response_includes_model_name(self):
        """Response includes the model name from MockResponse."""
        client = mock_client(responses=[
            MockResponse(content="test", model="custom-model")
        ])
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert response.model == "custom-model"

    def test_response_includes_token_usage(self):
        """Response includes token usage information."""
        client = mock_client(responses=[
            MockResponse(content="test", tokens=100, prompt_tokens=30)
        ])
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert response.usage.total_tokens == 100
        assert response.usage.prompt_tokens == 30
        assert response.usage.completion_tokens == 70


class TestEndToEndCapabilities:
    """Test capability-based pool resolution."""

    def test_chat_completion_capability(self):
        """Chat completion capability resolves correctly."""
        client = mock_client(responses=[MockResponse(content="Chat response")])
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert response.choices[0].message.content == "Chat response"

    def test_describe_shows_pool_info(self):
        """client.describe() returns pool and model information."""
        client = mock_client(responses=[MockResponse()])
        description = client.describe()
        assert description is not None
        assert len(str(description)) > 0


class TestEndToEndConfiguration:
    """Test programmatic configuration scenarios."""

    def test_create_with_mock_returns_response(self):
        """mock_client creates a usable client."""
        client = mock_client(responses=[MockResponse(content="Works!")])
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Test"}],
        )
        assert response.choices[0].message.content == "Works!"

    def test_multiple_clients_independent(self):
        """Multiple clients operate independently."""
        client1 = mock_client(responses=[MockResponse(content="Client 1")])
        client2 = mock_client(responses=[MockResponse(content="Client 2")])

        r1 = client1.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hi"}],
        )
        r2 = client2.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert r1.choices[0].message.content == "Client 1"
        assert r2.choices[0].message.content == "Client 2"

    def test_mock_response_defaults(self):
        """MockResponse has sensible defaults."""
        client = mock_client(responses=[MockResponse()])
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert response.choices[0].message.content == "Mock response"
        assert response.choices[0].finish_reason == "stop"
