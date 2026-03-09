---
layout: default
title: "DeepL"
---

# DeepL

**ID:** `provider.deepl.translation.v1`
**Type:** Provider

DeepL provides neural machine translation for 30+ languages with industry-leading accuracy. It supports document translation, formality control, glossaries, and formatting preservation, making it suitable for enterprise localization workflows, real-time translation pipelines, and multi-language content generation.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | DeepL REST API v2 |
| Capabilities | Yes | Single-capability translation service |
| Model Catalogue | No | Not applicable; single translation engine |
| Quota & Rate Limits | Yes | Character-based quotas per billing period |
| Cost & Pricing | Yes | Per-character pricing by plan |
| Error Classification | Yes | DeepL API error code mapping |
| Infrastructure | No | batch: no, files: no, fine-tune: no |

## Models

Not applicable. DeepL operates as a single translation engine.

## Target Language

```python
from enum import Enum

class DeepLTargetLanguage(str, Enum):
    """Target language options."""
    EN_US = "EN-US"
    EN_GB = "EN-GB"
    DE = "DE"
    FR = "FR"
    ES = "ES"
    IT = "IT"
    JA = "JA"
    KO = "KO"
    ZH = "ZH"
    PT_BR = "PT-BR"
    RU = "RU"
    NL = "NL"
    PL = "PL"
```

```typescript
export enum DeepLTargetLanguage {
    EN_US = "EN-US",
    EN_GB = "EN-GB",
    DE = "DE",
    FR = "FR",
    ES = "ES",
    IT = "IT",
    JA = "JA",
    KO = "KO",
    ZH = "ZH",
    PT_BR = "PT-BR",
    RU = "RU",
    NL = "NL",
    PL = "PL",
}
```

## Formality

```python
class DeepLFormality(str, Enum):
    """Formality options."""
    DEFAULT = "default"
    MORE = "more"
    LESS = "less"
    PREFER_MORE = "prefer_more"
    PREFER_LESS = "prefer_less"
```

```typescript
export enum DeepLFormality {
    DEFAULT = "default",
    MORE = "more",
    LESS = "less",
    PREFER_MORE = "prefer_more",
    PREFER_LESS = "prefer_less",
}
```

## Capabilities

```python
class DeepLCapability(str, Enum):
    """Capabilities supported."""
    TRANSLATION = "translation"
```

```typescript
export enum DeepLCapability {
    TRANSLATION = "translation",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `formality` | `str` | `"default"` | Formality level: `default`, `more`, `less`, `prefer_more`, or `prefer_less` |
| `split_sentences` | `str` | `"1"` | Sentence splitting: `0` (none), `1` (default), or `nonewlines` (split without newlines) |
| `preserve_formatting` | `bool` | `false` | Preserve original text formatting in translation |
| `tag_handling` | `str \| None` | `None` | Tag handling mode: `xml` or `html` for structured content |

## YAML Example

```yaml
providers:
  deepl.translation.v1:
    api_key: ${secrets:DEEPL_API_KEY}
    formality: default
    split_sentences: "1"
    preserve_formatting: true
    tag_handling: html
```
