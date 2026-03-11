# Obtaining Provider API Keys

This guide explains how to get API keys for every provider supported by ModelMesh. You only need **one key** to get started — add more providers later for failover and free-tier aggregation.

---

## Quick Reference

| Provider | Env Variable | Free Tier | Sign-Up Link |
|---|---|---|---|
| [OpenAI](#openai) | `OPENAI_API_KEY` | $5 credit (new accounts) | [platform.openai.com](https://platform.openai.com/signup) |
| [Anthropic](#anthropic) | `ANTHROPIC_API_KEY` | $5 credit (new accounts) | [console.anthropic.com](https://console.anthropic.com/) |
| [Google Gemini](#google-gemini) | `GOOGLE_API_KEY` | Generous free tier | [aistudio.google.com](https://aistudio.google.com/apikey) |
| [xAI (Grok)](#xai-grok) | `XAI_API_KEY` | $25 free credit | [console.x.ai](https://console.x.ai/) |
| [DeepSeek](#deepseek) | `DEEPSEEK_API_KEY` | Free trial credits | [platform.deepseek.com](https://platform.deepseek.com/) |
| [Mistral AI](#mistral-ai) | `MISTRAL_API_KEY` | Free tier available | [console.mistral.ai](https://console.mistral.ai/) |
| [Cohere](#cohere) | `COHERE_API_KEY` | Free trial tier | [dashboard.cohere.com](https://dashboard.cohere.com/) |
| [Groq](#groq) | `GROQ_API_KEY` | Free tier (rate-limited) | [console.groq.com](https://console.groq.com/) |
| [Perplexity](#perplexity) | `PERPLEXITY_API_KEY` | Free credits on signup | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) |
| [OpenRouter](#openrouter) | `OPENROUTER_API_KEY` | Free models available | [openrouter.ai/keys](https://openrouter.ai/keys) |
| [Together AI](#together-ai) | `TOGETHER_API_KEY` | $5 free credit | [api.together.ai](https://api.together.ai/) |
| [ElevenLabs](#elevenlabs) | `ELEVENLABS_API_KEY` | 10,000 chars/month free | [elevenlabs.io](https://elevenlabs.io/) |
| [AssemblyAI](#assemblyai) | `ASSEMBLYAI_API_KEY` | Free tier available | [assemblyai.com](https://www.assemblyai.com/) |
| [Azure Speech](#azure-speech) | `AZURE_SPEECH_KEY` | 5M chars/month free | [portal.azure.com](https://portal.azure.com/) |
| [Tavily](#tavily) | `TAVILY_API_KEY` | 1,000 searches/month free | [tavily.com](https://tavily.com/) |
| [Serper](#serper) | `SERPER_API_KEY` | 2,500 searches free | [serper.dev](https://serper.dev/) |
| [Jina AI](#jina-ai) | `JINA_API_KEY` | 1M tokens/month free | [jina.ai](https://jina.ai/) |
| [Firecrawl](#firecrawl) | `FIRECRAWL_API_KEY` | 500 pages/month free | [firecrawl.dev](https://www.firecrawl.dev/) |
| [Ollama](#ollama-local) | `OLLAMA_HOST` | Free (local) | [ollama.com](https://ollama.com/) |
| [LM Studio](#lm-studio-local) | `LMSTUDIO_HOST` | Free (local) | [lmstudio.ai](https://lmstudio.ai/) |
| [vLLM](#vllm-local) | `VLLM_HOST` | Free (local) | [docs.vllm.ai](https://docs.vllm.ai/) |
| [LocalAI](#localai-local) | `LOCALAI_HOST` | Free (local) | [localai.io](https://localai.io/) |

---

## Cloud LLM Providers

### OpenAI

**Models:** GPT-4o, GPT-4o-mini, GPT-4 Turbo, o1, o3-mini, DALL-E 3, Whisper, TTS

1. Go to [platform.openai.com/signup](https://platform.openai.com/signup)
2. Create an account (email or Google/Microsoft SSO)
3. Navigate to **API Keys** in the left sidebar
4. Click **Create new secret key**, give it a name
5. Copy the key (starts with `sk-`)

```bash
export OPENAI_API_KEY="sk-..."
```

**Connector ID:** `provider.openai.llm.v1`

---

### Anthropic

**Models:** Claude Opus 4, Claude Sonnet 4, Claude 3.5 Haiku

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Sign up with email or Google SSO
3. Navigate to **API Keys** in Settings
4. Click **Create Key**
5. Copy the key (starts with `sk-ant-`)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Connector ID:** `anthropic.claude.v1`

---

### Google Gemini

**Models:** Gemini 2.0 Flash, Gemini 2.0 Pro, Gemini 1.5 Pro, Gemini 1.5 Flash

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click **Create API Key**
4. Select or create a Google Cloud project
5. Copy the key (starts with `AI`)

```bash
export GOOGLE_API_KEY="AI..."
```

**Connector ID:** `provider.google.gemini.v1`

> **Tip:** Gemini has one of the most generous free tiers — great for development and free-tier aggregation.

---

### xAI (Grok)

**Models:** Grok-2, Grok-2 Mini, Grok-3, Grok-3 Mini

1. Go to [console.x.ai](https://console.x.ai/)
2. Sign up with your X (Twitter) account or email
3. Navigate to **API Keys**
4. Click **Create API Key**
5. Copy the key

```bash
export XAI_API_KEY="xai-..."
```

**Connector ID:** `provider.xai.grok.v1`

---

### DeepSeek

**Models:** DeepSeek-V3, DeepSeek-R1, DeepSeek-Coder

1. Go to [platform.deepseek.com](https://platform.deepseek.com/)
2. Create an account
3. Navigate to **API Keys**
4. Click **Create new API key**
5. Copy the key

```bash
export DEEPSEEK_API_KEY="sk-..."
```

**Connector ID:** `provider.deepseek.api.v1`

> **Tip:** DeepSeek offers very competitive pricing — one of the lowest cost-per-token providers.

---

### Mistral AI

**Models:** Mistral Large, Mistral Small, Mistral Nemo, Codestral, Pixtral

1. Go to [console.mistral.ai](https://console.mistral.ai/)
2. Create an account
3. Navigate to **API Keys** in the sidebar
4. Click **Create new key**
5. Copy the key

```bash
export MISTRAL_API_KEY="..."
```

**Connector ID:** `provider.mistral.api.v1`

---

### Cohere

**Models:** Command R+, Command R, Embed, Rerank

1. Go to [dashboard.cohere.com](https://dashboard.cohere.com/)
2. Sign up with email or Google SSO
3. Navigate to **API Keys**
4. Your trial key is shown automatically
5. Copy the key

```bash
export COHERE_API_KEY="..."
```

**Connector ID:** `provider.cohere.nlp.v1`

---

### Groq

**Models:** LLaMA 3.3, Gemma 2, Mixtral (ultra-fast inference)

1. Go to [console.groq.com](https://console.groq.com/)
2. Sign up with email or Google SSO
3. Navigate to **API Keys**
4. Click **Create API Key**
5. Copy the key (starts with `gsk_`)

```bash
export GROQ_API_KEY="gsk_..."
```

**Connector ID:** `provider.groq.api.v1`

> **Tip:** Groq provides extremely fast inference using LPU hardware. Great for low-latency use cases.

---

### Perplexity

**Models:** Sonar, Sonar Pro (search-augmented generation)

1. Go to [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api)
2. Sign up or log in
3. Navigate to **API** settings
4. Generate an API key
5. Copy the key (starts with `pplx-`)

```bash
export PERPLEXITY_API_KEY="pplx-..."
```

**Connector ID:** `provider.perplexity.search.v1`

---

## Aggregator Platforms

### OpenRouter

**Access to 200+ models** from multiple providers through a single API key.

1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Sign up with email or Google SSO
3. Click **Create Key**
4. Copy the key (starts with `sk-or-`)

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

**Connector ID:** `provider.openrouter.gateway.v1`

> **Tip:** OpenRouter includes many free models. Useful for accessing models from providers without direct API access.

---

### Together AI

**Models:** LLaMA, Mistral, Qwen, and other open-source models at scale.

1. Go to [api.together.ai](https://api.together.ai/)
2. Create an account
3. Navigate to **Settings → API Keys**
4. Copy your key

```bash
export TOGETHER_API_KEY="..."
```

**Connector ID:** `provider.together.api.v1`

---

## Audio & Media Providers

### ElevenLabs

**Capabilities:** Text-to-Speech (high-quality voices)

1. Go to [elevenlabs.io](https://elevenlabs.io/) and sign up
2. Navigate to your **Profile** (bottom-left)
3. Click **API Key** section
4. Copy your API key

```bash
export ELEVENLABS_API_KEY="..."
```

**Connector ID:** `provider.elevenlabs.tts.v1`

---

### AssemblyAI

**Capabilities:** Speech-to-Text, transcription, audio intelligence

1. Go to [assemblyai.com](https://www.assemblyai.com/) and sign up
2. Navigate to your **Dashboard**
3. Your API key is displayed on the dashboard home page
4. Copy the key

```bash
export ASSEMBLYAI_API_KEY="..."
```

**Connector ID:** `provider.assemblyai.stt.v1`

---

### Azure Speech

**Capabilities:** Text-to-Speech, Speech-to-Text (Microsoft Neural Voices)

1. Go to [portal.azure.com](https://portal.azure.com/)
2. Create an Azure account (free tier available)
3. Create a **Speech Services** resource
4. Navigate to **Keys and Endpoint**
5. Copy **Key 1** and note the **Region**

```bash
export AZURE_SPEECH_KEY="..."
export AZURE_SPEECH_REGION="eastus"   # your region
```

**Connector ID:** `provider.azure.tts.v1`

---

## Web Service Providers

### Tavily

**Capabilities:** AI-optimized web search

1. Go to [tavily.com](https://tavily.com/) and sign up
2. Navigate to your **Dashboard**
3. Your API key is shown on the overview page
4. Copy the key (starts with `tvly-`)

```bash
export TAVILY_API_KEY="tvly-..."
```

**Connector ID:** `provider.tavily.search.v1`

---

### Serper

**Capabilities:** Google Search API (SERP results)

1. Go to [serper.dev](https://serper.dev/) and sign up
2. Navigate to **API Key** in your dashboard
3. Copy your key

```bash
export SERPER_API_KEY="..."
```

**Connector ID:** `provider.serper.search.v1`

---

### Jina AI

**Capabilities:** Embeddings, reranking, web content extraction

1. Go to [jina.ai](https://jina.ai/) and sign up
2. Navigate to **API Keys** in your account settings
3. Create and copy your key

```bash
export JINA_API_KEY="..."
```

**Connector ID:** `provider.jina.ai.v1`

---

### Firecrawl

**Capabilities:** Web scraping, content extraction, markdown conversion

1. Go to [firecrawl.dev](https://www.firecrawl.dev/) and sign up
2. Navigate to **API Keys** in your dashboard
3. Create and copy your key (starts with `fc-`)

```bash
export FIRECRAWL_API_KEY="fc-..."
```

**Connector ID:** `provider.firecrawl.scrape.v1`

---

## Local / Self-Hosted Providers

These providers run on your own machine — no API key required, no usage costs.

### Ollama (Local)

**Models:** LLaMA 3, Mistral, Gemma, Phi, CodeLLaMA, and 100+ more

1. Download from [ollama.com](https://ollama.com/)
2. Install and run: `ollama serve`
3. Pull a model: `ollama pull llama3.3`
4. The API is available at `http://localhost:11434`

```bash
export OLLAMA_HOST="http://localhost:11434"
```

**Connector ID:** `ollama.local.v1`

---

### LM Studio (Local)

**Models:** Any GGUF model from Hugging Face

1. Download from [lmstudio.ai](https://lmstudio.ai/)
2. Install and launch LM Studio
3. Download a model from the Discover tab
4. Start the local server (Developer tab)
5. The API is available at `http://localhost:1234`

```bash
export LMSTUDIO_HOST="http://localhost:1234"
```

**Connector ID:** `lmstudio.local.v1`

---

### vLLM (Local)

**Models:** Any Hugging Face model with high-performance serving

1. Install: `pip install vllm`
2. Start the server:
   ```bash
   python -m vllm.entrypoints.openai.api_server \
     --model meta-llama/Llama-3.3-70B-Instruct
   ```
3. The API is available at `http://localhost:8000`

```bash
export VLLM_HOST="http://localhost:8000"
```

**Connector ID:** `vllm.local.v1`

---

### LocalAI (Local)

**Models:** LLaMA, Whisper, Stable Diffusion, and more via OpenAI-compatible API

1. Install from [localai.io](https://localai.io/)
2. Or run via Docker:
   ```bash
   docker run -p 8080:8080 localai/localai
   ```
3. The API is available at `http://localhost:8080`

```bash
export LOCALAI_HOST="http://localhost:8080"
```

**Connector ID:** `localai.local.v1`

---

## Using Keys in ModelMesh

### Environment Variables (Simplest)

Set one or more keys and call `create()`:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

```python
import modelmesh
client = modelmesh.create("chat-completion")
# ModelMesh auto-detects all configured providers
```

### .env File (Development)

Create a `.env` file in your project root:

```bash
cp .env.example .env
# Edit .env and add your keys
```

### YAML Configuration (Production)

Reference keys via secret store in `modelmesh.yaml`:

```yaml
providers:
  openai.llm.v1:
    connector: openai.llm.v1
    config:
      api_key: "${secrets:OPENAI_API_KEY}"
```

### Programmatic (Dynamic)

Pass keys directly in code:

```python
import modelmesh

client = modelmesh.create(
    "chat-completion",
    providers={"openai": {"api_key": "sk-..."}},
)
```

---

## Best Practices

1. **Start with one provider** — you can always add more later
2. **Use free tiers** — Gemini, Groq, and OpenRouter offer generous free tiers
3. **Never commit keys** — use `.env` files (gitignored) or secret stores
4. **Rotate keys regularly** — especially for production deployments
5. **Set budget limits** — prevent surprise bills with ModelMesh budget enforcement
6. **Use local providers for development** — Ollama and LM Studio are free and fast

---

## Recommended Free-Tier Stack

For maximum free usage, set up these providers:

```bash
export GOOGLE_API_KEY="AI..."           # Gemini: generous free tier
export GROQ_API_KEY="gsk_..."           # Groq: fast free inference
export OPENROUTER_API_KEY="sk-or-..."   # OpenRouter: access to free models
```

```python
client = modelmesh.create("chat-completion")
# Chains all three providers automatically
```

ModelMesh rotates between them when quotas are exhausted.

---

See also: [System Configuration](../SystemConfiguration.md) | [Connector Catalogue](../ConnectorCatalogue.md) | [FAQ](FAQ.md) | [Troubleshooting](Troubleshooting.md)
