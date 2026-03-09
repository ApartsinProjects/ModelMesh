# Session Stickiness

**ID:** `rotation.modelmesh.session-stickiness.v1`
**Type:** Rotation Policy

Routes all requests sharing the same `session_id` to the same model, maintaining session affinity for conversational contexts. When a session's assigned model becomes unavailable, behavior depends on the configured affinity mode: strict mode fails the request, while fallback mode routes to the next available model. New sessions without an existing assignment are routed using priority selection.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Deactivation | Yes | Standard deactivation triggers |
| Recovery | Yes | Standard recovery triggers |
| Selection | Yes | Session-affine model selection with configurable fallback |

## Constants

```python
from enum import Enum

class SessionAffinityMode(Enum):
    """Controls behavior when a session's assigned model is unavailable."""
    STRICT = "strict"       # Fail the request if the assigned model is unavailable
    FALLBACK = "fallback"   # Route to the next available model
```

```typescript
enum SessionAffinityMode {
    /** Fail the request if the assigned model is unavailable. */
    STRICT = "strict",
    /** Route to the next available model. */
    FALLBACK = "fallback",
}
```

## Behavior

Session stickiness maintains a mapping of `session_id` to model assignments. When a request includes a `session_id`, the strategy looks up the assigned model and routes to it if available. This ensures conversational continuity -- the same model handles all turns of a conversation.

**Selection logic:**

1. If the request includes a `session_id` and a model is assigned to that session:
   - If the assigned model is active, route to it.
   - If the assigned model is in standby:
     - **STRICT mode:** Return a `SessionModelUnavailableError` so the caller can decide how to proceed.
     - **FALLBACK mode:** Select the next available model using priority selection and update the session mapping.
2. If the request has a `session_id` but no model is assigned (new session):
   - Select a model using priority selection (or pool order if no priority is configured).
   - Store the `session_id` to model mapping.
3. If the request has no `session_id`, fall back to priority selection.
4. Session mappings expire after `session_timeout` of inactivity.

**Example:**

Given `affinity_mode: fallback` and `session_timeout: 30m`:

- Request (session=abc123): No existing mapping. Assigns gpt-4o. Routes to gpt-4o.
- Request (session=abc123): Mapping exists. Routes to gpt-4o.
- Request (session=xyz789): New session. Assigns gpt-4o (still highest priority).
- gpt-4o is deactivated.
- Request (session=abc123): gpt-4o unavailable, fallback mode. Reassigns to claude-sonnet-4-20250514. Routes to claude-sonnet-4-20250514.
- Request (session=xyz789): Same fallback. Reassigns to claude-sonnet-4-20250514.
- 30 minutes of inactivity on session abc123: mapping expires and is removed.

## Configuration

See [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.md#rotation-policy) for the full list of common rotation parameters including deactivation thresholds, recovery cooldowns, and probe settings.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `rotation.selection.affinity_mode` | string | `"fallback"` | Session affinity mode: `strict` (fail if model unavailable) or `fallback` (use next available model). |
| `rotation.selection.session_timeout` | duration | `"30m"` | Duration of inactivity before a session mapping expires and is removed. |

## YAML Example

```yaml
pools:
  text-generation:
    rotation:
      policy: modelmesh.session-stickiness.v1
      selection:
        affinity_mode: fallback
        session_timeout: 30m
      deactivation:
        retry_limit: 3
        error_codes: [429, 500, 502, 503]
      recovery:
        cooldown: 60s
        probe_interval: 300s
    models:
      - gpt-4o
      - claude-sonnet-4-20250514
      - gemini-2.5-pro
```
