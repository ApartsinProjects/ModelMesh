"""Tests for the starter project."""

from modelmesh.testing import mock_client


def test_chat_completion():
    """Test that chat completion returns a response."""
    client = mock_client(responses=["Hello! I can help with many things."])
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    assert response.choices[0].message.content == "Hello! I can help with many things."
