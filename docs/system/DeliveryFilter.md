---
layout: default
title: "DeliveryFilter"
---

# DeliveryFilter

Pipeline stage that filters candidate models by the requested delivery mode (synchronous, streaming, or batch). Models that do not support the requested mode are excluded from the candidate list before selection.

**Depends on:** [Model](Model.md).

---

## Python

```python
from __future__ import annotations

from enum import Enum


class DeliveryMode(Enum):
    """Supported delivery modes for completion requests."""

    SYNCHRONOUS = "sync"
    """Standard request-response completion."""

    STREAMING = "streaming"
    """Server-sent events or chunked transfer encoding."""

    BATCH = "batch"
    """Asynchronous batch processing."""


class DeliveryFilter:
    """Pipeline stage that filters candidates by delivery mode."""

    def filter(
        self,
        candidates: list[Model],
        delivery_mode: DeliveryMode,
    ) -> list[Model]:
        """Return only candidates that support the requested delivery mode.

        Args:
            candidates: List of candidate models from the pool.
            delivery_mode: The delivery mode requested by the caller.

        Returns:
            Filtered list containing only models that support the
            requested delivery mode.
        """
        ...
```

---

## TypeScript

```typescript
enum DeliveryMode {
  /** Standard request-response completion. */
  SYNCHRONOUS = "sync",
  /** Server-sent events or chunked transfer encoding. */
  STREAMING = "streaming",
  /** Asynchronous batch processing. */
  BATCH = "batch",
}

class DeliveryFilter {
  /** Return only candidates that support the requested delivery mode. */
  filter(candidates: Model[], deliveryMode: DeliveryMode): Model[];
}
```
