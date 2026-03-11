---
layout: default
title: "Round Robin"
---

# Round Robin

**ID:** `rotation.modelmesh.round-robin.v1`
**Type:** Rotation Policy

Cycles through active models in round-robin order, distributing requests evenly across all active models in the pool. Standby models are skipped. This strategy is useful when you want to spread load across multiple equivalent models or providers to avoid concentrating usage on a single endpoint.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Deactivation | Yes | Standard deactivation triggers |
| Recovery | Yes | Standard recovery triggers |
| Selection | Yes | Sequential cycling through active models |

## Behavior

Round-robin maintains an internal index that advances after each request. Only models in the `active` state are considered; standby models are skipped without advancing the index.

**Selection logic:**

1. Starting from the current index position, find the next active model in the pool.
2. Route the request to that model.
3. Advance the index by one position (wrapping around to the beginning of the pool).
4. If no active models exist, raise a `NoActiveModelError`.

**Example:**

Given a pool with models `[A, B, C]`, all active:

- Request 1: A (index 0)
- Request 2: B (index 1)
- Request 3: C (index 2)
- Request 4: A (index wraps to 0)

If B is deactivated:

- Request 5: C (B is skipped)
- Request 6: A
- Request 7: C (B is still skipped)

When B recovers, it is included in the rotation again from its original position.

## Configuration

This strategy uses only the common rotation parameters. No strategy-specific configuration is required.

See [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.md#rotation-policy) for the full list of common rotation parameters including deactivation thresholds, recovery cooldowns, and probe settings.

## YAML Example

```yaml
pools:
  text-generation:
    rotation:
      policy: modelmesh.round-robin.v1
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
