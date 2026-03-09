# DeepSeek

**ID:** `provider.deepseek.llm.v1`
**Type:** Provider

DeepSeek offers ultra-low-cost reasoning and chat models with the strongest price-to-performance ratio in the market. The DeepSeek platform provides two primary models: a general-purpose chat model and a dedicated reasoning model. New accounts receive 5 million free tokens with a 30-day expiry, and off-peak usage benefits from a 75% discount. DeepSeek models support tool calling and structured output, making them suitable for agent-based workflows at minimal cost.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Chat completions API with OpenAI-compatible format |
| Capabilities | Yes | Per-model capability reporting |
| Model Catalogue | No | Static model list; no dynamic discovery endpoint |
| Quota & Rate Limits | Yes | Rate limits with off-peak discount tracking |
| Cost & Pricing | Yes | Per-token pricing with time-of-day discounts |
| Error Classification | Yes | Structured error responses |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class DeepSeekModel(str, Enum):
    """Available models for DeepSeek."""
    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"
```

```typescript
export enum DeepSeekModel {
    DEEPSEEK_CHAT = "deepseek-chat",
    DEEPSEEK_REASONER = "deepseek-reasoner",
}
```

## Capabilities

```python
class DeepSeekCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    TOOL_CALLING = "tool-calling"
    STRUCTURED_OUTPUT = "structured-output"
```

```typescript
export enum DeepSeekCapability {
    TEXT_GENERATION = "text-generation",
    TOOL_CALLING = "tool-calling",
    STRUCTURED_OUTPUT = "structured-output",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | DeepSeek API key. Required. |
| `base_url` | string | `https://api.deepseek.com` | API base URL. |
| `timeout` | duration | `60s` | Request timeout. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |

## YAML Example

```yaml
providers:
  deepseek.llm.v1:
    api_key: ${secrets:DEEPSEEK_API_KEY}
    timeout: 60s
    max_retries: 3
```
