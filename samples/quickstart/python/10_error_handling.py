"""
10 - Error Handling Patterns
=============================

Shows how to handle different error types with ModelMesh's structured
exception hierarchy. Each exception carries metadata like provider_id,
retry hints, and budget details.

Uses the mock testing client for demonstration.
"""

from __future__ import annotations

from modelmesh.exceptions import (
    AllProvidersExhaustedError,
    AuthenticationError,
    BudgetExceededError,
    ConfigurationError,
    ModelMeshError,
    NoActiveModelError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    RoutingError,
)
from modelmesh.testing import MockResponse, mock_client


def demo_basic_error_handling():
    """Show the recommended catch pattern."""
    print("=== Basic Error Handling ===")

    client = mock_client(responses=[
        MockResponse(content="Success!", tokens=20),
    ])

    try:
        response = client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(f"  Response: {response.choices[0].message.content}")
    except ModelMeshError as e:
        print(f"  Error: {e}")


def demo_exception_hierarchy():
    """Demonstrate the full exception tree."""
    print("\n=== Exception Hierarchy ===")

    # All exceptions are instances of ModelMeshError
    errors = [
        NoActiveModelError("No models in pool 'chat'", pool_name="chat"),
        AllProvidersExhaustedError(
            "3 attempts failed",
            pool_name="chat",
            attempts=3,
            last_error=TimeoutError("Connection timed out"),
        ),
        AuthenticationError("Invalid API key", provider_id="openai"),
        RateLimitError(
            "Rate limited",
            provider_id="anthropic",
            retry_after=30,
        ),
        ProviderTimeoutError("Timed out", timeout_seconds=60),
        ConfigurationError("Missing provider config"),
        BudgetExceededError(
            "Daily limit exceeded",
            limit_type="daily",
            limit_value=10.0,
            actual_value=12.5,
        ),
    ]

    for err in errors:
        retry_hint = "retryable" if err.retryable else "permanent"
        print(f"  {err.__class__.__name__:35s} [{retry_hint}] {err}")


def demo_granular_catching():
    """Show how to catch specific exception types."""
    print("\n=== Granular Catching ===")

    # Simulate different error scenarios
    scenarios = [
        ("Rate limit", RateLimitError("Too many requests", provider_id="openai", retry_after=5)),
        ("Auth failure", AuthenticationError("Bad key", provider_id="anthropic")),
        ("No models", NoActiveModelError("Pool empty", pool_name="embeddings")),
        ("All exhausted", AllProvidersExhaustedError("Failed", attempts=3)),
        ("Over budget", BudgetExceededError("Over limit", limit_type="daily", limit_value=10.0)),
    ]

    for name, error in scenarios:
        print(f"\n  Scenario: {name}")
        try:
            raise error
        except RateLimitError as e:
            print(f"    -> Rate limited by {e.provider_id}, retry in {e.retry_after}s")
        except AuthenticationError as e:
            print(f"    -> Auth failed for {e.provider_id} -- check credentials")
        except NoActiveModelError as e:
            print(f"    -> No models in pool '{e.pool_name}' -- wait and retry")
        except AllProvidersExhaustedError as e:
            print(f"    -> All {e.attempts} attempts failed")
        except BudgetExceededError as e:
            print(f"    -> {e.limit_type} budget exceeded: ${e.limit_value}")
        except ModelMeshError as e:
            print(f"    -> Generic ModelMesh error: {e}")


def demo_retryable_check():
    """Show the retryable pattern."""
    print("\n=== Retryable Check ===")

    errors = [
        NoActiveModelError("Pool empty"),
        RateLimitError("Rate limited", retry_after=10),
        ProviderTimeoutError("Timeout", timeout_seconds=30),
        AuthenticationError("Bad key"),
        AllProvidersExhaustedError("Exhausted"),
        BudgetExceededError("Over budget"),
    ]

    for err in errors:
        action = "RETRY" if err.retryable else "FAIL"
        print(f"  {err.__class__.__name__:35s} -> {action}")


if __name__ == "__main__":
    demo_basic_error_handling()
    demo_exception_hierarchy()
    demo_granular_catching()
    demo_retryable_check()
    print("\nDone!")
