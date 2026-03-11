"""Tests for the LangChain adapter."""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.integrations.langchain_adapter import (
    ChatModelMesh,
    _messages_to_openai_format,
)
from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)


def _make_mock_mesh():
    """Create a mock ModelMesh instance that returns a canned response."""
    mesh = MagicMock()
    response = CompletionResponse(
        id="resp-123",
        model="gpt-4o",
        choices=[
            CompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content="Hello from mesh!"),
                finish_reason="stop",
            )
        ],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    mesh.route = AsyncMock(return_value=response)
    return mesh


class TestMessageConversion:
    """Test the _messages_to_openai_format helper."""

    def test_string_to_user_message(self):
        """String messages are converted to user role."""
        result = _messages_to_openai_format(["Hello"])
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_dict_passthrough(self):
        """Dict messages with role/content are passed through."""
        msg = {"role": "system", "content": "Be helpful"}
        result = _messages_to_openai_format([msg])
        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "Be helpful"

    def test_mixed_message_types(self):
        """Mixed string and dict messages are handled correctly."""
        messages = [
            {"role": "system", "content": "Be helpful"},
            "Hello, how are you?",
        ]
        result = _messages_to_openai_format(messages)
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "Hello, how are you?"

    def test_empty_list(self):
        """Empty message list returns empty list."""
        result = _messages_to_openai_format([])
        assert result == []

    def test_non_string_non_dict_converts_to_str(self):
        """Non-string, non-dict messages are converted to str."""
        result = _messages_to_openai_format([42])
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "42"

    def test_duck_typed_message(self):
        """Objects with content and type attributes are handled."""

        class FakeMessage:
            type = "human"
            content = "Duck typed"

        result = _messages_to_openai_format([FakeMessage()])
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Duck typed"

    def test_duck_typed_ai_message(self):
        """Objects with type='ai' map to assistant role."""

        class FakeAI:
            type = "ai"
            content = "I am AI"

        result = _messages_to_openai_format([FakeAI()])
        assert len(result) == 1
        assert result[0]["role"] == "assistant"

    def test_duck_typed_system_message(self):
        """Objects with type='system' map to system role."""

        class FakeSystem:
            type = "system"
            content = "You are helpful"

        result = _messages_to_openai_format([FakeSystem()])
        assert len(result) == 1
        assert result[0]["role"] == "system"


class TestLangChainAdapter:
    """Test LangChain integration adapter."""

    def test_import_without_langchain(self):
        """Module imports successfully even without langchain installed."""
        # If we got here, the import already worked
        assert ChatModelMesh is not None

    def test_create_adapter(self):
        """ChatModelMesh can be instantiated."""
        mesh = _make_mock_mesh()
        adapter = ChatModelMesh(mesh=mesh, model_name="chat-completion")
        assert adapter.model_name == "chat-completion"

    def test_adapter_repr(self):
        """ChatModelMesh has a readable repr."""
        mesh = _make_mock_mesh()
        adapter = ChatModelMesh(mesh=mesh, model_name="chat-completion")
        r = repr(adapter)
        assert "ChatModelMesh" in r
        assert "chat-completion" in r

    def test_llm_type(self):
        """_llm_type returns 'modelmesh'."""
        mesh = _make_mock_mesh()
        adapter = ChatModelMesh(mesh=mesh)
        assert adapter._llm_type == "modelmesh"

    def test_invoke_returns_response(self):
        """invoke() returns a response from the mesh."""
        mesh = _make_mock_mesh()
        adapter = ChatModelMesh(mesh=mesh, model_name="test-pool")

        result = adapter.invoke("Hello!")

        # The invoke should have called mesh.route
        mesh.route.assert_called_once()
        # The result contains the response content
        assert result["content"] == "Hello from mesh!"
        assert "additional_kwargs" in result

    def test_invoke_with_dict_messages(self):
        """invoke() with dict messages passes them through."""
        mesh = _make_mock_mesh()
        adapter = ChatModelMesh(mesh=mesh, model_name="test-pool")

        messages = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hello"},
        ]
        result = adapter.invoke(messages)

        assert result["content"] == "Hello from mesh!"

    def test_ainvoke_returns_response(self):
        """Async invoke works."""
        mesh = _make_mock_mesh()
        adapter = ChatModelMesh(mesh=mesh, model_name="test-pool")

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(adapter.ainvoke("Hello!"))
        finally:
            loop.close()

        assert result["content"] == "Hello from mesh!"

    def test_invoke_response_includes_usage(self):
        """invoke() response includes token usage information."""
        mesh = _make_mock_mesh()
        adapter = ChatModelMesh(mesh=mesh, model_name="test-pool")

        result = adapter.invoke("Hello!")
        usage = result["additional_kwargs"]["usage"]
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 5
        assert usage["total_tokens"] == 15

    def test_invoke_response_includes_model(self):
        """invoke() response includes model identifier."""
        mesh = _make_mock_mesh()
        adapter = ChatModelMesh(mesh=mesh, model_name="test-pool")

        result = adapter.invoke("Hello!")
        assert result["additional_kwargs"]["model"] == "gpt-4o"

    def test_default_parameters(self):
        """Default parameters have expected values."""
        mesh = _make_mock_mesh()
        adapter = ChatModelMesh(mesh=mesh)
        assert adapter.model_name == "text-generation"
        assert adapter.temperature == 1.0
        assert adapter.max_tokens is None
        assert adapter.streaming is False
