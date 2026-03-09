# Load Balanced

**ID:** `rotation.modelmesh.load-balanced.v1`
**Type:** Rotation Policy

Distributes requests proportionally across models based on their rate-limit headroom. Unlike round-robin (which distributes evenly) or rate-limit-aware (which switches entirely when a threshold is crossed), load-balanced continuously adjusts the distribution so that models with more remaining capacity receive proportionally more traffic.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Deactivation | Yes | Standard deactivation triggers |
| Recovery | Yes | Standard recovery triggers |
| Selection | Yes | Proportional distribution based on rate-limit headroom |

## Constants

```python
from enum import Enum

class BalanceMode(Enum):
    """How to calculate each model's share of traffic."""
    ABSOLUTE = "absolute"   # Distribute by absolute remaining capacity
    RELATIVE = "relative"   # Distribute by percentage of remaining capacity
```

```typescript
enum BalanceMode {
    /** Distribute by absolute remaining capacity. */
    ABSOLUTE = "absolute",
    /** Distribute by percentage of remaining capacity. */
    RELATIVE = "relative",
}
```

## Behavior

Load-balanced selection computes a weight for each active model based on its current rate-limit headroom and routes requests proportionally to those weights. The balance mode determines how weights are calculated.

**ABSOLUTE mode:**

Weights are based on the raw number of remaining requests. A model with 800 remaining requests gets twice the traffic of a model with 400 remaining requests, regardless of their total limits.

**RELATIVE mode (default):**

Weights are based on the percentage of remaining capacity. A model at 90% remaining (of its limit) gets the same weight as another model at 90% remaining, even if their absolute limits differ. This prevents models with higher rate limits from monopolizing traffic.

**Selection logic:**

1. For each active model, compute its weight:
   - ABSOLUTE: `weight = remaining_requests`
   - RELATIVE: `weight = remaining_requests / total_limit`
2. Normalize weights to a probability distribution.
3. Select a model using weighted random sampling according to the distribution.
4. If rate-limit data is unavailable for a model, assign it the median weight of known models.
5. If no active models exist, raise a `NoActiveModelError`.

**Example (RELATIVE mode):**

| Model | Limit | Remaining | Relative weight | Traffic share |
| --- | --- | --- | --- | --- |
| gpt-4o | 500 RPM | 400 | 0.80 | 42% |
| claude-sonnet-4-20250514 | 1000 RPM | 700 | 0.70 | 37% |
| gemini-2.5-pro | 300 RPM | 120 | 0.40 | 21% |

As gpt-4o's remaining capacity decreases, its share of traffic naturally decreases, shifting load toward models with more headroom.

**Example (ABSOLUTE mode):**

Using the same data:

| Model | Remaining | Absolute weight | Traffic share |
| --- | --- | --- | --- |
| claude-sonnet-4-20250514 | 700 | 700 | 57% |
| gpt-4o | 400 | 400 | 33% |
| gemini-2.5-pro | 120 | 120 | 10% |

In absolute mode, claude-sonnet-4-20250514 dominates because it has the most remaining capacity in raw terms.

## Configuration

See [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.md#rotation-policy) for the full list of common rotation parameters including deactivation thresholds, recovery cooldowns, and probe settings.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `rotation.selection.balance_mode` | string | `"relative"` | Balance mode: `absolute` (distribute by raw remaining capacity) or `relative` (distribute by percentage of remaining capacity). |

## YAML Example

```yaml
pools:
  text-generation:
    rotation:
      policy: modelmesh.load-balanced.v1
      selection:
        balance_mode: relative
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
