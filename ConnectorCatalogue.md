# Connector Catalogue

**Pre-shipped connector implementations for ModelMesh Lite.** Each section covers one connector type with descriptions, free-tier limits, and provider links. Custom connectors register in the same catalogue and receive identical treatment (see [Developer Manual](README.md#connector-based-extensibility)).

> Pricing and availability change frequently; consult each provider's documentation for current details.

---

## AI Model Providers

Provider connectors expose AI models through a uniform OpenAI-compatible interface. ModelMesh Lite ships with connectors for: **OpenAI**, **Gemini**, **HuggingFace**, **OpenRouter**, and **Cloudflare Workers AI**. The remaining providers below are supported through custom or community connectors.

### General-Purpose LLM Providers

| Provider | Description | Key Models | Free Tier | Docs |
| --- | --- | --- | --- | --- |
| **OpenAI** | Full-stack AI platform. Broadest capability set of any single provider. | GPT-5.2, GPT-5.2 Pro, GPT-5 mini, GPT-5 nano, Whisper, text-embedding-3-small/large, omni-moderation-latest | ~10 messages/5h (GPT-5.2 Instant); moderation API free; $5 initial credits | [developers.openai.com/api](https://developers.openai.com/api) |
| **Anthropic** | Safety-focused LLM provider. Strong at reasoning, code, and long-context tasks. | Claude Opus 4.5, Claude Sonnet 4.5, Claude Haiku 4.5 | ~30-100 messages/day (no Opus); 90% cached token discount | [docs.anthropic.com](https://docs.anthropic.com) |
| **Google Gemini** | Google's multimodal AI family. Largest context windows (up to 1M tokens). | Gemini 3.1 Pro, Gemini 3 Flash, Gemini 2.5 Pro/Flash | Generous rate-limited tier; no credit card required; 1M context included | [ai.google.dev/gemini-api](https://ai.google.dev/gemini-api) |
| **xAI (Grok)** | High-performance models with real-time data access via X integration. | Grok 4, Grok 4.1 Fast (2M context) | $25 signup credits; $150/month via data sharing | [docs.x.ai/developers](https://docs.x.ai/developers) |
| **DeepSeek** | Ultra-low-cost reasoning and chat. Strongest price-to-performance ratio. | DeepSeek V3.2 (chat), DeepSeek R1 (reasoning) | 5M tokens for new accounts (30-day expiry); off-peak 75% discount | [api-docs.deepseek.com](https://api-docs.deepseek.com) |
| **Mistral AI** | European AI lab with efficient open-weight and proprietary models. | Mistral Large, Mistral Small 3.1 (vision), Nemo, Codestral, Mistral Embed | Rate-limited access to all models; no credit card required | [docs.mistral.ai](https://docs.mistral.ai) |
| **Cohere** | Enterprise-focused: text understanding, embeddings, and retrieval. | Command R+, Command R, Embed 4 (multimodal), Rerank 3.5 | 1,000 calls/month; 5-20 calls/min; non-production only | [docs.cohere.com](https://docs.cohere.com) |
| **Perplexity (Sonar)** | Search-augmented AI. Grounded answers with real-time web data and citations. | Sonar, Sonar Pro, Sonar Reasoning Pro | No free API tier; Pro subscribers get $5/month credits | [docs.perplexity.ai](https://docs.perplexity.ai) |

### Media Generation Providers

| Provider | Description | Key Models | Free Tier | Docs |
| --- | --- | --- | --- | --- |
| **Stability AI** | Pioneer in open image generation models. | Stable Diffusion 3.5, SDXL, Stable Image Core | 25-200 credits on signup (~100-200 images); community license (revenue < $1M) | [platform.stability.ai/docs](https://platform.stability.ai/docs) |
| **fal.ai** | Fast media generation API. Specializes in image and video. | Flux, Kling 3.0, Ideogram V3, Stable Diffusion, HaiLuo (video) | Free credits for new users; pay-per-image thereafter | [docs.fal.ai](https://docs.fal.ai) |
| **Replicate** | Run any open-source model via API. Pay-per-second billing. | Flux, SDXL, Stable Video, Whisper, Llama 3, Wan 2.1 (video) | Limited free predictions; no credit card required | [replicate.com/docs](https://replicate.com/docs) |
| **ElevenLabs** | Leading voice AI. Realistic speech synthesis and voice cloning. | Multilingual v2, Turbo v2.5, Flash (low-latency) | 10,000 chars/month (~20 min audio); 3 custom voices; non-commercial | [elevenlabs.io/docs](https://elevenlabs.io/docs) |
| **AssemblyAI** | Speech intelligence platform. Transcription with built-in NLU. | Universal, Universal-Streaming, conformer-based | $50 credits (~185h transcription); one-time, non-recurring | [www.assemblyai.com/docs](https://www.assemblyai.com/docs) |

### Aggregators and Inference Platforms

| Provider | Description | Key Models | Free Tier | Docs |
| --- | --- | --- | --- | --- |
| **HuggingFace** | Gateway to 100,000+ open-source models across all modalities. | All public Hub models; curated Providers for Llama, Mistral, Flux, Whisper | Monthly credits; serverless for models < 10 GB; PRO ($9/mo) 20x more | [huggingface.co/docs/inference-providers](https://huggingface.co/docs/inference-providers) |
| **OpenRouter** | Unified API gateway to 290+ models from all major providers. | Aggregates OpenAI, Anthropic, Google, Meta, Mistral, DeepSeek, xAI | 24+ free models; 20 req/min, 200 req/day on free; no credit card | [openrouter.ai/docs](https://openrouter.ai/docs) |
| **Cloudflare Workers AI** | Edge-deployed AI inference with global distribution. No cold starts. | Llama 3, Mistral, Qwen, SDXL, Whisper, BGE embeddings | 10,000 neurons/day; 100k requests/day | [developers.cloudflare.com/workers-ai](https://developers.cloudflare.com/workers-ai) |
| **Groq** | Ultra-fast inference on custom LPU hardware. 500+ tokens/second. | Llama 4 Scout, Llama 3.3 70B, DeepSeek R1 Distill, Whisper Large v3 | Rate-limited access; no credit card; Developer tier 10x limits | [console.groq.com/docs](https://console.groq.com/docs) |
| **Together AI** | Open-model cloud with 200+ models, fine-tuning, and batch inference. | Llama 3, Mistral, Qwen, DeepSeek, Flux, SDXL | $5 credits on signup; 6,000 req/min on Build tier | [docs.together.ai](https://docs.together.ai) |

### Cloud Platforms

| Provider | Description | Key Models | Free Tier | Docs |
| --- | --- | --- | --- | --- |
| **AWS Bedrock** | Managed AI service with access to multiple foundation model providers. | Claude, Llama, Mistral, Amazon Nova, Stable Diffusion, Cohere, AI21 | No free tier; $200 new-account credit (all AWS, 6-month expiry) | [docs.aws.amazon.com/bedrock](https://docs.aws.amazon.com/bedrock) |
| **Google Cloud AI APIs** | Individual AI services for speech, vision, translation, and NLU. | Speech-to-Text (Chirp), TTS (WaveNet, Neural2), Vision, Translation, NL | 60 min/mo STT; 1M chars/mo TTS; 1,000 images/mo Vision; $300 credit | [cloud.google.com/apis](https://cloud.google.com/apis) |

### Provider Capability Matrix

| Provider              | Text Gen | Image Gen | Audio | Embeddings | Search | Tool Use | Batch | Fine-Tune | Free Tier     |
| --------------------- | -------- | --------- | ----- | ---------- | ------ | -------- | ----- | --------- | ------------- |
| **OpenAI**            | yes      | yes       | yes   | yes        | yes    | yes      | yes   | yes       | limited       |
| **Anthropic**         | yes      | -         | -     | -          | -      | yes      | yes   | -         | limited       |
| **Google Gemini**     | yes      | yes       | -     | yes        | yes    | yes      | yes   | yes       | generous      |
| **xAI (Grok)**        | yes      | -         | -     | -          | -      | yes      | yes   | -         | credits       |
| **DeepSeek**          | yes      | -         | -     | -          | -      | yes      | -     | -         | credits       |
| **Mistral AI**        | yes      | -         | -     | yes        | -      | yes      | -     | yes       | rate-limited  |
| **Cohere**            | yes      | -         | -     | yes        | yes    | yes      | -     | yes       | 1k calls/mo   |
| **HuggingFace**       | yes      | yes       | yes   | yes        | -      | -        | -     | yes       | credits       |
| **OpenRouter**        | yes      | yes       | yes   | yes        | -      | yes      | -     | -         | 24+ models    |
| **Cloudflare**        | yes      | yes       | yes   | yes        | -      | -        | -     | -         | 10k neurons/d |
| **Groq**              | yes      | -         | yes   | -          | -      | yes      | -     | -         | rate-limited  |
| **Together AI**       | yes      | yes       | -     | yes        | -      | yes      | yes   | yes       | $5 credit     |
| **Replicate**         | yes      | yes       | yes   | -          | -      | -        | -     | -         | limited       |
| **fal.ai**            | -        | yes       | -     | -          | -      | -        | -     | -         | credits       |
| **Stability AI**      | -        | yes       | -     | -          | -      | -        | -     | -         | credits       |
| **ElevenLabs**        | -        | -         | yes   | -          | -      | -        | -     | -         | 10k chars/mo  |
| **AssemblyAI**        | -        | -         | yes   | -          | -      | -        | -     | -         | $50 credit    |
| **Perplexity**        | yes      | -         | -     | -          | yes    | yes      | -     | -         | Pro only      |
| **AWS Bedrock**       | yes      | yes       | -     | yes        | -      | yes      | yes   | yes       | AWS credits   |
| **Google Cloud APIs** | -        | -         | yes   | -          | -      | -        | -     | -         | generous      |

---

## Web API Services

Non-AI web services can be wrapped as provider connectors, gaining the same rotation, quota management, and failover as AI models. These services are accessed through virtual model names and routed through capability pools like any other model.

### Search

| Service | Description | Free Tier | Docs |
| --- | --- | --- | --- |
| **Google Custom Search** | Programmable search engine for web and image search | 100 queries/day free; $5 per 1,000 queries thereafter | [developers.google.com/custom-search](https://developers.google.com/custom-search) |
| **Bing Web Search API** | Microsoft's web search API via Azure Cognitive Services | 1,000 transactions/month free (S1); 3 calls/second | [learn.microsoft.com/en-us/bing/search-apis](https://learn.microsoft.com/en-us/bing/search-apis) |
| **Tavily** | AI-optimized search API for LLM agents and RAG pipelines | 1,000 calls/month free; no credit card required | [docs.tavily.com](https://docs.tavily.com) |
| **Serper** | Google Search API for structured results (organic, news, images, maps) | 2,500 queries free on signup; no credit card required | [serper.dev/docs](https://serper.dev/docs) |

### Document Parsing

| Service | Description | Free Tier | Docs |
| --- | --- | --- | --- |
| **Unstructured** | Extracts structured data from PDFs, images, Office docs, HTML | Free serverless API with rate limits; open-source self-hosted available | [docs.unstructured.io](https://docs.unstructured.io) |
| **LlamaParse** | Document parsing by LlamaIndex. Optimized for complex layouts, tables, charts | 1,000 pages/day free; 10 files/day; no credit card required | [docs.cloud.llamaindex.ai](https://docs.cloud.llamaindex.ai) |

### Translation and Moderation

| Service | Description | Free Tier | Docs |
| --- | --- | --- | --- |
| **DeepL** | Machine translation API. 30+ languages with high accuracy | 500,000 characters/month free; document translation included | [developers.deepl.com/docs](https://developers.deepl.com/docs) |
| **Perspective API** | Content moderation. Scores text for toxicity, profanity, threats | Free for all users; 1 query/second default quota (increase on request) | [developers.perspectiveapi.com](https://developers.perspectiveapi.com) |

---

## Storage Connectors

Storage connectors persist library state, configuration, and observability logs to external backends.

| Connector | Backend | Concurrency | Free Tier | Best For | Docs |
| --- | --- | --- | --- | --- | --- |
| **`local-file`** | local disk | single-process only | Built-in | development, single-instance deploys | - |
| **`s3`** | AWS S3 | conditional writes | 5 GB, 20K GET, 2K PUT/month (12 months) | multi-instance, serverless | [aws.amazon.com/s3](https://aws.amazon.com/s3) |
| **`google-drive`** | Google Drive | revision-based | 15 GB free (shared across Google services) | shared team state, client-side apps | [developers.google.com/drive](https://developers.google.com/drive) |
| **`redis`** | Redis | atomic operations | Redis Cloud 30 MB free; self-hosted open-source | low-latency multi-instance sync | [redis.io](https://redis.io) |

---

## Secret Store Connectors

Secret store connectors resolve API keys and tokens from secure backends at runtime. Configuration references secrets by name (`${secrets:openai-key}`); the library resolves them through the configured store.

| Store | Description | Free Tier | Docs |
| --- | --- | --- | --- |
| **`env`** | Reads secrets from environment variables. Default store. | Built-in | - |
| **`dotenv`** | Loads secrets from `.env` files. Ideal for local development. | Built-in | - |
| **`aws-secrets-manager`** | Managed secret storage with automatic rotation and IAM integration | 30-day trial; then $0.40/secret/month + $0.05/10K calls | [aws.amazon.com/secrets-manager](https://aws.amazon.com/secrets-manager) |
| **`gcp-secret-manager`** | Google Cloud managed secrets with IAM and audit logging | 6 active versions free; 10K access ops/month free | [cloud.google.com/secret-manager](https://cloud.google.com/secret-manager) |
| **`azure-key-vault`** | Microsoft cloud secret, key, and certificate management | 10K operations/month free (Standard tier) | [azure.microsoft.com/en-us/products/key-vault](https://azure.microsoft.com/en-us/products/key-vault) |
| **`1password`** | Secrets Automation API for CI/CD and server-side use | No free API tier; requires Business or Enterprise plan | [developer.1password.com](https://developer.1password.com) |

### Deployment Patterns

| Environment | Recommended Store | Reason |
| --- | --- | --- |
| Local dev | `dotenv` / `env` | simple, no infra |
| AWS / GCP | native secret manager | IAM integration |
| Serverless | cloud secret manager | runtime injection |
| Client-side | server proxy | keys never reach client |
| CI/CD | `env` | pipeline-injected |

---

## Observability Connectors

Observability connectors export routing decisions, request logs, and aggregate statistics. Multiple connectors can be active simultaneously.

| Connector | Output | Description |
| --- | --- | --- |
| **`console`** | stdout/stderr | Writes routing decisions and logs to standard output. Default connector. |
| **`local-file`** | JSONL file | Appends structured records to a local file. Suitable for development and single-instance deploys. |
| **`webhook`** | HTTP POST | Sends routing events and logs to a configurable URL. Use for alerting, dashboards, or external log aggregation. |

---

## Discovery Connectors

Discovery connectors keep the model catalogue accurate and provider health visible without manual intervention.

| Connector | Description |
| --- | --- |
| **`registry-sync`** | Synchronizes the local model catalogue with provider APIs on a configurable schedule. Detects new models, deprecated models, and pricing changes. Sync frequency and auto-registration are configurable per provider. |
| **`health-monitor`** | Background process that probes providers at a configurable interval. Records latency, success/failure, and error codes; maintains rolling availability scores; feeds results into rotation policies for proactive deactivation. |

---

## Rotation Policies

Rotation policies govern model lifecycle within each pool. Each policy combines deactivation, recovery, and selection components, configurable independently per pool. Full attributes in [Appendix F](APPENDICES.md#appendix-f--per-pool-rotation-policy-attributes).

| Policy | Description |
| --- | --- |
| **`stick-until-failure`** | Use the current model until it fails, then rotate. Default policy. |
| **`priority-selection`** | Follow an ordered model/provider preference list; fall back on exhaust. |
| **`round-robin`** | Cycle through active models in sequence. |
| **`cost-first`** | Select the cheapest active model for each request. |
| **`latency-first`** | Select the model with the lowest observed latency. |
| **`session-stickiness`** | Route all requests in a session to the same model. |
| **`rate-limit-aware`** | Switch models preemptively before hitting rate limits. |
| **`load-balanced`** | Distribute requests proportionally to each model's rate-limit headroom. |
