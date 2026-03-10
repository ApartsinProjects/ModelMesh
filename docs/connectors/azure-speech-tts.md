---
layout: default
title: "Azure Speech"
---

# Azure Speech

**ID:** `provider.azure.tts.v1`
**Type:** Provider

Microsoft Azure Cognitive Services Speech provides neural text-to-speech with 400+ voices across 140+ languages and locales. The service uses SSML (Speech Synthesis Markup Language) for fine-grained control over pronunciation, pitch, speaking rate, and pauses. Azure Speech is region-based, with endpoints distributed globally. The free tier provides 0.5 million characters per month for neural voices.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Text-to-speech via REST API with SSML |
| Capabilities | Yes | Per-model TTS capability reporting |
| Model Catalogue | Yes | Voice listing via voices/list endpoint |
| Quota & Rate Limits | Yes | Character-based quota with region-specific limits |
| Cost & Pricing | Yes | Per-character pricing by voice type (Neural, Standard) |
| Error Classification | Yes | HTTP status code-based error classification |
| Infrastructure | No | batch: Long Audio API available separately |

## Voices

Azure Speech voices use the ShortName format `{locale}-{Name}Neural`:

```python
class AzureSpeechVoice(str, Enum):
    """Common Azure Neural voices."""
    JENNY = "en-US-JennyNeural"
    ANDREW = "en-US-AndrewNeural"
    ARIA = "en-US-AriaNeural"
    GUY = "en-US-GuyNeural"
    AMELIA = "en-GB-AmeliaNeural"
    DENISE = "fr-FR-DeniseNeural"
    XIAOXIAO = "zh-CN-XiaoxiaoNeural"
```

```typescript
export enum AzureSpeechVoice {
    JENNY = "en-US-JennyNeural",
    ANDREW = "en-US-AndrewNeural",
    ARIA = "en-US-AriaNeural",
    GUY = "en-US-GuyNeural",
    AMELIA = "en-GB-AmeliaNeural",
    DENISE = "fr-FR-DeniseNeural",
    XIAOXIAO = "zh-CN-XiaoxiaoNeural",
}
```

## Capabilities

```python
class AzureSpeechCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_TO_SPEECH = "text-to-speech"
```

```typescript
export enum AzureSpeechCapability {
    TEXT_TO_SPEECH = "text-to-speech",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | Azure Speech subscription key. Required. |
| `region` | string | `eastus` | Azure region for the Speech resource. |
| `base_url` | string | (derived from region) | Auto-computed as `https://{region}.tts.speech.microsoft.com`. Override for custom endpoints. |
| `voice` | string | `en-US-JennyNeural` | Default voice short name. |
| `language` | string | `en-US` | SSML language attribute. |
| `output_format` | string | `audio-24khz-48kbitrate-mono-mp3` | Audio output format. See Output Formats below. |
| `timeout` | duration | `30s` | Request timeout. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |

## Output Formats

| Format | Description |
| --- | --- |
| `audio-24khz-48kbitrate-mono-mp3` | MP3, 24 kHz, 48 kbps (default) |
| `audio-24khz-96kbitrate-mono-mp3` | MP3, 24 kHz, 96 kbps |
| `audio-48khz-192kbitrate-mono-mp3` | MP3, 48 kHz, 192 kbps |
| `riff-24khz-16bit-mono-pcm` | WAV, 24 kHz, 16-bit PCM |
| `ogg-24khz-16bit-mono-opus` | OGG Opus, 24 kHz |

## YAML Example

```yaml
providers:
  azure.tts.v1:
    api_key: ${secrets:AZURE_SPEECH_KEY}
    region: eastus
    voice: en-US-JennyNeural
    language: en-US
    output_format: audio-24khz-48kbitrate-mono-mp3
```

## Authentication

Azure Speech supports two authentication methods:

1. **Subscription key** (used by this connector): Pass the key via the `Ocp-Apim-Subscription-Key` header.
2. **Bearer token**: Exchange a subscription key for a 10-minute access token via the `issueToken` endpoint. Not used by this connector but supported by the Azure API.

## SSML

This connector automatically wraps input text in a valid SSML document. The voice and language are set from the configuration. Special XML characters (`&`, `<`, `>`) are automatically escaped.
