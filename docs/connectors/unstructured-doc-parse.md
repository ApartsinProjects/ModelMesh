# Unstructured

**ID:** `provider.unstructured.doc-parse.v1`
**Type:** Provider

Unstructured provides intelligent document parsing for a wide range of file formats including PDF, images, Microsoft Office documents, and HTML. It uses layout analysis, OCR, and table detection to extract structured content from unstructured documents, making it suitable for building RAG pipelines, document processing workflows, and data extraction systems.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Unstructured API and SDK |
| Capabilities | Yes | Single-capability document parsing |
| Model Catalogue | No | Not applicable; service-based |
| Quota & Rate Limits | Yes | Per-key request and page limits |
| Cost & Pricing | Yes | Per-page pricing by strategy |
| Error Classification | Yes | HTTP status code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

Not applicable. Unstructured operates as a document parsing service.

## Output Format

```python
from enum import Enum

class UnstructuredOutputFormat(str, Enum):
    """Output format options."""
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
```

```typescript
export enum UnstructuredOutputFormat {
    JSON = "json",
    CSV = "csv",
    MARKDOWN = "markdown",
}
```

## Capabilities

```python
class UnstructuredCapability(str, Enum):
    """Capabilities supported."""
    DOCUMENT_PARSING = "document-parsing"
```

```typescript
export enum UnstructuredCapability {
    DOCUMENT_PARSING = "document-parsing",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `strategy` | `str` | `"auto"` | Parsing strategy: `auto`, `fast`, `hi_res`, or `ocr_only` |
| `output_format` | `str` | `"json"` | Output format: `json`, `csv`, or `markdown` |
| `chunking_strategy` | `str \| None` | `None` | Chunking strategy: `by_title`, `by_page`, or `basic` |
| `max_characters` | `int \| None` | `None` | Maximum characters per chunk when chunking is enabled |
| `include_metadata` | `bool` | `true` | Include element metadata (coordinates, page numbers, etc.) in output |

## YAML Example

```yaml
providers:
  unstructured.doc-parse.v1:
    api_key: ${secrets:UNSTRUCTURED_API_KEY}
    strategy: hi_res
    output_format: json
    chunking_strategy: by_title
    max_characters: 1500
    include_metadata: true
```
