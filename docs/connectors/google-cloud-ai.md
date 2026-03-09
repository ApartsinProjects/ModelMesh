# Google Cloud AI APIs

**ID:** `provider.google.cloud-ai.v1`
**Type:** Provider

Google Cloud AI APIs provide access to Google's traditional machine learning services for speech, vision, translation, and natural language processing. These production-grade APIs offer pre-trained models optimized for specific tasks, integrated with Google Cloud's infrastructure for scalability, security, and enterprise support.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Google Cloud client libraries and REST API |
| Capabilities | Yes | Per-service capability metadata |
| Model Catalogue | No | Fixed set of service-specific models |
| Quota & Rate Limits | Yes | Per-project quotas managed via Cloud Console |
| Cost & Pricing | Yes | Per-request and per-unit pricing by service |
| Error Classification | Yes | Google Cloud error code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class GoogleCloudAIModel(str, Enum):
    """Available models."""
    SPEECH_TO_TEXT_V2 = "chirp_2"
    TEXT_TO_SPEECH_V1 = "standard"
    VISION_V1 = "builtin/stable"
    TRANSLATION_V3 = "general/nmt"
    NL_V2 = "builtin/latest"
```

```typescript
export enum GoogleCloudAIModel {
    SPEECH_TO_TEXT_V2 = "chirp_2",
    TEXT_TO_SPEECH_V1 = "standard",
    VISION_V1 = "builtin/stable",
    TRANSLATION_V3 = "general/nmt",
    NL_V2 = "builtin/latest",
}
```

## Capabilities

```python
class GoogleCloudAICapability(str, Enum):
    """Capabilities supported."""
    SPEECH_TO_TEXT = "speech-to-text"
    TEXT_TO_SPEECH = "text-to-speech"
    VISION = "vision"
    TRANSLATION = "translation"
    NLP = "nlp"
```

```typescript
export enum GoogleCloudAICapability {
    SPEECH_TO_TEXT = "speech-to-text",
    TEXT_TO_SPEECH = "text-to-speech",
    VISION = "vision",
    TRANSLATION = "translation",
    NLP = "nlp",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `project_id` | `str` | *required* | Google Cloud project identifier |
| `location` | `str` | *required* | Google Cloud region (e.g., `us-central1`) |
| `credentials_file` | `str \| None` | `None` | Path to service account JSON credentials file; falls back to Application Default Credentials |

## YAML Example

```yaml
providers:
  google.cloud-ai.v1:
    auth:
      method: service_account
      credentials_file: ${secrets:GOOGLE_APPLICATION_CREDENTIALS}
    project_id: ${secrets:GCP_PROJECT_ID}
    location: us-central1
```
