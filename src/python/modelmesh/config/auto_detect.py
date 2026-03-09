"""Provider auto-detection from environment variables.

Scans the environment for known API key variables and returns provider
configurations for use with the convenience layer. The registry maps
environment variable names to provider metadata, default models, and
connector IDs.

Detection rules (from ``docs/cdk/ConvenienceLayer.md``):

1. For each entry, check whether the environment variable is set and
   non-empty.
2. If ``names`` is specified, include only providers whose name matches.
3. If ``api_keys`` is specified, use the provided key instead of the
   environment variable for matching providers.
4. If no providers are detected, raise ``RuntimeError``.
"""
from __future__ import annotations

import os
from typing import Optional

from modelmesh.interfaces.provider import ModelInfo

__all__ = ["detect_providers", "PROVIDER_REGISTRY"]

PROVIDER_REGISTRY: dict[str, dict] = {
    "OPENAI_API_KEY": {
        "name": "openai",
        "connector": "openai.llm.v1",
        "base_url": "https://api.openai.com",
        "default_models": [
            ModelInfo(
                id="openai.gpt-4o",
                name="GPT-4o",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=128000,
                max_output_tokens=16384,
            ),
            ModelInfo(
                id="openai.gpt-4o-mini",
                name="GPT-4o Mini",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=128000,
                max_output_tokens=16384,
            ),
        ],
    },
    "ANTHROPIC_API_KEY": {
        "name": "anthropic",
        "connector": "anthropic.claude.v1",
        "base_url": "https://api.anthropic.com",
        "default_models": [
            ModelInfo(
                id="anthropic.claude-sonnet-4-20250514",
                name="Claude Sonnet 4",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=200000,
                max_output_tokens=16384,
            ),
            ModelInfo(
                id="anthropic.claude-haiku-4-5-20251001",
                name="Claude Haiku 4.5",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=200000,
                max_output_tokens=8192,
            ),
        ],
    },
    "GOOGLE_API_KEY": {
        "name": "google",
        "connector": "google.gemini.v1",
        "base_url": "https://generativelanguage.googleapis.com",
        "default_models": [
            ModelInfo(
                id="google.gemini-2.0-flash",
                name="Gemini 2.0 Flash",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=1048576,
                max_output_tokens=8192,
            ),
            ModelInfo(
                id="google.gemini-2.0-flash-lite",
                name="Gemini 2.0 Flash Lite",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=1048576,
                max_output_tokens=8192,
            ),
        ],
    },
    "GROQ_API_KEY": {
        "name": "groq",
        "connector": "groq.api.v1",
        "base_url": "https://api.groq.com",
        "default_models": [
            ModelInfo(
                id="groq.llama-3.3-70b-versatile",
                name="Llama 3.3 70B Versatile",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=128000,
                max_output_tokens=32768,
            ),
        ],
    },
    "MISTRAL_API_KEY": {
        "name": "mistral",
        "connector": "mistral.api.v1",
        "base_url": "https://api.mistral.ai",
        "default_models": [
            ModelInfo(
                id="mistral.mistral-large-latest",
                name="Mistral Large",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=128000,
                max_output_tokens=8192,
            ),
            ModelInfo(
                id="mistral.mistral-small-latest",
                name="Mistral Small",
                capabilities=[
                    "generation.text-generation.chat-completion",
                    "representation.embeddings.text-embeddings",
                ],
                context_window=128000,
                max_output_tokens=8192,
            ),
        ],
    },
    "TOGETHER_API_KEY": {
        "name": "together",
        "connector": "together.api.v1",
        "base_url": "https://api.together.xyz",
        "default_models": [
            ModelInfo(
                id="together.meta-llama-3.1-8b-instruct-turbo",
                name="Llama 3.1 8B Instruct Turbo",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=131072,
                max_output_tokens=4096,
            ),
        ],
    },
    "FIREWORKS_API_KEY": {
        "name": "fireworks",
        "connector": "fireworks.api.v1",
        "base_url": "https://api.fireworks.ai",
        "default_models": [
            ModelInfo(
                id="fireworks.llama-v3p1-8b-instruct",
                name="Llama 3.1 8B Instruct",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=131072,
                max_output_tokens=4096,
            ),
        ],
    },
    "OPENROUTER_API_KEY": {
        "name": "openrouter",
        "connector": "openrouter.gateway.v1",
        "base_url": "https://openrouter.ai",
        "default_models": [
            ModelInfo(
                id="openrouter.auto",
                name="OpenRouter Auto",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=128000,
                max_output_tokens=4096,
            ),
        ],
    },
    "HF_TOKEN": {
        "name": "huggingface",
        "connector": "huggingface.inference.v1",
        "base_url": "https://api-inference.huggingface.co",
        "default_models": [
            ModelInfo(
                id="huggingface.meta-llama-3.1-8b-instruct",
                name="Llama 3.1 8B Instruct",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=131072,
                max_output_tokens=4096,
            ),
        ],
    },
}


def detect_providers(
    names: Optional[list[str]] = None,
    api_keys: Optional[dict[str, str]] = None,
) -> list[dict]:
    """Scan environment variables for known API keys.

    Returns a list of provider configuration dicts for each detected
    provider. Each dict contains all fields from the registry entry
    plus the resolved ``env_var`` and ``api_key``.

    Args:
        names: If provided, restrict detection to providers whose
            ``name`` field appears in this list (e.g. ``["openai",
            "anthropic"]``).
        api_keys: If provided, use these keys instead of environment
            variables. Keys are either environment variable names
            (e.g. ``"OPENAI_API_KEY"``) or provider names (e.g.
            ``"openai"``). Provider names are resolved to their
            corresponding env var.

    Returns:
        List of provider configuration dicts. Each dict has keys:
        ``name``, ``connector``, ``base_url``, ``default_models``,
        ``env_var``, and ``api_key``.
    """
    detected: list[dict] = []

    for env_var, info in PROVIDER_REGISTRY.items():
        provider_name = info["name"]

        # Filter by names if specified
        if names and provider_name not in names:
            continue

        # Resolve the API key
        key: Optional[str] = None
        if api_keys is not None:
            # Try env var name first, then provider name
            key = api_keys.get(env_var) or api_keys.get(provider_name)
        if key is None:
            key = os.environ.get(env_var)

        if key:
            detected.append({**info, "env_var": env_var, "api_key": key})

    return detected
