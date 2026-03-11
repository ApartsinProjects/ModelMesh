"""Pre-built configuration templates for common deployment patterns.

Each function returns a ``dict`` suitable for ``MeshConfig.from_dict()``.
Templates can be used as-is or merged with custom overrides::

    from modelmesh.config.templates import cost_optimized
    from modelmesh.config.mesh_config import MeshConfig

    config = MeshConfig.from_dict(cost_optimized())
    # or merge overrides
    config = config.merge({"budget": {"daily_limit": 5.0}})
"""
from __future__ import annotations

from typing import Any

__all__ = [
    "cost_optimized",
    "latency_optimized",
    "high_availability",
    "development",
    "balanced",
]


def cost_optimized() -> dict[str, Any]:
    """Cost-optimized template: cheapest models first, strict budget.

    Routes via cost-first rotation, with tight budget limits and
    preferring free-tier / low-cost providers.
    """
    return {
        "secrets": {"store": "modelmesh.env.v1"},
        "providers": {
            "groq.api.v1": {"connector": "groq.api.v1"},
            "deepseek.api.v1": {"connector": "deepseek.api.v1"},
            "openai.llm.v1": {"connector": "openai.llm.v1"},
        },
        "models": {
            "llama-3.3-70b": {
                "provider": "groq.api.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "deepseek-chat": {
                "provider": "deepseek.api.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "gpt-4o-mini": {
                "provider": "openai.llm.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
        },
        "pools": {
            "text-generation": {
                "strategy": "modelmesh.cost-first.v1",
                "capability": "generation.text-generation",
            },
        },
        "budget": {
            "daily_limit": 5.0,
            "monthly_limit": 50.0,
            "alert_threshold": 0.8,
        },
    }


def latency_optimized() -> dict[str, Any]:
    """Latency-optimized template: fastest response wins.

    Routes via latency-first rotation, preferring providers with the
    lowest observed latency. Good for real-time applications.
    """
    return {
        "secrets": {"store": "modelmesh.env.v1"},
        "providers": {
            "groq.api.v1": {"connector": "groq.api.v1"},
            "openai.llm.v1": {"connector": "openai.llm.v1"},
            "anthropic.claude.v1": {"connector": "anthropic.claude.v1"},
        },
        "models": {
            "llama-3.3-70b": {
                "provider": "groq.api.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "gpt-4o-mini": {
                "provider": "openai.llm.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "claude-3-5-haiku": {
                "provider": "anthropic.claude.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
        },
        "pools": {
            "text-generation": {
                "strategy": "modelmesh.latency-first.v1",
                "capability": "generation.text-generation",
            },
        },
    }


def high_availability() -> dict[str, Any]:
    """High-availability template: maximum redundancy and failover.

    Uses stick-until-failure with low failure threshold and fast
    cooldown for rapid failover across multiple providers.
    """
    return {
        "secrets": {"store": "modelmesh.env.v1"},
        "providers": {
            "openai.llm.v1": {"connector": "openai.llm.v1"},
            "anthropic.claude.v1": {"connector": "anthropic.claude.v1"},
            "groq.api.v1": {"connector": "groq.api.v1"},
            "deepseek.api.v1": {"connector": "deepseek.api.v1"},
        },
        "models": {
            "gpt-4o": {
                "provider": "openai.llm.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "claude-3-5-sonnet": {
                "provider": "anthropic.claude.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "llama-3.3-70b": {
                "provider": "groq.api.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "deepseek-chat": {
                "provider": "deepseek.api.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
        },
        "pools": {
            "text-generation": {
                "strategy": "modelmesh.stick-until-failure.v1",
                "capability": "generation.text-generation",
                "failure_threshold": 2,
                "cooldown_seconds": 30,
            },
        },
        "observability": {
            "connector": "modelmesh.console.v1",
        },
    }


def development() -> dict[str, Any]:
    """Development template: single provider, verbose logging.

    Uses one provider with console observability for maximum
    visibility during development and debugging.
    """
    return {
        "secrets": {"store": "modelmesh.env.v1"},
        "providers": {
            "openai.llm.v1": {"connector": "openai.llm.v1"},
        },
        "models": {
            "gpt-4o-mini": {
                "provider": "openai.llm.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
        },
        "pools": {
            "text-generation": {
                "strategy": "modelmesh.stick-until-failure.v1",
                "capability": "generation.text-generation",
            },
        },
        "observability": {
            "connector": "modelmesh.console.v1",
        },
    }


def balanced() -> dict[str, Any]:
    """Balanced template: cost-aware with good availability.

    Uses load-balanced rotation with priority ordering and moderate
    budget limits. A good starting point for production workloads.
    """
    return {
        "secrets": {"store": "modelmesh.env.v1"},
        "providers": {
            "openai.llm.v1": {"connector": "openai.llm.v1"},
            "anthropic.claude.v1": {"connector": "anthropic.claude.v1"},
            "groq.api.v1": {"connector": "groq.api.v1"},
        },
        "models": {
            "gpt-4o-mini": {
                "provider": "openai.llm.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "claude-3-5-haiku": {
                "provider": "anthropic.claude.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
            "llama-3.3-70b": {
                "provider": "groq.api.v1",
                "capabilities": ["generation.text-generation.chat-completion"],
            },
        },
        "pools": {
            "text-generation": {
                "strategy": "modelmesh.load-balanced.v1",
                "capability": "generation.text-generation",
                "model_weights": {
                    "gpt-4o-mini": 2.0,
                    "claude-3-5-haiku": 2.0,
                    "llama-3.3-70b": 1.0,
                },
            },
        },
        "budget": {
            "daily_limit": 20.0,
            "monthly_limit": 200.0,
        },
    }
