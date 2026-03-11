# Testing with ModelMesh

ModelMesh provides a built-in mock client for unit testing without live API calls. The mock client has the same interface as the real [`MeshClient`](../SystemServices.html), so your tests use the exact same code paths your application uses. For error simulation, see the [Error Handling](ErrorHandling.html) guide for the complete exception hierarchy.

## Quick Start

### Python

```python
from modelmesh.testing import mock_client, MockResponse

# Create a mock client with pre-configured responses
client = mock_client(responses=[
    MockResponse(content="Hello!", model="gpt-4o", tokens=10),
    MockResponse(content="Goodbye!", model="claude-3", tokens=15),
])

# Use exactly like a real client
response = client.chat.completions.create(
    model="text-generation",
    messages=[{"role": "user", "content": "Hi"}],
)

assert response.choices[0].message.content == "Hello!"
assert response.usage.total_tokens == 10
```

### TypeScript

```typescript
import { mockClient } from '@nistrapa/modelmesh-core/testing';

const client = mockClient({
  responses: [
    { content: 'Hello!', model: 'gpt-4o', tokens: 10 },
    { content: 'Goodbye!', model: 'claude-3', tokens: 15 },
  ],
});

const response = await client.chat.completions.create({
  model: 'text-generation',
  messages: [{ role: 'user', content: 'Hi' }],
});

expect(response.choices[0].message?.content).toBe('Hello!');
```

## MockResponse Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | `str` | `"Mock response"` | Assistant reply content |
| `model` | `str` | `"mock-model"` | Model ID in response |
| `tokens` | `int` | `10` | Total token count |
| `prompt_tokens` | `int?` | `tokens // 3` | Prompt token count |
| `completion_tokens` | `int?` | auto | Completion token count |
| `finish_reason` | `str` | `"stop"` | Stop reason |

## Call Inspection

The mock client records every call for assertion:

```python
client = mock_client(responses=[MockResponse(content="OK")])

client.chat.completions.create(
    model="my-pool",
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Summarize."},
    ],
)

# Inspect what was sent
assert len(client.calls) == 1
assert client.calls[0].model == "my-pool"
assert client.calls[0].messages[1]["content"] == "Summarize."
```

## Response Cycling

When you configure multiple responses, each call returns the next one in order. After the last response is consumed, subsequent calls repeat the final response:

```python
client = mock_client(responses=[
    MockResponse(content="First"),
    MockResponse(content="Second"),
])

r1 = client.chat.completions.create(model="test", messages=[])
r2 = client.chat.completions.create(model="test", messages=[])
r3 = client.chat.completions.create(model="test", messages=[])  # repeats "Second"

assert r1.choices[0].message.content == "First"
assert r2.choices[0].message.content == "Second"
assert r3.choices[0].message.content == "Second"
```

## Context Manager Support (Python)

The mock client supports both sync and async context managers:

```python
with mock_client(responses=[MockResponse(content="test")]) as client:
    response = client.chat.completions.create(model="test", messages=[])
    assert response.choices[0].message.content == "test"
# Cleanup happens automatically
```

## Additional Mock Methods

The mock client also provides stub implementations of helper methods:

| Method | Returns |
|--------|---------|
| `pool_status()` | Mock pool status dict |
| `active_providers()` | `["mock-provider"]` |
| `describe()` | Human-readable pool description |
| `explain()` | Mock routing explanation |
| `models.list()` | Empty model list |

## Pytest Example

```python
import pytest
from modelmesh.testing import mock_client, MockResponse


@pytest.fixture
def client():
    return mock_client(responses=[
        MockResponse(content="Test response", tokens=20),
    ])


def test_my_application(client):
    """Test that my app handles the response correctly."""
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello"}],
    )
    result = my_app_process(response)
    assert result == expected_output


def test_multiple_turns(client):
    """Test multi-turn conversation."""
    responses = [
        MockResponse(content="I can help with that."),
        MockResponse(content="Here is the answer."),
    ]
    multi_client = mock_client(responses=responses)

    r1 = multi_client.chat.completions.create(
        model="chat", messages=[{"role": "user", "content": "Q1"}]
    )
    r2 = multi_client.chat.completions.create(
        model="chat", messages=[{"role": "user", "content": "Q2"}]
    )
    assert "help" in r1.choices[0].message.content
    assert "answer" in r2.choices[0].message.content
```

---

See also: [FAQ](FAQ.html) · [Quick Start](QuickStart.html) · [Error Handling](ErrorHandling.html)
