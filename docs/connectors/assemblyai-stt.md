# AssemblyAI

**ID:** `provider.assemblyai.stt.v1`
**Type:** Provider

AssemblyAI is a speech intelligence platform providing transcription with built-in natural language understanding. The platform offers two model tiers: the high-accuracy Universal model and the cost-efficient Nano model. Beyond basic transcription, AssemblyAI provides audio intelligence features including speaker diarization, sentiment analysis, topic detection, and entity recognition. New accounts receive $50 in credits, providing approximately 185 hours of transcription.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Async transcription with polling and real-time streaming |
| Capabilities | Yes | Per-model capability reporting for transcription and audio intelligence |
| Model Catalogue | No | Static model list; two model tiers available |
| Quota & Rate Limits | Yes | Concurrent transcription limits with usage tracking |
| Cost & Pricing | Yes | Per-second audio pricing by model tier |
| Error Classification | Yes | Structured error responses with transcript status |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class AssemblyAIModel(str, Enum):
    """Available models for AssemblyAI."""
    UNIVERSAL = "universal"
    NANO = "nano"
```

```typescript
export enum AssemblyAIModel {
    UNIVERSAL = "universal",
    NANO = "nano",
}
```

## Languages

```python
class TranscriptLanguage(str, Enum):
    """Common languages supported for transcription."""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    DUTCH = "nl"
    JAPANESE = "ja"
    KOREAN = "ko"
    CHINESE = "zh"
    HINDI = "hi"
    TURKISH = "tr"
    RUSSIAN = "ru"
    POLISH = "pl"
    UKRAINIAN = "uk"
    VIETNAMESE = "vi"
```

```typescript
export enum TranscriptLanguage {
    ENGLISH = "en",
    SPANISH = "es",
    FRENCH = "fr",
    GERMAN = "de",
    ITALIAN = "it",
    PORTUGUESE = "pt",
    DUTCH = "nl",
    JAPANESE = "ja",
    KOREAN = "ko",
    CHINESE = "zh",
    HINDI = "hi",
    TURKISH = "tr",
    RUSSIAN = "ru",
    POLISH = "pl",
    UKRAINIAN = "uk",
    VIETNAMESE = "vi",
}
```

## Capabilities

```python
class AssemblyAICapability(str, Enum):
    """Capabilities supported by this provider."""
    SPEECH_TO_TEXT = "speech-to-text"
    AUDIO_INTELLIGENCE = "audio-intelligence"
```

```typescript
export enum AssemblyAICapability {
    SPEECH_TO_TEXT = "speech-to-text",
    AUDIO_INTELLIGENCE = "audio-intelligence",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | AssemblyAI API key. Required. |
| `base_url` | string | `https://api.assemblyai.com/v2` | API base URL. |
| `timeout` | duration | `300s` | Request timeout. Longer default for audio processing. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `language_detection` | boolean | `false` | Enable automatic language detection. When enabled, the language parameter is ignored. |
| `speaker_labels` | boolean | `false` | Enable speaker diarization to identify individual speakers. |
| `word_timestamps` | boolean | `false` | Include word-level timestamps in the transcript. |

## YAML Example

```yaml
providers:
  assemblyai.stt.v1:
    api_key: ${secrets:ASSEMBLYAI_API_KEY}
    timeout: 300s
    language_detection: true
    speaker_labels: true
    word_timestamps: true
```
