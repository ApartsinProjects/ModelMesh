# Replicate

**ID:** `provider.replicate.inference.v1`
**Type:** Provider

Replicate provides an API for running open-source machine learning models with pay-per-second billing. The platform hosts a vast catalogue of community and official models spanning image generation, text generation, video creation, and speech-to-text. Replicate handles all infrastructure concerns including GPU provisioning and scaling, making it straightforward to run any open-source model without managing hardware. Webhook support enables efficient async workflows for longer-running predictions.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Prediction API with synchronous and async modes |
| Capabilities | Yes | Per-model capability reporting based on model metadata |
| Model Catalogue | Yes | Extensive model catalogue via API with versioning |
| Quota & Rate Limits | Yes | Concurrency-based limits with usage tracking |
| Cost & Pricing | Yes | Per-second GPU billing; varies by hardware tier |
| Error Classification | Yes | Structured prediction status and error reporting |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class ReplicateModel(str, Enum):
    """Available models for Replicate."""
    FLUX_SCHNELL = "black-forest-labs/flux-schnell"
    SDXL = "stability-ai/sdxl"
    LLAMA_3 = "meta/llama-3"
    WHISPER = "openai/whisper"
```

```typescript
export enum ReplicateModel {
    FLUX_SCHNELL = "black-forest-labs/flux-schnell",
    SDXL = "stability-ai/sdxl",
    LLAMA_3 = "meta/llama-3",
    WHISPER = "openai/whisper",
}
```

## Capabilities

```python
class ReplicateCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    IMAGE_GENERATION = "image-generation"
    VIDEO_GENERATION = "video-generation"
    SPEECH_TO_TEXT = "speech-to-text"
```

```typescript
export enum ReplicateCapability {
    TEXT_GENERATION = "text-generation",
    IMAGE_GENERATION = "image-generation",
    VIDEO_GENERATION = "video-generation",
    SPEECH_TO_TEXT = "speech-to-text",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | Replicate API token. Required. |
| `base_url` | string | `https://api.replicate.com/v1` | API base URL. |
| `timeout` | duration | `300s` | Request timeout. Longer default for cold-start models. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `webhook_url` | string | `null` | URL to receive prediction completion webhooks. |
| `webhook_events` | list | `["completed"]` | Webhook event filters: `start`, `output`, `logs`, `completed`. |

## YAML Example

```yaml
providers:
  replicate.inference.v1:
    api_key: ${secrets:REPLICATE_API_TOKEN}
    timeout: 300s
    webhook_url: https://my-app.example.com/webhooks/replicate
    webhook_events:
      - completed
```
