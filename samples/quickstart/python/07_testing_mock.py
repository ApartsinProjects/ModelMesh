"""
07 - Testing with Mock Client
==============================

Shows how to use ``mock_client()`` for unit testing without live APIs.
The mock client behaves identically to the real MeshClient — same
``client.chat.completions.create()`` interface — but returns
pre-configured responses and records all calls for assertion.

Run this sample directly or use it as a pattern for pytest tests.
"""

from __future__ import annotations

from modelmesh.testing import MockResponse, mock_client


def test_basic_response():
    """Mock client returns the configured response."""
    client = mock_client(responses=[
        MockResponse(content="Hello!", model="gpt-4o", tokens=10),
    ])

    response = client.chat.completions.create(
        model="text-generation",
        messages=[{"role": "user", "content": "Hi"}],
    )

    assert response.choices[0].message.content == "Hello!"
    assert response.model == "gpt-4o"
    assert response.usage.total_tokens == 10
    print("[OK] Basic response works")


def test_call_inspection():
    """Inspect what was sent to the client."""
    client = mock_client(responses=[MockResponse(content="OK")])

    client.chat.completions.create(
        model="my-pool",
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Summarize this."},
        ],
    )

    assert len(client.calls) == 1
    assert client.calls[0].model == "my-pool"
    assert len(client.calls[0].messages) == 2
    assert client.calls[0].messages[1]["content"] == "Summarize this."
    print("[OK] Call inspection works")


def test_multiple_responses():
    """Cycle through multiple pre-configured responses."""
    client = mock_client(responses=[
        MockResponse(content="First"),
        MockResponse(content="Second"),
        MockResponse(content="Third"),
    ])

    r1 = client.chat.completions.create(model="test", messages=[])
    r2 = client.chat.completions.create(model="test", messages=[])
    r3 = client.chat.completions.create(model="test", messages=[])

    assert r1.choices[0].message.content == "First"
    assert r2.choices[0].message.content == "Second"
    assert r3.choices[0].message.content == "Third"
    print("[OK] Multiple responses cycle correctly")


def test_context_manager():
    """Mock client supports the context manager protocol."""
    with mock_client(responses=[MockResponse(content="inside")]) as client:
        resp = client.chat.completions.create(model="test", messages=[])
        assert resp.choices[0].message.content == "inside"
    print("[OK] Context manager works")


def test_explain_and_status():
    """Mock client provides routing explanation and pool status."""
    client = mock_client()

    explanation = client.explain()
    assert "pool_name" in explanation
    assert "selected_model" in explanation

    status = client.pool_status()
    assert "mock-pool" in status
    print("[OK] Explain and pool_status work")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_basic_response()
    test_call_inspection()
    test_multiple_responses()
    test_context_manager()
    test_explain_and_status()
    print("\nAll tests passed!")
