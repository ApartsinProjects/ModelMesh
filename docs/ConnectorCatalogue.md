---
layout: default
title: "Connector Catalogue"
---

# Connector Catalogue

**Pre-shipped connector implementations for ModelMesh Lite.** Each section lists available implementations for one connector type. Individual connector documentation is in [connectors/](connectors/openai-llm.html). Interface definitions are in [ConnectorInterfaces.md](ConnectorInterfaces.html). Custom connectors implement the same interfaces and register in the same catalogue (see [Developer Manual](SystemConcept.html#connector-based-extensibility)).

> **Building custom connectors?** The [Connector Development Kit](cdk/Overview.html) provides base classes and tutorials for creating new connectors with minimal code.

> Pricing and availability change frequently; consult each provider's documentation for current details.

> **Connector ID format:** Connector IDs shown below use the short form used in YAML configuration. The fully-qualified form adds a type prefix (e.g., `provider.openai.llm.v1`) but this prefix is optional and typically omitted.

---

## Naming Convention

Every connector has a globally unique identifier following the pattern:

```
connector_type.vendor.service.version
```

| Segment | Description | Examples |
| --- | --- | --- |
| **connector_type** | Connector category | `provider`, `rotation`, `secret-store`, `storage`, `observability`, `discovery` |
| **vendor** | Company or organization; `modelmesh` for built-in connectors | `openai`, `aws`, `google`, `modelmesh` |
| **service** | Capability hint (providers) or service name (others) | `llm`, `image-gen`, `tts`, `secrets-manager`, `s3` |
| **version** | Version tag | `v1`, `v2` |

In YAML configuration, the `connector_type.` prefix is omitted within its own section (e.g., under `providers:`, write `openai.llm.v1` instead of `provider.openai.llm.v1`).

---

## Provider Connectors

Interface: [ConnectorInterfaces.md — Provider](ConnectorInterfaces.html#provider)

ModelMesh Lite ships with provider connectors for: **OpenAI** (`provider.openai.llm.v1`), **Gemini** (`provider.google.gemini.v1`), **OpenRouter** (`provider.openrouter.gateway.v1`), **Anthropic** (`anthropic.claude.v1`), **Groq** (`provider.groq.api.v1`), **DeepSeek** (`provider.deepseek.api.v1`), **Mistral** (`provider.mistral.api.v1`), **Together AI** (`provider.together.api.v1`), **xAI Grok** (`provider.xai.grok.v1`), **Cohere** (`provider.cohere.nlp.v1`), **Perplexity** (`provider.perplexity.search.v1`), **ElevenLabs** (`provider.elevenlabs.tts.v1`), **Azure Speech** (`provider.azure.tts.v1`), **AssemblyAI** (`provider.assemblyai.stt.v1`), **Tavily** (`provider.tavily.search.v1`), **Serper** (`provider.serper.search.v1`), **Jina** (`provider.jina.search.v1`), **Firecrawl** (`provider.firecrawl.search.v1`), **Ollama** (`ollama.local.v1`), **LM Studio** (`lmstudio.local.v1`), **vLLM** (`vllm.local.v1`), and **LocalAI** (`localai.local.v1`). Providers marked **(Planned)** below are not yet implemented.

### Provider Capability Format

Provider connectors (OpenAI, Anthropic, and others) declare model capabilities using **dot-notation paths** that reference the [capability hierarchy](ModelCapabilities.html). Short-form capability names (`"chat"`, `"tools"`, `"vision"`) are no longer used; capabilities now map directly to tree nodes such as `generation.text-generation.chat-completion`. Features like tool calling, vision, and system prompt support are declared separately in a `features` dict.

**Before (short-form, deprecated):**

```python
ModelInfo(
    id="gpt-4o",
    capabilities=["chat", "tools", "vision"],
)
```

**After (dot-notation):**

```python
ModelInfo(
    id="gpt-4o",
    capabilities=["generation.text-generation.chat-completion"],
    features={"tool_calling": True, "vision": True, "system_prompt": True},
)
```

The provider-level `capabilities` config follows the same convention. For example, both `provider.openai.llm.v1` and `anthropic.claude.v1` declare `capabilities=["generation.text-generation.chat-completion"]` instead of the former `["chat"]`.

> **Auto-discovery of model capabilities:** When a model defined in configuration does not declare `capabilities`, ModelMesh queries the provider connector's `list_models()` method to resolve them automatically. If the provider returns per-model capability information, those capabilities are used. Otherwise, the provider-level `get_capabilities()` is used as a fallback. This means most configurations only need to specify a provider and model ID; capabilities are inferred from the connector.

### Pool Definition Modes

Pools support three definition modes (see also [SystemConfiguration.md -- Pools](SystemConfiguration.html#pools)):

| Mode | Config Fields | Behaviour |
| --- | --- | --- |
| **Capability-based** | `capability` | Pool targets a capability node. Models whose resolved capabilities overlap with that node (or its descendants) are matched automatically. |
| **Explicit models** | `models` | Pool contains a fixed list of model IDs. No capability matching is performed. |
| **Hybrid** | `capability` + `models` | Capability matching discovers models automatically, and the explicit `models` list adds additional entries on top. |

```yaml
pools:
  # Capability-based: all models with chat-completion capability
  text-generation:
    capability: generation.text-generation.chat-completion
    strategy: modelmesh.cost-first.v1

  # Explicit models: hand-picked model IDs only
  premium-chat:
    models: [gpt-4o, claude-sonnet-4-20250514]
    strategy: modelmesh.priority-selection.v1

  # Hybrid: capability matching plus extra models
  code-review:
    capability: generation.text-generation.code-generation
    models: [gpt-4o]
    strategy: modelmesh.priority-selection.v1
```

### General-Purpose LLM Providers

| Provider | ID | Description | Key Models | Free Tier | Docs |
| --- | --- | --- | --- | --- | --- |
| **OpenAI** | `provider.openai.llm.v1` | Full-stack AI platform. Broadest capability set of any single provider. | GPT-4o, GPT-4.1, GPT-4.1 mini/nano, o3, o3-mini, o4-mini, DALL-E 3, Whisper, TTS-1, text-embedding-3-small/large, text-moderation-latest | Moderation API free; $5 initial credits | [developers.openai.com/api](https://developers.openai.com/api) |
| **Anthropic** | `anthropic.claude.v1` | Safety-focused LLM provider. Strong at reasoning, code, and long-context tasks. | Claude Opus 4, Claude Sonnet 4, Claude 3.7 Sonnet, Claude 3.5 Haiku, Claude 3.5 Sonnet | ~30-100 messages/day (no Opus); 90% cached token discount | [docs.anthropic.com](https://docs.anthropic.com) |
| **Google Gemini** | `provider.google.gemini.v1` | Google's multimodal AI family. Largest context windows (up to 1M tokens). | Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.0 Flash, Gemini 2.0 Flash Lite, Gemini 1.5 Pro/Flash | Generous rate-limited tier; no credit card required; 1M context included | [ai.google.dev/gemini-api](https://ai.google.dev/gemini-api) |
| **xAI (Grok)** | `provider.xai.grok.v1` | High-performance models with real-time data access via X integration. | Grok 3, Grok 3 Mini, Grok 3 Fast, Grok 2, Grok 2 Vision | $25 signup credits; $150/month via data sharing | [docs.x.ai/developers](https://docs.x.ai/developers) |
| **DeepSeek** | `provider.deepseek.api.v1` | Ultra-low-cost reasoning and chat. Strongest price-to-performance ratio. | DeepSeek Chat, DeepSeek Reasoner | 5M tokens for new accounts (30-day expiry); off-peak 75% discount | [api-docs.deepseek.com](https://api-docs.deepseek.com) |
| **Mistral AI** | `provider.mistral.api.v1` | European AI lab with efficient open-weight and proprietary models. | Mistral Large, Mistral Small, Mistral Nemo, Codestral, Mistral Embed | Rate-limited access to all models; no credit card required | [docs.mistral.ai](https://docs.mistral.ai) |
| **Cohere** | `provider.cohere.nlp.v1` | Enterprise-focused: text understanding, embeddings, and retrieval. | Command R+, Command R, Command A, Embed v4, Embed v3 (English/Multilingual), Rerank v3.5 | 1,000 calls/month; 5-20 calls/min; non-production only | [docs.cohere.com](https://docs.cohere.com) |
| **Perplexity (Sonar)** | `provider.perplexity.search.v1` | Search-augmented AI. Grounded answers with real-time web data and citations. | Sonar, Sonar Pro, Sonar Reasoning, Sonar Reasoning Pro | No free API tier; Pro subscribers get $5/month credits | [docs.perplexity.ai](https://docs.perplexity.ai) |

### Media Generation Providers

| Provider | ID | Description | Key Models | Free Tier | Docs |
| --- | --- | --- | --- | --- | --- |
| **Stability AI** (Planned) | `provider.stability.image-gen.v1` | Pioneer in open image generation models. *Not yet implemented.* | SD 3.5 Large/Medium/Turbo, Stable Image Core, Stable Image Ultra | 25-200 credits on signup (~100-200 images); community license (revenue < $1M) | [platform.stability.ai/docs](https://platform.stability.ai/docs) |
| **fal.ai** (Planned) | `provider.fal.media-gen.v1` | Fast media generation API. Specializes in image and video. *Not yet implemented.* | Flux Pro/Dev/Schnell, Kling V2 (video), Ideogram V3, HaiLuo (video) | Free credits for new users; pay-per-image thereafter | [docs.fal.ai](https://docs.fal.ai) |
| **Replicate** (Planned) | `provider.replicate.inference.v1` | Run any open-source model via API. Pay-per-second billing. *Not yet implemented.* | Flux Schnell, SDXL, Llama 3, Whisper | Limited free predictions; no credit card required | [replicate.com/docs](https://replicate.com/docs) |
| **ElevenLabs** | `provider.elevenlabs.tts.v1` | Leading voice AI. Realistic speech synthesis and voice cloning. | Multilingual v2, Turbo v2.5, Flash v2.5, Monolingual v1 | 10,000 chars/month (~20 min audio); 3 custom voices; non-commercial | [elevenlabs.io/docs](https://elevenlabs.io/docs) |
| **AssemblyAI** | `provider.assemblyai.stt.v1` | Speech intelligence platform. Transcription with built-in NLU. | Universal, Nano | $50 credits (~185h transcription); one-time, non-recurring | [www.assemblyai.com/docs](https://www.assemblyai.com/docs) |
| **Azure Speech** | `provider.azure.tts.v1` | Microsoft Azure Cognitive Services Speech. Neural TTS with 400+ voices in 140+ languages. | en-US-JennyNeural, en-US-AndrewNeural, and all Azure Neural voices | 0.5M chars/month free (Neural); 5M chars/month free (Standard) | [learn.microsoft.com/azure/ai-services/speech-service](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech) |

### Aggregators and Inference Platforms

| Provider | ID | Description | Key Models | Free Tier | Docs |
| --- | --- | --- | --- | --- | --- |
| **HuggingFace** (Planned) | `provider.huggingface.inference.v1` | Gateway to 100,000+ open-source models across all modalities. *Not yet implemented.* | All public Hub models; curated Providers for Llama, Mistral, Flux, Whisper | Monthly credits; serverless for models < 10 GB; PRO ($9/mo) 20x more | [huggingface.co/docs/inference-providers](https://huggingface.co/docs/inference-providers) |
| **OpenRouter** | `provider.openrouter.gateway.v1` | Unified API gateway to 290+ models from all major providers. | Aggregates OpenAI, Anthropic, Google, Meta, Mistral, DeepSeek, xAI | 24+ free models; 20 req/min, 200 req/day on free; no credit card | [openrouter.ai/docs](https://openrouter.ai/docs) |
| **Cloudflare Workers AI** (Planned) | `provider.cloudflare.workers-ai.v1` | Edge-deployed AI inference with global distribution. No cold starts. *Not yet implemented.* | Llama 3, Mistral, Qwen, SDXL, Whisper, BGE embeddings | 10,000 neurons/day; 100k requests/day | [developers.cloudflare.com/workers-ai](https://developers.cloudflare.com/workers-ai) |
| **Groq** | `provider.groq.api.v1` | Ultra-fast inference on custom LPU hardware. 500+ tokens/second. | Llama 3.3 70B, Llama 3.1 8B, Gemma 2 9B, DeepSeek R1 Distill, Whisper Large v3/v3-turbo | Rate-limited access; no credit card; Developer tier 10x limits | [console.groq.com/docs](https://console.groq.com/docs) |
| **Together AI** | `provider.together.api.v1` | Open-model cloud with 200+ models, fine-tuning, and batch inference. | Llama 3, Mistral, Qwen, DeepSeek, Flux, SDXL | $5 credits on signup; 6,000 req/min on Build tier | [docs.together.ai](https://docs.together.ai) |

### Cloud Platforms

| Provider | ID | Description | Key Models | Free Tier | Docs |
| --- | --- | --- | --- | --- | --- |
| **AWS Bedrock** (Planned) | `provider.aws.bedrock.v1` | Managed AI service with access to multiple foundation model providers. *Not yet implemented.* | Claude Sonnet 4, Claude 3.5 Haiku, Llama 3.1, Mistral Large, Amazon Nova Pro/Lite, Titan Embed, Stable Diffusion XL | No free tier; $200 new-account credit (all AWS, 6-month expiry) | [docs.aws.amazon.com/bedrock](https://docs.aws.amazon.com/bedrock) |
| **Google Cloud AI APIs** (Planned) | `provider.google.cloud-ai.v1` | Individual AI services for speech, vision, translation, and NLU. *Not yet implemented.* | Speech-to-Text (Chirp), TTS (WaveNet, Neural2), Vision, Translation, NL | 60 min/mo STT; 1M chars/mo TTS; 1,000 images/mo Vision; $300 credit | [cloud.google.com/apis](https://cloud.google.com/apis) |

### Local / Self-Hosted Providers

Local model servers expose OpenAI-compatible REST APIs, so each connector extends `OpenAICompatibleProvider` with different defaults. No API key is required — authentication is disabled by default. All local providers are **Node.js only** (`RuntimeEnvironment.NODE_ONLY`).

| Provider | ID | Default URL | Env Var | Default Models | Description |
| --- | --- | --- | --- | --- | --- |
| **Ollama** | `ollama.local.v1` | `http://localhost:11434` | `OLLAMA_HOST` | llama3, codellama, mistral, gemma2 | Run open-source LLMs locally. Simple install, model library, GPU acceleration. |
| **LM Studio** | `lmstudio.local.v1` | `http://localhost:1234` | `LMSTUDIO_HOST` | *(user-loaded)* | Desktop app for running local models. GUI model browser and chat. |
| **vLLM** | `vllm.local.v1` | `http://localhost:8000` | `VLLM_HOST` | *(user-loaded)* | High-throughput serving engine. PagedAttention, continuous batching. |
| **LocalAI** | `localai.local.v1` | `http://localhost:8080` | `LOCALAI_HOST` | *(user-loaded)* | Drop-in OpenAI replacement. Supports LLMs, image gen, audio, embeddings. |

**Auto-detection:** Local providers are detected via host environment variables (e.g., `OLLAMA_HOST=http://myserver:11434`). Unlike cloud providers, no API key env var is needed — the presence of the host variable alone enables the provider.

**Configuration:**

All local providers share the same configuration parameters inherited from `OpenAICompatibleProvider`:

| Parameter | Type | Description |
| --- | --- | --- |
| `base_url` | string | Server URL. Defaults to localhost (see table above). |
| `api_key` | string | API key for authentication. Default: `""` (no auth). |
| `models` | list | Model catalogue. Ollama ships defaults; others are empty (user-loaded). |
| `capabilities` | list | Capability paths. Default: `["generation.text-generation.chat-completion"]`. |
| `timeout` | integer | Request timeout in seconds. Default: `60`. |

**Example configuration:**

```yaml
providers:
  ollama.local.v1:
    connector: ollama.local.v1
    config:
      base_url: http://gpu-server:11434
      models:
        - id: deepseek-r1
          capabilities: [generation.text-generation.chat-completion]

  vllm.local.v1:
    connector: vllm.local.v1
    config:
      base_url: http://inference-server:8000
      models:
        - id: meta-llama/Llama-3-70B-Instruct
          capabilities: [generation.text-generation.chat-completion]
```

### Web API Services

Non-AI web services can be wrapped as provider connectors using the same interface, gaining rotation, quota management, and failover. These services are accessed through virtual model names and routed through capability pools like any other model.

#### Search

| Service | ID | Description | Free Tier | Docs |
| --- | --- | --- | --- | --- |
| **Google Custom Search** | `provider.google.search.v1` | Programmable search engine for web and image search | 100 queries/day free; $5 per 1,000 queries thereafter | [developers.google.com/custom-search](https://developers.google.com/custom-search) |
| **Bing Web Search API** | `provider.microsoft.bing-search.v1` | Microsoft's web search API via Azure Cognitive Services | 1,000 transactions/month free (S1); 3 calls/second | [learn.microsoft.com/en-us/bing/search-apis](https://learn.microsoft.com/en-us/bing/search-apis) |
| **Tavily** | `provider.tavily.search.v1` | AI-optimized search API for LLM agents and RAG pipelines | 1,000 calls/month free; no credit card required | [docs.tavily.com](https://docs.tavily.com) |
| **Serper** | `provider.serper.search.v1` | Google Search API for structured results (organic, news, images, maps) | 2,500 queries free on signup; no credit card required | [serper.dev/docs](https://serper.dev/docs) |

#### Document Parsing

| Service | ID | Description | Free Tier | Docs |
| --- | --- | --- | --- | --- |
| **Unstructured** (Planned) | `provider.unstructured.doc-parse.v1` | Extracts structured data from PDFs, images, Office docs, HTML. *Not yet implemented.* | Free serverless API with rate limits; open-source self-hosted available | [docs.unstructured.io](https://docs.unstructured.io) |
| **LlamaParse** (Planned) | `provider.llamaindex.doc-parse.v1` | Document parsing by LlamaIndex. Optimized for complex layouts, tables, charts. *Not yet implemented.* | 1,000 pages/day free; 10 files/day; no credit card required | [docs.cloud.llamaindex.ai](https://docs.cloud.llamaindex.ai) |

#### Translation and Moderation

| Service | ID | Description | Free Tier | Docs |
| --- | --- | --- | --- | --- |
| **DeepL** (Planned) | `provider.deepl.translation.v1` | Machine translation API. 30+ languages with high accuracy. *Not yet implemented.* | 500,000 characters/month free; document translation included | [developers.deepl.com/docs](https://developers.deepl.com/docs) |
| **Perspective API** (Planned) | `provider.google.moderation.v1` | Content moderation. Scores text for toxicity, profanity, threats. *Not yet implemented.* | Free for all users; 1 query/second default quota (increase on request) | [developers.perspectiveapi.com](https://developers.perspectiveapi.com) |

### Provider Capability Matrix

| Provider              | Text Gen | Image Gen | Audio | Embeddings | Search | Tool Use | Batch | Fine-Tune | Free Tier     |
| --------------------- | -------- | --------- | ----- | ---------- | ------ | -------- | ----- | --------- | ------------- |
| **OpenAI**            | yes      | yes       | yes   | yes        | -      | yes      | yes   | yes       | limited       |
| **Anthropic**         | yes      | -         | -     | -          | -      | yes      | yes   | -         | limited       |
| **Google Gemini**     | yes      | yes       | -     | yes        | -      | yes      | yes   | yes       | generous      |
| **xAI (Grok)**        | yes      | -         | -     | -          | -      | yes      | yes   | -         | credits       |
| **DeepSeek**          | yes      | -         | -     | -          | -      | yes      | -     | -         | credits       |
| **Mistral AI**        | yes      | -         | -     | yes        | -      | yes      | -     | yes       | rate-limited  |
| **Cohere**            | yes      | -         | -     | yes        | yes    | yes      | -     | yes       | 1k calls/mo   |
| **OpenRouter**        | yes      | yes       | yes   | yes        | -      | yes      | -     | -         | 24+ models    |
| **Groq**              | yes      | -         | yes   | -          | -      | yes      | -     | -         | rate-limited  |
| **Together AI**       | yes      | yes       | -     | yes        | -      | yes      | yes   | yes       | $5 credit     |
| **ElevenLabs**        | -        | -         | yes   | -          | -      | -        | -     | -         | 10k chars/mo  |
| **AssemblyAI**        | -        | -         | yes   | -          | -      | -        | -     | -         | $50 credit    |
| **Azure Speech**      | -        | -         | yes   | -          | -      | -        | -     | -         | 0.5M chars/mo |
| **Perplexity**        | yes      | -         | -     | -          | yes    | yes      | -     | -         | Pro only      |
| **Ollama**            | yes      | -         | -     | yes        | -      | yes      | -     | -         | free (local)  |
| **LM Studio**         | yes      | -         | -     | yes        | -      | yes      | -     | -         | free (local)  |
| **vLLM**              | yes      | -         | -     | yes        | -      | yes      | yes   | -         | free (local)  |
| **LocalAI**           | yes      | yes       | yes   | yes        | -      | yes      | -     | -         | free (local)  |

### CDK Base Classes for Providers

| Base Class | Environment | Transport | Streaming | Use Case |
| --- | --- | --- | --- | --- |
| **BaseProvider** | Node.js | `http`/`https` | Node.js streams | Server-side applications, CLI tools, backend services |
| **BrowserBaseProvider** | Browser, Deno, Bun, Workers | Fetch API | `ReadableStream` | Single-page apps, browser extensions, edge runtimes |

Both classes expose the same provider interface and the same protected hooks for subclassing. See [cdk/BaseClasses.md](cdk/BaseClasses.html#browserbAseprovider) for details and [guides/BrowserUsage.md](guides/BrowserUsage.html) for browser setup.

### Runtime Environment Metadata

Every TypeScript connector class declares a `static readonly RUNTIME` property indicating browser/Node.js compatibility. This enables build-time tree-shaking and runtime compatibility checks.

```typescript
import { RuntimeEnvironment } from '@nistrapa/modelmesh-core';

// Check a connector's runtime requirement
console.log(OllamaProvider.RUNTIME);        // 'node'
console.log(LocalStorageStorage.RUNTIME);    // 'browser'
console.log(MemoryStorage.RUNTIME);          // 'universal'
```

| Value | Constant | Environment | Examples |
| --- | --- | --- | --- |
| `'node'` | `RuntimeEnvironment.NODE_ONLY` | Node.js, Bun, Deno (server) | All cloud/local providers, file storage, env/dotenv/json/encrypted/keyring secret stores |
| `'browser'` | `RuntimeEnvironment.BROWSER_ONLY` | Browser (window + document) | localStorage/sessionStorage/IndexedDB storage, BrowserSecretStore |
| `'universal'` | `RuntimeEnvironment.UNIVERSAL` | Any JavaScript runtime | MemoryStorage, MemorySecretStore, BrowserBaseProvider, all rotation policies, ConsoleObservability |

**Runtime Guard** (`detectRuntime()`, `assertRuntimeCompatible()`): Detects the current environment at runtime and throws a descriptive error if a connector is used in an incompatible environment. Available from `@nistrapa/modelmesh-core`:

```typescript
import { detectRuntime, assertRuntimeCompatible } from '@nistrapa/modelmesh-core';

const runtime = detectRuntime(); // 'node' or 'browser'
assertRuntimeCompatible('modelmesh.localstorage.v1', RuntimeEnvironment.BROWSER_ONLY);
// Throws: "Connector modelmesh.localstorage.v1 requires browser environment but running in node"
```

### Audio Namespace

ElevenLabs (`elevenlabs.tts.v1`), Azure Speech (`azure.tts.v1`), and AssemblyAI (`assemblyai.stt.v1`) are accessible through the MeshClient audio namespace, which follows the OpenAI SDK audio pattern:

```python
# Text-to-speech
audio_response = client.audio.speech.create(
    model="text-to-speech",
    input="Hello, world!",
    voice="alloy",
)

# Speech-to-text
transcript = client.audio.transcriptions.create(
    model="speech-to-text",
    file=audio_file,
)
```

Audio requests are internally bridged to `CompletionRequest`/`CompletionResponse` via the `AudioRequest` and `AudioResponse` types (see [ConnectorInterfaces.md -- Audio](ConnectorInterfaces.html#audio)). The same rotation, failover, and pool logic applies to audio providers.

---

## Rotation Policies

Interface: [ConnectorInterfaces.md — Rotation Policy](ConnectorInterfaces.html#rotation-policy). Full attributes in [SystemConfiguration.md — Pools](SystemConfiguration.html#pools).

| Policy | Description |
| --- | --- |
| **`rotation.modelmesh.stick-until-failure.v1`** | Use the current model until it fails, then rotate. Default policy. |
| **`rotation.modelmesh.priority-selection.v1`** | *(Planned)* Follow an ordered model/provider preference list; fall back on exhaust. |
| **`rotation.modelmesh.round-robin.v1`** | *(Planned)* Cycle through active models in sequence. |
| **`rotation.modelmesh.cost-first.v1`** | *(Planned)* Select the cheapest active model for each request. |
| **`rotation.modelmesh.latency-first.v1`** | *(Planned)* Select the model with the lowest observed latency. |
| **`rotation.modelmesh.session-stickiness.v1`** | *(Planned)* Route all requests in a session to the same model. |
| **`rotation.modelmesh.rate-limit-aware.v1`** | *(Planned)* Switch models preemptively before hitting rate limits. |
| **`rotation.modelmesh.load-balanced.v1`** | *(Planned)* Distribute requests proportionally to each model's rate-limit headroom. |

---

## Secret Store Connectors

Interface: [ConnectorInterfaces.md — Secret Store](ConnectorInterfaces.html#secret-store)

| Store | Description | Free Tier | Docs |
| --- | --- | --- | --- |
| **`secret-store.modelmesh.env.v1`** | Reads secrets from environment variables. Default store. | Built-in | - |
| **`secret-store.modelmesh.dotenv.v1`** | Loads secrets from `.env` files. Ideal for local development. | Built-in | - |
| **`secret-store.aws.secrets-manager.v1`** | *(Planned)* Managed secret storage with automatic rotation and IAM integration | 30-day trial; then $0.40/secret/month + $0.05/10K calls | [aws.amazon.com/secrets-manager](https://aws.amazon.com/secrets-manager) |
| **`secret-store.google.secret-manager.v1`** | *(Planned)* Google Cloud managed secrets with IAM and audit logging | 6 active versions free; 10K access ops/month free | [cloud.google.com/secret-manager](https://cloud.google.com/secret-manager) |
| **`secret-store.microsoft.key-vault.v1`** | *(Planned)* Microsoft cloud secret, key, and certificate management | 10K operations/month free (Standard tier) | [azure.microsoft.com/en-us/products/key-vault](https://azure.microsoft.com/en-us/products/key-vault) |
| **`secret-store.1password.connect.v1`** | *(Planned)* Secrets Automation API for CI/CD and server-side use | No free API tier; requires Business or Enterprise plan | [developer.1password.com](https://developer.1password.com) |
| **`secret-store.modelmesh.json-secrets.v1`** | Reads secrets from a local JSON file. Keys are top-level object keys; values are strings. Supports dot-notation for nested keys. | Built-in | - |
| **`secret-store.modelmesh.memory-secrets.v1`** | Holds secrets in an in-memory dictionary. Ideal for testing, scripting, and user-provided keys. Supports runtime add/remove via SecretManagement interface. | Built-in | - |
| **`secret-store.modelmesh.encrypted-file.v1`** | AES-256-GCM encrypted JSON file. Secrets are decrypted at initialization using a passphrase (PBKDF2) or raw key. Supports save/load round-trips. | Built-in | - |
| **`secret-store.modelmesh.keyring.v1`** | Resolves secrets from the OS keyring (macOS Keychain, Windows Credential Locker, Linux Secret Service). | Built-in | - |
| **`secret-store.modelmesh.browser-secrets.v1`** | Browser localStorage-backed secret store. Persists secrets across page reloads. TypeScript / browser only. | Built-in (TS only) | - |

### Connector-Specific Configuration

**`secret-store.modelmesh.dotenv.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `path` | string | Path to `.env` file. Default: `./.env`. |
| `override` | boolean | Override existing environment variables. Default: `false`. |

**`secret-store.aws.secrets-manager.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `region` | string | AWS region (e.g., `us-east-1`). |
| `prefix` | string | Key name prefix for scoping (e.g., `modelmesh/`). |
| `version_stage` | string | Version stage to retrieve: `AWSCURRENT`, `AWSPREVIOUS`. Default: `AWSCURRENT`. |

**`secret-store.google.secret-manager.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `project` | string | GCP project ID. |
| `prefix` | string | Secret name prefix for scoping. |

**`secret-store.microsoft.key-vault.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `vault_url` | string | Key Vault URL (e.g., `https://my-vault.vault.azure.net`). |
| `tenant_id` | string | Azure AD tenant ID. |

**`secret-store.1password.connect.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `server_url` | string | 1Password Connect server URL. |
| `vault_id` | string | Vault UUID to resolve secrets from. |
| `token` | string | Connect server token (or secret reference). |

**`secret-store.modelmesh.json-secrets.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `file_path` | string | Path to the JSON secrets file. |
| `json_path` | string | Dot-notation path to scope lookups to a nested object (e.g., `secrets.production`). |
| `fail_on_missing` | boolean | Throw on missing keys. Default: `true`. |

**`secret-store.modelmesh.memory-secrets.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `secrets` | object | Dictionary of secret name/value pairs. |
| `fail_on_missing` | boolean | Throw on missing keys. Default: `true`. |
| `cache_enabled` | boolean | Enable TTL-based caching. Default: `true`. |

**`secret-store.modelmesh.encrypted-file.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `file_path` | string | Path to the encrypted secrets file. |
| `passphrase` | string | Human-readable passphrase for PBKDF2 key derivation. |
| `encryption_key` | string | Raw 32-byte key as a 64-character hex string. Overrides passphrase. |
| `pbkdf2_iterations` | integer | PBKDF2 iteration count. Default: `600000`. |
| `fail_on_missing` | boolean | Throw on missing keys. Default: `true`. |

**`secret-store.modelmesh.keyring.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `service_name` | string | Keyring service/application name. Default: `modelmesh`. |
| `fail_on_missing` | boolean | Throw on missing keys. Default: `true`. |

**`secret-store.modelmesh.browser-secrets.v1`:** *(TypeScript / Browser only)*

| Parameter | Type | Description |
| --- | --- | --- |
| `prefix` | string | Key namespace prefix in localStorage. Default: `modelmesh-secret:`. |
| `failOnMissing` | boolean | Throw on missing keys. Default: `true`. |

Stores secrets in the browser's localStorage. Supports the full `SecretManagement` interface (`set`, `delete`, `list`). Secrets persist across page reloads and browser restarts. **Warning:** localStorage is not encrypted — secrets are visible in browser DevTools. Suitable for user-provided API keys in personal tools; not recommended for shared production deployments.

### Deployment Patterns

| Environment | Recommended Store | Reason |
| --- | --- | --- |
| Local dev | `modelmesh.dotenv.v1` / `modelmesh.env.v1` | simple, no infra |
| Unit tests | `modelmesh.memory-secrets.v1` | inject known secrets without env setup |
| Scripts | `modelmesh.memory-secrets.v1` | pass keys from user input at runtime |
| Shared config | `modelmesh.encrypted-file.v1` | keys encrypted at rest, safe to commit |
| Desktop apps | `modelmesh.keyring.v1` | OS-native secure storage |
| Browser apps | `modelmesh.browser-secrets.v1` | persistent, user-provided keys |
| Browser testing | `modelmesh.memory-secrets.v1` | no browser APIs needed |
| AWS / GCP | native secret manager | IAM integration |
| Serverless | cloud secret manager | runtime injection |
| Client-side | server proxy | keys never reach client |
| CI/CD | `modelmesh.env.v1` | pipeline-injected |

---

## Storage Connectors

Interface: [ConnectorInterfaces.md — Storage](ConnectorInterfaces.html#storage)

| Connector | Backend | Concurrency | Free Tier | Best For | Docs |
| --- | --- | --- | --- | --- | --- |
| **`storage.modelmesh.local-file.v1`** | local disk | single-process only | Built-in | development, single-instance deploys | - |
| **`storage.aws.s3.v1`** | *(Planned)* AWS S3 | conditional writes | 5 GB, 20K GET, 2K PUT/month (12 months) | multi-instance, serverless | [aws.amazon.com/s3](https://aws.amazon.com/s3) |
| **`storage.google.drive.v1`** | *(Planned)* Google Drive | revision-based | 15 GB free (shared across Google services) | shared team state, client-side apps | [developers.google.com/drive](https://developers.google.com/drive) |
| **`storage.redis.redis.v1`** | *(Planned)* Redis | atomic operations | Redis Cloud 30 MB free; self-hosted open-source | low-latency multi-instance sync | [redis.io](https://redis.io) |
| **`storage.modelmesh.sqlite.v1`** | SQLite | single-process only | Built-in | structured local storage, queryable state | - |
| **`storage.modelmesh.memory.v1`** | in-memory | single-process only | Built-in | testing, ephemeral workloads, no persistence | - |
| **`storage.modelmesh.localstorage.v1`** | browser localStorage | single-tab | Built-in (TS only) | browser apps, small state (~5-10 MB) | - |
| **`storage.modelmesh.sessionstorage.v1`** | browser sessionStorage | single-tab | Built-in (TS only) | browser apps, session-scoped state | - |
| **`storage.modelmesh.indexeddb.v1`** | browser IndexedDB | single-origin | Built-in (TS only) | browser apps, large state, no size limit | - |

### Connector-Specific Configuration

**`storage.modelmesh.local-file.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `path` | string | File path for state data (e.g., `./mesh-state.json`). |
| `backup` | boolean | Create a `.bak` copy before each write. Default: `false`. |

**`storage.aws.s3.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `bucket` | string | S3 bucket name. |
| `key` | string | Object key (e.g., `state.json`). |
| `region` | string | AWS region. |
| `endpoint` | string | Custom S3-compatible endpoint URL. |

**`storage.google.drive.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `folder_id` | string | Google Drive folder ID for state files. |
| `credentials` | string | Service account credentials path or secret reference. |
| `filename` | string | File name in Drive. Default: `mesh-state.json`. |

**`storage.redis.redis.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `url` | string | Redis connection URL (e.g., `redis://localhost:6379/0`). |
| `host` | string | Redis host. Alternative to `url`. |
| `port` | integer | Redis port. Default: `6379`. |
| `db` | integer | Redis database number. Default: `0`. |
| `password` | string | Redis password or secret reference. |
| `key_prefix` | string | Key namespace prefix (e.g., `modelmesh:`). |
| `ttl` | duration | Expiration for stored entries. Default: none. |

**`storage.modelmesh.sqlite.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `path` | string | Path to the SQLite database file (e.g., `./mesh-state.db`). |
| `table` | string | Table name for state data. Default: `modelmesh_state`. |

**`storage.modelmesh.memory.v1`:**

No configuration parameters. All data is held in-memory and lost on process exit. Useful for testing and ephemeral workloads.

**`storage.modelmesh.localstorage.v1`:** *(TypeScript / Browser only)*

| Parameter | Type | Description |
| --- | --- | --- |
| `prefix` | string | Key namespace prefix in localStorage. Default: `modelmesh:`. |

Data is serialized as base64-encoded JSON. Persists across page reloads and browser restarts. Subject to the browser's localStorage quota (~5-10 MB per origin). Requires `RuntimeEnvironment.BROWSER_ONLY`.

**`storage.modelmesh.sessionstorage.v1`:** *(TypeScript / Browser only)*

| Parameter | Type | Description |
| --- | --- | --- |
| `prefix` | string | Key namespace prefix in sessionStorage. Default: `modelmesh:`. |

Identical to localStorage storage, but data is cleared when the browser tab closes. Useful for ephemeral browser-session state.

**`storage.modelmesh.indexeddb.v1`:** *(TypeScript / Browser only)*

| Parameter | Type | Description |
| --- | --- | --- |
| `dbName` | string | IndexedDB database name. Default: `modelmesh`. |
| `storeName` | string | Object store name. Default: `storage`. |
| `version` | number | Database schema version. Default: `1`. |

Natively async storage using the browser's IndexedDB API. Stores binary data directly as `Uint8Array` (no base64 overhead). No practical size limit. Recommended for browser apps with large state. Connection is lazily initialized on first use; call `close()` to release the connection.

---

### Browser Storage Deployment Patterns

| Scenario | Recommended Store | Reason |
| --- | --- | --- |
| Browser SPA, small state | `modelmesh.localstorage.v1` | Persistent, simple, synchronous-feel API |
| Browser SPA, large state | `modelmesh.indexeddb.v1` | No size limit, native binary support |
| Tab-scoped state | `modelmesh.sessionstorage.v1` | Auto-cleared on tab close |
| Browser testing | `modelmesh.memory.v1` | No browser APIs needed |

---

## Observability Connectors

Interface: [ConnectorInterfaces.md — Observability](ConnectorInterfaces.html#observability)

The observability interface combines four concerns: **events** (state changes), **logging** (request/response data), **statistics** (aggregate metrics), and **tracing** (severity-tagged structured traces). All core components (Router, Pool, Mesh) and CDK base classes (BaseProvider) emit traces through the configured observability connector. If no connector is configured, the `null` connector is used (zero overhead).

### Severity Levels

All trace entries carry a severity level. The `min_severity` configuration option filters traces below the threshold.

| Level | Value | Usage |
| --- | --- | --- |
| `DEBUG` | `"debug"` | Detailed diagnostic info: request routing, pool resolution, model selection |
| `INFO` | `"info"` | Normal operational events: initialization, successful requests, rotation |
| `WARNING` | `"warning"` | Potential issues: request failures, retries, provider errors |
| `ERROR` | `"error"` | Significant failures: model deactivation, pool exhaustion, all retries failed |
| `CRITICAL` | `"critical"` | System-level failures: unrecoverable errors, configuration invalid |

### Pre-shipped Connectors

| Connector | Output | Description |
| --- | --- | --- |
| **`observability.modelmesh.null.v1`** | (none) | No-op connector. Discards all output with zero overhead. Used as default when no observability is configured. |
| **`observability.modelmesh.console.v1`** | stdout | ANSI-colored console output for development and debugging. Color-codes events by type and traces by severity. |
| **`observability.modelmesh.file.v1`** | JSONL file | Appends structured JSON-Lines records to a local file. Suitable for development, log aggregation, and single-instance deploys. |
| **`observability.modelmesh.webhook.v1`** | HTTP POST | Sends routing events and logs to a configurable URL. Use for alerting, dashboards, or external log aggregation. |
| **`observability.modelmesh.json-log.v1`** | JSONL file | Appends JSON Lines records to a file. Each line is a self-contained JSON object with type, timestamp, and payload. Optimized for log aggregation pipelines. |
| **`observability.modelmesh.callback.v1`** | Python callback | Invokes a user-supplied Python callable for each event. Useful for custom integrations, in-process dashboards, and testing. |

### Connector-Specific Configuration

**`observability.modelmesh.console.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `log_level` | string | Detail level for request logging: `metadata`, `summary`, `full`. Default: `metadata`. |
| `min_severity` | string | Minimum severity for trace output: `debug`, `info`, `warning`, `error`, `critical`. Default: `info`. |
| `event_filter` | list | Event types to include (empty = all). Default: `[]`. |
| `use_color` | boolean | Enable ANSI color codes. Default: `true`. |
| `show_timestamp` | boolean | Show timestamps in output. Default: `true`. |
| `prefix` | string | Prefix for all output lines. Default: `[ModelMesh]`. |
| `redact_secrets` | boolean | Redact API keys and tokens in output. Default: `true`. |

**`observability.modelmesh.file.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `file_path` | string | Output file path. Default: `modelmesh.log`. |
| `log_level` | string | Detail level for request logging: `metadata`, `summary`, `full`. Default: `metadata`. |
| `min_severity` | string | Minimum severity for trace output. Default: `info`. |
| `append` | boolean | Append to existing file (vs overwrite). Default: `true`. |
| `flush_each_line` | boolean | Flush after every write for durability. Default: `true`. |
| `max_file_size_bytes` | integer | Maximum file size before rotation (0 = no limit). Default: `0`. |
| `redact_secrets` | boolean | Redact API keys and tokens. Default: `true`. |

**`observability.modelmesh.webhook.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `url` | string | Webhook endpoint URL. |
| `headers` | object | Custom HTTP headers (e.g., authorization). |
| `timeout` | duration | Request timeout (e.g., `10s`). |
| `retry_count` | integer | Retries on delivery failure. Default: `3`. |
| `batch_size` | integer | Events to buffer before sending. Default: `1` (immediate). |

**`observability.modelmesh.json-log.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `file_path` | string | Output JSONL file path. Default: `modelmesh-events.jsonl`. |
| `min_severity` | string | Minimum severity for trace output. Default: `info`. |
| `append` | boolean | Append to existing file (vs overwrite). Default: `true`. |

**`observability.modelmesh.callback.v1`:**

| Parameter | Type | Description |
| --- | --- | --- |
| `callback` | callable | Python callable invoked with each event dict. |
| `min_severity` | string | Minimum severity for trace output. Default: `info`. |

### Trace Record Format

All observability connectors write records with a `"type"` field. The file connector writes one JSON object per line (JSON-Lines format):

```jsonl
{"type":"trace","severity":"info","timestamp":"...","component":"mesh","message":"Initialized: 2 provider(s), 1 pool(s)"}
{"type":"trace","severity":"debug","timestamp":"...","component":"router","message":"Routing request","metadata":{"model":"chat-completion"}}
{"type":"trace","severity":"warning","timestamp":"...","component":"pool.text-generation","message":"Request failure","metadata":{"model_id":"openai.gpt-4o","failure_count":2,"threshold":3}}
{"type":"trace","severity":"error","timestamp":"...","component":"pool.text-generation","message":"Model deactivated","metadata":{"model_id":"openai.gpt-4o","reason":"error_threshold"}}
{"type":"event","event_type":"model_rotated","timestamp":"...","model_id":"openai.gpt-4o","provider_id":"openai.llm.v1"}
{"type":"log","timestamp":"...","model_id":"openai.gpt-4o","provider_id":"openai.llm.v1","status_code":200,"latency_ms":450}
{"type":"stats","scope_id":"pool.text-generation","requests_total":100,"requests_success":97,"requests_failed":3}
```

### Components That Emit Traces

| Component | Traces Emitted |
| --- | --- |
| **ModelMesh** | INFO: initialization, shutdown. DEBUG: provider/pool setup. WARNING: rotation with no alternative. |
| **Router** | DEBUG: request routing, pool resolution. INFO: request success. WARNING: failures, retries. ERROR: pool exhaustion. |
| **CapabilityPool** | DEBUG: model added, request succeeded. WARNING: request failure. ERROR: model deactivated. INFO: rotation, reactivation. |
| **BaseProvider** | DEBUG: sending request, error classification. INFO: request success with latency/tokens. WARNING: retryable errors. ERROR: non-retryable errors. |

---

## Discovery Connectors

Interface: [ConnectorInterfaces.md — Discovery](ConnectorInterfaces.html#discovery)

| Connector | Description |
| --- | --- |
| **`discovery.modelmesh.registry-sync.v1`** | Synchronizes the local model catalogue with provider APIs on a configurable schedule. Detects new models, deprecated models, and pricing changes. Sync frequency and auto-registration are configurable per provider. |
| **`discovery.modelmesh.health-monitor.v1`** | Probes providers at a configurable interval. Records latency, success/failure, and error codes; maintains rolling availability scores; feeds results into rotation policies for proactive deactivation. |
