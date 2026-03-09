# CDK Helpers Reference

Utility functions, type helpers, and test utilities that support connector development. These are standalone, stateless tools -- they do not depend on mixin state or connector instances and can be imported individually.

> **Cross-references:** Types referenced below are defined in the interface documentation:
> - [Provider](../interfaces/Provider.md) -- `CompletionRequest`, `CompletionResponse`, `TokenUsage`, `ModelInfo`
> - [Storage](../interfaces/Storage.md) -- `SerializationFormat`, `StorageEntry`
> - [Rotation Policy](../interfaces/RotationPolicy.md) -- `ModelSnapshot`, `ModelStatus`, `SelectionResult`
> - [Secret Store](../interfaces/SecretStore.md) -- `SecretStoreConnector`
> - [Observability](../interfaces/Observability.md) -- `ObservabilityConnector`, `RoutingEvent`, `RequestLogEntry`, `AggregateStats`, `Severity`, `TraceEntry`
> - [Discovery](../interfaces/Discovery.md) -- `DiscoveryConnector`, `ProbeResult`

---

## Utility Functions

### `parse_duration`

Parse a human-readable duration string into seconds.

**Signature:** `parse_duration(value: str) -> float`

| Input | Output |
| --- | --- |
| `"30s"` | `30.0` |
| `"5m"` | `300.0` |
| `"1h"` | `3600.0` |
| `"7d"` | `604800.0` |

#### Python

```python
import re


def parse_duration(value: str) -> float:
    """Parse a human-readable duration string into seconds.

    Supported suffixes:
        - ``s`` -- seconds
        - ``m`` -- minutes
        - ``h`` -- hours
        - ``d`` -- days

    Args:
        value: Duration string (e.g. "30s", "5m", "1h", "7d").

    Returns:
        Duration in seconds as a float.

    Raises:
        ValueError: If the string does not match the expected format.

    Examples:
        >>> parse_duration("30s")
        30.0
        >>> parse_duration("5m")
        300.0
        >>> parse_duration("1.5h")
        5400.0
    """
    multipliers = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(s|m|h|d)$", value.strip())
    if not match:
        raise ValueError(
            f"Invalid duration '{value}'. "
            f"Expected format: <number><s|m|h|d> (e.g. '30s', '5m', '1h')"
        )
    return float(match.group(1)) * multipliers[match.group(2)]
```

#### TypeScript

```typescript
/**
 * Parse a human-readable duration string into seconds.
 *
 * Supported suffixes: s (seconds), m (minutes), h (hours), d (days).
 *
 * @param value - Duration string (e.g. "30s", "5m", "1h", "7d").
 * @returns Duration in seconds.
 * @throws Error if the string does not match the expected format.
 *
 * @example
 * parseDuration("30s"); // 30
 * parseDuration("5m");  // 300
 * parseDuration("1.5h"); // 5400
 */
function parseDuration(value: string): number {
    const multipliers: Record<string, number> = {
        s: 1,
        m: 60,
        h: 3600,
        d: 86400,
    };

    const match = value.trim().match(/^(\d+(?:\.\d+)?)\s*(s|m|h|d)$/);
    if (!match) {
        throw new Error(
            `Invalid duration '${value}'. ` +
            `Expected format: <number><s|m|h|d> (e.g. '30s', '5m', '1h')`,
        );
    }

    return parseFloat(match[1]) * multipliers[match[2]];
}
```

---

### `format_duration`

Format a number of seconds into a human-readable duration string, choosing the largest whole unit.

**Signature:** `format_duration(seconds: float) -> str`

| Input | Output |
| --- | --- |
| `30.0` | `"30s"` |
| `300.0` | `"5m"` |
| `3600.0` | `"1h"` |
| `90.0` | `"90s"` |

#### Python

```python
def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string.

    Selects the largest unit (d, h, m, s) that divides evenly into
    the value. Falls back to seconds with one decimal place if no
    unit divides evenly.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string (e.g. "5m", "1h", "30s").

    Examples:
        >>> format_duration(300.0)
        '5m'
        >>> format_duration(3600.0)
        '1h'
        >>> format_duration(90.0)
        '90s'
    """
    units = [
        (86400.0, "d"),
        (3600.0, "h"),
        (60.0, "m"),
        (1.0, "s"),
    ]

    for divisor, suffix in units:
        if seconds >= divisor and seconds % divisor == 0:
            value = int(seconds / divisor)
            return f"{value}{suffix}"

    # Fractional seconds: use one decimal place
    return f"{seconds:.1f}s"
```

#### TypeScript

```typescript
/**
 * Format seconds into a human-readable duration string.
 *
 * Selects the largest unit (d, h, m, s) that divides evenly.
 * Falls back to seconds with one decimal place if no unit divides evenly.
 *
 * @param seconds - Duration in seconds.
 * @returns Formatted duration string (e.g. "5m", "1h", "30s").
 *
 * @example
 * formatDuration(300);  // "5m"
 * formatDuration(3600); // "1h"
 * formatDuration(90);   // "90s"
 */
function formatDuration(seconds: number): string {
    const units: [number, string][] = [
        [86400, "d"],
        [3600, "h"],
        [60, "m"],
        [1, "s"],
    ];

    for (const [divisor, suffix] of units) {
        if (seconds >= divisor && seconds % divisor === 0) {
            return `${seconds / divisor}${suffix}`;
        }
    }

    return `${seconds.toFixed(1)}s`;
}
```

---

### `redact_secret`

Redact a secret value for safe logging, preserving only a short prefix.

**Signature:** `redact_secret(value: str) -> str`

| Input | Output |
| --- | --- |
| `"sk-abc123xyz"` | `"sk-***"` |
| `"ghp_A1B2C3D4E5"` | `"ghp_***"` |
| `"short"` | `"***"` |

#### Python

```python
def redact_secret(value: str) -> str:
    """Redact a secret value for safe logging.

    Preserves a recognizable prefix (up to the first delimiter or the
    first 4 characters) and replaces the remainder with '***'. Values
    shorter than 6 characters are fully redacted.

    Args:
        value: The secret string to redact.

    Returns:
        A redacted version of the string safe for log output.

    Examples:
        >>> redact_secret("sk-abc123xyz")
        'sk-***'
        >>> redact_secret("ghp_A1B2C3D4E5")
        'ghp_***'
        >>> redact_secret("short")
        '***'
    """
    if len(value) < 6:
        return "***"

    # Look for a common prefix delimiter (dash, underscore)
    for delimiter in ("-", "_"):
        idx = value.find(delimiter)
        if 0 < idx <= 6:
            return value[: idx + 1] + "***"

    # Fall back to first 4 characters
    return value[:4] + "***"
```

#### TypeScript

```typescript
/**
 * Redact a secret value for safe logging.
 *
 * Preserves a recognizable prefix (up to the first delimiter or the
 * first 4 characters) and replaces the remainder with '***'. Values
 * shorter than 6 characters are fully redacted.
 *
 * @param value - The secret string to redact.
 * @returns A redacted version safe for log output.
 *
 * @example
 * redactSecret("sk-abc123xyz");    // "sk-***"
 * redactSecret("ghp_A1B2C3D4E5"); // "ghp_***"
 * redactSecret("short");           // "***"
 */
function redactSecret(value: string): string {
    if (value.length < 6) {
        return "***";
    }

    for (const delimiter of ["-", "_"]) {
        const idx = value.indexOf(delimiter);
        if (idx > 0 && idx <= 6) {
            return value.slice(0, idx + 1) + "***";
        }
    }

    return value.slice(0, 4) + "***";
}
```

---

### `merge_configs`

Deep-merge two configuration dictionaries. The `override` dict takes precedence; nested dicts are merged recursively rather than replaced wholesale.

**Signature:** `merge_configs(base, override) -> config`

#### Python

```python
from typing import Any


def merge_configs(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    """Deep-merge two configuration dictionaries.

    Values from ``override`` take precedence. Nested dicts are merged
    recursively so that a partial override does not erase sibling keys.
    Lists and scalar values are replaced entirely by the override.

    Args:
        base: Base configuration dictionary.
        override: Override dictionary whose values take precedence.

    Returns:
        A new merged dictionary. Neither input is mutated.

    Examples:
        >>> base = {"provider": {"timeout": "30s", "retries": 3}}
        >>> override = {"provider": {"timeout": "60s"}}
        >>> merge_configs(base, override)
        {'provider': {'timeout': '60s', 'retries': 3}}
    """
    merged: dict[str, Any] = {}

    all_keys = set(base) | set(override)
    for key in all_keys:
        base_val = base.get(key)
        over_val = override.get(key)

        if key not in override:
            merged[key] = _deep_copy_value(base_val)
        elif key not in base:
            merged[key] = _deep_copy_value(over_val)
        elif isinstance(base_val, dict) and isinstance(over_val, dict):
            merged[key] = merge_configs(base_val, over_val)
        else:
            merged[key] = _deep_copy_value(over_val)

    return merged


def _deep_copy_value(value: Any) -> Any:
    """Create a shallow-safe copy of a value for merge output."""
    if isinstance(value, dict):
        return {k: _deep_copy_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return list(value)
    return value
```

#### TypeScript

```typescript
/**
 * Deep-merge two configuration objects.
 *
 * Values from `override` take precedence. Nested objects are merged
 * recursively so that a partial override does not erase sibling keys.
 * Arrays and scalar values are replaced entirely by the override.
 *
 * @param base - Base configuration object.
 * @param override - Override object whose values take precedence.
 * @returns A new merged object. Neither input is mutated.
 *
 * @example
 * const base = { provider: { timeout: "30s", retries: 3 } };
 * const override = { provider: { timeout: "60s" } };
 * mergeConfigs(base, override);
 * // { provider: { timeout: "60s", retries: 3 } }
 */
function mergeConfigs(
    base: Record<string, unknown>,
    override: Record<string, unknown>,
): Record<string, unknown> {
    const merged: Record<string, unknown> = {};

    const allKeys = new Set([...Object.keys(base), ...Object.keys(override)]);

    for (const key of allKeys) {
        const baseVal = base[key];
        const overVal = override[key];

        if (!(key in override)) {
            merged[key] = deepCopyValue(baseVal);
        } else if (!(key in base)) {
            merged[key] = deepCopyValue(overVal);
        } else if (isPlainObject(baseVal) && isPlainObject(overVal)) {
            merged[key] = mergeConfigs(
                baseVal as Record<string, unknown>,
                overVal as Record<string, unknown>,
            );
        } else {
            merged[key] = deepCopyValue(overVal);
        }
    }

    return merged;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function deepCopyValue(value: unknown): unknown {
    if (isPlainObject(value)) {
        const copy: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(value)) {
            copy[k] = deepCopyValue(v);
        }
        return copy;
    }
    if (Array.isArray(value)) {
        return [...value];
    }
    return value;
}
```

---

### `validate_connector_id`

Validate that a connector ID string conforms to the `type.vendor.service.version` format.

**Signature:** `validate_connector_id(id: str) -> bool`

| Input | Output |
| --- | --- |
| `"provider.openai.chat.v1"` | `True` |
| `"storage.local.filesystem.v2"` | `True` |
| `"invalid-format"` | `False` |
| `"a.b.c"` | `False` |

#### Python

```python
import re

VALID_CONNECTOR_TYPES = {
    "provider", "rotation", "secret_store",
    "storage", "observability", "discovery",
}


def validate_connector_id(connector_id: str) -> bool:
    """Validate that a connector ID follows the type.vendor.service.version format.

    Each segment must be a non-empty string of lowercase letters, digits,
    and underscores. The type segment must be one of the six recognized
    connector types. The version segment must start with 'v' followed
    by a number.

    Args:
        connector_id: The connector ID string to validate.

    Returns:
        True if the ID is valid, False otherwise.

    Examples:
        >>> validate_connector_id("provider.openai.chat.v1")
        True
        >>> validate_connector_id("storage.local.filesystem.v2")
        True
        >>> validate_connector_id("invalid-format")
        False
    """
    segment_pattern = re.compile(r"^[a-z][a-z0-9_]*$")
    version_pattern = re.compile(r"^v\d+$")

    parts = connector_id.split(".")
    if len(parts) != 4:
        return False

    conn_type, vendor, service, version = parts

    if conn_type not in VALID_CONNECTOR_TYPES:
        return False

    if not segment_pattern.match(vendor):
        return False

    if not segment_pattern.match(service):
        return False

    if not version_pattern.match(version):
        return False

    return True
```

#### TypeScript

```typescript
const VALID_CONNECTOR_TYPES = new Set([
    "provider",
    "rotation",
    "secret_store",
    "storage",
    "observability",
    "discovery",
]);

/**
 * Validate that a connector ID follows the type.vendor.service.version format.
 *
 * Each segment must be a non-empty string of lowercase letters, digits,
 * and underscores. The type segment must be one of the six recognized
 * connector types. The version segment must start with 'v' followed
 * by a number.
 *
 * @param connectorId - The connector ID string to validate.
 * @returns True if the ID is valid, false otherwise.
 *
 * @example
 * validateConnectorId("provider.openai.chat.v1");       // true
 * validateConnectorId("storage.local.filesystem.v2");    // true
 * validateConnectorId("invalid-format");                 // false
 */
function validateConnectorId(connectorId: string): boolean {
    const segmentPattern = /^[a-z][a-z0-9_]*$/;
    const versionPattern = /^v\d+$/;

    const parts = connectorId.split(".");
    if (parts.length !== 4) return false;

    const [connType, vendor, service, version] = parts;

    if (!VALID_CONNECTOR_TYPES.has(connType)) return false;
    if (!segmentPattern.test(vendor)) return false;
    if (!segmentPattern.test(service)) return false;
    if (!versionPattern.test(version)) return false;

    return true;
}
```

---

## Type Helpers

### `ConnectorType` Enum

Enumerates the six connector categories in ModelMesh Lite.

#### Python

```python
from enum import Enum


class ConnectorType(Enum):
    """Enumeration of the six connector categories.

    Each connector in the system belongs to exactly one type. The type
    determines which interfaces the connector must implement and where
    it fits in the routing pipeline.
    """
    PROVIDER = "provider"
    ROTATION = "rotation"
    SECRET_STORE = "secret_store"
    STORAGE = "storage"
    OBSERVABILITY = "observability"
    DISCOVERY = "discovery"
```

#### TypeScript

```typescript
/**
 * Enumeration of the six connector categories.
 *
 * Each connector belongs to exactly one type. The type determines
 * which interfaces the connector must implement and where it fits
 * in the routing pipeline.
 */
enum ConnectorType {
    PROVIDER = "provider",
    ROTATION = "rotation",
    SECRET_STORE = "secret_store",
    STORAGE = "storage",
    OBSERVABILITY = "observability",
    DISCOVERY = "discovery",
}
```

---

### `ConnectorMetadata` Dataclass

Descriptor for a registered connector, carrying its identity, type, and human-readable description.

#### Python

```python
from dataclasses import dataclass


@dataclass
class ConnectorMetadata:
    """Descriptor for a registered connector.

    Carries the connector's identity, type classification, version,
    and a human-readable description. Used by the registry for
    discovery and by observability connectors for event payloads.

    Attributes:
        id: Full connector ID in type.vendor.service.version format.
        type: Connector category.
        version: Semantic version string (e.g. "v1").
        vendor: Organization or author (e.g. "openai", "local").
        service: Service or backend name (e.g. "chat", "filesystem").
        description: Human-readable summary of the connector.
    """
    id: str
    type: ConnectorType
    version: str
    vendor: str
    service: str
    description: str
```

#### TypeScript

```typescript
/**
 * Descriptor for a registered connector.
 *
 * Carries the connector's identity, type classification, version,
 * and a human-readable description. Used by the registry for
 * discovery and by observability connectors for event payloads.
 */
interface ConnectorMetadata {
    /** Full connector ID in type.vendor.service.version format. */
    id: string;
    /** Connector category. */
    type: ConnectorType;
    /** Semantic version string (e.g. "v1"). */
    version: string;
    /** Organization or author (e.g. "openai", "local"). */
    vendor: string;
    /** Service or backend name (e.g. "chat", "filesystem"). */
    service: string;
    /** Human-readable summary of the connector. */
    description: string;
}
```

---

### `connector_id`

Build a connector ID string from its constituent parts.

**Signature:** `connector_id(type, vendor, service, version) -> str`

#### Python

```python
def connector_id(
    type: ConnectorType | str,
    vendor: str,
    service: str,
    version: str,
) -> str:
    """Build a connector ID string from its constituent parts.

    Produces the canonical ``type.vendor.service.version`` format
    used throughout the system for connector registration and lookup.

    Args:
        type: Connector type as a ConnectorType enum or raw string.
        vendor: Organization or author name.
        service: Service or backend name.
        version: Version string (e.g. "v1").

    Returns:
        The assembled connector ID string.

    Examples:
        >>> connector_id(ConnectorType.PROVIDER, "openai", "chat", "v1")
        'provider.openai.chat.v1'
        >>> connector_id("storage", "local", "filesystem", "v2")
        'storage.local.filesystem.v2'
    """
    type_str = type.value if isinstance(type, ConnectorType) else type
    return f"{type_str}.{vendor}.{service}.{version}"
```

#### TypeScript

```typescript
/**
 * Build a connector ID string from its constituent parts.
 *
 * Produces the canonical type.vendor.service.version format used
 * throughout the system for connector registration and lookup.
 *
 * @param type - Connector type enum value or raw string.
 * @param vendor - Organization or author name.
 * @param service - Service or backend name.
 * @param version - Version string (e.g. "v1").
 * @returns The assembled connector ID string.
 *
 * @example
 * connectorId(ConnectorType.PROVIDER, "openai", "chat", "v1");
 * // "provider.openai.chat.v1"
 */
function connectorId(
    type: ConnectorType | string,
    vendor: string,
    service: string,
    version: string,
): string {
    return `${type}.${vendor}.${service}.${version}`;
}
```

---

## Test Utilities

### MockHttpClient

Records outgoing requests and returns canned responses. Useful for unit-testing provider connectors without making real HTTP calls. Response sequences can be configured per path so consecutive calls return different results.

#### Python

```python
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class RecordedRequest:
    """A request captured by the mock HTTP client."""
    method: str
    path: str
    json: Any = None
    kwargs: dict = field(default_factory=dict)


class MockHttpClient:
    """Mock HTTP client that records requests and returns canned responses.

    Configure response sequences per path before exercising the
    connector under test. Each call to a path pops the next response
    from the sequence; when exhausted, the last response repeats.

    Attributes:
        requests: List of all recorded requests in call order.
    """

    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []
        self._responses: dict[str, list[Any]] = {}
        self._stream_responses: dict[str, list[list[str]]] = {}

    def add_response(self, path: str, response: Any) -> None:
        """Enqueue a response for a given path.

        Args:
            path: URL path that triggers this response.
            response: JSON-serializable response body.
        """
        self._responses.setdefault(path, []).append(response)

    def add_stream_response(self, path: str, chunks: list[str]) -> None:
        """Enqueue a streaming response for a given path.

        Args:
            path: URL path that triggers this streaming response.
            chunks: List of SSE data strings yielded in order.
        """
        self._stream_responses.setdefault(path, []).append(chunks)

    async def get(self, path: str, **kwargs: Any) -> Any:
        """Simulate a GET request.

        Args:
            path: URL path.
            **kwargs: Additional arguments (recorded but not used).

        Returns:
            The next canned response for this path.
        """
        self.requests.append(RecordedRequest("GET", path, kwargs=kwargs))
        return self._pop_response(path)

    async def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        """Simulate a POST request.

        Args:
            path: URL path.
            json: Request body.
            **kwargs: Additional arguments (recorded but not used).

        Returns:
            The next canned response for this path.
        """
        self.requests.append(RecordedRequest("POST", path, json=json, kwargs=kwargs))
        return self._pop_response(path)

    async def stream(
        self, path: str, json: Any = None, **kwargs: Any
    ) -> AsyncIterator[str]:
        """Simulate a streaming POST request.

        Args:
            path: URL path.
            json: Request body.
            **kwargs: Additional arguments (recorded but not used).

        Yields:
            SSE data strings from the canned stream response.
        """
        self.requests.append(RecordedRequest("POST", path, json=json, kwargs=kwargs))
        chunks = self._pop_stream_response(path)
        for chunk in chunks:
            yield chunk

    def _pop_response(self, path: str) -> Any:
        """Pop the next response, repeating the last one when exhausted."""
        responses = self._responses.get(path, [{}])
        if len(responses) > 1:
            return responses.pop(0)
        return responses[0]

    def _pop_stream_response(self, path: str) -> list[str]:
        """Pop the next stream response, repeating the last one when exhausted."""
        responses = self._stream_responses.get(path, [[]])
        if len(responses) > 1:
            return responses.pop(0)
        return responses[0]
```

#### TypeScript

```typescript
/** A request captured by the mock HTTP client. */
interface RecordedRequest {
    method: string;
    path: string;
    body?: unknown;
    options?: Record<string, unknown>;
}

/**
 * Mock HTTP client that records requests and returns canned responses.
 *
 * Configure response sequences per path before exercising the
 * connector under test. Each call to a path pops the next response;
 * when exhausted, the last response repeats.
 */
class MockHttpClient {
    /** All recorded requests in call order. */
    readonly requests: RecordedRequest[] = [];

    private responses = new Map<string, unknown[]>();
    private streamResponses = new Map<string, string[][]>();

    /**
     * Enqueue a response for a given path.
     *
     * @param path - URL path that triggers this response.
     * @param response - JSON-serializable response body.
     */
    addResponse(path: string, response: unknown): void {
        if (!this.responses.has(path)) {
            this.responses.set(path, []);
        }
        this.responses.get(path)!.push(response);
    }

    /**
     * Enqueue a streaming response for a given path.
     *
     * @param path - URL path that triggers this streaming response.
     * @param chunks - SSE data strings yielded in order.
     */
    addStreamResponse(path: string, chunks: string[]): void {
        if (!this.streamResponses.has(path)) {
            this.streamResponses.set(path, []);
        }
        this.streamResponses.get(path)!.push(chunks);
    }

    /** Simulate a GET request. */
    async get<T = unknown>(path: string, options?: Record<string, unknown>): Promise<T> {
        this.requests.push({ method: "GET", path, options });
        return this.popResponse(path) as T;
    }

    /** Simulate a POST request. */
    async post<T = unknown>(
        path: string,
        body?: unknown,
        options?: Record<string, unknown>,
    ): Promise<T> {
        this.requests.push({ method: "POST", path, body, options });
        return this.popResponse(path) as T;
    }

    /** Simulate a streaming POST request. */
    async *stream(
        path: string,
        body?: unknown,
        options?: Record<string, unknown>,
    ): AsyncGenerator<string> {
        this.requests.push({ method: "POST", path, body, options });
        const chunks = this.popStreamResponse(path);
        for (const chunk of chunks) {
            yield chunk;
        }
    }

    private popResponse(path: string): unknown {
        const queue = this.responses.get(path) ?? [{}];
        return queue.length > 1 ? queue.shift()! : queue[0];
    }

    private popStreamResponse(path: string): string[] {
        const queue = this.streamResponses.get(path) ?? [[]];
        return queue.length > 1 ? queue.shift()! : queue[0];
    }
}
```

---

### MockModelSnapshot

Factory for creating `ModelSnapshot` test instances with sensible defaults and configurable overrides.

#### Python

```python
from datetime import datetime
from typing import Optional


def mock_model_snapshot(
    model_id: str = "gpt-4",
    provider_id: str = "openai",
    status: str = "active",
    failure_count: int = 0,
    error_rate: float = 0.0,
    cooldown_remaining: Optional[float] = None,
    quota_used: int = 0,
    tokens_used: int = 0,
    cost_accumulated: float = 0.0,
    latency_avg: Optional[float] = None,
    last_request: Optional[datetime] = None,
    last_failure: Optional[datetime] = None,
) -> "ModelSnapshot":
    """Create a ModelSnapshot instance for testing.

    All fields have sensible defaults representing a healthy active model.
    Override individual fields to simulate specific conditions.

    Args:
        model_id: Model identifier.
        provider_id: Provider identifier.
        status: Model status ("active" or "standby").
        failure_count: Number of consecutive failures.
        error_rate: Error rate over the sliding window (0.0--1.0).
        cooldown_remaining: Seconds remaining in cooldown, or None.
        quota_used: Number of requests consumed in the current quota period.
        tokens_used: Total tokens consumed.
        cost_accumulated: Total cost in USD.
        latency_avg: Average latency in milliseconds.
        last_request: Timestamp of the most recent request.
        last_failure: Timestamp of the most recent failure.

    Returns:
        A ModelSnapshot instance ready for use in tests.

    Examples:
        >>> healthy = mock_model_snapshot()
        >>> failing = mock_model_snapshot(failure_count=5, error_rate=0.8)
        >>> standby = mock_model_snapshot(status="standby", cooldown_remaining=30.0)
    """
    from modelmesh.interfaces.rotation_policy import ModelSnapshot, ModelStatus

    return ModelSnapshot(
        model_id=model_id,
        provider_id=provider_id,
        status=ModelStatus(status),
        failure_count=failure_count,
        error_rate=error_rate,
        cooldown_remaining=cooldown_remaining,
        quota_used=quota_used,
        tokens_used=tokens_used,
        cost_accumulated=cost_accumulated,
        latency_avg=latency_avg,
        last_request=last_request,
        last_failure=last_failure,
    )
```

#### TypeScript

```typescript
/**
 * Create a ModelSnapshot instance for testing.
 *
 * All fields have sensible defaults representing a healthy active model.
 * Override individual fields to simulate specific conditions.
 *
 * @param overrides - Fields to override from the defaults.
 * @returns A ModelSnapshot instance ready for use in tests.
 *
 * @example
 * const healthy = mockModelSnapshot();
 * const failing = mockModelSnapshot({ failure_count: 5, error_rate: 0.8 });
 * const standby = mockModelSnapshot({ status: ModelStatus.STANDBY, cooldown_remaining: 30 });
 */
function mockModelSnapshot(overrides: Partial<ModelSnapshot> = {}): ModelSnapshot {
    return {
        model_id: "gpt-4",
        provider_id: "openai",
        status: ModelStatus.ACTIVE,
        failure_count: 0,
        error_rate: 0.0,
        quota_used: 0,
        tokens_used: 0,
        cost_accumulated: 0.0,
        ...overrides,
    };
}
```

---

### MockCompletionRequest

Factory for creating `CompletionRequest` test instances.

#### Python

```python
from typing import Optional


def mock_completion_request(
    model: str = "gpt-4",
    messages: Optional[list[dict]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[list[dict]] = None,
    stream: bool = False,
) -> "CompletionRequest":
    """Create a CompletionRequest instance for testing.

    Provides a minimal valid request by default. Override individual
    fields to test specific scenarios.

    Args:
        model: Target model identifier.
        messages: Conversation messages. Defaults to a single user message.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens to generate.
        tools: Tool definitions for function calling.
        stream: Whether to request streaming output.

    Returns:
        A CompletionRequest instance ready for use in tests.

    Examples:
        >>> simple = mock_completion_request()
        >>> streaming = mock_completion_request(stream=True)
        >>> with_tools = mock_completion_request(tools=[{"type": "function", ...}])
    """
    from modelmesh.interfaces.provider import CompletionRequest

    if messages is None:
        messages = [{"role": "user", "content": "Hello, world!"}]

    return CompletionRequest(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        stream=stream,
    )
```

#### TypeScript

```typescript
/**
 * Create a CompletionRequest instance for testing.
 *
 * Provides a minimal valid request by default. Override individual
 * fields to test specific scenarios.
 *
 * @param overrides - Fields to override from the defaults.
 * @returns A CompletionRequest instance ready for use in tests.
 *
 * @example
 * const simple = mockCompletionRequest();
 * const streaming = mockCompletionRequest({ stream: true });
 */
function mockCompletionRequest(
    overrides: Partial<CompletionRequest> = {},
): CompletionRequest {
    return {
        model: "gpt-4",
        messages: [{ role: "user", content: "Hello, world!" }],
        stream: false,
        ...overrides,
    };
}
```

---

### ConnectorTestHarness

Runs standard interface compliance tests against any connector implementation. Validates that the connector correctly implements its declared interface contract. Each test method targets one specific behavior and produces a clear pass/fail result.

#### Test Methods

| Method | Interface | Validates |
| --- | --- | --- |
| `test_provider_complete` | Provider / ModelExecution | `complete()` returns a `CompletionResponse` with required fields |
| `test_provider_stream` | Provider / ModelExecution | `stream()` yields one or more `CompletionResponse` chunks |
| `test_rotation_deactivation` | Rotation / Deactivation | `should_deactivate()` returns `True` when failure count exceeds threshold |
| `test_rotation_recovery` | Rotation / Recovery | `should_recover()` returns `True` after cooldown expires |
| `test_rotation_selection` | Rotation / Selection | `select()` returns a `SelectionResult` with a valid model from candidates |
| `test_secret_store_get` | Secret Store / Resolution | `get()` returns a string value for a known secret name |
| `test_storage_crud` | Storage / Persistence + Inventory | Full save, load, list, delete cycle completes without error |
| `test_observability_emit_log_flush_trace` | Observability / Events + Logging + Statistics + Tracing | `emit()`, `log()`, `flush()`, and `trace()` execute without raising exceptions |
| `test_discovery_probe` | Discovery / Health Monitoring | `probe()` returns a `ProbeResult` with required fields |

#### Python

```python
import asyncio
from datetime import datetime, timedelta
from typing import Any


class ConnectorTestHarness:
    """Run standard interface compliance tests against connector implementations.

    Each test method validates one aspect of a connector's interface
    contract. Tests are designed to be run in isolation and produce
    clear pass/fail results with diagnostic messages.

    Attributes:
        results: Dict mapping test names to (passed, message) tuples
            after run_all() completes.
    """

    def __init__(self) -> None:
        self.results: dict[str, tuple[bool, str]] = {}

    async def test_provider_complete(self, provider: Any) -> bool:
        """Verify that complete() returns a CompletionResponse.

        Args:
            provider: A connector implementing the ModelExecution interface.

        Returns:
            True if the test passes.
        """
        request = mock_completion_request()
        response = await provider.complete(request)

        assert hasattr(response, "id"), "Response missing 'id' field"
        assert hasattr(response, "model"), "Response missing 'model' field"
        assert hasattr(response, "choices"), "Response missing 'choices' field"
        assert hasattr(response, "usage"), "Response missing 'usage' field"
        assert isinstance(response.choices, list), "'choices' must be a list"

        self.results["test_provider_complete"] = (True, "PASSED")
        return True

    async def test_provider_stream(self, provider: Any) -> bool:
        """Verify that stream() yields one or more CompletionResponse chunks.

        Args:
            provider: A connector implementing the ModelExecution interface.

        Returns:
            True if the test passes.
        """
        request = mock_completion_request(stream=True)
        chunks = []

        async for chunk in provider.stream(request):
            chunks.append(chunk)

        assert len(chunks) > 0, "stream() must yield at least one chunk"
        assert hasattr(chunks[0], "id"), "Chunk missing 'id' field"

        self.results["test_provider_stream"] = (True, "PASSED")
        return True

    async def test_rotation_deactivation(self, policy: Any) -> bool:
        """Verify that should_deactivate() triggers on high failure count.

        Args:
            policy: A connector implementing the DeactivationPolicy interface.

        Returns:
            True if the test passes.
        """
        healthy = mock_model_snapshot(failure_count=0, error_rate=0.0)
        assert not policy.should_deactivate(healthy), (
            "Healthy model should not be deactivated"
        )

        failing = mock_model_snapshot(failure_count=10, error_rate=0.9)
        assert policy.should_deactivate(failing), (
            "Failing model should be deactivated"
        )

        reason = policy.get_reason(failing)
        assert reason is not None, "Deactivation reason must not be None"

        self.results["test_rotation_deactivation"] = (True, "PASSED")
        return True

    async def test_rotation_recovery(self, policy: Any) -> bool:
        """Verify that should_recover() triggers after cooldown expires.

        Args:
            policy: A connector implementing the RecoveryPolicy interface.

        Returns:
            True if the test passes.
        """
        in_cooldown = mock_model_snapshot(
            status="standby",
            cooldown_remaining=60.0,
        )
        assert not policy.should_recover(in_cooldown), (
            "Model in cooldown should not recover"
        )

        cooldown_done = mock_model_snapshot(
            status="standby",
            cooldown_remaining=0.0,
            failure_count=0,
        )
        assert policy.should_recover(cooldown_done), (
            "Model with expired cooldown should recover"
        )

        self.results["test_rotation_recovery"] = (True, "PASSED")
        return True

    async def test_rotation_selection(self, strategy: Any) -> bool:
        """Verify that select() returns a SelectionResult with a valid model.

        Args:
            strategy: A connector implementing the SelectionStrategy interface.

        Returns:
            True if the test passes.
        """
        candidates = [
            mock_model_snapshot(model_id="gpt-4", latency_avg=200.0),
            mock_model_snapshot(model_id="gpt-3.5-turbo", latency_avg=100.0),
            mock_model_snapshot(model_id="claude-3", provider_id="anthropic", latency_avg=150.0),
        ]
        request = mock_completion_request()

        result = strategy.select(candidates, request)

        assert hasattr(result, "model_id"), "SelectionResult missing 'model_id'"
        assert hasattr(result, "provider_id"), "SelectionResult missing 'provider_id'"
        assert hasattr(result, "score"), "SelectionResult missing 'score'"
        assert result.model_id in {c.model_id for c in candidates}, (
            "Selected model must be from the candidate list"
        )

        self.results["test_rotation_selection"] = (True, "PASSED")
        return True

    async def test_secret_store_get(self, store: Any) -> bool:
        """Verify that get() returns a string for a known secret name.

        The store must be pre-populated with a secret named 'test-key'
        before running this test.

        Args:
            store: A connector implementing the SecretResolution interface.

        Returns:
            True if the test passes.
        """
        value = store.get("test-key")

        assert isinstance(value, str), "get() must return a string"
        assert len(value) > 0, "Secret value must not be empty"

        self.results["test_secret_store_get"] = (True, "PASSED")
        return True

    async def test_storage_crud(self, storage: Any) -> bool:
        """Verify a full save/load/list/delete cycle.

        Args:
            storage: A connector implementing the StorageConnector interface.

        Returns:
            True if the test passes.
        """
        key = "test/harness/entry"
        test_data = b'{"test": true}'

        from modelmesh.interfaces.storage import StorageEntry

        entry = StorageEntry(key=key, data=test_data, metadata={"source": "test"})

        # Save
        await storage.save(key, entry)

        # Load
        loaded = await storage.load(key)
        assert loaded is not None, "load() must return the saved entry"
        assert loaded.data == test_data, "Loaded data must match saved data"

        # List
        keys = await storage.list("test/")
        assert key in keys, "list() must include the saved key"

        # Delete
        deleted = await storage.delete(key)
        assert deleted is True, "delete() must return True for existing key"

        # Verify deletion
        after_delete = await storage.load(key)
        assert after_delete is None, "load() must return None after deletion"

        self.results["test_storage_crud"] = (True, "PASSED")
        return True

    async def test_observability_emit_log_flush_trace(self, connector: Any) -> bool:
        """Verify that emit(), log(), flush(), and trace() execute without raising.

        Args:
            connector: A connector implementing the ObservabilityConnector interface.

        Returns:
            True if the test passes.
        """
        from modelmesh.interfaces.observability import (
            AggregateStats,
            EventType,
            RequestLogEntry,
            RoutingEvent,
            Severity,
            TraceEntry,
        )

        # emit
        event = RoutingEvent(
            event_type=EventType.MODEL_ACTIVATED,
            timestamp=datetime.utcnow(),
            model_id="gpt-4",
            provider_id="openai",
        )
        connector.emit(event)

        # log
        log_entry = RequestLogEntry(
            timestamp=datetime.utcnow(),
            model_id="gpt-4",
            provider_id="openai",
            capability="chat",
            delivery_mode="sync",
            latency_ms=150.0,
            status_code=200,
            tokens_in=50,
            tokens_out=100,
        )
        connector.log(log_entry)

        # flush
        stats = {
            "gpt-4": AggregateStats(
                requests_total=100,
                requests_success=95,
                requests_failed=5,
                tokens_in=5000,
                tokens_out=10000,
                cost_total=1.50,
                latency_avg=150.0,
                latency_p95=300.0,
                downtime_total=0.0,
                rotation_events=2,
            )
        }
        connector.flush(stats)

        # trace
        trace_entry = TraceEntry(
            severity=Severity.INFO,
            timestamp=datetime.utcnow(),
            component="test",
            message="Test trace entry",
        )
        connector.trace(trace_entry)

        self.results["test_observability_emit_log_flush_trace"] = (True, "PASSED")
        return True

    async def test_discovery_probe(self, connector: Any) -> bool:
        """Verify that probe() returns a ProbeResult with required fields.

        Args:
            connector: A connector implementing the HealthMonitoring interface.

        Returns:
            True if the test passes.
        """
        result = await connector.probe("openai")

        assert hasattr(result, "provider_id"), "ProbeResult missing 'provider_id'"
        assert hasattr(result, "success"), "ProbeResult missing 'success'"
        assert isinstance(result.success, bool), "'success' must be a boolean"
        assert result.provider_id == "openai", (
            "ProbeResult provider_id must match the requested provider"
        )

        self.results["test_discovery_probe"] = (True, "PASSED")
        return True

    async def run_all(self, connector: Any, connector_type: str) -> dict[str, tuple[bool, str]]:
        """Run all applicable tests for the given connector type.

        Args:
            connector: The connector instance to test.
            connector_type: One of "provider", "rotation", "secret_store",
                "storage", "observability", "discovery".

        Returns:
            Dict mapping test names to (passed, message) tuples.
        """
        test_map = {
            "provider": [self.test_provider_complete, self.test_provider_stream],
            "rotation": [
                self.test_rotation_deactivation,
                self.test_rotation_recovery,
                self.test_rotation_selection,
            ],
            "secret_store": [self.test_secret_store_get],
            "storage": [self.test_storage_crud],
            "observability": [self.test_observability_emit_log_flush_trace],
            "discovery": [self.test_discovery_probe],
        }

        tests = test_map.get(connector_type, [])
        for test_fn in tests:
            name = test_fn.__name__
            try:
                await test_fn(connector)
            except (AssertionError, Exception) as exc:
                self.results[name] = (False, f"FAILED: {exc}")

        return self.results
```

#### TypeScript

```typescript
/**
 * Run standard interface compliance tests against connector implementations.
 *
 * Each test method validates one aspect of a connector's interface
 * contract. Tests produce clear pass/fail results with diagnostics.
 */
class ConnectorTestHarness {
    /** Maps test names to [passed, message] tuples after completion. */
    readonly results = new Map<string, [boolean, string]>();

    /**
     * Verify that complete() returns a CompletionResponse.
     *
     * @param provider - A connector implementing ModelExecution.
     */
    async testProviderComplete(provider: {
        complete(req: CompletionRequest): Promise<CompletionResponse>;
    }): Promise<boolean> {
        const request = mockCompletionRequest();
        const response = await provider.complete(request);

        this.assert(response.id != null, "Response missing 'id'");
        this.assert(response.model != null, "Response missing 'model'");
        this.assert(Array.isArray(response.choices), "'choices' must be an array");
        this.assert(response.usage != null, "Response missing 'usage'");

        this.results.set("testProviderComplete", [true, "PASSED"]);
        return true;
    }

    /**
     * Verify that stream() yields one or more chunks.
     *
     * @param provider - A connector implementing ModelExecution.
     */
    async testProviderStream(provider: {
        stream(req: CompletionRequest): AsyncIterable<CompletionResponse>;
    }): Promise<boolean> {
        const request = mockCompletionRequest({ stream: true });
        const chunks: CompletionResponse[] = [];

        for await (const chunk of provider.stream(request)) {
            chunks.push(chunk);
        }

        this.assert(chunks.length > 0, "stream() must yield at least one chunk");
        this.assert(chunks[0].id != null, "Chunk missing 'id'");

        this.results.set("testProviderStream", [true, "PASSED"]);
        return true;
    }

    /**
     * Verify deactivation triggers on high failure count.
     *
     * @param policy - A connector implementing DeactivationPolicy.
     */
    async testRotationDeactivation(policy: {
        shouldDeactivate(snapshot: ModelSnapshot): boolean;
        getReason(snapshot: ModelSnapshot): string | null;
    }): Promise<boolean> {
        const healthy = mockModelSnapshot({ failure_count: 0, error_rate: 0.0 });
        this.assert(
            !policy.shouldDeactivate(healthy),
            "Healthy model should not be deactivated",
        );

        const failing = mockModelSnapshot({ failure_count: 10, error_rate: 0.9 });
        this.assert(
            policy.shouldDeactivate(failing),
            "Failing model should be deactivated",
        );

        const reason = policy.getReason(failing);
        this.assert(reason !== null, "Deactivation reason must not be null");

        this.results.set("testRotationDeactivation", [true, "PASSED"]);
        return true;
    }

    /**
     * Verify recovery triggers after cooldown expires.
     *
     * @param policy - A connector implementing RecoveryPolicy.
     */
    async testRotationRecovery(policy: {
        shouldRecover(snapshot: ModelSnapshot): boolean;
    }): Promise<boolean> {
        const inCooldown = mockModelSnapshot({
            status: ModelStatus.STANDBY,
            cooldown_remaining: 60,
        });
        this.assert(
            !policy.shouldRecover(inCooldown),
            "Model in cooldown should not recover",
        );

        const cooldownDone = mockModelSnapshot({
            status: ModelStatus.STANDBY,
            cooldown_remaining: 0,
            failure_count: 0,
        });
        this.assert(
            policy.shouldRecover(cooldownDone),
            "Model with expired cooldown should recover",
        );

        this.results.set("testRotationRecovery", [true, "PASSED"]);
        return true;
    }

    /**
     * Verify select() returns a SelectionResult from candidates.
     *
     * @param strategy - A connector implementing SelectionStrategy.
     */
    async testRotationSelection(strategy: {
        select(candidates: ModelSnapshot[], request: CompletionRequest): SelectionResult;
    }): Promise<boolean> {
        const candidates = [
            mockModelSnapshot({ model_id: "gpt-4", latency_avg: 200 }),
            mockModelSnapshot({ model_id: "gpt-3.5-turbo", latency_avg: 100 }),
            mockModelSnapshot({ model_id: "claude-3", provider_id: "anthropic", latency_avg: 150 }),
        ];
        const request = mockCompletionRequest();

        const result = strategy.select(candidates, request);

        this.assert(result.model_id != null, "SelectionResult missing 'model_id'");
        this.assert(result.provider_id != null, "SelectionResult missing 'provider_id'");
        this.assert(result.score != null, "SelectionResult missing 'score'");

        const validIds = new Set(candidates.map((c) => c.model_id));
        this.assert(
            validIds.has(result.model_id),
            "Selected model must be from the candidate list",
        );

        this.results.set("testRotationSelection", [true, "PASSED"]);
        return true;
    }

    /**
     * Verify get() returns a string for a known secret.
     * The store must be pre-populated with 'test-key' before calling.
     *
     * @param store - A connector implementing SecretResolution.
     */
    async testSecretStoreGet(store: {
        get(name: string): string;
    }): Promise<boolean> {
        const value = store.get("test-key");

        this.assert(typeof value === "string", "get() must return a string");
        this.assert(value.length > 0, "Secret value must not be empty");

        this.results.set("testSecretStoreGet", [true, "PASSED"]);
        return true;
    }

    /**
     * Verify a full save/load/list/delete cycle.
     *
     * @param storage - A connector implementing StorageConnector.
     */
    async testStorageCrud(storage: {
        save(key: string, entry: StorageEntry): Promise<void>;
        load(key: string): Promise<StorageEntry | null>;
        list(prefix?: string): Promise<string[]>;
        delete(key: string): Promise<boolean>;
    }): Promise<boolean> {
        const key = "test/harness/entry";
        const testData = new TextEncoder().encode('{"test": true}');
        const entry: StorageEntry = {
            key,
            data: testData,
            metadata: { source: "test" },
        };

        await storage.save(key, entry);

        const loaded = await storage.load(key);
        this.assert(loaded !== null, "load() must return the saved entry");

        const keys = await storage.list("test/");
        this.assert(keys.includes(key), "list() must include the saved key");

        const deleted = await storage.delete(key);
        this.assert(deleted === true, "delete() must return true for existing key");

        const afterDelete = await storage.load(key);
        this.assert(afterDelete === null, "load() must return null after deletion");

        this.results.set("testStorageCrud", [true, "PASSED"]);
        return true;
    }

    /**
     * Verify emit(), log(), flush(), and trace() execute without throwing.
     *
     * @param connector - A connector implementing ObservabilityConnector.
     */
    async testObservabilityEmitLogFlushTrace(connector: {
        emit(event: RoutingEvent): void;
        log(entry: RequestLogEntry): void;
        flush(stats: Record<string, AggregateStats>): void;
        trace(entry: TraceEntry): void;
    }): Promise<boolean> {
        connector.emit({
            event_type: EventType.MODEL_ACTIVATED,
            timestamp: new Date(),
            model_id: "gpt-4",
            provider_id: "openai",
            metadata: {},
        });

        connector.log({
            timestamp: new Date(),
            model_id: "gpt-4",
            provider_id: "openai",
            capability: "chat",
            delivery_mode: "sync",
            latency_ms: 150,
            status_code: 200,
            tokens_in: 50,
            tokens_out: 100,
        });

        connector.flush({
            "gpt-4": {
                requests_total: 100,
                requests_success: 95,
                requests_failed: 5,
                tokens_in: 5000,
                tokens_out: 10000,
                cost_total: 1.5,
                latency_avg: 150,
                latency_p95: 300,
                downtime_total: 0,
                rotation_events: 2,
            },
        });

        connector.trace({
            severity: Severity.INFO,
            timestamp: new Date(),
            component: "test",
            message: "Test trace entry",
        });

        this.results.set("testObservabilityEmitLogFlushTrace", [true, "PASSED"]);
        return true;
    }

    /**
     * Verify probe() returns a ProbeResult with required fields.
     *
     * @param connector - A connector implementing HealthMonitoring.
     */
    async testDiscoveryProbe(connector: {
        probe(providerId: string): Promise<ProbeResult>;
    }): Promise<boolean> {
        const result = await connector.probe("openai");

        this.assert(result.provider_id != null, "ProbeResult missing 'provider_id'");
        this.assert(typeof result.success === "boolean", "'success' must be a boolean");
        this.assert(
            result.provider_id === "openai",
            "ProbeResult provider_id must match requested provider",
        );

        this.results.set("testDiscoveryProbe", [true, "PASSED"]);
        return true;
    }

    /**
     * Run all applicable tests for the given connector type.
     *
     * @param connector - The connector instance to test.
     * @param connectorType - One of the ConnectorType values.
     * @returns Map of test names to [passed, message] tuples.
     */
    async runAll(
        connector: unknown,
        connectorType: string,
    ): Promise<Map<string, [boolean, string]>> {
        type TestFn = (target: any) => Promise<boolean>;

        const testMap: Record<string, TestFn[]> = {
            provider: [
                (c) => this.testProviderComplete(c),
                (c) => this.testProviderStream(c),
            ],
            rotation: [
                (c) => this.testRotationDeactivation(c),
                (c) => this.testRotationRecovery(c),
                (c) => this.testRotationSelection(c),
            ],
            secret_store: [(c) => this.testSecretStoreGet(c)],
            storage: [(c) => this.testStorageCrud(c)],
            observability: [(c) => this.testObservabilityEmitLogFlushTrace(c)],
            discovery: [(c) => this.testDiscoveryProbe(c)],
        };

        const tests = testMap[connectorType] ?? [];
        for (const testFn of tests) {
            try {
                await testFn(connector);
            } catch (error) {
                const name = testFn.name || "unknown";
                this.results.set(name, [false, `FAILED: ${error}`]);
            }
        }

        return this.results;
    }

    private assert(condition: boolean, message: string): void {
        if (!condition) {
            throw new Error(message);
        }
    }
}
```

---

## Auto-Detection Utilities

Helpers used by the convenience layer (`modelmesh.create()`) to automatically detect available providers from environment variables. These are also available for direct use when building custom provider discovery logic.

### `detect_providers()`

Scans environment variables for known API keys and returns a list of detected provider configurations. Used internally by `modelmesh.create()` to set up providers without explicit configuration.

**Signature:**

- **Python:** `detect_providers() -> list[QuickProviderConfig]`
- **TypeScript:** `detectProviders(): QuickProviderConfig[]`

**Returns:** A list of `QuickProviderConfig` objects, one for each provider whose API key was found in the environment. Each config has `base_url` and `api_key` populated; `models` is left empty so that `QuickProvider` will auto-discover them.

#### Python

```python
import os
from dataclasses import dataclass


@dataclass
class QuickProviderConfig:
    """Minimal provider configuration for auto-detected providers."""
    name: str
    base_url: str
    api_key: str
    models: list = None  # empty triggers auto-discovery

    def __post_init__(self):
        if self.models is None:
            self.models = []


def detect_providers() -> list[QuickProviderConfig]:
    """Scan environment variables for known API keys.

    Iterates over ``_PROVIDER_REGISTRY`` and checks each entry's
    environment variable. For every key found, builds a
    ``QuickProviderConfig`` with the provider's base URL and the
    resolved API key.

    Returns:
        List of provider configs for every detected provider.

    Example::

        providers = detect_providers()
        # [QuickProviderConfig(name='openai', base_url='https://api.openai.com/v1', ...),
        #  QuickProviderConfig(name='anthropic', base_url='https://api.anthropic.com', ...)]
    """
    detected: list[QuickProviderConfig] = []
    for env_var, entry in _PROVIDER_REGISTRY.items():
        api_key = os.environ.get(env_var)
        if api_key:
            detected.append(QuickProviderConfig(
                name=entry["name"],
                base_url=entry["base_url"],
                api_key=api_key,
            ))
    return detected
```

#### TypeScript

```typescript
interface QuickProviderConfig {
    name: string;
    baseUrl: string;
    apiKey: string;
    models: unknown[];  // empty triggers auto-discovery
}

/**
 * Scan environment variables for known API keys.
 *
 * Iterates over `PROVIDER_REGISTRY` and checks each entry's
 * environment variable. For every key found, builds a
 * `QuickProviderConfig` with the provider's base URL and the
 * resolved API key.
 *
 * @returns List of provider configs for every detected provider.
 */
function detectProviders(): QuickProviderConfig[] {
    const detected: QuickProviderConfig[] = [];
    for (const [envVar, entry] of Object.entries(PROVIDER_REGISTRY)) {
        const apiKey = process.env[envVar];
        if (apiKey) {
            detected.push({
                name: entry.name,
                baseUrl: entry.baseUrl,
                apiKey,
                models: [],
            });
        }
    }
    return detected;
}
```

---

### `_PROVIDER_REGISTRY`

Internal mapping from environment variable names to provider configurations. Contains 9 pre-configured providers covering the most widely used AI APIs. Each entry stores the provider name, base URL, and the environment variable that holds the API key.

> **Note:** This registry is intentionally kept internal (prefixed with `_` in Python, not exported in TypeScript). Use `detect_providers()` / `detectProviders()` to interact with it.

#### Python

```python
_PROVIDER_REGISTRY: dict[str, dict[str, str]] = {
    "OPENAI_API_KEY": {
        "name": "openai",
        "base_url": "https://api.openai.com/v1",
    },
    "ANTHROPIC_API_KEY": {
        "name": "anthropic",
        "base_url": "https://api.anthropic.com",
    },
    "GOOGLE_API_KEY": {
        "name": "google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
    },
    "MISTRAL_API_KEY": {
        "name": "mistral",
        "base_url": "https://api.mistral.ai/v1",
    },
    "GROQ_API_KEY": {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "TOGETHER_API_KEY": {
        "name": "together",
        "base_url": "https://api.together.xyz/v1",
    },
    "FIREWORKS_API_KEY": {
        "name": "fireworks",
        "base_url": "https://api.fireworks.ai/inference/v1",
    },
    "DEEPSEEK_API_KEY": {
        "name": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
    },
    "OPENROUTER_API_KEY": {
        "name": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
    },
}
```

#### TypeScript

```typescript
/** Internal mapping from environment variable names to provider configs. */
const PROVIDER_REGISTRY: Record<string, { name: string; baseUrl: string }> = {
    OPENAI_API_KEY: {
        name: "openai",
        baseUrl: "https://api.openai.com/v1",
    },
    ANTHROPIC_API_KEY: {
        name: "anthropic",
        baseUrl: "https://api.anthropic.com",
    },
    GOOGLE_API_KEY: {
        name: "google",
        baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    },
    MISTRAL_API_KEY: {
        name: "mistral",
        baseUrl: "https://api.mistral.ai/v1",
    },
    GROQ_API_KEY: {
        name: "groq",
        baseUrl: "https://api.groq.com/openai/v1",
    },
    TOGETHER_API_KEY: {
        name: "together",
        baseUrl: "https://api.together.xyz/v1",
    },
    FIREWORKS_API_KEY: {
        name: "fireworks",
        baseUrl: "https://api.fireworks.ai/inference/v1",
    },
    DEEPSEEK_API_KEY: {
        name: "deepseek",
        baseUrl: "https://api.deepseek.com/v1",
    },
    OPENROUTER_API_KEY: {
        name: "openrouter",
        baseUrl: "https://openrouter.ai/api/v1",
    },
};
```
