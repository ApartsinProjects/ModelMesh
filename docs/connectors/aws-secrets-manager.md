# AWS Secrets Manager

**ID:** `secret-store.aws.secrets-manager.v1`
**Type:** Secret Store

Resolves and manages secrets stored in AWS Secrets Manager. Supports IAM-based authentication, secret versioning, and optional key name prefixing for multi-environment scoping. Both Resolution and Management interfaces are supported, enabling the CLI to provision and rotate secrets across environments.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Resolution | Yes | Retrieves secret values by name using the AWS SDK |
| Management | Yes | Create, update, list, and delete secrets via the AWS SDK |

## Constants

```python
from enum import Enum

class AuthMethod(Enum):
    """Authentication method for AWS Secrets Manager."""
    IAM_ROLE = "iam_role"       # Use IAM role (EC2, ECS, Lambda)
    ACCESS_KEY = "access_key"   # Use AWS access key ID and secret access key
    PROFILE = "profile"         # Use a named profile from ~/.aws/credentials
```

```typescript
enum AuthMethod {
    /** Use IAM role (EC2, ECS, Lambda). */
    IAM_ROLE = "iam_role",
    /** Use AWS access key ID and secret access key. */
    ACCESS_KEY = "access_key",
    /** Use a named profile from ~/.aws/credentials. */
    PROFILE = "profile",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `region` | string | _(required)_ | AWS region where secrets are stored (e.g., `us-east-1`). |
| `prefix` | string \| null | `null` | Prefix prepended to secret names for scoping (e.g., `modelmesh/`). When set, a resolution request for `OPENAI_API_KEY` resolves to `modelmesh/OPENAI_API_KEY` in AWS. |
| `version_stage` | string | `"AWSCURRENT"` | Version stage to retrieve. Use `AWSCURRENT` for the latest version or `AWSPREVIOUS` for the prior version during rotation. |

See [ConnectorInterfaces.md -- Secret Store](../ConnectorInterfaces.md#secret-store) for common secret store parameters (caching, reload-on-rotation, fail-on-missing).

## YAML Example

```yaml
secrets:
  store: aws.secrets-manager.v1
  config:
    region: us-east-1
    prefix: modelmesh/prod/
    version_stage: AWSCURRENT

providers:
  - connector: openai.llm.v1
    auth:
      api_key: ${secrets:OPENAI_API_KEY}
  - connector: anthropic.llm.v1
    auth:
      api_key: ${secrets:ANTHROPIC_API_KEY}
```

In this configuration, `${secrets:OPENAI_API_KEY}` resolves to the AWS secret named `modelmesh/prod/OPENAI_API_KEY` in the `us-east-1` region. Authentication uses the default AWS credential chain (environment variables, IAM role, or named profile).
