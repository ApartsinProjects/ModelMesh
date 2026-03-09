# Google Custom Search

**ID:** `provider.google.search.v1`
**Type:** Provider

Google Custom Search provides programmatic access to Google's search engine through the Custom Search JSON API. It enables applications to perform web searches with customizable search engines, supporting filtered results, safe search, language preferences, and geographic targeting. This connector is used for retrieval-augmented generation and grounding workflows.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Custom Search JSON API v1 |
| Capabilities | Yes | Single-capability search service |
| Model Catalogue | No | Not applicable; single search service |
| Quota & Rate Limits | Yes | 10,000 queries/day free tier, additional via billing |
| Cost & Pricing | Yes | Per-query pricing beyond free tier |
| Error Classification | Yes | Google API error code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

Not applicable. Google Custom Search operates as a single service endpoint without selectable models.

## Capabilities

```python
class GoogleSearchCapability(str, Enum):
    """Capabilities supported."""
    WEB_SEARCH = "web-search"
```

```typescript
export enum GoogleSearchCapability {
    WEB_SEARCH = "web-search",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `cx` | `str` | *required* | Custom Search Engine ID (Programmable Search Engine identifier) |
| `num_results` | `int` | `10` | Number of search results to return per query (1-10) |
| `safe_search` | `str` | `"medium"` | Safe search filtering level: `off`, `medium`, or `high` |
| `language` | `str \| None` | `None` | Restrict results to a specific language (e.g., `lang_en`) |
| `country` | `str \| None` | `None` | Restrict results to a specific country (e.g., `countryUS`) |

## YAML Example

```yaml
providers:
  google.search.v1:
    api_key: ${secrets:GOOGLE_SEARCH_API_KEY}
    cx: ${secrets:GOOGLE_CSE_ID}
    num_results: 10
    safe_search: medium
    language: lang_en
```
