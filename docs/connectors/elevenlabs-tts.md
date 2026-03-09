---
layout: default
title: "ElevenLabs"
---

# ElevenLabs

**ID:** `provider.elevenlabs.tts.v1`
**Type:** Provider

ElevenLabs is a leading voice AI platform offering realistic speech synthesis and voice cloning. The platform provides multiple model tiers from the low-latency Flash model to the high-fidelity Multilingual v2 model, supporting 29+ languages. ElevenLabs is known for producing some of the most natural-sounding synthetic speech available, with fine-grained control over voice characteristics including stability and similarity. The free tier provides 10,000 characters per month with up to 3 custom voices for non-commercial use.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Text-to-speech and voice cloning endpoints with streaming |
| Capabilities | Yes | Per-model capability reporting for TTS and cloning |
| Model Catalogue | Yes | Voice and model listing via API |
| Quota & Rate Limits | Yes | Character-based quota tracking with tier limits |
| Cost & Pricing | Yes | Per-character pricing based on subscription tier |
| Error Classification | Yes | Structured error responses with quota information |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class ElevenLabsModel(str, Enum):
    """Available models for ElevenLabs."""
    MULTILINGUAL_V2 = "eleven_multilingual_v2"
    TURBO_V2_5 = "eleven_turbo_v2_5"
    FLASH = "eleven_flash_v2_5"
    MONOLINGUAL_V1 = "eleven_monolingual_v1"
```

```typescript
export enum ElevenLabsModel {
    MULTILINGUAL_V2 = "eleven_multilingual_v2",
    TURBO_V2_5 = "eleven_turbo_v2_5",
    FLASH = "eleven_flash_v2_5",
    MONOLINGUAL_V1 = "eleven_monolingual_v1",
}
```

## Voices

```python
class ElevenLabsVoiceId(str, Enum):
    """Common pre-made voice IDs."""
    RACHEL = "21m00Tcm4TlvDq8ikWAM"
    DREW = "29vD33N1CtxCmqQRPOHJ"
    CLYDE = "2EiwWnXFnvU5JabPnv8n"
    PAUL = "5Q0t7uMcjvnagumLfvZi"
```

```typescript
export enum ElevenLabsVoiceId {
    RACHEL = "21m00Tcm4TlvDq8ikWAM",
    DREW = "29vD33N1CtxCmqQRPOHJ",
    CLYDE = "2EiwWnXFnvU5JabPnv8n",
    PAUL = "5Q0t7uMcjvnagumLfvZi",
}
```

## Capabilities

```python
class ElevenLabsCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_TO_SPEECH = "text-to-speech"
    VOICE_CLONING = "voice-cloning"
```

```typescript
export enum ElevenLabsCapability {
    TEXT_TO_SPEECH = "text-to-speech",
    VOICE_CLONING = "voice-cloning",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | ElevenLabs API key. Required. |
| `base_url` | string | `https://api.elevenlabs.io/v1` | API base URL. |
| `timeout` | duration | `60s` | Request timeout. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `voice_id` | string | `null` | Default voice ID for TTS requests. See Voices section for pre-made options. |
| `stability` | float | `0.5` | Voice stability (0.0-1.0). Lower values produce more expressive speech. |
| `similarity_boost` | float | `0.75` | Voice similarity boost (0.0-1.0). Higher values make the voice more consistent. |
| `output_format` | string | `mp3_44100_128` | Audio output format: `mp3_44100_128`, `pcm_16000`, `pcm_44100`. |

## YAML Example

```yaml
providers:
  elevenlabs.tts.v1:
    api_key: ${secrets:ELEVENLABS_API_KEY}
    voice_id: 21m00Tcm4TlvDq8ikWAM
    stability: 0.5
    similarity_boost: 0.75
    output_format: mp3_44100_128
```
