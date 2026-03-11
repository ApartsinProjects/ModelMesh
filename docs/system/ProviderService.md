---
layout: default
title: "ProviderService"
---

# ProviderService

Runtime representation of a configured provider. Wraps the provider connector (which handles API communication) with operational state tracking: quota consumption, rate-limit headroom, and health status. A provider manages one or more models. Named `ProviderService` to distinguish from the connector interface documented in [ConnectorInterfaces.md](../ConnectorInterfaces.md).

**Depends on:** [ProviderConnector](../interfaces/Provider.md), [ProviderState](ProviderState.md), [SecretResolver](SecretResolver.md).

---

## Python

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RateLimitInfo:
    """Current rate-limit headroom for a provider."""

    requests_remaining: int
    """Requests remaining in the current rate-limit window."""

    tokens_remaining: int
    """Tokens remaining in the current rate-limit window."""

    reset_at: float
    """Unix timestamp when the rate-limit window resets."""


@dataclass
class HealthStatus:
    """Provider health status snapshot."""

    available: bool
    auth_valid: bool
    availability_score: float
    last_probe: float | None


class ProviderService:
    """Runtime provider wrapper with state tracking."""

    _name: str
    _connector: ProviderConnector
    _state: ProviderState
    _secret_resolver: SecretResolver
    _models: dict[str, Model]

    def __init__(
        self,
        name: str,
        connector: ProviderConnector,
        secret_resolver: SecretResolver,
    ) -> None:
        self._name = name
        self._connector = connector
        self._secret_resolver = secret_resolver
        self._state = ProviderState()
        self._models = {}

    @property
    def name(self) -> str:
        """Return the provider identifier."""
        return self._name

    def execute(
        self,
        model: Model,
        request: CompletionRequest,
    ) -> CompletionResponse:
        """Execute a request through the provider connector.

        Args:
            model: The model to target.
            request: The completion request payload.

        Returns:
            The completion response from the provider API.

        Raises:
            ProviderError: If the provider returns an error.
            AuthenticationError: If credentials are invalid.
            RateLimitError: If rate limits are exceeded.
        """
        ...

    def check_quota(self) -> dict[str, Any]:
        """Query current quota usage from the provider API (if supported).

        Returns:
            Dictionary with quota usage details (requests_used,
            tokens_used, budget_used).
        """
        ...

    def get_rate_limits(self) -> RateLimitInfo:
        """Return current rate-limit headroom.

        Returns:
            A RateLimitInfo snapshot.
        """
        ...

    def get_health(self) -> HealthStatus:
        """Return the provider's health status and availability score.

        Returns:
            A HealthStatus snapshot.
        """
        ...

    def is_available(self) -> bool:
        """Return whether the provider is operational (auth valid, not
        deactivated).

        Returns:
            True if the provider can accept requests.
        """
        ...

    def get_models(self) -> list[Model]:
        """Return all models registered under this provider.

        Returns:
            List of Model instances.
        """
        ...
```

---

## TypeScript

```typescript
interface RateLimitInfo {
  /** Requests remaining in the current rate-limit window. */
  requestsRemaining: number;
  /** Tokens remaining in the current rate-limit window. */
  tokensRemaining: number;
  /** Unix timestamp when the rate-limit window resets. */
  resetAt: number;
}

interface HealthStatus {
  available: boolean;
  authValid: boolean;
  availabilityScore: number;
  lastProbe: number | null;
}

class ProviderService {
  private _name: string;
  private connector: ProviderConnector;
  private state: ProviderState;
  private secretResolver: SecretResolver;
  private models: Map<string, Model>;

  constructor(
    name: string,
    connector: ProviderConnector,
    secretResolver: SecretResolver,
  );

  /** Return the provider identifier. */
  get name(): string;

  /** Execute a request through the provider connector. */
  async execute(
    model: Model,
    request: CompletionRequest,
  ): Promise<CompletionResponse>;

  /** Query current quota usage from the provider API. */
  async checkQuota(): Promise<Record<string, unknown>>;

  /** Return current rate-limit headroom. */
  getRateLimits(): RateLimitInfo;

  /** Return the provider's health status and availability score. */
  getHealth(): HealthStatus;

  /** Return whether the provider is operational. */
  isAvailable(): boolean;

  /** Return all models registered under this provider. */
  getModels(): Model[];
}
```

---

## Configuration

Provider parameters are configured under the `providers` section. See [SystemConfiguration.md -- Providers](../SystemConfiguration.md#providers).

| Parameter | Type | Description |
| --- | --- | --- |
| `enabled` | boolean | Enable or disable the provider |
| `api_key` | string | API key or secret reference (`${secrets:name}`) |
| `base_url` | string | Custom API endpoint URL |
| `connector` | string | Provider connector ID |
| `auth.*` | map | Authentication configuration |
| `quota.*` | map | Quota tracking configuration |
| `budget.*` | map | Spend cap configuration |
