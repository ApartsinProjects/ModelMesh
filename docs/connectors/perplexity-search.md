---
layout: default
title: "Perplexity (Sonar)"
---

# Perplexity (Sonar)

**ID:** `provider.perplexity.search.v1`
**Type:** Provider

Perplexity provides search-augmented AI through its Sonar model family, delivering grounded answers with real-time web data and inline citations. Unlike traditional LLM providers, Perplexity models are designed to retrieve and synthesize information from the live web, making them ideal for tasks requiring up-to-date knowledge. The platform offers both standard and reasoning-enhanced models at different speed and depth trade-offs. There is no free API tier, but Perplexity Pro subscribers receive monthly API credits.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Chat completions with citations and search context |
| Capabilities | Yes | Per-model capability reporting including search and grounding |
| Model Catalogue | No | Static model list; limited API discovery |
| Quota & Rate Limits | Yes | Per-model rate limits with usage tracking |
| Cost & Pricing | Yes | Per-token pricing; search-augmented requests priced separately |
| Error Classification | Yes | Structured error responses |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class PerplexityModel(str, Enum):
    """Available models for Perplexity Sonar."""
    SONAR = "sonar"
    SONAR_PRO = "sonar-pro"
    SONAR_REASONING = "sonar-reasoning"
    SONAR_REASONING_PRO = "sonar-reasoning-pro"
```

```typescript
export enum PerplexityModel {
    SONAR = "sonar",
    SONAR_PRO = "sonar-pro",
    SONAR_REASONING = "sonar-reasoning",
    SONAR_REASONING_PRO = "sonar-reasoning-pro",
}
```

## Capabilities

```python
class PerplexityCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    SEARCH = "search"
    GROUNDED_GENERATION = "grounded-generation"
    TOOL_CALLING = "tool-calling"
```

```typescript
export enum PerplexityCapability {
    TEXT_GENERATION = "text-generation",
    SEARCH = "search",
    GROUNDED_GENERATION = "grounded-generation",
    TOOL_CALLING = "tool-calling",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | Perplexity API key. Required. |
| `base_url` | string | `https://api.perplexity.ai` | API base URL. |
| `timeout` | duration | `60s` | Request timeout. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `return_citations` | boolean | `true` | Include source citations in responses. |
| `search_recency_filter` | string | `null` | Filter search results by recency: `day`, `week`, `month`, `year`. |

## YAML Example

```yaml
providers:
  perplexity.search.v1:
    api_key: ${secrets:PERPLEXITY_API_KEY}
    timeout: 60s
    return_citations: true
    search_recency_filter: week
```
