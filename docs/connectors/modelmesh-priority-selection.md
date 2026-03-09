---
layout: default
title: "Priority Selection"
---

# Priority Selection

**ID:** `rotation.modelmesh.priority-selection.v1`
**Type:** Rotation Policy

Always selects the highest-priority available model from the configured priority list. If a higher-priority model recovers from standby, traffic is immediately routed back to it. This strategy is ideal when you have a preferred model (e.g., highest quality or best cost) and want to use alternatives only as fallbacks.

---

## Supported Interfaces

| Interface | Supported | Notes |
| --- | --- | --- |
| Deactivation | Yes | Standard deactivation triggers |
| Recovery | Yes | Standard recovery triggers |
| Selection | Yes | Always picks the highest-priority active model |

## Behavior

Priority selection evaluates the configured priority list on every request and selects the first model that is currently in the `active` state. Unlike stick-until-failure, this strategy eagerly returns to higher-priority models as soon as they recover.

**Selection logic:**

1. Iterate through `model_priority` in order (index 0 = highest priority).
2. If a model in the list is active, select it.
3. If no model in `model_priority` is active, fall back to `provider_priority` ordering.
4. If neither list yields an active model, apply `fallback_strategy` (`round-robin` or `error`).

**Example:**

Given `model_priority: [gpt-4o, claude-sonnet-4-20250514, gemini-2.5-pro]`:

- Normal operation: all requests go to gpt-4o.
- gpt-4o is deactivated (rate limit hit): requests shift to claude-sonnet-4-20250514.
- gpt-4o recovers (cooldown expires): requests immediately return to gpt-4o.
- Both gpt-4o and claude-sonnet-4-20250514 are down: requests go to gemini-2.5-pro.
- All models in the priority list are down: `fallback_strategy` is invoked.

## Configuration

See [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.html#rotation-policy) for the full list of common rotation parameters including deactivation thresholds, recovery cooldowns, and probe settings.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `rotation.selection.model_priority` | list | `[]` | Ordered list of model names. Index 0 is highest priority. |
| `rotation.selection.provider_priority` | list | `[]` | Ordered list of provider IDs. Used when no model in `model_priority` is active. |
| `rotation.selection.fallback_strategy` | string | `"round-robin"` | Strategy when all priority models are exhausted: `round-robin` or `error`. |

## YAML Example

```yaml
pools:
  text-generation:
    rotation:
      policy: modelmesh.priority-selection.v1
      selection:
        model_priority:
          - gpt-4o
          - claude-sonnet-4-20250514
          - gemini-2.5-pro
        provider_priority:
          - openai.llm.v1
          - anthropic.llm.v1
          - google.gemini.v1
        fallback_strategy: round-robin
      deactivation:
        retry_limit: 3
        error_codes: [429, 500, 502, 503]
      recovery:
        cooldown: 30s
        probe_interval: 120s
```
