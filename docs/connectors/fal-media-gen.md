# fal.ai

**ID:** `provider.fal.media-gen.v1`
**Type:** Provider

fal.ai is a fast media generation API specializing in image and video creation. The platform provides access to state-of-the-art models including Flux for image generation, Kling for video generation, and Ideogram for typography-aware image creation. fal.ai is designed for speed, offering some of the fastest inference times for media generation tasks. The platform uses a queue-based architecture for longer-running tasks like video generation, with webhook support for asynchronous result delivery.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Synchronous and queue-based async execution |
| Capabilities | Yes | Per-model capability reporting for image and video |
| Model Catalogue | No | Models identified by path-based IDs |
| Quota & Rate Limits | Yes | Credit-based usage tracking |
| Cost & Pricing | Yes | Per-generation pricing varies by model and resolution |
| Error Classification | Yes | Structured error responses with queue status |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class FalModel(str, Enum):
    """Available models for fal.ai."""
    FLUX_PRO = "fal-ai/flux-pro"
    FLUX_DEV = "fal-ai/flux/dev"
    FLUX_SCHNELL = "fal-ai/flux/schnell"
    KLING_V2 = "fal-ai/kling-video/v2"
    IDEOGRAM_V3 = "fal-ai/ideogram/v3"
    HAILUO_VIDEO = "fal-ai/hailuo-ai/minimax-video-01"
```

```typescript
export enum FalModel {
    FLUX_PRO = "fal-ai/flux-pro",
    FLUX_DEV = "fal-ai/flux/dev",
    FLUX_SCHNELL = "fal-ai/flux/schnell",
    KLING_V2 = "fal-ai/kling-video/v2",
    IDEOGRAM_V3 = "fal-ai/ideogram/v3",
    HAILUO_VIDEO = "fal-ai/hailuo-ai/minimax-video-01",
}
```

## Capabilities

```python
class FalCapability(str, Enum):
    """Capabilities supported by this provider."""
    IMAGE_GENERATION = "image-generation"
    VIDEO_GENERATION = "video-generation"
```

```typescript
export enum FalCapability {
    IMAGE_GENERATION = "image-generation",
    VIDEO_GENERATION = "video-generation",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | fal.ai API key. Required. |
| `base_url` | string | `https://fal.run` | API base URL. |
| `timeout` | duration | `300s` | Request timeout. Longer default for video generation. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `queue_mode` | boolean | `false` | Enable queue-based async execution for long-running tasks. When enabled, requests return a queue ID for polling. |

## YAML Example

```yaml
providers:
  fal.media-gen.v1:
    api_key: ${secrets:FAL_API_KEY}
    timeout: 300s
    queue_mode: true
```
