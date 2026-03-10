---
layout: default
title: "Groq"
---

# Groq

**ID:** `provider.groq.api.v1`
**Type:** Provider

Groq delivers ultra-fast AI inference powered by custom Language Processing Units (LPUs). Purpose-built silicon enables industry-leading throughput and latency for large language models, making Groq ideal for real-time applications that require sub-second response times. It supports text generation and speech-to-text workloads.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | OpenAI-compatible chat completions API |
| Capabilities | Yes | Per-model capability metadata |
| Model Catalogue | Yes | Curated catalogue of LPU-optimized models |
| Quota & Rate Limits | Yes | Token-per-minute and request-per-minute limits |
| Cost & Pricing | Yes | Per-token pricing by model |
| Error Classification | Yes | Standard HTTP error mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class GroqModel(str, Enum):
    """Available models."""
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"
    LLAMA_3_1_8B = "llama-3.1-8b-instant"
    GEMMA_2_9B = "gemma2-9b-it"
    DEEPSEEK_R1_DISTILL = "deepseek-r1-distill-llama-70b"
    WHISPER_LARGE_V3 = "whisper-large-v3"
    WHISPER_LARGE_V3_TURBO = "whisper-large-v3-turbo"
```

```typescript
export enum GroqModel {
    LLAMA_3_3_70B = "llama-3.3-70b-versatile",
    LLAMA_3_1_8B = "llama-3.1-8b-instant",
    GEMMA_2_9B = "gemma2-9b-it",
    DEEPSEEK_R1_DISTILL = "deepseek-r1-distill-llama-70b",
    WHISPER_LARGE_V3 = "whisper-large-v3",
    WHISPER_LARGE_V3_TURBO = "whisper-large-v3-turbo",
}
```

## Capabilities

```python
class GroqCapability(str, Enum):
    """Capabilities supported."""
    TEXT_GENERATION = "text-generation"
    SPEECH_TO_TEXT = "speech-to-text"
    TOOL_CALLING = "tool-calling"
```

```typescript
export enum GroqCapability {
    TEXT_GENERATION = "text-generation",
    SPEECH_TO_TEXT = "speech-to-text",
    TOOL_CALLING = "tool-calling",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| *No connector-specific parameters* | | | Standard authentication via API key is sufficient |

## YAML Example

```yaml
providers:
  groq.api.v1:
    api_key: ${secrets:GROQ_API_KEY}
```
