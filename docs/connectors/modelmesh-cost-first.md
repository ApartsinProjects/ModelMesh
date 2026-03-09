---
layout: default
title: "Cost First"
---

# Cost First

**ID:** `rotation.modelmesh.cost-first.v1`
**Type:** Rotation Policy

Selects the cheapest available model based on per-token pricing for each request. Pricing data is sourced from provider connectors via their Cost & Pricing interface. This strategy is ideal for workloads where multiple models offer equivalent capability and cost optimization is the primary concern.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Deactivation | Yes | Standard deactivation triggers |
| Recovery | Yes | Standard recovery triggers |
| Selection | Yes | Selects the lowest-cost active model per request |

## Behavior

Cost-first recalculates model cost on each request using the pricing metadata reported by provider connectors. The model with the lowest effective cost per token is selected. If multiple models have identical pricing, the first one encountered in pool order is chosen.

**Selection logic:**

1. Gather pricing data for all active models in the pool (via `get_pricing` from each provider connector).
2. Calculate effective cost per token for each model. Both input and output token costs are considered, weighted by expected output ratio if available.
3. Select the model with the lowest effective cost.
4. If pricing data is unavailable for a model, that model is ranked last (treated as most expensive).
5. If no active models exist, raise a `NoActiveModelError`.

**Example:**

Given a pool with models and their per-1K-token costs:

| Model | Input cost | Output cost | Effective cost |
| --- | --- | --- | --- |
| deepseek-v3.2 | $0.14 | $0.28 | Lowest |
| gemini-2.5-flash | $0.15 | $0.60 | Middle |
| gpt-4o | $2.50 | $10.00 | Highest |

All requests are routed to deepseek-v3.2. If deepseek-v3.2 is deactivated (quota hit), requests shift to gemini-2.5-flash. Pricing is re-evaluated on each request, so if a provider announces a price change, the selection adapts immediately.

## Configuration

This strategy uses only the common rotation parameters. Pricing data is sourced from provider connectors -- no strategy-specific configuration is required.

See [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.html#rotation-policy) for the full list of common rotation parameters including deactivation thresholds, recovery cooldowns, and probe settings.

## YAML Example

```yaml
pools:
  text-generation:
    rotation:
      policy: modelmesh.cost-first.v1
      deactivation:
        retry_limit: 3
        budget_limit: 10.00
        error_codes: [429, 500, 502, 503]
      recovery:
        cooldown: 60s
        on_quota_reset: true
    models:
      - deepseek-v3.2
      - gemini-2.5-flash
      - gpt-4o
```
