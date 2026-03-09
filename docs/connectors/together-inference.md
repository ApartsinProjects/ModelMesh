# Together AI

**ID:** `provider.together.inference.v1`
**Type:** Provider

Together AI provides access to 200+ open-source models with optimized inference, fine-tuning, and batch processing capabilities. The platform specializes in running leading open-source models with high throughput and competitive pricing, supporting text generation, image generation, and embeddings workloads.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | OpenAI-compatible chat completions API |
| Capabilities | Yes | Per-model capability metadata |
| Model Catalogue | Yes | Full catalogue of 200+ open-source models |
| Quota & Rate Limits | Yes | Per-key rate limits and concurrency tracking |
| Cost & Pricing | Yes | Per-token and per-image pricing |
| Error Classification | Yes | Standard HTTP error mapping |
| Infrastructure | Partial | batch: yes, files: no, fine-tune: yes |

## Models

```python
from enum import Enum

class TogetherModel(str, Enum):
    """Available models."""
    LLAMA_3_1_405B = "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo"
    LLAMA_3_1_70B = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
    QWEN_2_5_72B = "Qwen/Qwen2.5-72B-Instruct-Turbo"
    DEEPSEEK_V3 = "deepseek-ai/DeepSeek-V3"
    FLUX_1_SCHNELL = "black-forest-labs/FLUX.1-schnell-Free"
    SDXL = "stabilityai/stable-diffusion-xl-base-1.0"
```

```typescript
export enum TogetherModel {
    LLAMA_3_1_405B = "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
    LLAMA_3_1_70B = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    QWEN_2_5_72B = "Qwen/Qwen2.5-72B-Instruct-Turbo",
    DEEPSEEK_V3 = "deepseek-ai/DeepSeek-V3",
    FLUX_1_SCHNELL = "black-forest-labs/FLUX.1-schnell-Free",
    SDXL = "stabilityai/stable-diffusion-xl-base-1.0",
}
```

## Capabilities

```python
class TogetherCapability(str, Enum):
    """Capabilities supported."""
    TEXT_GENERATION = "text-generation"
    IMAGE_GENERATION = "image-generation"
    EMBEDDINGS = "embeddings"
    TOOL_CALLING = "tool-calling"
    BATCH = "batch"
    FINE_TUNING = "fine-tuning"
```

```typescript
export enum TogetherCapability {
    TEXT_GENERATION = "text-generation",
    IMAGE_GENERATION = "image-generation",
    EMBEDDINGS = "embeddings",
    TOOL_CALLING = "tool-calling",
    BATCH = "batch",
    FINE_TUNING = "fine-tuning",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| *No connector-specific parameters* | | | Standard authentication via API key is sufficient |

## YAML Example

```yaml
providers:
  together.inference.v1:
    api_key: ${secrets:TOGETHER_API_KEY}
```
