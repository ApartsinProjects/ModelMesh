# Tavily

**ID:** `provider.tavily.search.v1`
**Type:** Provider

Tavily is an AI-optimized search engine designed specifically for retrieval-augmented generation and AI agent workflows. It returns clean, relevant results with optional AI-generated answer summaries and raw content extraction, reducing the need for post-processing. Tavily supports configurable search depth for balancing speed and comprehensiveness.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Tavily Search REST API |
| Capabilities | Yes | Search and grounded generation |
| Model Catalogue | No | Not applicable; single search service |
| Quota & Rate Limits | Yes | Per-key request limits |
| Cost & Pricing | Yes | Per-search pricing by depth |
| Error Classification | Yes | HTTP status code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

Not applicable. Tavily operates as a single search service endpoint.

## Search Depth

```python
from enum import Enum

class TavilySearchDepth(str, Enum):
    """Search depth options."""
    BASIC = "basic"
    ADVANCED = "advanced"
```

```typescript
export enum TavilySearchDepth {
    BASIC = "basic",
    ADVANCED = "advanced",
}
```

## Capabilities

```python
class TavilyCapability(str, Enum):
    """Capabilities supported."""
    WEB_SEARCH = "web-search"
    GROUNDED_GENERATION = "grounded-generation"
```

```typescript
export enum TavilyCapability {
    WEB_SEARCH = "web-search",
    GROUNDED_GENERATION = "grounded-generation",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `search_depth` | `str` | `"basic"` | Search depth: `basic` for fast results, `advanced` for comprehensive crawling |
| `include_answer` | `bool` | `false` | Include an AI-generated answer summary in results |
| `include_raw_content` | `bool` | `false` | Include raw page content in results |
| `max_results` | `int` | `5` | Maximum number of search results to return |
| `include_domains` | `list \| None` | `None` | Restrict search to specific domains |
| `exclude_domains` | `list \| None` | `None` | Exclude specific domains from search results |

## YAML Example

```yaml
providers:
  tavily.search.v1:
    api_key: ${secrets:TAVILY_API_KEY}
    search_depth: advanced
    include_answer: true
    include_raw_content: false
    max_results: 5
    include_domains:
      - docs.python.org
      - stackoverflow.com
```
