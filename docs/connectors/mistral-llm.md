# Mistral AI

**ID:** `provider.mistral.llm.v1`
**Type:** Provider

Mistral AI is a European AI lab producing efficient open-weight and proprietary language models. The platform offers a range of models from the compact Mistral Nemo to the powerful Mistral Large, along with the specialized Codestral model for code generation. Mistral provides embedding capabilities and supports fine-tuning for model customization. All models are available through a rate-limited free tier with no credit card required.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Chat completions with streaming and function calling |
| Capabilities | Yes | Per-model capability and context window reporting |
| Model Catalogue | Yes | Dynamic model listing via the Models API |
| Quota & Rate Limits | Yes | Tier-based rate limits with free-tier quotas |
| Cost & Pricing | Yes | Per-token pricing across all model tiers |
| Error Classification | Yes | Structured error responses with rate-limit headers |
| Infrastructure | Partial | batch: no, files: no, fine-tune: yes |

## Models

```python
from enum import Enum

class MistralModel(str, Enum):
    """Available models for Mistral AI."""
    MISTRAL_LARGE = "mistral-large-latest"
    MISTRAL_SMALL = "mistral-small-latest"
    MISTRAL_NEMO = "open-mistral-nemo"
    CODESTRAL = "codestral-latest"
    MISTRAL_EMBED = "mistral-embed"
```

```typescript
export enum MistralModel {
    MISTRAL_LARGE = "mistral-large-latest",
    MISTRAL_SMALL = "mistral-small-latest",
    MISTRAL_NEMO = "open-mistral-nemo",
    CODESTRAL = "codestral-latest",
    MISTRAL_EMBED = "mistral-embed",
}
```

## Capabilities

```python
class MistralCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    CODE_GENERATION = "code-generation"
    EMBEDDINGS = "embeddings"
    TOOL_CALLING = "tool-calling"
    STRUCTURED_OUTPUT = "structured-output"
    FINE_TUNING = "fine-tuning"
```

```typescript
export enum MistralCapability {
    TEXT_GENERATION = "text-generation",
    CODE_GENERATION = "code-generation",
    EMBEDDINGS = "embeddings",
    TOOL_CALLING = "tool-calling",
    STRUCTURED_OUTPUT = "structured-output",
    FINE_TUNING = "fine-tuning",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | Mistral API key. Required. |
| `base_url` | string | `https://api.mistral.ai/v1` | API base URL. |
| `timeout` | duration | `60s` | Request timeout. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |

## YAML Example

```yaml
providers:
  mistral.llm.v1:
    api_key: ${secrets:MISTRAL_API_KEY}
    timeout: 60s
    max_retries: 3
```
