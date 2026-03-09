---
layout: default
title: "OpenAI"
---

# OpenAI

**ID:** `provider.openai.llm.v1`
**Type:** Provider

OpenAI is a full-stack AI platform offering the broadest capability set of any single provider. It spans text generation, image generation, speech-to-text, text-to-speech, embeddings, and content moderation through a unified API. OpenAI models are known for strong general-purpose reasoning, code generation, and multimodal understanding. The platform provides comprehensive infrastructure support including batch processing, file management, and fine-tuning.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Chat completions, image generation, audio, embeddings, and moderation endpoints |
| Capabilities | Yes | Full capability reporting across all model types |
| Model Catalogue | Yes | Dynamic model listing via the Models API |
| Quota & Rate Limits | Yes | Per-model RPM/TPM limits with header-based tracking |
| Cost & Pricing | Yes | Per-token pricing for text; per-image and per-second for media |
| Error Classification | Yes | Structured error codes with retry guidance |
| Infrastructure | Yes | batch: yes, files: yes, fine-tune: yes |

## Models

```python
from enum import Enum

class OpenAIModel(str, Enum):
    """Available models for OpenAI."""
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4_TURBO = "gpt-4-turbo"
    O1 = "o1"
    O1_MINI = "o1-mini"
    O3 = "o3"
    O3_MINI = "o3-mini"
    O4_MINI = "o4-mini"
    GPT_4_1 = "gpt-4.1"
    GPT_4_1_MINI = "gpt-4.1-mini"
    GPT_4_1_NANO = "gpt-4.1-nano"
    DALL_E_3 = "dall-e-3"
    WHISPER_1 = "whisper-1"
    TTS_1 = "tts-1"
    TTS_1_HD = "tts-1-hd"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_MODERATION_LATEST = "text-moderation-latest"
```

```typescript
export enum OpenAIModel {
    GPT_4O = "gpt-4o",
    GPT_4O_MINI = "gpt-4o-mini",
    GPT_4_TURBO = "gpt-4-turbo",
    O1 = "o1",
    O1_MINI = "o1-mini",
    O3 = "o3",
    O3_MINI = "o3-mini",
    O4_MINI = "o4-mini",
    GPT_4_1 = "gpt-4.1",
    GPT_4_1_MINI = "gpt-4.1-mini",
    GPT_4_1_NANO = "gpt-4.1-nano",
    DALL_E_3 = "dall-e-3",
    WHISPER_1 = "whisper-1",
    TTS_1 = "tts-1",
    TTS_1_HD = "tts-1-hd",
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large",
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small",
    TEXT_MODERATION_LATEST = "text-moderation-latest",
}
```

## Capabilities

```python
class OpenAICapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    IMAGE_GENERATION = "image-generation"
    SPEECH_TO_TEXT = "speech-to-text"
    TEXT_TO_SPEECH = "text-to-speech"
    EMBEDDINGS = "embeddings"
    MODERATION = "moderation"
    TOOL_CALLING = "tool-calling"
    STRUCTURED_OUTPUT = "structured-output"
    BATCH = "batch"
    FINE_TUNING = "fine-tuning"
```

```typescript
export enum OpenAICapability {
    TEXT_GENERATION = "text-generation",
    IMAGE_GENERATION = "image-generation",
    SPEECH_TO_TEXT = "speech-to-text",
    TEXT_TO_SPEECH = "text-to-speech",
    EMBEDDINGS = "embeddings",
    MODERATION = "moderation",
    TOOL_CALLING = "tool-calling",
    STRUCTURED_OUTPUT = "structured-output",
    BATCH = "batch",
    FINE_TUNING = "fine-tuning",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | OpenAI API key. Required. |
| `organization` | string | `null` | OpenAI organization ID for billing attribution. |
| `project` | string | `null` | OpenAI project ID for scoped access. |
| `base_url` | string | `https://api.openai.com/v1` | API base URL. Override for proxies or compatible endpoints. |
| `timeout` | duration | `60s` | Request timeout. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |

## YAML Example

```yaml
providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    organization: org-abc123
    timeout: 120s
    max_retries: 3
```
