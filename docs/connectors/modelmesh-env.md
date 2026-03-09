---
layout: default
title: "Environment Variables"
---

# Environment Variables

**ID:** `secret-store.modelmesh.env.v1`
**Type:** Secret Store

The default secret store. Resolves secrets by reading environment variables from the current process. This is the simplest store and requires no external dependencies or configuration. Suitable for local development, CI/CD pipelines (where secrets are injected as environment variables), and containerized deployments.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Resolution | Yes | Reads `os.environ[name]` for the given secret name |
| Management | No | Read-only; environment variables cannot be set through this store |

## Connector-Specific Configuration

This connector has no specific configuration parameters. It reads directly from the process environment.

See [ConnectorInterfaces.md -- Secret Store](../ConnectorInterfaces.html#secret-store) for common secret store parameters (caching, reload-on-rotation, fail-on-missing).

## YAML Example

```yaml
secrets:
  store: modelmesh.env.v1

providers:
  - connector: openai.llm.v1
    auth:
      api_key: ${secrets:OPENAI_API_KEY}
  - connector: anthropic.llm.v1
    auth:
      api_key: ${secrets:ANTHROPIC_API_KEY}
```

In this configuration, `${secrets:OPENAI_API_KEY}` resolves to the value of the `OPENAI_API_KEY` environment variable at initialization and whenever a provider is activated during rotation.
