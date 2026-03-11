---
layout: default
title: "ModelMesh"
---

# ModelMesh

Top-level library facade and entry point for ModelMesh Lite. Initializes all subsystems, loads configuration, resolves secrets, registers connectors, builds capability pools, and wires dependencies. Applications interact with this object to obtain a router, access an OpenAI-compatible client, reload configuration, or shut down gracefully.

**Depends on:** [Router](Router.md), [ModelRegistry](ModelRegistry.md), [ConnectorRegistry](ConnectorRegistry.md), [SecretResolver](SecretResolver.md), [StateManager](StateManager.md), [EventEmitter](EventEmitter.md).

---

## Python

```python
from __future__ import annotations

from typing import Any


class MeshConfig:
    """Parsed configuration object representing all top-level YAML sections."""

    raw: dict[str, Any]

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw


class ModelMesh:
    """Library facade -- single entry point for all ModelMesh Lite functionality."""

    _router: Router
    _client: OpenAIClient
    _registry: ModelRegistry
    _connector_registry: ConnectorRegistry
    _secret_resolver: SecretResolver
    _state_manager: StateManager
    _event_emitter: EventEmitter
    _config: MeshConfig

    # --- lifecycle --------------------------------------------------------

    def initialize(self, config: MeshConfig) -> None:
        """Load configuration, resolve secrets, register connectors, build
        pools, and start background services (discovery, health monitor,
        statistics flush).
        """
        ...

    def shutdown(self) -> None:
        """Flush pending state and statistics, stop background services, and
        release storage locks.
        """
        ...

    def reload_config(self, config: MeshConfig) -> None:
        """Hot-reload configuration without full restart.  Re-resolves secrets,
        updates pools, and re-registers connectors.
        """
        ...

    # --- accessors --------------------------------------------------------

    def get_router(self) -> Router:
        """Return the configured Router instance."""
        ...

    def get_client(self) -> OpenAIClient:
        """Return an OpenAIClient wired to the router."""
        ...

    def get_registry(self) -> ModelRegistry:
        """Return the ModelRegistry."""
        ...

    # --- class methods (alternative constructors) -------------------------

    @classmethod
    def from_yaml(cls, path: str) -> ModelMesh:
        """Create a ModelMesh instance from a YAML configuration file.

        Args:
            path: Filesystem path to the YAML configuration file.

        Returns:
            A fully initialized ModelMesh instance.
        """
        ...

    @classmethod
    def from_storage(cls, connector: str, **kwargs: Any) -> ModelMesh:
        """Create a ModelMesh instance by loading configuration from a storage
        connector.

        Args:
            connector: Storage connector identifier.
            **kwargs: Connector-specific parameters (bucket, key, etc.).

        Returns:
            A fully initialized ModelMesh instance.
        """
        ...
```

---

## TypeScript

```typescript
class MeshConfig {
  /** Raw parsed configuration from YAML, JSON, or programmatic input. */
  readonly raw: Record<string, unknown>;

  constructor(raw?: Record<string, unknown>);
  static fromFile(path: string): MeshConfig;
  static fromDict(data: Record<string, unknown>): MeshConfig;

  get providers(): Record<string, unknown>;
  get models(): Record<string, unknown>;
  get pools(): Record<string, unknown>;
  merge(overrides: Record<string, unknown>): MeshConfig;
  validate(): string[];
}

class ModelMesh {
  private router: Router;
  private client: OpenAIClient;
  private registry: ModelRegistry;
  private connectorRegistry: ConnectorRegistry;
  private secretResolver: SecretResolver;
  private stateManager: StateManager;
  private eventEmitter: EventEmitter;
  private config: MeshConfig;

  // --- lifecycle --------------------------------------------------------

  /** Load configuration, resolve secrets, register connectors, build pools,
   *  and start background services. */
  async initialize(config: MeshConfig): Promise<void>;

  /** Flush pending state and statistics, stop background services, and
   *  release storage locks. */
  async shutdown(): Promise<void>;

  /** Hot-reload configuration without full restart. */
  async reloadConfig(config: MeshConfig): Promise<void>;

  // --- accessors --------------------------------------------------------

  /** Return the configured Router instance. */
  getRouter(): Router;

  /** Return an OpenAIClient wired to the router. */
  getClient(): OpenAIClient;

  /** Return the ModelRegistry. */
  getRegistry(): ModelRegistry;

  // --- static factories -------------------------------------------------

  /** Create a ModelMesh instance from a YAML configuration file. */
  static async fromYaml(path: string): Promise<ModelMesh>;

  /** Create a ModelMesh instance by loading configuration from a storage
   *  connector. */
  static async fromStorage(
    connector: string,
    options?: Record<string, unknown>,
  ): Promise<ModelMesh>;
}
```

---

## Configuration

All top-level YAML sections apply to ModelMesh. See [SystemConfiguration.md](../SystemConfiguration.md) for the full reference.

| Section | Description |
| --- | --- |
| `providers` | Provider definitions and credentials |
| `models` | Model definitions, capabilities, and constraints |
| `pools` | Capability pool definitions and routing strategies |
| `connectors` | Connector package paths and configuration |
| `secrets` | Secret store connector and cache settings |
| `storage` | State persistence connector and sync policy |
| `observability` | Logging, statistics, and event routing |
| `proxy` | Proxy server bind address, port, and endpoints |
| `discovery` | Model discovery sync settings |
