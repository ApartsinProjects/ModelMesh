# LlamaParse

**ID:** `provider.llamaindex.doc-parse.v1`
**Type:** Provider

LlamaParse is a document parsing service by LlamaIndex optimized for extracting structured content from complex documents. It excels at handling intricate layouts with tables, charts, diagrams, and multi-column text, producing clean output in text, Markdown, or JSON formats suitable for downstream LLM consumption and RAG pipelines.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | LlamaParse REST API |
| Capabilities | Yes | Single-capability document parsing |
| Model Catalogue | No | Not applicable; service-based |
| Quota & Rate Limits | Yes | Per-key page limits and concurrency |
| Cost & Pricing | Yes | Per-page pricing |
| Error Classification | Yes | HTTP status code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

Not applicable. LlamaParse operates as a document parsing service.

## Result Type

```python
from enum import Enum

class LlamaParseResultType(str, Enum):
    """Result type options."""
    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"
```

```typescript
export enum LlamaParseResultType {
    TEXT = "text",
    MARKDOWN = "markdown",
    JSON = "json",
}
```

## Capabilities

```python
class LlamaParseCapability(str, Enum):
    """Capabilities supported."""
    DOCUMENT_PARSING = "document-parsing"
```

```typescript
export enum LlamaParseCapability {
    DOCUMENT_PARSING = "document-parsing",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `result_type` | `str` | `"text"` | Output format: `text`, `markdown`, or `json` |
| `num_workers` | `int` | `4` | Number of parallel workers for processing multi-page documents |
| `language` | `str` | `"en"` | Primary language of the document for OCR optimization |
| `skip_diagonal_text` | `bool` | `false` | Skip diagonal or rotated text during extraction |
| `do_not_unroll_columns` | `bool` | `false` | Preserve column layout instead of linearizing multi-column text |

## YAML Example

```yaml
providers:
  llamaindex.doc-parse.v1:
    api_key: ${secrets:LLAMA_CLOUD_API_KEY}
    result_type: markdown
    num_workers: 4
    language: en
    skip_diagonal_text: false
    do_not_unroll_columns: false
```
