# Serper

**ID:** `provider.serper.search.v1`
**Type:** Provider

Serper provides fast, reliable access to Google Search results through a simple API. It supports multiple search types including web search, news, images, maps, and shopping, delivering structured JSON results suitable for AI agent workflows, competitive analysis, and retrieval-augmented generation pipelines.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Serper REST API |
| Capabilities | Yes | Single-capability with multiple search types |
| Model Catalogue | No | Not applicable; service-based |
| Quota & Rate Limits | Yes | Per-key request limits and monthly quotas |
| Cost & Pricing | Yes | Per-query pricing by plan |
| Error Classification | Yes | HTTP status code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

Not applicable. Serper operates as a service-based endpoint.

## Search Type

```python
from enum import Enum

class SerperSearchType(str, Enum):
    """Search type options."""
    SEARCH = "search"
    NEWS = "news"
    IMAGES = "images"
    MAPS = "maps"
    SHOPPING = "shopping"
```

```typescript
export enum SerperSearchType {
    SEARCH = "search",
    NEWS = "news",
    IMAGES = "images",
    MAPS = "maps",
    SHOPPING = "shopping",
}
```

## Capabilities

```python
class SerperCapability(str, Enum):
    """Capabilities supported."""
    WEB_SEARCH = "web-search"
```

```typescript
export enum SerperCapability {
    WEB_SEARCH = "web-search",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | `str` | `"search"` | Search type: `search`, `news`, `images`, `maps`, or `shopping` |
| `country` | `str \| None` | `None` | Country code for localized results (e.g., `us`, `gb`, `de`) |
| `locale` | `str \| None` | `None` | Locale for results language (e.g., `en`, `fr`, `de`) |
| `num_results` | `int` | `10` | Number of results to return per query |

## YAML Example

```yaml
providers:
  serper.search.v1:
    api_key: ${secrets:SERPER_API_KEY}
    type: search
    country: us
    locale: en
    num_results: 10
```
