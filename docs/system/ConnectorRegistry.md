# ConnectorRegistry

Catalogue of available connector implementations. The registry loads built-in connectors at initialization and custom connectors from packages referenced in configuration. All connector types -- provider, rotation, secret store, storage, observability, and discovery -- register here and are retrieved by their naming-convention ID. Connector packages are zip archives or directory paths containing one or more connector implementations that self-register on load.

**Depends on:** [ModelMesh](ModelMesh.md)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ConnectorType(Enum):
    """Classification of connector implementations."""
    PROVIDER = "provider"
    ROTATION = "rotation"
    SECRET_STORE = "secret_store"
    STORAGE = "storage"
    OBSERVABILITY = "observability"
    DISCOVERY = "discovery"


@dataclass
class ConnectorInfo:
    """Descriptor for a registered connector implementation."""
    id: str
    connector_type: ConnectorType
    version: str
    description: str


class ConnectorRegistry:
    """Catalogue of available connector implementations.

    Loads built-in connectors at initialization and custom connectors
    from packages referenced in configuration. All connector types
    register here and are retrieved by their naming-convention ID.
    """

    def register(self, connector_id: str, implementation: Any) -> None:
        """Register a connector implementation by its naming-convention ID.

        The connector ID follows the pattern:
        ``<namespace>.<name>.v<version>`` (e.g., ``modelmesh.openai.v1``).
        Duplicate registrations for the same ID raise an error.

        Args:
            connector_id: Unique connector identifier.
            implementation: The connector implementation object or class.
        """
        ...

    def get_connector(self, connector_id: str) -> Any:
        """Return a connector implementation by ID.

        Args:
            connector_id: The registered connector identifier.

        Returns:
            The connector implementation.

        Raises:
            KeyError: If no connector is registered with the given ID.
        """
        ...

    def list_connectors(
        self, connector_type: Optional[str] = None
    ) -> list[ConnectorInfo]:
        """Return all registered connectors, optionally filtered by type.

        Args:
            connector_type: If provided, return only connectors of this
                type (e.g., "provider", "storage").

        Returns:
            A list of ConnectorInfo descriptors.
        """
        ...

    def load_package(self, path: str) -> list[str]:
        """Load a connector package and register its connectors.

        Accepts a file path to a zip archive or directory, or a URL
        to a remote package. Discovers and registers all connector
        implementations found in the package.

        Args:
            path: File path or URL to the connector package.

        Returns:
            A list of connector IDs that were registered from the package.
        """
        ...
```

## TypeScript

```typescript
/** Classification of connector implementations. */
enum ConnectorType {
    PROVIDER = "provider",
    ROTATION = "rotation",
    SECRET_STORE = "secret_store",
    STORAGE = "storage",
    OBSERVABILITY = "observability",
    DISCOVERY = "discovery",
}

/** Descriptor for a registered connector implementation. */
interface ConnectorInfo {
    id: string;
    connector_type: ConnectorType;
    version: string;
    description: string;
}

/** Catalogue of available connector implementations. */
class ConnectorRegistry {
    /**
     * Register a connector implementation by its naming-convention ID.
     *
     * The connector ID follows the pattern: `<namespace>.<name>.v<version>`.
     */
    register(connectorId: string, implementation: unknown): void {
        throw new Error("Not implemented");
    }

    /**
     * Return a connector implementation by ID.
     *
     * Throws if no connector is registered with the given ID.
     */
    getConnector(connectorId: string): unknown {
        throw new Error("Not implemented");
    }

    /**
     * Return all registered connectors, optionally filtered by type.
     */
    listConnectors(connectorType?: string): ConnectorInfo[] {
        throw new Error("Not implemented");
    }

    /**
     * Load a connector package and register its connectors.
     *
     * Returns the list of connector IDs registered from the package.
     */
    loadPackage(path: string): string[] {
        throw new Error("Not implemented");
    }
}
```

---

## Configuration

See [SystemConfiguration.md -- Connectors](../SystemConfiguration.md#connectors) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `connectors.packages` | list | Paths or URLs to connector packages to load at initialization. |
