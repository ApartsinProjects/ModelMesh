---
layout: default
title: "Dotenv File"
---

# Dotenv File

**ID:** `secret-store.modelmesh.dotenv.v1`
**Type:** Secret Store

Loads secrets from a `.env` file on disk. Ideal for local development where secrets are stored in a file that is excluded from version control (via `.gitignore`). The store reads key-value pairs from the file and makes them available for secret resolution. Supports standard dotenv syntax including comments, quoted values, and multiline values.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Resolution | Yes | Reads key-value pairs from the configured `.env` file |
| Management | No | Read-only; secrets cannot be written back to the file through this store |

## Connector-Specific Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `path` | string | `"./.env"` | Path to the `.env` file. Relative paths are resolved from the working directory. |
| `override` | boolean | `false` | Whether to override existing environment variables with values from the file. When `false`, existing environment variables take precedence. |

See [ConnectorInterfaces.md -- Secret Store](../ConnectorInterfaces.html#secret-store) for common secret store parameters (caching, reload-on-rotation, fail-on-missing).

## YAML Example

```yaml
secrets:
  store: modelmesh.dotenv.v1
  config:
    path: ./.env
    override: false

providers:
  - connector: openai.llm.v1
    auth:
      api_key: ${secrets:OPENAI_API_KEY}
  - connector: anthropic.claude.v1
    auth:
      api_key: ${secrets:ANTHROPIC_API_KEY}
```

With a `.env` file containing:

```
OPENAI_API_KEY=sk-proj-abc123
ANTHROPIC_API_KEY=sk-ant-xyz789
```

The store loads these values at initialization. If `OPENAI_API_KEY` is already set in the environment and `override` is `false`, the environment variable takes precedence over the file value.
