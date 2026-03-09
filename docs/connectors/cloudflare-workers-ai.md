---
layout: default
title: "Cloudflare Workers AI"
---

# Cloudflare Workers AI

**ID:** `provider.cloudflare.workers-ai.v1`
**Type:** Provider

Cloudflare Workers AI provides edge-native AI inference powered by Cloudflare's global network. Models run on GPUs deployed across Cloudflare's data centers, delivering low-latency inference close to end users. It supports text generation, image generation, speech-to-text, and embeddings workloads with pay-per-use pricing and no cold starts.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | REST API with Workers bindings |
| Capabilities | Yes | Per-model capability metadata |
| Model Catalogue | Yes | Curated catalogue of optimized models |
| Quota & Rate Limits | Yes | Per-account neuron quotas |
| Cost & Pricing | Yes | Neuron-based pricing per model |
| Error Classification | Yes | HTTP status code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class CloudflareWorkersAIModel(str, Enum):
    """Available models."""
    LLAMA_3_1_8B = "@cf/meta/llama-3.1-8b-instruct"
    MISTRAL_7B = "@cf/mistral/mistral-7b-instruct-v0.1"
    QWEN_1_5_7B = "@cf/qwen/qwen1.5-7b-chat-awq"
    STABLE_DIFFUSION_XL = "@cf/stabilityai/stable-diffusion-xl-base-1.0"
    WHISPER = "@cf/openai/whisper"
    BGE_BASE = "@cf/baai/bge-base-en-v1.5"
```

```typescript
export enum CloudflareWorkersAIModel {
    LLAMA_3_1_8B = "@cf/meta/llama-3.1-8b-instruct",
    MISTRAL_7B = "@cf/mistral/mistral-7b-instruct-v0.1",
    QWEN_1_5_7B = "@cf/qwen/qwen1.5-7b-chat-awq",
    STABLE_DIFFUSION_XL = "@cf/stabilityai/stable-diffusion-xl-base-1.0",
    WHISPER = "@cf/openai/whisper",
    BGE_BASE = "@cf/baai/bge-base-en-v1.5",
}
```

## Capabilities

```python
class CloudflareWorkersAICapability(str, Enum):
    """Capabilities supported."""
    TEXT_GENERATION = "text-generation"
    IMAGE_GENERATION = "image-generation"
    SPEECH_TO_TEXT = "speech-to-text"
    EMBEDDINGS = "embeddings"
    TOOL_CALLING = "tool-calling"
```

```typescript
export enum CloudflareWorkersAICapability {
    TEXT_GENERATION = "text-generation",
    IMAGE_GENERATION = "image-generation",
    SPEECH_TO_TEXT = "speech-to-text",
    EMBEDDINGS = "embeddings",
    TOOL_CALLING = "tool-calling",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `account_id` | `str` | *required* | Cloudflare account identifier |
| `gateway_id` | `str \| None` | `None` | Optional AI Gateway ID for logging, caching, and rate limiting |

## YAML Example

```yaml
providers:
  cloudflare.workers-ai.v1:
    api_key: ${secrets:CLOUDFLARE_API_TOKEN}
    account_id: ${secrets:CLOUDFLARE_ACCOUNT_ID}
    gateway_id: my-ai-gateway
```
