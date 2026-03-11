"""Circuit breaker mixin for provider connectors.

Implements the circuit breaker pattern to prevent cascading failures.
When a provider's error rate exceeds the threshold, the circuit opens
and requests fail fast without calling the provider. After a reset
timeout, a single probe request is allowed through; if it succeeds the
circuit closes, otherwise it re-opens.

States::

    CLOSED  ──failure threshold──▶  OPEN
    OPEN    ──reset timeout──────▶  HALF_OPEN
    HALF_OPEN ──success──────────▶  CLOSED
    HALF_OPEN ──failure──────────▶  OPEN

Usage::

    class MyProvider(CircuitBreakerMixin, ProviderConnector):
        def __init__(self):
            super().__init__()
            self.configure_circuit_breaker(
                failure_threshold=5,
                reset_timeout=60.0,
                half_open_max=1,
            )

        async def complete(self, request):
            self.check_circuit()  # raises CircuitOpenError if open
            try:
                result = await self._do_complete(request)
                self.record_success()
                return result
            except Exception as exc:
                self.record_failure()
                raise
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

__all__ = [
    "CircuitBreakerMixin",
    "CircuitState",
    "CircuitOpenError",
    "CircuitBreakerConfig",
]


class CircuitState(Enum):
    """Current state of the circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a request is rejected because the circuit is open.

    Attributes:
        remaining: Seconds until the circuit transitions to half-open.
    """

    def __init__(self, remaining: float) -> None:
        self.remaining = remaining
        super().__init__(
            f"Circuit breaker is open. Retry in {remaining:.1f}s"
        )


@dataclass
class CircuitBreakerConfig:
    """Configuration for the circuit breaker.

    Attributes:
        failure_threshold: Number of failures to trip the circuit.
        reset_timeout: Seconds to wait before transitioning OPEN → HALF_OPEN.
        half_open_max: Max probe requests allowed in HALF_OPEN state.
        success_threshold: Successes in HALF_OPEN needed to close the circuit.
    """

    failure_threshold: int = 5
    reset_timeout: float = 60.0
    half_open_max: int = 1
    success_threshold: int = 1


class CircuitBreakerMixin:
    """Mixin providing circuit breaker protection for provider connectors.

    Thread-safe: all state mutations are guarded by a lock.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cb_config = CircuitBreakerConfig()
        self._cb_state = CircuitState.CLOSED
        self._cb_failure_count: int = 0
        self._cb_success_count: int = 0
        self._cb_last_failure_at: float = 0.0
        self._cb_half_open_count: int = 0
        self._cb_lock = threading.Lock()

    def configure_circuit_breaker(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max: int = 1,
        success_threshold: int = 1,
    ) -> None:
        """Configure the circuit breaker parameters."""
        self._cb_config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
            half_open_max=half_open_max,
            success_threshold=success_threshold,
        )

    @property
    def circuit_state(self) -> CircuitState:
        """Current circuit breaker state (may auto-transition)."""
        with self._cb_lock:
            self._maybe_transition()
            return self._cb_state

    def check_circuit(self) -> None:
        """Check whether a request is allowed. Raises CircuitOpenError if not."""
        with self._cb_lock:
            self._maybe_transition()

            if self._cb_state == CircuitState.CLOSED:
                return

            if self._cb_state == CircuitState.HALF_OPEN:
                if self._cb_half_open_count < self._cb_config.half_open_max:
                    self._cb_half_open_count += 1
                    return
                remaining = self._cb_config.reset_timeout
                raise CircuitOpenError(remaining)

            # OPEN
            elapsed = time.monotonic() - self._cb_last_failure_at
            remaining = max(0.0, self._cb_config.reset_timeout - elapsed)
            raise CircuitOpenError(remaining)

    def record_success(self) -> None:
        """Record a successful request."""
        with self._cb_lock:
            if self._cb_state == CircuitState.HALF_OPEN:
                self._cb_success_count += 1
                if self._cb_success_count >= self._cb_config.success_threshold:
                    self._cb_state = CircuitState.CLOSED
                    self._cb_failure_count = 0
                    self._cb_success_count = 0
                    self._cb_half_open_count = 0
            elif self._cb_state == CircuitState.CLOSED:
                # Reset consecutive failure count on success
                self._cb_failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        with self._cb_lock:
            self._cb_last_failure_at = time.monotonic()

            if self._cb_state == CircuitState.HALF_OPEN:
                # Probe failed — re-open
                self._cb_state = CircuitState.OPEN
                self._cb_half_open_count = 0
                self._cb_success_count = 0
                return

            self._cb_failure_count += 1
            if self._cb_failure_count >= self._cb_config.failure_threshold:
                self._cb_state = CircuitState.OPEN

    def reset_circuit(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._cb_lock:
            self._cb_state = CircuitState.CLOSED
            self._cb_failure_count = 0
            self._cb_success_count = 0
            self._cb_half_open_count = 0

    def circuit_breaker_stats(self) -> dict:
        """Return current circuit breaker statistics."""
        with self._cb_lock:
            self._maybe_transition()
            return {
                "state": self._cb_state.value,
                "failure_count": self._cb_failure_count,
                "success_count": self._cb_success_count,
                "last_failure_at": self._cb_last_failure_at,
                "config": {
                    "failure_threshold": self._cb_config.failure_threshold,
                    "reset_timeout": self._cb_config.reset_timeout,
                    "half_open_max": self._cb_config.half_open_max,
                    "success_threshold": self._cb_config.success_threshold,
                },
            }

    def _maybe_transition(self) -> None:
        """Auto-transition OPEN → HALF_OPEN if timeout has elapsed.

        Must be called while holding ``_cb_lock``.
        """
        if self._cb_state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._cb_last_failure_at
            if elapsed >= self._cb_config.reset_timeout:
                self._cb_state = CircuitState.HALF_OPEN
                self._cb_half_open_count = 0
                self._cb_success_count = 0
