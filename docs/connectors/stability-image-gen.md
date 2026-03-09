# Stability AI

**ID:** `provider.stability.image-gen.v1`
**Type:** Provider

Stability AI is a pioneer in open image generation, developing the Stable Diffusion family of models. The platform provides a range of image generation models from the fast SD 3.5 Large Turbo to the high-quality Stable Image Ultra, covering diverse use cases from rapid prototyping to production-grade image creation. Stability AI also offers image editing and upscaling capabilities. New accounts receive signup credits, and models under a revenue threshold of $1M can use the community license.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Image generation, editing, and upscaling endpoints |
| Capabilities | Yes | Per-model capability reporting for generation, editing, and upscaling |
| Model Catalogue | No | Static model list; no dynamic discovery endpoint |
| Quota & Rate Limits | Yes | Credit-based usage tracking |
| Cost & Pricing | Yes | Per-image pricing based on model and resolution |
| Error Classification | Yes | Structured error responses with content filter feedback |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class StabilityModel(str, Enum):
    """Available models for Stability AI."""
    SD_3_5_LARGE = "sd3.5-large"
    SD_3_5_MEDIUM = "sd3.5-medium"
    SD_3_5_LARGE_TURBO = "sd3.5-large-turbo"
    STABLE_IMAGE_CORE = "stable-image-core"
    STABLE_IMAGE_ULTRA = "stable-image-ultra"
```

```typescript
export enum StabilityModel {
    SD_3_5_LARGE = "sd3.5-large",
    SD_3_5_MEDIUM = "sd3.5-medium",
    SD_3_5_LARGE_TURBO = "sd3.5-large-turbo",
    STABLE_IMAGE_CORE = "stable-image-core",
    STABLE_IMAGE_ULTRA = "stable-image-ultra",
}
```

## Capabilities

```python
class StabilityCapability(str, Enum):
    """Capabilities supported by this provider."""
    IMAGE_GENERATION = "image-generation"
    IMAGE_EDITING = "image-editing"
    UPSCALING = "upscaling"
```

```typescript
export enum StabilityCapability {
    IMAGE_GENERATION = "image-generation",
    IMAGE_EDITING = "image-editing",
    UPSCALING = "upscaling",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | Stability AI API key. Required. |
| `base_url` | string | `https://api.stability.ai/v2beta` | API base URL. |
| `timeout` | duration | `120s` | Request timeout. Longer default for image generation. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `output_format` | string | `png` | Default output image format: `png`, `jpeg`, or `webp`. |
| `aspect_ratio` | string | `1:1` | Default aspect ratio for generated images (e.g., `1:1`, `16:9`, `9:16`, `4:3`). |

## YAML Example

```yaml
providers:
  stability.image-gen.v1:
    api_key: ${secrets:STABILITY_API_KEY}
    timeout: 120s
    output_format: png
    aspect_ratio: "16:9"
```
