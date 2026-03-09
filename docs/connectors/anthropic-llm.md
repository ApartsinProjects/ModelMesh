# Anthropic

**ID:** `provider.anthropic.llm.v1`
**Type:** Provider

Anthropic is a safety-focused AI lab producing the Claude family of large language models. Claude models excel at reasoning, code generation, analysis, and long-context tasks. Anthropic emphasizes responsible AI development, and its models are known for following nuanced instructions and producing well-structured outputs. The API supports batch processing for high-volume workloads with significant cost savings.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | Messages API with streaming support |
| Capabilities | Yes | Per-model capability and context window reporting |
| Model Catalogue | Yes | Static catalogue with version-dated model identifiers |
| Quota & Rate Limits | Yes | Tier-based RPM/TPM limits with header tracking |
| Cost & Pricing | Yes | Per-token pricing with cached token discounts (up to 90%) |
| Error Classification | Yes | Structured error types with overload and rate-limit distinction |
| Infrastructure | Partial | batch: yes, files: no, fine-tune: no |

## Models

```python
from enum import Enum

class AnthropicModel(str, Enum):
    """Available models for Anthropic."""
    CLAUDE_OPUS_4 = "claude-opus-4-20250514"
    CLAUDE_SONNET_4 = "claude-sonnet-4-20250514"
    CLAUDE_3_7_SONNET = "claude-3-7-sonnet-20250219"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-20241022"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
```

```typescript
export enum AnthropicModel {
    CLAUDE_OPUS_4 = "claude-opus-4-20250514",
    CLAUDE_SONNET_4 = "claude-sonnet-4-20250514",
    CLAUDE_3_7_SONNET = "claude-3-7-sonnet-20250219",
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-20241022",
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022",
}
```

## Capabilities

```python
class AnthropicCapability(str, Enum):
    """Capabilities supported by this provider."""
    TEXT_GENERATION = "text-generation"
    VISION = "vision"
    TOOL_CALLING = "tool-calling"
    STRUCTURED_OUTPUT = "structured-output"
```

```typescript
export enum AnthropicCapability {
    TEXT_GENERATION = "text-generation",
    VISION = "vision",
    TOOL_CALLING = "tool-calling",
    STRUCTURED_OUTPUT = "structured-output",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `api_key` | string | - | Anthropic API key. Required. |
| `base_url` | string | `https://api.anthropic.com` | API base URL. Override for proxies. |
| `anthropic_version` | string | `2023-06-01` | API version header value. |
| `timeout` | duration | `120s` | Request timeout. Longer default for extended thinking. |
| `max_retries` | integer | `3` | Maximum number of automatic retries on transient errors. |
| `max_tokens` | integer | `4096` | Default maximum output tokens per request. |

## YAML Example

```yaml
providers:
  anthropic.llm.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}
    timeout: 120s
    max_tokens: 8192
    max_retries: 3
```
