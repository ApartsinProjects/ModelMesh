---
layout: default
title: "1Password Connect"
---

# 1Password Connect

**ID:** `secret-store.1password.connect.v1`
**Type:** Secret Store

Resolves secrets from a 1Password Connect Server. 1Password Connect provides a REST API for accessing secrets stored in 1Password vaults, designed for server-side and CI/CD use cases. Secret management (creating, updating, deleting) is handled through the 1Password application and is not available through this connector.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Resolution | Yes | Retrieves secret values from a 1Password vault via the Connect Server API |
| Management | No | Secrets are managed through the 1Password application |

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `server_url` | string | _(required)_ | URL of the 1Password Connect Server (e.g., `http://localhost:8080`). |
| `vault_id` | string | _(required)_ | UUID of the 1Password vault to resolve secrets from. |
| `token` | string | _(required)_ | Connect Server access token. Store this token in an environment variable and reference it (e.g., `${env:OP_CONNECT_TOKEN}`) to avoid embedding credentials in configuration files. |

See [ConnectorInterfaces.md -- Secret Store](../ConnectorInterfaces.html#secret-store) for common secret store parameters (caching, reload-on-rotation, fail-on-missing).

## YAML Example

```yaml
secrets:
  store: 1password.connect.v1
  config:
    server_url: http://localhost:8080
    vault_id: abc123def456ghi789
    token: ${env:OP_CONNECT_TOKEN}

providers:
  - connector: openai.llm.v1
    auth:
      api_key: ${secrets:OPENAI_API_KEY}
  - connector: anthropic.claude.v1
    auth:
      api_key: ${secrets:ANTHROPIC_API_KEY}
```

In this configuration, `${secrets:OPENAI_API_KEY}` resolves to the item titled `OPENAI_API_KEY` in the specified 1Password vault. The Connect Server token is itself loaded from the `OP_CONNECT_TOKEN` environment variable to avoid storing credentials in the YAML file.
