# Perspective API

**ID:** `provider.google.moderation.v1`
**Type:** Provider

Perspective API by Google Jigsaw provides machine learning-based content moderation by scoring text for attributes such as toxicity, identity attack, insult, profanity, and threat. It is designed for real-time content moderation workflows, comment filtering, and safety guardrails in AI-generated content pipelines.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Perspective API v1alpha1 |
| Capabilities | Yes | Single-capability content moderation |
| Model Catalogue | No | Not applicable; single moderation engine |
| Quota & Rate Limits | Yes | Queries-per-second quotas |
| Cost & Pricing | No | Free tier available; usage-based for high volume |
| Error Classification | Yes | Google API error code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

Not applicable. Perspective API operates as a single moderation scoring engine.

## Attribute Type

```python
from enum import Enum

class PerspectiveAttributeType(str, Enum):
    """Attribute types for scoring."""
    TOXICITY = "TOXICITY"
    SEVERE_TOXICITY = "SEVERE_TOXICITY"
    IDENTITY_ATTACK = "IDENTITY_ATTACK"
    INSULT = "INSULT"
    PROFANITY = "PROFANITY"
    THREAT = "THREAT"
    SEXUALLY_EXPLICIT = "SEXUALLY_EXPLICIT"
```

```typescript
export enum PerspectiveAttributeType {
    TOXICITY = "TOXICITY",
    SEVERE_TOXICITY = "SEVERE_TOXICITY",
    IDENTITY_ATTACK = "IDENTITY_ATTACK",
    INSULT = "INSULT",
    PROFANITY = "PROFANITY",
    THREAT = "THREAT",
    SEXUALLY_EXPLICIT = "SEXUALLY_EXPLICIT",
}
```

## Capabilities

```python
class PerspectiveCapability(str, Enum):
    """Capabilities supported."""
    CONTENT_MODERATION = "content-moderation"
```

```typescript
export enum PerspectiveCapability {
    CONTENT_MODERATION = "content-moderation",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `attributes` | `list` | `["TOXICITY"]` | List of attribute types to score (see `PerspectiveAttributeType` enum) |
| `score_threshold` | `float` | `0.7` | Minimum score threshold for flagging content (0.0 - 1.0) |
| `languages` | `list \| None` | `None` | List of language codes for the content (e.g., `["en"]`); auto-detected if not specified |
| `do_not_store` | `bool` | `true` | When `true`, Perspective API will not store the submitted text |

## YAML Example

```yaml
providers:
  google.moderation.v1:
    api_key: ${secrets:PERSPECTIVE_API_KEY}
    attributes:
      - TOXICITY
      - SEVERE_TOXICITY
      - INSULT
      - PROFANITY
    score_threshold: 0.7
    languages:
      - en
    do_not_store: true
```
