# xAI (Grok)

**ID:** `provider.xai.grok.v1`
**Type:** Provider

xAI develops the Grok family of high-performance language models with real-time data access through X (formerly Twitter) integration. Grok models are designed for fast, capable text generation with strong reasoning abilities. The platform offers competitive pricing with generous signup credits and supports batch processing for cost-efficient high-volume workloads. Grok models feature vision capabilities and tool calling support.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Chat completions API with OpenAI-compatible format |
| Capabilities | Yes | Per-model capability reporting |
| Model Catalogue | Yes | Model listing via API |
| Quota & Rate Limits | Yes | Tier-based rate limits with header tracking |
| Cost & Pricing | Yes | Per-token pricing with batch discounts |
| Error Classification | Yes | Structured error codes compatible with OpenAI format |
| Infrastructure | Partial | batch: yes, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class GrokModel(str, Enum):
    """Available models for xAI Grok."""
    GROK_3 = "grok-3"
    GROK_3_MINI = "grok-3-mini"
    GROK_3_FAST = "grok-3-fast"
    GROK_2 = "grok-2"
    GROK_2_VISION = "grok-2-vision"
```

```typescript
export enum GrokModel {
    GROK_3 = "grok-3",
    GROK_3_MINI = "grok-3-mini",
    GROK_3_FAST = "grok-3-fast",
    GROK_2 = "grok-2",
    GROK_2_VISION = "grok-2-vision",
}
```

## Capabilities

```python
class GrokCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    VISION = "vision"
    TOOL_CALLING = "tool-calling"
    BATCH = "batch"
```

```typescript
export enum GrokCapability {
    TEXT_GENERATION = "text-generation",
    VISION = "vision",
    TOOL_CALLING = "tool-calling",
    BATCH = "batch",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | xAI API key. Required. |
| `base_url` | string | `https://api.x.ai/v1` | API base URL. |
| `timeout` | duration | `60s` | Request timeout. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |

## YAML Example

```yaml
providers:
  xai.grok.v1:
    api_key: ${secrets:XAI_API_KEY}
    timeout: 60s
    max_retries: 3
```
