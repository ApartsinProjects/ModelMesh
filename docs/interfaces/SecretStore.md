---
layout: default
title: "Secret Store Interface"
---

# Secret Store Interface

A secret store connector resolves API keys and tokens from a secure backend at runtime. Configuration references secrets by name (`${secrets:openai-key}`); the library resolves them through the configured store at initialization and on rotation (when a new provider is activated).

> **Reference:** [ConnectorInterfaces.md -- Secret Store](../ConnectorInterfaces.html#secret-store) | [ConnectorCatalogue.md -- Secret Store Connectors](../ConnectorCatalogue.html#secret-store-connectors)

---

## Sub-Interfaces

| Sub-Interface | Required | Purpose |
| --- | --- | --- |
| **Resolution** | yes | Retrieve a secret value by name |
| **Management** | no | Store, list, and remove secrets (CLI utility for credential provisioning) |

---

## Supporting Types

### Python

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SecretValue:
    """A resolved secret with optional version and expiration metadata."""
    value: str
    version: Optional[str] = None
    expires_at: Optional[datetime] = None
```

### TypeScript

```typescript
/** A resolved secret with optional version and expiration metadata. */
interface SecretValue {
    value: string;
    version?: string;
    expires_at?: Date;
}
```

---

## Interface Definitions

### Python

```python
from abc import ABC, abstractmethod


class SecretResolution(ABC):
    """Retrieve a secret value by name.

    The only required interface -- all secret store connectors must
    implement this. Called at initialization and on rotation when a
    new provider is activated.
    """

    @abstractmethod
    def get(self, name: str) -> str:
        """Resolve a secret by name and return its value.

        Raises:
            KeyError: If the secret is not found and fail_on_missing is True.
        """
        ...


class SecretManagement(ABC):
    """Store, list, and remove secrets.

    Optional interface used by the CLI utility for credential provisioning
    across environments. Not required for runtime operation.
    """

    @abstractmethod
    def set(self, name: str, value: str) -> None:
        """Store or update a secret."""
        ...

    @abstractmethod
    def list(self) -> list[str]:
        """Return the names of all available secrets."""
        ...

    @abstractmethod
    def delete(self, name: str) -> None:
        """Remove a secret by name.

        Raises:
            KeyError: If the secret does not exist.
        """
        ...


class SecretStoreConnector(SecretResolution):
    """Full secret store connector combining the required Resolution interface.

    Implementations that support credential provisioning should also
    inherit from SecretManagement.
    """
    pass
```

### TypeScript

```typescript
/** Retrieve a secret value by name. Required for all secret store connectors. */
interface SecretResolution {
    /**
     * Resolve a secret by name and return its value.
     * @throws {Error} If the secret is not found and fail_on_missing is true.
     */
    get(name: string): string;
}

/** Store, list, and remove secrets. Optional management interface. */
interface SecretManagement {
    /** Store or update a secret. */
    set(name: string, value: string): void;

    /** Return the names of all available secrets. */
    list(): string[];

    /**
     * Remove a secret by name.
     * @throws {Error} If the secret does not exist.
     */
    delete(name: string): void;
}

/** Full secret store connector combining the required Resolution interface. */
interface SecretStoreConnector extends SecretResolution {}
```

---

## Common Configuration

Parameters shared by all secret store connectors. Individual stores may add connector-specific parameters (see [ConnectorCatalogue.md -- Secret Store Connectors](../ConnectorCatalogue.html#secret-store-connectors)).

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `secret-store.resolution.cache_enabled` | boolean | `true` | Cache resolved secrets in memory. |
| `secret-store.resolution.cache_ttl` | duration | `300s` | Time-to-live for cached secrets. |
| `secret-store.resolution.reload_on_rotation` | boolean | `true` | Re-resolve secrets when a new provider is activated during rotation. |
| `secret-store.resolution.fail_on_missing` | boolean | `true` | Fail initialization if a referenced secret is not found. |

---

## CDK Base Class

The CDK provides [BaseSecretStore](../cdk/BaseClasses.html#basesecretstore) with in-memory cache and TTL. Specialized class: [FileSecretStore](../cdk/BaseClasses.html#filesecretstore). See [DeveloperGuide -- Tutorial 5](../cdk/DeveloperGuide.html#tutorial-5-complete-connector-set-for-acmecorp).
