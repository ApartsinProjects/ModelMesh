# Latency First

**ID:** `rotation.modelmesh.latency-first.v1`
**Type:** Rotation Policy

Selects the model with the lowest recent average latency. Latency data is sourced from `ModelState.latency_history`, which records response times for each model over a sliding window. This strategy adapts to real-time performance conditions, automatically shifting traffic away from slow models.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Deactivation | Yes | Standard deactivation triggers |
| Recovery | Yes | Standard recovery triggers |
| Selection | Yes | Selects the active model with the lowest recent latency |

## Behavior

Latency-first evaluates each active model's recent performance and selects the one with the lowest average response time. The strategy uses the `latency_history` field from the model's state, which is a rolling window of observed latencies maintained by the router.

**Selection logic:**

1. For each active model, compute the average latency over the recent sliding window.
2. Select the model with the lowest average latency.
3. If a model has no latency history (e.g., newly activated or recovered), it is assigned a neutral score (median of known latencies) to allow it to be tested without being unfairly penalized or prioritized.
4. If multiple models have identical average latency, the first one in pool order is chosen.
5. If no active models exist, raise a `NoActiveModelError`.

**Example:**

Given a pool with three models and their recent average latencies:

| Model | Avg latency (last 50 requests) |
| --- | --- |
| groq-llama-3.3-70b | 180ms |
| gpt-4o | 650ms |
| claude-sonnet-4-20250514 | 820ms |

All requests are routed to groq-llama-3.3-70b. If Groq's latency spikes to 2000ms due to load, the average shifts upward over subsequent requests, and traffic naturally migrates to gpt-4o. The adaptation speed depends on the sliding window size -- smaller windows react faster but are more sensitive to individual outliers.

## Configuration

This strategy uses only the common rotation parameters. Latency data is collected automatically by the router -- no strategy-specific configuration is required.

See [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.md#rotation-policy) for the full list of common rotation parameters including deactivation thresholds, recovery cooldowns, and probe settings.

## YAML Example

```yaml
pools:
  text-generation:
    rotation:
      policy: modelmesh.latency-first.v1
      deactivation:
        retry_limit: 3
        error_codes: [429, 500, 502, 503]
      recovery:
        cooldown: 30s
        probe_interval: 120s
    models:
      - groq-llama-3.3-70b
      - gpt-4o
      - claude-sonnet-4-20250514
```
