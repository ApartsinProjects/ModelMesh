# Azure Key Vault

**ID:** `secret-store.microsoft.key-vault.v1`
**Type:** Secret Store

Resolves and manages secrets stored in Azure Key Vault. Supports multiple authentication methods including managed identity (for Azure-hosted workloads), client secret (for service principals), and Azure CLI credentials (for local development). Both Resolution and Management interfaces are supported.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Resolution | Yes | Retrieves secret values by name using the Azure SDK |
| Management | Yes | Create, update, list, and delete secrets via the Azure SDK |

## Constants

```python
from enum import Enum

class AuthMethod(Enum):
    """Authentication method for Azure Key Vault."""
    MANAGED_IDENTITY = "managed_identity"   # Use Azure Managed Identity (VMs, App Service, Functions)
    CLIENT_SECRET = "client_secret"         # Use service principal with client ID and secret
    CLI = "cli"                             # Use Azure CLI credentials (local development)
```

```typescript
enum AuthMethod {
    /** Use Azure Managed Identity (VMs, App Service, Functions). */
    MANAGED_IDENTITY = "managed_identity",
    /** Use service principal with client ID and secret. */
    CLIENT_SECRET = "client_secret",
    /** Use Azure CLI credentials (local development). */
    CLI = "cli",
}
```

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `vault_url` | string | _(required)_ | The Key Vault URL (e.g., `https://myvault.vault.azure.net`). |
| `tenant_id` | string | _(required)_ | Azure Active Directory tenant ID for authentication. |

See [ConnectorInterfaces.md -- Secret Store](../ConnectorInterfaces.md#secret-store) for common secret store parameters (caching, reload-on-rotation, fail-on-missing).

## YAML Example

```yaml
secrets:
  store: microsoft.key-vault.v1
  config:
    vault_url: https://myvault.vault.azure.net
    tenant_id: 12345678-abcd-efgh-ijkl-123456789012

providers:
  - connector: openai.llm.v1
    auth:
      api_key: ${secrets:OPENAI-API-KEY}
  - connector: anthropic.llm.v1
    auth:
      api_key: ${secrets:ANTHROPIC-API-KEY}
```

In this configuration, `${secrets:OPENAI-API-KEY}` resolves to the secret named `OPENAI-API-KEY` in the `myvault` Key Vault. Note that Azure Key Vault secret names support alphanumeric characters and hyphens only (no underscores). Authentication uses the default Azure credential chain (managed identity, environment variables, or CLI credentials).
