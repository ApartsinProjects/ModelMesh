"""Tests for all pre-shipped provider connectors.

Covers CONNECTOR_ID, default config, headers, endpoints, model listing,
capabilities, and request/response translation for all 17 providers.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.interfaces.provider import CompletionRequest

# ---- LLM Providers (OpenAI-compatible) ----
from modelmesh.connectors.providers.groq_provider import (
    GroqProvider, GroqProviderConfig,
)
from modelmesh.connectors.providers.deepseek_provider import (
    DeepSeekProvider, DeepSeekProviderConfig,
)
from modelmesh.connectors.providers.mistral_provider import (
    MistralProvider, MistralProviderConfig,
)
from modelmesh.connectors.providers.together_provider import (
    TogetherProvider, TogetherProviderConfig,
)
from modelmesh.connectors.providers.openrouter_provider import (
    OpenRouterProvider, OpenRouterProviderConfig,
)
from modelmesh.connectors.providers.xai_provider import (
    XAIProvider, XAIProviderConfig,
)
from modelmesh.connectors.providers.perplexity_provider import (
    PerplexityProvider, PerplexityProviderConfig,
)

# ---- Non-OpenAI LLM Providers ----
from modelmesh.connectors.providers.gemini_provider import (
    GeminiProvider, GeminiProviderConfig,
)
from modelmesh.connectors.providers.cohere_provider import (
    CohereProvider, CohereProviderConfig,
)

# ---- Media Providers ----
from modelmesh.connectors.providers.elevenlabs_provider import (
    ElevenLabsProvider, ElevenLabsProviderConfig,
)

# ---- Search & Utility Providers ----
from modelmesh.connectors.providers.tavily_provider import (
    TavilyProvider, TavilyProviderConfig,
)
from modelmesh.connectors.providers.serper_provider import (
    SerperProvider, SerperProviderConfig,
)
from modelmesh.connectors.providers.jina_provider import (
    JinaProvider, JinaProviderConfig,
)
from modelmesh.connectors.providers.firecrawl_provider import (
    FirecrawlProvider, FirecrawlProviderConfig,
)
from modelmesh.connectors.providers.assemblyai_provider import (
    AssemblyAIProvider, AssemblyAIProviderConfig,
)
from modelmesh.connectors.providers.azure_speech_provider import (
    AzureSpeechProvider, AzureSpeechProviderConfig,
)

# ---- Local Model Providers ----
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


# ========================================================================
# Groq
# ========================================================================

class TestGroqProvider(unittest.TestCase):
    def setUp(self):
        self.config = GroqProviderConfig(api_key="gsk-test")
        self.provider = GroqProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(GroqProvider.CONNECTOR_ID, "groq.api.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.groq.com/openai")

    def test_headers_bearer(self):
        headers = self.provider._build_headers()
        self.assertEqual(headers["Authorization"], "Bearer gsk-test")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_default_models(self):
        models = self.provider.list_models()
        self.assertGreaterEqual(len(models), 4)
        ids = [m.id for m in models]
        self.assertIn("llama-3.3-70b-versatile", ids)

    def test_supports_chat(self):
        self.assertTrue(
            self.provider.supports("generation.text-generation.chat-completion")
        )

    def test_no_args_construction(self):
        p = GroqProvider()
        self.assertIsNotNone(p.list_models())


# ========================================================================
# DeepSeek
# ========================================================================

class TestDeepSeekProvider(unittest.TestCase):
    def setUp(self):
        self.config = DeepSeekProviderConfig(api_key="ds-test")
        self.provider = DeepSeekProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(DeepSeekProvider.CONNECTOR_ID, "deepseek.api.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.deepseek.com")

    def test_headers_bearer(self):
        headers = self.provider._build_headers()
        self.assertEqual(headers["Authorization"], "Bearer ds-test")

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("deepseek-chat", ids)
        self.assertIn("deepseek-reasoner", ids)

    def test_no_args_construction(self):
        p = DeepSeekProvider()
        self.assertEqual(len(p.list_models()), 2)


# ========================================================================
# Mistral
# ========================================================================

class TestMistralProvider(unittest.TestCase):
    def setUp(self):
        self.config = MistralProviderConfig(api_key="ms-test")
        self.provider = MistralProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(MistralProvider.CONNECTOR_ID, "mistral.api.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.mistral.ai")

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(endpoint, "https://api.mistral.ai/v1/chat/completions")

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("mistral-large-latest", ids)
        self.assertIn("mistral-small-latest", ids)
        self.assertIn("codestral-latest", ids)
        self.assertIn("mistral-embed", ids)

    def test_has_embedding_model(self):
        models = self.provider.list_models()
        embed = [m for m in models if m.id == "mistral-embed"]
        self.assertEqual(len(embed), 1)
        self.assertIn(
            "representation.embeddings.text-embeddings",
            embed[0].capabilities,
        )


# ========================================================================
# Together AI
# ========================================================================

class TestTogetherProvider(unittest.TestCase):
    def setUp(self):
        self.config = TogetherProviderConfig(api_key="tog-test")
        self.provider = TogetherProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(TogetherProvider.CONNECTOR_ID, "together.api.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.together.xyz")

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(
            endpoint, "https://api.together.xyz/v1/chat/completions"
        )

    def test_default_models(self):
        models = self.provider.list_models()
        self.assertGreaterEqual(len(models), 4)

    def test_has_image_gen_model(self):
        models = self.provider.list_models()
        img = [m for m in models
               if any("image" in c for c in m.capabilities)]
        self.assertGreater(len(img), 0)


# ========================================================================
# OpenRouter
# ========================================================================

class TestOpenRouterProvider(unittest.TestCase):
    def setUp(self):
        self.config = OpenRouterProviderConfig(api_key="or-test")
        self.provider = OpenRouterProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(
            OpenRouterProvider.CONNECTOR_ID, "openrouter.gateway.v1"
        )

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://openrouter.ai/api")

    def test_headers_include_x_title(self):
        headers = self.provider._build_headers()
        self.assertIn("X-Title", headers)
        self.assertEqual(headers["X-Title"], "ModelMesh")
        self.assertEqual(headers["Authorization"], "Bearer or-test")

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("auto", ids)

    def test_custom_referer(self):
        config = OpenRouterProviderConfig(
            api_key="or-test",
            http_referer="https://myapp.com",
            x_title="MyApp",
        )
        provider = OpenRouterProvider(config)
        headers = provider._build_headers()
        self.assertEqual(headers["HTTP-Referer"], "https://myapp.com")
        self.assertEqual(headers["X-Title"], "MyApp")


# ========================================================================
# xAI (Grok)
# ========================================================================

class TestXAIProvider(unittest.TestCase):
    def setUp(self):
        self.config = XAIProviderConfig(api_key="xai-test")
        self.provider = XAIProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(XAIProvider.CONNECTOR_ID, "xai.grok.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.x.ai")

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("grok-2", ids)
        self.assertIn("grok-2-mini", ids)

    def test_headers_bearer(self):
        headers = self.provider._build_headers()
        self.assertEqual(headers["Authorization"], "Bearer xai-test")


# ========================================================================
# Perplexity
# ========================================================================

class TestPerplexityProvider(unittest.TestCase):
    def setUp(self):
        self.config = PerplexityProviderConfig(api_key="pplx-test")
        self.provider = PerplexityProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(PerplexityProvider.CONNECTOR_ID, "perplexity.search.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.perplexity.ai")

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("sonar", ids)

    def test_has_search_capability(self):
        models = self.provider.list_models()
        for m in models:
            self.assertTrue(
                any("retrieval" in c or "search" in c for c in m.capabilities),
                f"Model {m.id} should have search/retrieval capability",
            )


# ========================================================================
# Google Gemini
# ========================================================================

class TestGeminiProvider(unittest.TestCase):
    def setUp(self):
        self.config = GeminiProviderConfig(api_key="gem-test")
        self.provider = GeminiProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(GeminiProvider.CONNECTOR_ID, "google.gemini.v1")

    def test_default_base_url(self):
        self.assertEqual(
            self.config.base_url,
            "https://generativelanguage.googleapis.com",
        )

    def test_headers_no_authorization(self):
        headers = self.provider._build_headers()
        self.assertNotIn("Authorization", headers)
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_endpoint_contains_api_key(self):
        self.provider._current_model = "gemini-2.0-flash"
        endpoint = self.provider._get_completion_endpoint()
        self.assertIn("key=gem-test", endpoint)
        self.assertIn("gemini-2.0-flash", endpoint)

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("gemini-2.0-flash", ids)

    def test_build_payload_gemini_format(self):
        request = CompletionRequest(
            model="gemini-2.0-flash",
            messages=[
                {"role": "user", "content": "Hello"},
            ],
        )
        payload = self.provider._build_request_payload(request)
        self.assertIn("contents", payload)
        self.assertIn("generationConfig", payload)
        self.assertNotIn("messages", payload)

    def test_build_payload_system_instruction(self):
        request = CompletionRequest(
            model="gemini-2.0-flash",
            messages=[
                {"role": "system", "content": "Be helpful"},
                {"role": "user", "content": "Hello"},
            ],
        )
        payload = self.provider._build_request_payload(request)
        self.assertIn("systemInstruction", payload)

    def test_build_payload_role_mapping(self):
        request = CompletionRequest(
            model="gemini-2.0-flash",
            messages=[
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "Bye"},
            ],
        )
        payload = self.provider._build_request_payload(request)
        roles = [c["role"] for c in payload["contents"]]
        self.assertIn("model", roles)
        self.assertNotIn("assistant", roles)

    def test_parse_response(self):
        data = {
            "candidates": [{
                "content": {"parts": [{"text": "Hi from Gemini!"}]},
                "finishReason": "STOP",
            }],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }
        resp = self.provider._parse_response(data)
        self.assertEqual(resp.choices[0].message.content, "Hi from Gemini!")
        self.assertEqual(resp.choices[0].finish_reason, "stop")
        self.assertEqual(resp.usage.prompt_tokens, 10)
        self.assertEqual(resp.usage.completion_tokens, 5)


# ========================================================================
# Cohere
# ========================================================================

class TestCohereProvider(unittest.TestCase):
    def setUp(self):
        self.config = CohereProviderConfig(api_key="co-test")
        self.provider = CohereProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(CohereProvider.CONNECTOR_ID, "cohere.nlp.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.cohere.com")

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(endpoint, "https://api.cohere.com/v2/chat")

    def test_headers_bearer(self):
        headers = self.provider._build_headers()
        self.assertEqual(headers["Authorization"], "Bearer co-test")

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("command-a-03-2025", ids)

    def test_has_embedding_model(self):
        models = self.provider.list_models()
        embed = [m for m in models if "embed" in m.id]
        self.assertGreater(len(embed), 0)

    def test_has_reranking_model(self):
        models = self.provider.list_models()
        rerank = [m for m in models if "rerank" in m.id]
        self.assertGreater(len(rerank), 0)

    def test_build_payload_cohere_format(self):
        request = CompletionRequest(
            model="command-a-03-2025",
            messages=[{"role": "user", "content": "Hello"}],
        )
        payload = self.provider._build_request_payload(request)
        self.assertIn("model", payload)
        self.assertIn("messages", payload)

    def test_parse_response(self):
        data = {
            "id": "co-123",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hi from Cohere!"}],
            },
            "finish_reason": "COMPLETE",
            "usage": {
                "billed_units": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                },
            },
        }
        resp = self.provider._parse_response(data)
        self.assertEqual(resp.choices[0].message.content, "Hi from Cohere!")
        self.assertEqual(resp.choices[0].finish_reason, "stop")
        self.assertEqual(resp.usage.prompt_tokens, 10)
        self.assertEqual(resp.usage.completion_tokens, 5)


# ========================================================================
# ElevenLabs
# ========================================================================

class TestElevenLabsProvider(unittest.TestCase):
    def setUp(self):
        self.config = ElevenLabsProviderConfig(api_key="el-test")
        self.provider = ElevenLabsProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(ElevenLabsProvider.CONNECTOR_ID, "elevenlabs.tts.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.elevenlabs.io")

    def test_headers_xi_api_key(self):
        headers = self.provider._build_headers()
        self.assertIn("xi-api-key", headers)
        self.assertEqual(headers["xi-api-key"], "el-test")
        self.assertNotIn("Authorization", headers)

    def test_endpoint_has_voice_id(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertIn("text-to-speech", endpoint)

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("eleven_multilingual_v2", ids)

    def test_tts_capability(self):
        models = self.provider.list_models()
        for m in models:
            self.assertTrue(
                any("text-to-speech" in c for c in m.capabilities),
                f"Model {m.id} should have TTS capability",
            )

    def test_build_payload_tts_format(self):
        request = CompletionRequest(
            model="eleven_multilingual_v2",
            messages=[{"role": "user", "content": "Hello world"}],
        )
        payload = self.provider._build_request_payload(request)
        self.assertIn("text", payload)
        self.assertEqual(payload["text"], "Hello world")
        self.assertIn("model_id", payload)


# ========================================================================
# Tavily
# ========================================================================

class TestTavilyProvider(unittest.TestCase):
    def setUp(self):
        self.config = TavilyProviderConfig(api_key="tvly-test")
        self.provider = TavilyProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(TavilyProvider.CONNECTOR_ID, "tavily.search.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.tavily.com")

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(endpoint, "https://api.tavily.com/search")

    def test_headers_no_auth(self):
        headers = self.provider._build_headers()
        self.assertNotIn("Authorization", headers)

    def test_build_payload_has_api_key(self):
        request = CompletionRequest(
            model="tavily-search",
            messages=[{"role": "user", "content": "AI news"}],
        )
        payload = self.provider._build_request_payload(request)
        self.assertIn("api_key", payload)
        self.assertEqual(payload["api_key"], "tvly-test")
        self.assertIn("query", payload)

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("tavily-search", ids)


# ========================================================================
# Serper
# ========================================================================

class TestSerperProvider(unittest.TestCase):
    def setUp(self):
        self.config = SerperProviderConfig(api_key="serp-test")
        self.provider = SerperProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(SerperProvider.CONNECTOR_ID, "serper.search.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://google.serper.dev")

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(endpoint, "https://google.serper.dev/search")

    def test_headers_x_api_key(self):
        headers = self.provider._build_headers()
        self.assertIn("X-API-KEY", headers)
        self.assertEqual(headers["X-API-KEY"], "serp-test")

    def test_build_payload(self):
        request = CompletionRequest(
            model="serper-google-search",
            messages=[{"role": "user", "content": "weather today"}],
        )
        payload = self.provider._build_request_payload(request)
        self.assertIn("q", payload)
        self.assertEqual(payload["q"], "weather today")


# ========================================================================
# Jina
# ========================================================================

class TestJinaProvider(unittest.TestCase):
    def setUp(self):
        self.config = JinaProviderConfig(api_key="jina-test")
        self.provider = JinaProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(JinaProvider.CONNECTOR_ID, "jina.ai.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.jina.ai")

    def test_headers_bearer(self):
        headers = self.provider._build_headers()
        self.assertEqual(headers["Authorization"], "Bearer jina-test")

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("jina-reader", ids)
        self.assertIn("jina-embeddings-v3", ids)

    def test_has_multiple_capabilities(self):
        models = self.provider.list_models()
        cap_set = set()
        for m in models:
            cap_set.update(m.capabilities)
        self.assertGreater(len(cap_set), 1)


# ========================================================================
# Firecrawl
# ========================================================================

class TestFirecrawlProvider(unittest.TestCase):
    def setUp(self):
        self.config = FirecrawlProviderConfig(api_key="fc-test")
        self.provider = FirecrawlProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(FirecrawlProvider.CONNECTOR_ID, "firecrawl.scrape.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.firecrawl.dev")

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(endpoint, "https://api.firecrawl.dev/v1/scrape")

    def test_headers_bearer(self):
        headers = self.provider._build_headers()
        self.assertEqual(headers["Authorization"], "Bearer fc-test")

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("firecrawl-scrape", ids)

    def test_build_payload(self):
        request = CompletionRequest(
            model="firecrawl-scrape",
            messages=[{"role": "user", "content": "https://example.com"}],
        )
        payload = self.provider._build_request_payload(request)
        self.assertIn("url", payload)
        self.assertEqual(payload["url"], "https://example.com")


# ========================================================================
# AssemblyAI
# ========================================================================

class TestAssemblyAIProvider(unittest.TestCase):
    def setUp(self):
        self.config = AssemblyAIProviderConfig(api_key="asm-test")
        self.provider = AssemblyAIProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(AssemblyAIProvider.CONNECTOR_ID, "assemblyai.stt.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "https://api.assemblyai.com")

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(
            endpoint, "https://api.assemblyai.com/v2/transcript"
        )

    def test_headers_no_bearer_prefix(self):
        headers = self.provider._build_headers()
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "asm-test")

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("assemblyai-best", ids)

    def test_stt_capability(self):
        models = self.provider.list_models()
        for m in models:
            self.assertTrue(
                any("speech-to-text" in c for c in m.capabilities),
                f"Model {m.id} should have STT capability",
            )


# ========================================================================
# Azure Speech TTS
# ========================================================================

class TestAzureSpeechProvider(unittest.TestCase):
    def setUp(self):
        self.config = AzureSpeechProviderConfig(api_key="azure-test-key")
        self.provider = AzureSpeechProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(AzureSpeechProvider.CONNECTOR_ID, "azure.tts.v1")

    def test_default_region(self):
        self.assertEqual(self.config.region, "eastus")

    def test_default_base_url_from_region(self):
        self.assertEqual(
            self.config.base_url,
            "https://eastus.tts.speech.microsoft.com",
        )

    def test_custom_region_updates_base_url(self):
        config = AzureSpeechProviderConfig(
            api_key="key", region="westeurope"
        )
        self.assertEqual(
            config.base_url,
            "https://westeurope.tts.speech.microsoft.com",
        )

    def test_headers_subscription_key(self):
        headers = self.provider._build_headers()
        self.assertIn("Ocp-Apim-Subscription-Key", headers)
        self.assertEqual(
            headers["Ocp-Apim-Subscription-Key"], "azure-test-key"
        )

    def test_headers_content_type_ssml(self):
        headers = self.provider._build_headers()
        self.assertEqual(headers["Content-Type"], "application/ssml+xml")

    def test_headers_output_format(self):
        headers = self.provider._build_headers()
        self.assertIn("X-Microsoft-OutputFormat", headers)
        self.assertEqual(
            headers["X-Microsoft-OutputFormat"],
            "audio-24khz-48kbitrate-mono-mp3",
        )

    def test_headers_user_agent(self):
        headers = self.provider._build_headers()
        self.assertIn("User-Agent", headers)

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertEqual(
            endpoint,
            "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1",
        )

    def test_default_models(self):
        models = self.provider.list_models()
        ids = [m.id for m in models]
        self.assertIn("en-US-JennyNeural", ids)
        self.assertIn("en-US-AndrewNeural", ids)

    def test_tts_capability(self):
        models = self.provider.list_models()
        for m in models:
            self.assertTrue(
                any("text-to-speech" in c for c in m.capabilities),
                f"Model {m.id} should have TTS capability",
            )

    def test_build_payload_ssml_format(self):
        request = CompletionRequest(
            model="en-US-JennyNeural",
            messages=[{"role": "user", "content": "Hello world"}],
        )
        payload = self.provider._build_request_payload(request)
        ssml = payload["__ssml_body"]
        self.assertIn("<speak", ssml)
        self.assertIn("<voice", ssml)
        self.assertIn("en-US-JennyNeural", ssml)
        self.assertIn("Hello world", ssml)

    def test_build_payload_escapes_xml(self):
        request = CompletionRequest(
            model="en-US-JennyNeural",
            messages=[{"role": "user", "content": "A & B < C"}],
        )
        payload = self.provider._build_request_payload(request)
        ssml = payload["__ssml_body"]
        self.assertIn("A &amp; B &lt; C", ssml)
        self.assertNotIn("A & B < C", ssml)

    def test_default_voice(self):
        self.assertEqual(self.config.voice, "en-US-JennyNeural")

    def test_default_language(self):
        self.assertEqual(self.config.language, "en-US")


# ========================================================================
# Ollama (Local)
# ========================================================================

class TestOllamaProvider(unittest.TestCase):
    def setUp(self):
        self.config = OllamaProviderConfig()
        self.provider = OllamaProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(OllamaProvider.CONNECTOR_ID, "ollama.local.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "http://localhost:11434")

    def test_empty_api_key(self):
        self.assertEqual(self.config.api_key, "")

    def test_default_models_count(self):
        models = self.provider.list_models()
        self.assertEqual(len(models), 4)
        ids = [m.id for m in models]
        self.assertIn("llama3", ids)
        self.assertIn("codellama", ids)
        self.assertIn("mistral", ids)
        self.assertIn("gemma2", ids)

    def test_capabilities(self):
        self.assertTrue(
            self.provider.supports("generation.text-generation.chat-completion")
        )

    def test_endpoint(self):
        endpoint = self.provider._get_completion_endpoint()
        self.assertIn("/v1/chat/completions", endpoint)

    def test_headers_no_auth_when_empty(self):
        headers = self.provider._build_headers()
        self.assertNotIn("Authorization", headers)

    def test_runtime_metadata(self):
        self.assertEqual(OllamaProvider.RUNTIME, "node")


# ========================================================================
# LM Studio (Local)
# ========================================================================

class TestLMStudioProvider(unittest.TestCase):
    def setUp(self):
        self.config = LMStudioProviderConfig()
        self.provider = LMStudioProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(LMStudioProvider.CONNECTOR_ID, "lmstudio.local.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "http://localhost:1234")

    def test_empty_api_key(self):
        self.assertEqual(self.config.api_key, "")

    def test_empty_default_models(self):
        models = self.provider.list_models()
        self.assertEqual(len(models), 0)

    def test_runtime_metadata(self):
        self.assertEqual(LMStudioProvider.RUNTIME, "node")


# ========================================================================
# vLLM (Local)
# ========================================================================

class TestVLLMProvider(unittest.TestCase):
    def setUp(self):
        self.config = VLLMProviderConfig()
        self.provider = VLLMProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(VLLMProvider.CONNECTOR_ID, "vllm.local.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "http://localhost:8000")

    def test_empty_api_key(self):
        self.assertEqual(self.config.api_key, "")

    def test_empty_default_models(self):
        models = self.provider.list_models()
        self.assertEqual(len(models), 0)

    def test_runtime_metadata(self):
        self.assertEqual(VLLMProvider.RUNTIME, "node")


# ========================================================================
# LocalAI (Local)
# ========================================================================

class TestLocalAIProvider(unittest.TestCase):
    def setUp(self):
        self.config = LocalAIProviderConfig()
        self.provider = LocalAIProvider(self.config)

    def test_connector_id(self):
        self.assertEqual(LocalAIProvider.CONNECTOR_ID, "localai.local.v1")

    def test_default_base_url(self):
        self.assertEqual(self.config.base_url, "http://localhost:8080")

    def test_empty_api_key(self):
        self.assertEqual(self.config.api_key, "")

    def test_empty_default_models(self):
        models = self.provider.list_models()
        self.assertEqual(len(models), 0)

    def test_runtime_metadata(self):
        self.assertEqual(LocalAIProvider.RUNTIME, "node")


# ========================================================================
# Auto-detect registry per-provider validation
# ========================================================================

from modelmesh.config.auto_detect import PROVIDER_REGISTRY


class TestProviderRegistryPerProvider(unittest.TestCase):
    """Validate each entry in the PROVIDER_REGISTRY."""

    EXPECTED = {
        "OPENAI_API_KEY": ("openai", "openai.llm.v1"),
        "ANTHROPIC_API_KEY": ("anthropic", "anthropic.claude.v1"),
        "GOOGLE_API_KEY": ("google", "google.gemini.v1"),
        "GROQ_API_KEY": ("groq", "groq.api.v1"),
        "MISTRAL_API_KEY": ("mistral", "mistral.api.v1"),
        "TOGETHER_API_KEY": ("together", "together.api.v1"),
        "OPENROUTER_API_KEY": ("openrouter", "openrouter.gateway.v1"),
        "DEEPSEEK_API_KEY": ("deepseek", "deepseek.api.v1"),
        "XAI_API_KEY": ("xai", "xai.grok.v1"),
        "COHERE_API_KEY": ("cohere", "cohere.nlp.v1"),
        "PERPLEXITY_API_KEY": ("perplexity", "perplexity.search.v1"),
        "ELEVENLABS_API_KEY": ("elevenlabs", "elevenlabs.tts.v1"),
        "TAVILY_API_KEY": ("tavily", "tavily.search.v1"),
        "SERPER_API_KEY": ("serper", "serper.search.v1"),
        "JINA_API_KEY": ("jina", "jina.ai.v1"),
        "FIRECRAWL_API_KEY": ("firecrawl", "firecrawl.scrape.v1"),
        "ASSEMBLYAI_API_KEY": ("assemblyai", "assemblyai.stt.v1"),
    }

    def test_all_expected_env_vars_present(self):
        for env_var in self.EXPECTED:
            self.assertIn(
                env_var, PROVIDER_REGISTRY,
                f"Expected {env_var} in PROVIDER_REGISTRY",
            )

    def test_provider_names_match(self):
        for env_var, (name, _) in self.EXPECTED.items():
            if env_var in PROVIDER_REGISTRY:
                self.assertEqual(
                    PROVIDER_REGISTRY[env_var]["name"], name,
                    f"Wrong name for {env_var}",
                )

    def test_connector_ids_match(self):
        for env_var, (_, connector) in self.EXPECTED.items():
            if env_var in PROVIDER_REGISTRY:
                self.assertEqual(
                    PROVIDER_REGISTRY[env_var]["connector"], connector,
                    f"Wrong connector for {env_var}",
                )

    def test_all_have_base_url(self):
        for env_var, info in PROVIDER_REGISTRY.items():
            self.assertTrue(
                info.get("base_url", "").startswith("https://"),
                f"{env_var} base_url should start with https://",
            )

    def test_all_have_default_models(self):
        for env_var, info in PROVIDER_REGISTRY.items():
            models = info.get("default_models", [])
            self.assertGreater(
                len(models), 0,
                f"{env_var} should have at least one default model",
            )

    def test_all_models_have_capabilities(self):
        for env_var, info in PROVIDER_REGISTRY.items():
            for model in info.get("default_models", []):
                caps = model.capabilities if hasattr(model, "capabilities") else model.get("capabilities", [])
                self.assertGreater(
                    len(caps), 0,
                    f"Model {model.id if hasattr(model, 'id') else model} "
                    f"in {env_var} should have capabilities",
                )

    def test_unique_provider_names(self):
        names = [info["name"] for info in PROVIDER_REGISTRY.values()]
        self.assertEqual(len(names), len(set(names)), "Provider names must be unique")

    def test_unique_connector_ids(self):
        connectors = [info["connector"] for info in PROVIDER_REGISTRY.values()]
        self.assertEqual(
            len(connectors), len(set(connectors)),
            "Connector IDs must be unique",
        )


if __name__ == "__main__":
    unittest.main()
