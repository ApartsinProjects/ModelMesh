---
layout: default
title: "Stick Until Failure"
---

# Stick Until Failure

**ID:** `rotation.modelmesh.stick-until-failure.v1`
**Type:** Rotation Policy

The default rotation strategy. Keeps routing all requests to the same model until it fails or is deactivated, then rotates to the next available model. This approach minimizes rotation overhead and provides the most predictable routing behavior. Ideal for stable deployments where models rarely fail or for single-model pools.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Deactivation | Yes | Standard deactivation triggers |
| Recovery | Yes | Standard recovery triggers |
| Selection | Yes | Sticky to current model; rotate only on failure |

## Behavior

Stick-until-failure maintains a pointer to the "current" model in the pool. Every request is routed to this model as long as it remains in the `active` state. When the current model is deactivated (due to error threshold, quota exhaustion, or any other deactivation trigger), the strategy advances the pointer to the next available active model.

**Selection logic:**

1. If the current model is active, return it immediately.
2. If the current model has been deactivated, scan the remaining active models in pool order.
3. Select the first active model found and set it as the new current model.
4. If no active models remain, raise a `NoActiveModelError`.

**Example:**

Given a pool with models `[A, B, C]` where A is the current model:

- Requests 1-100: routed to A (A is active).
- Request 101: A returns a 500 error, triggering deactivation after exceeding `retry_limit`.
- Requests 102+: routed to B (B becomes the new current model).
- If A recovers (cooldown expires, probe succeeds), A becomes available again but B remains the current model until B itself fails.

## Configuration

This strategy uses only the common rotation parameters. No strategy-specific configuration is required.

See [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.html#rotation-policy) for the full list of common rotation parameters including deactivation thresholds, recovery cooldowns, and probe settings.

## YAML Example

```yaml
pools:
  text-generation:
    rotation:
      policy: modelmesh.stick-until-failure.v1
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
