---
layout: default
title: "Google Cloud Secret Manager"
---

# Google Cloud Secret Manager

**ID:** `secret-store.google.secret-manager.v1`
**Type:** Secret Store

Resolves and manages secrets stored in Google Cloud Secret Manager. Uses GCP service account or Application Default Credentials for authentication. Supports secret versioning, IAM-based access control, and optional name prefixing for multi-environment scoping. Both Resolution and Management interfaces are supported.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Resolution | Yes | Retrieves secret values by name using the GCP SDK |
| Management | Yes | Create, update, list, and delete secrets via the GCP SDK |

## Constants

```python
from enum import Enum

class AuthMethod(Enum):
    """Authentication method for Google Cloud Secret Manager."""
    SERVICE_ACCOUNT = "service_account"           # Use a service account key file
    APPLICATION_DEFAULT = "application_default"   # Use Application Default Credentials (ADC)
```

```typescript
enum AuthMethod {
    /** Use a service account key file. */
    SERVICE_ACCOUNT = "service_account",
    /** Use Application Default Credentials (ADC). */
    APPLICATION_DEFAULT = "application_default",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `project` | string | _(required)_ | GCP project ID where secrets are stored. |
| `prefix` | string \| null | `null` | Prefix prepended to secret names for scoping (e.g., `modelmesh-prod-`). When set, a resolution request for `OPENAI_API_KEY` resolves to `modelmesh-prod-OPENAI_API_KEY` in GCP. |

See [ConnectorInterfaces.md -- Secret Store](../ConnectorInterfaces.html#secret-store) for common secret store parameters (caching, reload-on-rotation, fail-on-missing).

## YAML Example

```yaml
secrets:
  store: google.secret-manager.v1
  config:
    project: my-gcp-project-id
    prefix: modelmesh-prod-

providers:
  - connector: openai.llm.v1
    auth:
      api_key: ${secrets:OPENAI_API_KEY}
  - connector: anthropic.llm.v1
    auth:
      api_key: ${secrets:ANTHROPIC_API_KEY}
```

In this configuration, `${secrets:OPENAI_API_KEY}` resolves to the GCP secret named `modelmesh-prod-OPENAI_API_KEY` in the `my-gcp-project-id` project. The latest secret version is retrieved by default. Authentication uses Application Default Credentials unless a service account key file is explicitly configured.
