---
layout: default
title: "Hugging Face Inference API"
---

# Hugging Face Inference API

**ID:** `provider.huggingface.inference.v1`
**Type:** Provider

Hugging Face Inference API provides a gateway to over 100,000 open-source models across all modalities hosted on the Hugging Face Hub. The platform supports text generation, image generation, speech-to-text, embeddings, and many other tasks through a unified API. Models under 10 GB can run on the serverless free tier, with GPU-accelerated inference available for larger models. Hugging Face also supports fine-tuning and batch processing through its training and inference providers ecosystem.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Serverless and dedicated inference endpoints |
| Capabilities | Yes | Per-model capability reporting based on Hub metadata and pipeline tags |
| Model Catalogue | Yes | Access to 100,000+ models via the Hub API |
| Quota & Rate Limits | Yes | Credit-based and rate-limited tiers; PRO tier for higher limits |
| Cost & Pricing | Yes | Free tier for small models; per-second billing for dedicated endpoints |
| Error Classification | Yes | Structured error responses with model loading status |
| Infrastructure | Partial | batch: yes, files: no, fine-tune: yes |

## Models

```python
from enum import Enum

class HuggingFaceModel(str, Enum):
    """Popular models on Hugging Face Hub. The full catalogue includes 100,000+ models."""
    META_LLAMA_3_1_70B = "meta-llama/Llama-3.1-70B-Instruct"
    MISTRAL_7B = "mistralai/Mistral-7B-Instruct-v0.3"
    QWEN2_5_72B = "Qwen/Qwen2.5-72B-Instruct"
    STABLE_DIFFUSION_XL = "stabilityai/stable-diffusion-xl-base-1.0"
    WHISPER_LARGE_V3 = "openai/whisper-large-v3"
```

```typescript
export enum HuggingFaceModel {
    /** Popular models on Hugging Face Hub. The full catalogue includes 100,000+ models. */
    META_LLAMA_3_1_70B = "meta-llama/Llama-3.1-70B-Instruct",
    MISTRAL_7B = "mistralai/Mistral-7B-Instruct-v0.3",
    QWEN2_5_72B = "Qwen/Qwen2.5-72B-Instruct",
    STABLE_DIFFUSION_XL = "stabilityai/stable-diffusion-xl-base-1.0",
    WHISPER_LARGE_V3 = "openai/whisper-large-v3",
}
```

## Capabilities

```python
class HuggingFaceCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    IMAGE_GENERATION = "image-generation"
    SPEECH_TO_TEXT = "speech-to-text"
    EMBEDDINGS = "embeddings"
    TOOL_CALLING = "tool-calling"
    BATCH = "batch"
    FINE_TUNING = "fine-tuning"
```

```typescript
export enum HuggingFaceCapability {
    TEXT_GENERATION = "text-generation",
    IMAGE_GENERATION = "image-generation",
    SPEECH_TO_TEXT = "speech-to-text",
    EMBEDDINGS = "embeddings",
    TOOL_CALLING = "tool-calling",
    BATCH = "batch",
    FINE_TUNING = "fine-tuning",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | Hugging Face API token. Required. |
| `base_url` | string | `https://api-inference.huggingface.co` | API base URL for serverless inference. |
| `timeout` | duration | `120s` | Request timeout. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `use_gpu` | boolean | `false` | Request GPU-accelerated inference when available. |
| `wait_for_model` | boolean | `false` | Wait for the model to load instead of returning a 503 if the model is not ready. |

## YAML Example

```yaml
providers:
  huggingface.inference.v1:
    api_key: ${secrets:HUGGINGFACE_API_TOKEN}
    timeout: 120s
    use_gpu: true
    wait_for_model: true
```
