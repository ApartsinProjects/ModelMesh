# SecretResolver

Resolves `${secrets:name}` references in configuration through the configured secret store connector. The resolver caches resolved values in memory with a configurable TTL to minimize calls to the secret backend. Secrets are re-resolved on provider rotation when a new provider is activated, ensuring that API keys and tokens are always current. The resolver supports bulk resolution of entire configuration objects and manual cache invalidation for rotation or key renewal scenarios.

**Depends on:** [SecretStoreConnector](../ConnectorInterfaces.md#secret-store)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SecretResolver:
    """Resolves ${secrets:name} references through a secret store connector.

    Caches resolved values in memory with configurable TTL. Re-resolves
    secrets on provider rotation when a new provider is activated.
    """

    def resolve(self, reference: str) -> str:
        """Return the secret value for a ${secrets:name} reference.

        Checks the in-memory cache first. If the cached value has
        expired or does not exist, resolves from the configured
        secret store connector.

        Args:
            reference: A secret reference string (e.g., "${secrets:openai-key}").

        Returns:
            The resolved secret value.

        Raises:
            KeyError: If the secret name is not found in the store.
            ValueError: If the reference format is invalid.
        """
        ...

    def resolve_all(self, config: dict) -> dict:
        """Resolve all secret references in a configuration object.

        Recursively walks the configuration dictionary and replaces
        all ``${secrets:name}`` string values with their resolved
        secret values. Non-secret values are passed through unchanged.

        Args:
            config: Configuration dictionary potentially containing
                secret references.

        Returns:
            A new dictionary with all secret references resolved.
        """
        ...

    def invalidate(self, name: str) -> None:
        """Remove a cached secret, forcing re-resolution on next access.

        Use this when a secret has been rotated or renewed externally
        and the cached value is no longer valid.

        Args:
            name: The secret name to invalidate (without the
                ``${secrets:}`` wrapper).
        """
        ...

    def reload(self) -> None:
        """Re-resolve all cached secrets from the store.

        Clears the entire cache and re-resolves every previously
        cached secret. Called automatically when reload_on_rotation
        is enabled and a provider rotation occurs.
        """
        ...
```

## TypeScript

```typescript
/** Resolves ${secrets:name} references through a secret store connector. */
class SecretResolver {
    /**
     * Return the secret value for a ${secrets:name} reference.
     *
     * Checks the in-memory cache first, then resolves from the
     * configured secret store connector.
     *
     * Throws if the secret name is not found or the reference format
     * is invalid.
     */
    resolve(reference: string): string {
        throw new Error("Not implemented");
    }

    /**
     * Resolve all secret references in a configuration object.
     *
     * Recursively replaces all ${secrets:name} values with resolved secrets.
     */
    resolveAll(config: Record<string, unknown>): Record<string, unknown> {
        throw new Error("Not implemented");
    }

    /**
     * Remove a cached secret, forcing re-resolution on next access.
     */
    invalidate(name: string): void {
        throw new Error("Not implemented");
    }

    /**
     * Re-resolve all cached secrets from the store.
     *
     * Clears the entire cache and re-resolves every previously cached secret.
     */
    reload(): void {
        throw new Error("Not implemented");
    }
}
```

---

## Configuration

See [SystemConfiguration.md -- Secrets](../SystemConfiguration.md#secrets) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `secrets.store` | string | Secret store connector ID (e.g., `modelmesh.env-file.v1`). |
| `secrets.cache_ttl` | duration | Cache lifetime for resolved secrets (e.g., `300s`). |
| `secrets.reload_on_rotation` | boolean | Re-resolve secrets when a new provider is activated during rotation. |
