# AWS Bedrock

**ID:** `provider.aws.bedrock.v1`
**Type:** Provider

AWS Bedrock is a fully managed service that provides access to foundation models from leading AI companies through a single API. It supports models from Anthropic, Meta, Mistral, Amazon, and Stability AI with enterprise-grade security, private networking, and integration with the broader AWS ecosystem. Authentication uses IAM roles and service accounts.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Model Execution | Yes | AWS SDK InvokeModel / Converse API |
| Capabilities | Yes | Per-model capability metadata |
| Model Catalogue | Yes | Regional model availability catalogue |
| Quota & Rate Limits | Yes | Per-model provisioned throughput and on-demand limits |
| Cost & Pricing | Yes | Per-token pricing with on-demand and provisioned options |
| Error Classification | Yes | AWS error code mapping |
| Infrastructure | Partial | batch: yes, files: no, fine-tune: yes |

## Models

```python
from enum import Enum

class AWSBedrockModel(str, Enum):
    """Available models."""
    CLAUDE_SONNET_4 = "anthropic.claude-sonnet-4-20250514-v1:0"
    CLAUDE_3_5_HAIKU = "anthropic.claude-3-5-haiku-20241022-v1:0"
    LLAMA_3_1_70B = "meta.llama3-1-70b-instruct-v1:0"
    MISTRAL_LARGE = "mistral.mistral-large-2407-v1:0"
    AMAZON_NOVA_PRO = "amazon.nova-pro-v1:0"
    AMAZON_NOVA_LITE = "amazon.nova-lite-v1:0"
    TITAN_EMBED = "amazon.titan-embed-text-v2:0"
    SD_XL = "stability.stable-diffusion-xl-v1"
```

```typescript
export enum AWSBedrockModel {
    CLAUDE_SONNET_4 = "anthropic.claude-sonnet-4-20250514-v1:0",
    CLAUDE_3_5_HAIKU = "anthropic.claude-3-5-haiku-20241022-v1:0",
    LLAMA_3_1_70B = "meta.llama3-1-70b-instruct-v1:0",
    MISTRAL_LARGE = "mistral.mistral-large-2407-v1:0",
    AMAZON_NOVA_PRO = "amazon.nova-pro-v1:0",
    AMAZON_NOVA_LITE = "amazon.nova-lite-v1:0",
    TITAN_EMBED = "amazon.titan-embed-text-v2:0",
    SD_XL = "stability.stable-diffusion-xl-v1",
}
```

## Capabilities

```python
class AWSBedrockCapability(str, Enum):
    """Capabilities supported."""
    TEXT_GENERATION = "text-generation"
    IMAGE_GENERATION = "image-generation"
    EMBEDDINGS = "embeddings"
    TOOL_CALLING = "tool-calling"
    BATCH = "batch"
    FINE_TUNING = "fine-tuning"
```

```typescript
export enum AWSBedrockCapability {
    TEXT_GENERATION = "text-generation",
    IMAGE_GENERATION = "image-generation",
    EMBEDDINGS = "embeddings",
    TOOL_CALLING = "tool-calling",
    BATCH = "batch",
    FINE_TUNING = "fine-tuning",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `region` | `str` | *required* | AWS region for the Bedrock endpoint (e.g., `us-east-1`) |
| `profile` | `str \| None` | `None` | AWS CLI profile name for credential resolution |
| `role_arn` | `str \| None` | `None` | IAM role ARN to assume for cross-account access |

## YAML Example

```yaml
providers:
  aws.bedrock.v1:
    auth:
      method: service_account
      profile: ${secrets:AWS_PROFILE}
      role_arn: arn:aws:iam::123456789012:role/BedrockAccess
    region: us-east-1
```
