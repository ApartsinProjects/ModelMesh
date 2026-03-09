---
layout: default
title: "Google Gemini"
---

# Google Gemini

**ID:** `provider.google.gemini.v1`
**Type:** Provider

Google Gemini is Google's multimodal AI family offering some of the largest context windows available, up to 1 million tokens. Gemini models support text generation, image generation, vision understanding, embeddings, and grounded search. The platform provides a generous free tier with no credit card required, making it accessible for development and prototyping. Gemini excels at multimodal reasoning, long-document analysis, and tasks requiring grounding in real-world information.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | GenerateContent API with streaming and multimodal input |
| Capabilities | Yes | Per-model capability and context window reporting |
| Model Catalogue | Yes | Dynamic model listing via the Models API |
| Quota & Rate Limits | Yes | Per-model RPM/TPM limits; generous free-tier quotas |
| Cost & Pricing | Yes | Per-token pricing with free-tier thresholds |
| Error Classification | Yes | Structured error responses with safety feedback |
| Infrastructure | Yes | batch: yes, files: yes, fine-tune: yes |

## Models

```python
from enum import Enum

class GeminiModel(str, Enum):
    """Available models for Google Gemini."""
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    GEMINI_2_0_FLASH_LITE = "gemini-2.0-flash-lite"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
```

```typescript
export enum GeminiModel {
    GEMINI_2_5_PRO = "gemini-2.5-pro",
    GEMINI_2_5_FLASH = "gemini-2.5-flash",
    GEMINI_2_0_FLASH = "gemini-2.0-flash",
    GEMINI_2_0_FLASH_LITE = "gemini-2.0-flash-lite",
    GEMINI_1_5_PRO = "gemini-1.5-pro",
    GEMINI_1_5_FLASH = "gemini-1.5-flash",
}
```

## Capabilities

```python
class GeminiCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    IMAGE_GENERATION = "image-generation"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    TOOL_CALLING = "tool-calling"
    STRUCTURED_OUTPUT = "structured-output"
    GROUNDING = "grounding"
    BATCH = "batch"
    FINE_TUNING = "fine-tuning"
```

```typescript
export enum GeminiCapability {
    TEXT_GENERATION = "text-generation",
    IMAGE_GENERATION = "image-generation",
    VISION = "vision",
    EMBEDDINGS = "embeddings",
    TOOL_CALLING = "tool-calling",
    STRUCTURED_OUTPUT = "structured-output",
    GROUNDING = "grounding",
    BATCH = "batch",
    FINE_TUNING = "fine-tuning",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | Google AI API key. Required. |
| `base_url` | string | `https://generativelanguage.googleapis.com/v1beta` | API base URL. |
| `timeout` | duration | `120s` | Request timeout. Longer default for large context operations. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `safety_settings` | object | `null` | Default safety threshold settings per harm category. |
| `context_window` | integer | `1000000` | Maximum context window in tokens. Up to 1M for supported models. |

## YAML Example

```yaml
providers:
  google.gemini.v1:
    api_key: ${secrets:GEMINI_API_KEY}
    timeout: 180s
    max_retries: 3
    context_window: 1000000
```
