# Bing Web Search API

**ID:** `provider.microsoft.bing-search.v1`
**Type:** Provider

Bing Web Search API provides access to Microsoft's search engine capabilities including web, image, news, and video search. It returns rich structured results with ranking, snippets, and metadata, making it suitable for retrieval-augmented generation, content discovery, and multi-modal search workflows.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Bing Search REST API v7 |
| Capabilities | Yes | Multi-capability search service |
| Model Catalogue | No | Not applicable; service-based |
| Quota & Rate Limits | Yes | Transactions-per-second and monthly quotas |
| Cost & Pricing | Yes | Per-transaction pricing by tier |
| Error Classification | Yes | Bing API error code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

Not applicable. Bing Web Search API operates as a service-based endpoint without selectable models.

## Capabilities

```python
class BingSearchCapability(str, Enum):
    """Capabilities supported."""
    WEB_SEARCH = "web-search"
    IMAGE_SEARCH = "image-search"
    NEWS_SEARCH = "news-search"
    VIDEO_SEARCH = "video-search"
```

```typescript
export enum BingSearchCapability {
    WEB_SEARCH = "web-search",
    IMAGE_SEARCH = "image-search",
    NEWS_SEARCH = "news-search",
    VIDEO_SEARCH = "video-search",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `market` | `str \| None` | `None` | Market code for results localization (e.g., `en-US`, `de-DE`) |
| `count` | `int` | `10` | Number of results to return per query |
| `safe_search` | `str` | `"Moderate"` | Safe search filtering level: `Off`, `Moderate`, or `Strict` |
| `freshness` | `str \| None` | `None` | Filter results by age: `Day`, `Week`, or `Month` |

## YAML Example

```yaml
providers:
  microsoft.bing-search.v1:
    api_key: ${secrets:BING_SEARCH_API_KEY}
    market: en-US
    count: 10
    safe_search: Moderate
    freshness: Week
```
