# ModelMesh Configure Skill

## Purpose
Generate a `modelmesh.yaml` configuration file tailored to the user's needs.

## Decision Steps

1. **Which providers?** Ask which API keys the user has available.
2. **Which capabilities?** What does their app need?
   - Chat completion (text generation)
   - Text embeddings
   - Text-to-speech
   - Speech-to-text
   - Image generation
   - Code generation
3. **Which rotation strategy?**
   - `stick-until-failure` (default, recommended) — stay with working model
   - `cost-first` — minimize spending
   - `round-robin` — spread load evenly
   - `latency-first` — fastest response
   - `rate-limit-aware` — avoid rate limits
4. **Budget controls?** Does the user want daily spend limits per provider?
5. **Secret store?** How are API keys managed?
   - `modelmesh.env.v1` (default) — environment variables
   - `modelmesh.dotenv.v1` — .env file
   - Cloud options: AWS Secrets Manager, Google Secret Manager, Azure Key Vault

## Configuration Template

```yaml
# modelmesh.yaml — Generated configuration
secrets:
  store: modelmesh.env.v1

providers:
  # Add providers based on user's available API keys
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 10.00     # optional

  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}

  groq.api.v1:
    api_key: ${secrets:GROQ_API_KEY}

models:
  # Add models for each provider
  gpt-4o-mini:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
    features:
      tool_calling: true
      structured_output: true
      json_mode: true
      system_prompt: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384

  claude-3-5-haiku:
    provider: anthropic.claude.v1
    capabilities:
      - generation.text-generation.chat-completion
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 200000
      max_output_tokens: 8192

  llama-3.3-70b:
    provider: groq.api.v1
    capabilities:
      - generation.text-generation.chat-completion
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 131072
      max_output_tokens: 32768

pools:
  text-generation:
    strategy: modelmesh.stick-until-failure.v1
    capability: generation.text-generation
```

## Provider Reference

| Provider ID | Env Var | Models |
|---|---|---|
| `openai.llm.v1` | `OPENAI_API_KEY` | gpt-4o, gpt-4o-mini, gpt-4-turbo |
| `anthropic.claude.v1` | `ANTHROPIC_API_KEY` | claude-sonnet-4, claude-3-5-haiku |
| `google.gemini.v1` | `GOOGLE_API_KEY` | gemini-2.0-flash, gemini-1.5-pro |
| `groq.api.v1` | `GROQ_API_KEY` | llama-3.3-70b, mixtral-8x7b |
| `deepseek.api.v1` | `DEEPSEEK_API_KEY` | deepseek-chat, deepseek-coder |
| `mistral.api.v1` | `MISTRAL_API_KEY` | mistral-large, mistral-medium |
| `together.api.v1` | `TOGETHER_API_KEY` | Various open-source models |
| `openrouter.gateway.v1` | `OPENROUTER_API_KEY` | Multi-provider gateway |
| `xai.grok.v1` | `XAI_API_KEY` | grok-2, grok-2-mini |
| `cohere.nlp.v1` | `COHERE_API_KEY` | command-r, command-r-plus |

## Capability Paths

| Short Name | Full Path | Use For |
|---|---|---|
| `chat-completion` | `generation.text-generation.chat-completion` | Chat, Q&A, text generation |
| `text-generation` | `generation.text-generation` | Broader text generation pool |
| `text-embeddings` | `representation.embeddings.text-embeddings` | Semantic search, RAG |
| `text-to-speech` | `generation.audio.text-to-speech` | Voice synthesis |
| `speech-to-text` | `understanding.audio.speech-to-text` | Transcription |
| `text-to-image` | `generation.image.text-to-image` | Image generation |
| `code-generation` | `generation.text-generation.code-generation` | Code completion |

## Strategy Reference

| Strategy ID | Best For |
|---|---|
| `modelmesh.stick-until-failure.v1` | General use (default) |
| `modelmesh.round-robin.v1` | Even load distribution |
| `modelmesh.cost-first.v1` | Budget-sensitive apps |
| `modelmesh.latency-first.v1` | Real-time applications |
| `modelmesh.priority-selection.v1` | Preferred model with fallback |
| `modelmesh.rate-limit-aware.v1` | High-volume apps |
| `modelmesh.load-balanced.v1` | Weighted traffic splitting |
| `modelmesh.session-stickiness.v1` | Conversation continuity |

## Verification

After creating the config, verify:

```python
from modelmesh.config.mesh_config import MeshConfig
config = MeshConfig.from_yaml("modelmesh.yaml")
print(f"Providers: {len(config.providers)}")
print(f"Models: {len(config.models)}")
print(f"Pools: {len(config.pools)}")
```
