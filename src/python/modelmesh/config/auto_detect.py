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

__all__ = ["detect_providers", "PROVIDER_REGISTRY", "LOCAL_PROVIDER_REGISTRY"]

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
    "DEEPSEEK_API_KEY": {
        "name": "deepseek",
        "connector": "deepseek.api.v1",
        "base_url": "https://api.deepseek.com",
        "default_models": [
            ModelInfo(
                id="deepseek.deepseek-chat",
                name="DeepSeek Chat",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=64000,
                max_output_tokens=8192,
            ),
        ],
    },
    "XAI_API_KEY": {
        "name": "xai",
        "connector": "xai.grok.v1",
        "base_url": "https://api.x.ai",
        "default_models": [
            ModelInfo(
                id="xai.grok-2",
                name="Grok-2",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=128000,
                max_output_tokens=32768,
            ),
        ],
    },
    "COHERE_API_KEY": {
        "name": "cohere",
        "connector": "cohere.nlp.v1",
        "base_url": "https://api.cohere.com",
        "default_models": [
            ModelInfo(
                id="cohere.command-a-03-2025",
                name="Command A",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=256000,
                max_output_tokens=8192,
            ),
        ],
    },
    "PERPLEXITY_API_KEY": {
        "name": "perplexity",
        "connector": "perplexity.search.v1",
        "base_url": "https://api.perplexity.ai",
        "default_models": [
            ModelInfo(
                id="perplexity.sonar",
                name="Sonar",
                capabilities=["retrieval.grounded-generation.web-search"],
                context_window=128000,
                max_output_tokens=8192,
            ),
        ],
    },
    "ELEVENLABS_API_KEY": {
        "name": "elevenlabs",
        "connector": "elevenlabs.tts.v1",
        "base_url": "https://api.elevenlabs.io",
        "default_models": [
            ModelInfo(
                id="elevenlabs.eleven_multilingual_v2",
                name="Eleven Multilingual v2",
                capabilities=["generation.audio.text-to-speech"],
                context_window=5000,
                max_output_tokens=0,
            ),
        ],
    },
    "TAVILY_API_KEY": {
        "name": "tavily",
        "connector": "tavily.search.v1",
        "base_url": "https://api.tavily.com",
        "default_models": [
            ModelInfo(
                id="tavily.tavily-search",
                name="Tavily Search",
                capabilities=["retrieval.semantic-search.web-search"],
                context_window=400,
                max_output_tokens=0,
            ),
        ],
    },
    "SERPER_API_KEY": {
        "name": "serper",
        "connector": "serper.search.v1",
        "base_url": "https://google.serper.dev",
        "default_models": [
            ModelInfo(
                id="serper.serper-google-search",
                name="Google Search via Serper",
                capabilities=["retrieval.semantic-search.web-search"],
                context_window=2048,
                max_output_tokens=0,
            ),
        ],
    },
    "JINA_API_KEY": {
        "name": "jina",
        "connector": "jina.ai.v1",
        "base_url": "https://api.jina.ai",
        "default_models": [
            ModelInfo(
                id="jina.jina-reader",
                name="Jina Reader",
                capabilities=["understanding.document-understanding.content-extraction"],
                context_window=0,
                max_output_tokens=0,
            ),
            ModelInfo(
                id="jina.jina-embeddings-v3",
                name="Jina Embeddings v3",
                capabilities=["representation.embeddings.text-embeddings"],
                context_window=8192,
                max_output_tokens=0,
            ),
        ],
    },
    "FIRECRAWL_API_KEY": {
        "name": "firecrawl",
        "connector": "firecrawl.scrape.v1",
        "base_url": "https://api.firecrawl.dev",
        "default_models": [
            ModelInfo(
                id="firecrawl.firecrawl-scrape",
                name="Firecrawl Scrape",
                capabilities=["understanding.document-understanding.content-extraction"],
                context_window=0,
                max_output_tokens=0,
            ),
        ],
    },
    "ASSEMBLYAI_API_KEY": {
        "name": "assemblyai",
        "connector": "assemblyai.stt.v1",
        "base_url": "https://api.assemblyai.com",
        "default_models": [
            ModelInfo(
                id="assemblyai.assemblyai-best",
                name="AssemblyAI Best",
                capabilities=["understanding.audio.speech-to-text"],
                context_window=0,
                max_output_tokens=0,
            ),
        ],
    },
}


LOCAL_PROVIDER_REGISTRY: dict[str, dict] = {
    "OLLAMA_HOST": {
        "name": "ollama",
        "connector": "ollama.local.v1",
        "base_url": "http://localhost:11434",
        "default_models": [
            ModelInfo(
                id="ollama.llama3",
                name="Llama 3",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=8192,
                max_output_tokens=4096,
            ),
        ],
    },
    "LMSTUDIO_HOST": {
        "name": "lmstudio",
        "connector": "lmstudio.local.v1",
        "base_url": "http://localhost:1234",
        "default_models": [],
    },
    "VLLM_HOST": {
        "name": "vllm",
        "connector": "vllm.local.v1",
        "base_url": "http://localhost:8000",
        "default_models": [],
    },
    "LOCALAI_HOST": {
        "name": "localai",
        "connector": "localai.local.v1",
        "base_url": "http://localhost:8080",
        "default_models": [],
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

    # Detect local providers (host-based, not API-key-based)
    for env_var, info in LOCAL_PROVIDER_REGISTRY.items():
        provider_name = info["name"]
        if names and provider_name not in names:
            continue

        host: Optional[str] = None
        if api_keys is not None:
            host = api_keys.get(env_var) or api_keys.get(provider_name)
        if host is None:
            host = os.environ.get(env_var)

        if host:
            detected.append({
                **info,
                "base_url": host,
                "env_var": env_var,
                "api_key": "",
            })

    return detected
