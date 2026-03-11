---
layout: default
title: "StateFilter"
---

# StateFilter

Pipeline stage that excludes standby models and models from deactivated providers. Ensures only healthy, active models reach the selection stage of the routing pipeline.

**Depends on:** [Model](Model.md), [ModelState](ModelState.md), [ProviderState](ProviderState.md).

---

## Python

```python
from __future__ import annotations


class StateFilter:
    """Pipeline stage that excludes standby and unhealthy models."""

    def filter(self, candidates: list[Model]) -> list[Model]:
        """Return only candidates with active status and available providers.

        Excludes models where:
        - ModelState.status is 'standby'
        - The model's provider is not available (ProviderState.available is
          False or ProviderState.auth_valid is False)

        Args:
            candidates: List of candidate models from the pool.

        Returns:
            Filtered list containing only active models from available
            providers.
        """
        ...
```

---

## TypeScript

```typescript
class StateFilter {
  /** Return only candidates with active status and available providers.
   *
   *  Excludes models where:
   *  - ModelState.status is 'standby'
   *  - The model's provider is not available
   */
  filter(candidates: Model[]): Model[];
}
```
