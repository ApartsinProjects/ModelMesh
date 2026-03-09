---
layout: default
title: "OpenRouter"
---

# OpenRouter

**ID:** `provider.openrouter.gateway.v1`
**Type:** Provider

OpenRouter is a unified gateway that aggregates 290+ models from multiple AI providers behind a single API. It supports automatic routing, fallback strategies, and provider preferences, allowing applications to access models from Anthropic, OpenAI, Google, Meta, DeepSeek, and others without managing individual provider integrations.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | OpenAI-compatible chat completions API |
| Capabilities | Yes | Per-model capability detection |
| Model Catalogue | Yes | Full catalogue of 290+ models with metadata |
| Quota & Rate Limits | Yes | Per-key rate limits and credit tracking |
| Cost & Pricing | Yes | Per-model pricing with cost estimation |
| Error Classification | Yes | Provider-specific error mapping |
| Infrastructure | Partial | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class OpenRouterModel(str, Enum):
    """Available models."""
    AUTO = "openrouter/auto"
    CLAUDE_SONNET_4 = "anthropic/claude-sonnet-4"
    GPT_4O = "openai/gpt-4o"
    GEMINI_2_5_PRO = "google/gemini-2.5-pro"
    LLAMA_3_1_405B = "meta-llama/llama-3.1-405b-instruct"
    DEEPSEEK_R1 = "deepseek/deepseek-r1"
```

```typescript
export enum OpenRouterModel {
    AUTO = "openrouter/auto",
    CLAUDE_SONNET_4 = "anthropic/claude-sonnet-4",
    GPT_4O = "openai/gpt-4o",
    GEMINI_2_5_PRO = "google/gemini-2.5-pro",
    LLAMA_3_1_405B = "meta-llama/llama-3.1-405b-instruct",
    DEEPSEEK_R1 = "deepseek/deepseek-r1",
}
```

## Capabilities

```python
class OpenRouterCapability(str, Enum):
    """Capabilities supported."""
    TEXT_GENERATION = "text-generation"
    IMAGE_GENERATION = "image-generation"
    EMBEDDINGS = "embeddings"
    TOOL_CALLING = "tool-calling"
```

```typescript
export enum OpenRouterCapability {
    TEXT_GENERATION = "text-generation",
    IMAGE_GENERATION = "image-generation",
    EMBEDDINGS = "embeddings",
    TOOL_CALLING = "tool-calling",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `route` | `str` | `"fallback"` | Routing strategy: `fallback` tries providers in order, `round-robin` distributes requests evenly |
| `transforms` | `list` | `[]` | List of request transforms to apply (e.g., middle-out compression) |
| `provider_preferences` | `dict` | `{}` | Provider ordering and filtering preferences for model routing |

## YAML Example

```yaml
providers:
  openrouter.gateway.v1:
    api_key: ${secrets:OPENROUTER_API_KEY}
    route: fallback
    transforms:
      - middle-out
    provider_preferences:
      allow:
        - Anthropic
        - OpenAI
      order:
        - Anthropic
```
