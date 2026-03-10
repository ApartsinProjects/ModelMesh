"""Pre-shipped provider connectors for ModelMesh Lite.

Exports LLM providers (OpenAI, Anthropic, Google Gemini, Groq, DeepSeek,
Mistral, Together, OpenRouter, xAI, Cohere, Perplexity), media providers
(ElevenLabs, Azure Speech, AssemblyAI), and non-LLM utility providers
(Tavily, Serper, Jina, Firecrawl) with their configuration classes.
Also exports local/self-hosted providers (Ollama, LM Studio, vLLM, LocalAI).
"""
from __future__ import annotations

from modelmesh.connectors.providers.anthropic_provider import (
    AnthropicProvider,
    AnthropicProviderConfig,
)
from modelmesh.connectors.providers.assemblyai_provider import (
    AssemblyAIProvider,
    AssemblyAIProviderConfig,
)
from modelmesh.connectors.providers.cohere_provider import (
    CohereProvider,
    CohereProviderConfig,
)
from modelmesh.connectors.providers.deepseek_provider import (
    DeepSeekProvider,
    DeepSeekProviderConfig,
)
from modelmesh.connectors.providers.elevenlabs_provider import (
    ElevenLabsProvider,
    ElevenLabsProviderConfig,
)
from modelmesh.connectors.providers.firecrawl_provider import (
    FirecrawlProvider,
    FirecrawlProviderConfig,
)
from modelmesh.connectors.providers.gemini_provider import (
    GeminiProvider,
    GeminiProviderConfig,
)
from modelmesh.connectors.providers.groq_provider import (
    GroqProvider,
    GroqProviderConfig,
)
from modelmesh.connectors.providers.jina_provider import (
    JinaProvider,
    JinaProviderConfig,
)
from modelmesh.connectors.providers.mistral_provider import (
    MistralProvider,
    MistralProviderConfig,
)
from modelmesh.connectors.providers.openai_provider import (
    OpenAIProvider,
    OpenAIProviderConfig,
)
from modelmesh.connectors.providers.openrouter_provider import (
    OpenRouterProvider,
    OpenRouterProviderConfig,
)
from modelmesh.connectors.providers.perplexity_provider import (
    PerplexityProvider,
    PerplexityProviderConfig,
)
from modelmesh.connectors.providers.serper_provider import (
    SerperProvider,
    SerperProviderConfig,
)
from modelmesh.connectors.providers.tavily_provider import (
    TavilyProvider,
    TavilyProviderConfig,
)
from modelmesh.connectors.providers.together_provider import (
    TogetherProvider,
    TogetherProviderConfig,
)
from modelmesh.connectors.providers.xai_provider import (
    XAIProvider,
    XAIProviderConfig,
)
from modelmesh.connectors.providers.azure_speech_provider import (
    AzureSpeechProvider,
    AzureSpeechProviderConfig,
)
from modelmesh.connectors.providers.ollama_provider import (
    OllamaProvider,
    OllamaProviderConfig,
)
from modelmesh.connectors.providers.lmstudio_provider import (
    LMStudioProvider,
    LMStudioProviderConfig,
)
from modelmesh.connectors.providers.vllm_provider import (
    VLLMProvider,
    VLLMProviderConfig,
)
from modelmesh.connectors.providers.localai_provider import (
    LocalAIProvider,
    LocalAIProviderConfig,
)

__all__ = [
    # LLM providers
    "OpenAIProvider",
    "OpenAIProviderConfig",
    "AnthropicProvider",
    "AnthropicProviderConfig",
    "GeminiProvider",
    "GeminiProviderConfig",
    "GroqProvider",
    "GroqProviderConfig",
    "DeepSeekProvider",
    "DeepSeekProviderConfig",
    "MistralProvider",
    "MistralProviderConfig",
    "TogetherProvider",
    "TogetherProviderConfig",
    "OpenRouterProvider",
    "OpenRouterProviderConfig",
    "XAIProvider",
    "XAIProviderConfig",
    "CohereProvider",
    "CohereProviderConfig",
    "PerplexityProvider",
    "PerplexityProviderConfig",
    # Media providers
    "ElevenLabsProvider",
    "ElevenLabsProviderConfig",
    # Search & utility providers
    "TavilyProvider",
    "TavilyProviderConfig",
    "SerperProvider",
    "SerperProviderConfig",
    "JinaProvider",
    "JinaProviderConfig",
    "FirecrawlProvider",
    "FirecrawlProviderConfig",
    "AssemblyAIProvider",
    "AssemblyAIProviderConfig",
    # Azure Speech TTS
    "AzureSpeechProvider",
    "AzureSpeechProviderConfig",
    # Local / self-hosted providers
    "OllamaProvider",
    "OllamaProviderConfig",
    "LMStudioProvider",
    "LMStudioProviderConfig",
    "VLLMProvider",
    "VLLMProviderConfig",
    "LocalAIProvider",
    "LocalAIProviderConfig",
]
