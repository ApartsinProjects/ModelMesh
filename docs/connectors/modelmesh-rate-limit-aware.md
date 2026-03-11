---
layout: default
title: "Rate Limit Aware"
---

# Rate Limit Aware

**ID:** `rotation.modelmesh.rate-limit-aware.v1`
**Type:** Rotation Policy

Preemptively switches models before hitting rate limits. Monitors rate-limit headroom from provider responses (HTTP headers such as `x-ratelimit-remaining` and `x-ratelimit-limit`) and switches to another model when usage reaches the configured threshold. This strategy prevents 429 errors proactively rather than reacting to them after they occur.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Deactivation | Yes | Standard deactivation triggers |
| Recovery | Yes | Standard recovery triggers |
| Selection | Yes | Preemptive model switching based on rate-limit headroom |

## Constants

```python
from enum import Enum

class ThrottleAction(Enum):
    """Action to take when a model approaches its rate limit."""
    SWITCH_MODEL = "switch_model"     # Immediately switch to another model
    DELAY_REQUEST = "delay_request"   # Delay the request until headroom recovers
    QUEUE = "queue"                   # Queue the request for later execution
```

```typescript
enum ThrottleAction {
    /** Immediately switch to another model. */
    SWITCH_MODEL = "switch_model",
    /** Delay the request until headroom recovers. */
    DELAY_REQUEST = "delay_request",
    /** Queue the request for later execution. */
    QUEUE = "queue",
}
```

## Behavior

Rate-limit-aware selection tracks each model's remaining rate-limit capacity as a fraction of its total limit. When a model's usage crosses the configured threshold (e.g., 80% of its limit consumed), the strategy proactively switches to the next available model that has sufficient headroom.

**Selection logic:**

1. For each active model, compute the current usage ratio: `usage_ratio = 1 - (remaining / limit)`.
2. If the preferred model's `usage_ratio` is below `threshold`, route to it.
3. If the preferred model's `usage_ratio` is at or above `threshold`:
   - **SWITCH_MODEL:** Select the active model with the most remaining headroom.
   - **DELAY_REQUEST:** Hold the request until the current model's rate-limit window resets, respecting `min_delta` between requests.
   - **QUEUE:** Enqueue the request and process it when capacity is available.
4. If `max_rpm` is set and the current model has exceeded that limit, treat it as if the threshold has been crossed.
5. Enforce `min_delta` as the minimum interval between consecutive requests to the same model.
6. If no active models have sufficient headroom, fall back to the model with the most remaining capacity.

**Example:**

Given `threshold: 0.8` and models with these rate limits:

| Model | Limit | Remaining | Usage ratio | Status |
| --- | --- | --- | --- | --- |
| gpt-4o | 500 RPM | 80 | 0.84 | Above threshold |
| claude-sonnet-4-20250514 | 1000 RPM | 600 | 0.40 | Below threshold |
| gemini-2.5-pro | 300 RPM | 250 | 0.17 | Below threshold |

gpt-4o has crossed the 80% threshold. The strategy switches to claude-sonnet-4-20250514 (most absolute headroom). If claude-sonnet-4-20250514 also crosses the threshold, traffic shifts to gemini-2.5-pro. When gpt-4o's rate-limit window resets, its headroom is restored and it becomes eligible again.

## Configuration

See [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.md#rotation-policy) for the full list of common rotation parameters including deactivation thresholds, recovery cooldowns, and probe settings.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `rotation.selection.rate_limit.threshold` | float | `0.8` | Usage fraction (0.0--1.0) at which to preemptively switch models. `0.8` means switch when 80% of the rate limit is consumed. |
| `rotation.selection.rate_limit.min_delta` | duration | `"0s"` | Minimum time interval between consecutive requests to the same model. |
| `rotation.selection.rate_limit.max_rpm` | integer | `0` | Hard cap on requests per minute to any single model. `0` means no cap (use provider-reported limits only). |

## YAML Example

```yaml
pools:
  text-generation:
    rotation:
      policy: modelmesh.rate-limit-aware.v1
      selection:
        rate_limit:
          threshold: 0.8
          min_delta: 100ms
          max_rpm: 450
      deactivation:
        retry_limit: 3
        error_codes: [429, 500, 502, 503]
      recovery:
        cooldown: 30s
        on_quota_reset: true
    models:
      - gpt-4o
      - claude-sonnet-4-20250514
      - gemini-2.5-pro
```
