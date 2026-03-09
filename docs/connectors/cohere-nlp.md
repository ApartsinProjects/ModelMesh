---
layout: default
title: "Cohere"
---

# Cohere

**ID:** `provider.cohere.nlp.v1`
**Type:** Provider

Cohere is an enterprise-focused NLP platform specializing in text understanding, embeddings, and retrieval. The platform provides the Command R family for text generation, high-quality embedding models for semantic search, and a dedicated reranking model for improving search relevance. Cohere offers robust tool calling support and fine-tuning capabilities. The free tier provides 1,000 API calls per month for non-production use.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Chat, embed, and rerank endpoints |
| Capabilities | Yes | Per-model capability reporting across generation, embedding, and reranking |
| Model Catalogue | Yes | Model listing via API |
| Quota & Rate Limits | Yes | Tier-based limits; free tier at 5-20 calls/min |
| Cost & Pricing | Yes | Per-token and per-call pricing by model |
| Error Classification | Yes | Structured error responses |
| Infrastructure | Partial | batch: no, files: no, fine-tune: yes |

## Models

```python
from enum import Enum

class CohereModel(str, Enum):
    """Available models for Cohere."""
    COMMAND_R_PLUS = "command-r-plus"
    COMMAND_R = "command-r"
    COMMAND_A = "command-a"
    EMBED_V4 = "embed-v4"
    EMBED_ENGLISH_V3 = "embed-english-v3.0"
    EMBED_MULTILINGUAL_V3 = "embed-multilingual-v3.0"
    RERANK_V3_5 = "rerank-v3.5"
```

```typescript
export enum CohereModel {
    COMMAND_R_PLUS = "command-r-plus",
    COMMAND_R = "command-r",
    COMMAND_A = "command-a",
    EMBED_V4 = "embed-v4",
    EMBED_ENGLISH_V3 = "embed-english-v3.0",
    EMBED_MULTILINGUAL_V3 = "embed-multilingual-v3.0",
    RERANK_V3_5 = "rerank-v3.5",
}
```

## Capabilities

```python
class CohereCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    EMBEDDINGS = "embeddings"
    RERANKING = "reranking"
    SEARCH = "search"
    TOOL_CALLING = "tool-calling"
    FINE_TUNING = "fine-tuning"
```

```typescript
export enum CohereCapability {
    TEXT_GENERATION = "text-generation",
    EMBEDDINGS = "embeddings",
    RERANKING = "reranking",
    SEARCH = "search",
    TOOL_CALLING = "tool-calling",
    FINE_TUNING = "fine-tuning",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | Cohere API key. Required. |
| `base_url` | string | `https://api.cohere.com/v2` | API base URL. |
| `timeout` | duration | `60s` | Request timeout. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `client_name` | string | `null` | Client identifier for request attribution. |

## YAML Example

```yaml
providers:
  cohere.nlp.v1:
    api_key: ${secrets:COHERE_API_KEY}
    timeout: 60s
    max_retries: 3
```
