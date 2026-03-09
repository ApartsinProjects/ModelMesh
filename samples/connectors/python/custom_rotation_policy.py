"""
Custom Rotation Policy Connector -- Time-of-Day Routing

Demonstrates how to implement a custom rotation policy for ModelMesh Lite
that routes requests to cheaper models during off-peak hours and premium
models during business hours.

This is useful for organizations that want to minimize costs during nights
and weekends while ensuring high-quality responses during core working hours.

See: docs/interfaces/RotationPolicy.md
"""
# For a simpler CDK-based approach, see samples/cdk/python/

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Supporting types (from RotationPolicy interface)
# ---------------------------------------------------------------------------

class ModelStatus(Enum):
    """Lifecycle status of a model within a pool."""
    ACTIVE = "active"
    STANDBY = "standby"


class DeactivationReason(Enum):
    """Reason a model was moved from active to standby."""
    ERROR_THRESHOLD = "error_threshold"
    QUOTA_EXHAUSTED = "quota_exhausted"
    BUDGET_EXCEEDED = "budget_exceeded"
    TOKEN_LIMIT = "token_limit"
    REQUEST_LIMIT = "request_limit"
    MAINTENANCE_WINDOW = "maintenance_window"
    MANUAL = "manual"


class RecoveryTrigger(Enum):
    """Trigger that caused a standby model to return to active."""
    COOLDOWN_EXPIRED = "cooldown_expired"
    QUOTA_RESET = "quota_reset"
    PROBE_SUCCESS = "probe_success"
    MANUAL = "manual"
    STARTUP_PROBE = "startup_probe"


@dataclass
class ModelSnapshot:
    """Point-in-time snapshot of a model's operational state."""
    model_id: str
    provider_id: str
    status: ModelStatus
    failure_count: int
    error_rate: float
    cooldown_remaining: Optional[float] = None
    quota_used: int = 0
    tokens_used: int = 0
    cost_accumulated: float = 0.0
    latency_avg: Optional[float] = None
    last_request: Optional[datetime] = None
    last_failure: Optional[datetime] = None


@dataclass
class SelectionResult:
    """Result of the selection strategy choosing a model for a request."""
    model_id: str
    provider_id: str
    score: float
    reason: str


# ---------------------------------------------------------------------------
# CompletionRequest reference (from Provider interface)
# ---------------------------------------------------------------------------

@dataclass
class CompletionRequest:
    """Normalized request sent to a provider for completion."""
    model: str
    messages: list[dict]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[list[dict]] = None
    stream: bool = False


# ---------------------------------------------------------------------------
# Interface ABCs (from RotationPolicy interface)
# ---------------------------------------------------------------------------

class DeactivationPolicy(ABC):
    @abstractmethod
    def should_deactivate(self, snapshot: ModelSnapshot) -> bool: ...

    @abstractmethod
    def get_reason(self, snapshot: ModelSnapshot) -> DeactivationReason | None: ...


class RecoveryPolicy(ABC):
    @abstractmethod
    def should_recover(self, snapshot: ModelSnapshot) -> bool: ...

    @abstractmethod
    def get_recovery_schedule(self, snapshot: ModelSnapshot) -> datetime | None: ...


class SelectionStrategy(ABC):
    @abstractmethod
    def select(
        self, candidates: list[ModelSnapshot], request: CompletionRequest
    ) -> SelectionResult: ...

    @abstractmethod
    def score(
        self, candidate: ModelSnapshot, request: CompletionRequest
    ) -> float: ...


# ---------------------------------------------------------------------------
# Time-of-day configuration
# ---------------------------------------------------------------------------

@dataclass
class TimeWindow:
    """A named time window with start/end hours (24h format, UTC).

    If start_hour > end_hour, the window wraps around midnight
    (e.g., 22:00 to 06:00).
    """
    name: str
    start_hour: int  # 0-23, inclusive
    end_hour: int  # 0-23, exclusive
    days_of_week: list[int]  # 0=Sunday, 6=Saturday

    def contains(self, hour: int, day_of_week: int) -> bool:
        """Return True if the given hour and day fall within this window."""
        if day_of_week not in self.days_of_week:
            return False

        if self.start_hour < self.end_hour:
            # Normal window: e.g., 09:00 to 17:00
            return self.start_hour <= hour < self.end_hour
        elif self.start_hour > self.end_hour:
            # Wraps midnight: e.g., 22:00 to 06:00
            return hour >= self.start_hour or hour < self.end_hour
        else:
            # start_hour == end_hour means the window covers the full day.
            return True


class ModelTierEnum(Enum):
    """Classification of a model into a cost tier.

    Premium models are preferred during business hours; economy models
    are preferred off-peak. Standard models are always available.
    """
    PREMIUM = "premium"
    STANDARD = "standard"
    ECONOMY = "economy"


@dataclass
class ModelTierMapping:
    """Maps a model ID pattern to a tier.

    Patterns support simple glob matching: "*" matches any sequence of
    characters (e.g. "gpt-4*" matches "gpt-4o" and "gpt-4-turbo").
    """
    pattern: str
    tier: ModelTierEnum
    cost_weight: float  # Base cost weight (higher = more expensive)


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------

@dataclass
class TimeOfDayPolicyConfig:
    """Full configuration for the time-of-day rotation policy."""
    timezone: str  # IANA timezone (e.g. "America/New_York")
    business_hours: TimeWindow
    off_peak_hours: TimeWindow
    tier_mappings: list[ModelTierMapping]
    error_rate_threshold: float = 0.5
    max_consecutive_failures: int = 5
    latency_weight: float = 0.2  # Must sum to 1.0 with cost_weight and error_weight
    cost_weight: float = 0.6
    error_weight: float = 0.2


def _glob_match(pattern: str, text: str) -> bool:
    """Simple glob matching: '*' matches any sequence of characters."""
    import re
    regex_str = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return bool(re.match(regex_str, text))


class TimeOfDayRotationPolicy(DeactivationPolicy, RecoveryPolicy, SelectionStrategy):
    """Combined rotation policy implementing all three sub-interfaces.

    Routes requests to cheaper models during off-peak hours and premium
    models during business hours. Implements deactivation, recovery, and
    selection based on time-of-day cost/quality weighting.

    Configuration example (YAML):

        pools:
          chat-pool:
            rotation:
              policy: custom
              policy_class: TimeOfDayRotationPolicy
              config:
                timezone: "America/New_York"
                business_hours:
                  name: business_hours
                  start_hour: 9
                  end_hour: 17
                  days_of_week: [1, 2, 3, 4, 5]   # Monday-Friday
                off_peak_hours:
                  name: off_peak
                  start_hour: 17
                  end_hour: 9
                  days_of_week: [0, 1, 2, 3, 4, 5, 6]  # All days
                tier_mappings:
                  - pattern: "gpt-4*"
                    tier: premium
                    cost_weight: 10.0
                  - pattern: "gpt-3.5*"
                    tier: standard
                    cost_weight: 3.0
                  - pattern: "meta-llama/*70B*"
                    tier: premium
                    cost_weight: 8.0
                  - pattern: "meta-llama/*7B*"
                    tier: economy
                    cost_weight: 1.0
                  - pattern: "mistralai/Mistral-7B*"
                    tier: economy
                    cost_weight: 1.0
                error_rate_threshold: 0.5
                max_consecutive_failures: 5
                latency_weight: 0.2
                cost_weight: 0.6
                error_weight: 0.2
    """

    def __init__(self, config: TimeOfDayPolicyConfig) -> None:
        self._config = config

        # Validate that scoring weights sum to 1.0 (within floating-point tolerance).
        total_weight = config.latency_weight + config.cost_weight + config.error_weight
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(
                f"Scoring weights must sum to 1.0, got {total_weight:.3f}"
            )

    # ------------------------------------------------------------------
    # DeactivationPolicy
    # ------------------------------------------------------------------

    def should_deactivate(self, snapshot: ModelSnapshot) -> bool:
        """Evaluate whether the model should be moved to standby.

        A model is deactivated when:
          1. Its error rate exceeds the threshold (always, regardless of time).
          2. It has too many consecutive failures (always).
          3. It is a PREMIUM model and we are currently in off-peak hours.
        """
        return self.get_reason(snapshot) is not None

    def get_reason(self, snapshot: ModelSnapshot) -> DeactivationReason | None:
        """Determine the deactivation reason, if any."""
        # Always deactivate on high error rates.
        if snapshot.error_rate >= self._config.error_rate_threshold:
            return DeactivationReason.ERROR_THRESHOLD

        # Always deactivate after too many consecutive failures.
        if snapshot.failure_count >= self._config.max_consecutive_failures:
            return DeactivationReason.ERROR_THRESHOLD

        # Time-based deactivation.
        tier = self._get_model_tier(snapshot.model_id)
        hour, day_of_week = self._current_time_in_timezone()

        if (
            tier == ModelTierEnum.PREMIUM
            and self._config.off_peak_hours.contains(hour, day_of_week)
        ):
            # Premium models should be deactivated during off-peak to save cost.
            return DeactivationReason.MAINTENANCE_WINDOW

        return None

    # ------------------------------------------------------------------
    # RecoveryPolicy
    # ------------------------------------------------------------------

    def should_recover(self, snapshot: ModelSnapshot) -> bool:
        """Determine whether a standby model should be reactivated.

        A model should recover when:
          1. It was deactivated due to errors and the cooldown has expired.
          2. It is a PREMIUM model and business hours have started.
          3. It is an ECONOMY model and off-peak hours have started.
          4. It is a STANDARD model whenever cooldown expires.
        """
        # If still cooling down from error-based deactivation, do not recover.
        if snapshot.cooldown_remaining and snapshot.cooldown_remaining > 0:
            return False

        # If the model still has a high error rate, do not recover yet.
        if snapshot.error_rate >= self._config.error_rate_threshold:
            return False

        tier = self._get_model_tier(snapshot.model_id)
        hour, day_of_week = self._current_time_in_timezone()

        # Premium models recover at the start of business hours.
        if (
            tier == ModelTierEnum.PREMIUM
            and self._config.business_hours.contains(hour, day_of_week)
        ):
            return True

        # Economy models recover at the start of off-peak hours.
        if (
            tier == ModelTierEnum.ECONOMY
            and self._config.off_peak_hours.contains(hour, day_of_week)
        ):
            return True

        # Standard models recover whenever their cooldown expires.
        if tier == ModelTierEnum.STANDARD:
            return True

        # Models deactivated for errors can recover once cooldown expires.
        if snapshot.failure_count > 0 and (snapshot.cooldown_remaining or 0) <= 0:
            return True

        return False

    def get_recovery_schedule(self, snapshot: ModelSnapshot) -> datetime | None:
        """Return the next scheduled recovery check time."""
        now = datetime.now(timezone.utc)

        # If the model has a remaining cooldown, schedule after it expires.
        if snapshot.cooldown_remaining and snapshot.cooldown_remaining > 0:
            return now + timedelta(seconds=snapshot.cooldown_remaining)

        tier = self._get_model_tier(snapshot.model_id)
        hour, day_of_week = self._current_time_in_timezone()

        # Premium model outside business hours: schedule for next business start.
        if (
            tier == ModelTierEnum.PREMIUM
            and not self._config.business_hours.contains(hour, day_of_week)
        ):
            return self._next_window_start(self._config.business_hours)

        # Economy model outside off-peak hours: schedule for next off-peak start.
        if (
            tier == ModelTierEnum.ECONOMY
            and not self._config.off_peak_hours.contains(hour, day_of_week)
        ):
            return self._next_window_start(self._config.off_peak_hours)

        # Standard models and already-in-window models: check in 60 seconds.
        return now + timedelta(seconds=60)

    # ------------------------------------------------------------------
    # SelectionStrategy
    # ------------------------------------------------------------------

    def select(
        self, candidates: list[ModelSnapshot], request: CompletionRequest
    ) -> SelectionResult:
        """Select the best model from the active candidate list.

        Scores each candidate considering time-of-day cost preferences,
        current latency, and error rate, then returns the highest-scoring model.
        """
        if not candidates:
            raise ValueError("No active candidates available for selection")

        best_candidate = candidates[0]
        best_score = float("-inf")

        for candidate in candidates:
            candidate_score = self.score(candidate, request)
            if candidate_score > best_score:
                best_score = candidate_score
                best_candidate = candidate

        tier = self._get_model_tier(best_candidate.model_id)
        hour, day_of_week = self._current_time_in_timezone()
        window_name = (
            "business_hours"
            if self._config.business_hours.contains(hour, day_of_week)
            else "off_peak"
        )

        return SelectionResult(
            model_id=best_candidate.model_id,
            provider_id=best_candidate.provider_id,
            score=best_score,
            reason=f"Selected {tier.value} model for {window_name} (score: {best_score:.3f})",
        )

    def score(
        self, candidate: ModelSnapshot, request: CompletionRequest
    ) -> float:
        """Score a single candidate for the given request.

        The score is a weighted combination of three factors:
          - Cost score: how well the model's cost tier matches the current time window
          - Latency score: inverse of average latency (lower latency = higher score)
          - Error score: inverse of error rate (lower error rate = higher score)

        During business hours, premium models get a cost boost.
        During off-peak hours, economy models get a cost boost.
        Standard models receive a neutral cost score at all times.
        """
        tier = self._get_model_tier(candidate.model_id)
        hour, day_of_week = self._current_time_in_timezone()
        is_business = self._config.business_hours.contains(hour, day_of_week)

        # --- Cost score (0.0 to 1.0) ---
        # During business hours: premium=1.0, standard=0.6, economy=0.3
        # During off-peak:       economy=1.0, standard=0.6, premium=0.2
        if is_business:
            cost_score = {
                ModelTierEnum.PREMIUM: 1.0,
                ModelTierEnum.STANDARD: 0.6,
                ModelTierEnum.ECONOMY: 0.3,
            }.get(tier, 0.5)
        else:
            cost_score = {
                ModelTierEnum.ECONOMY: 1.0,
                ModelTierEnum.STANDARD: 0.6,
                ModelTierEnum.PREMIUM: 0.2,
            }.get(tier, 0.5)

        # --- Latency score (0.0 to 1.0) ---
        # Map latency from [0ms, 10000ms] to [1.0, 0.0].
        max_latency = 10_000  # 10 seconds as the worst-case benchmark
        avg_latency = candidate.latency_avg if candidate.latency_avg is not None else 500
        latency_score = max(0.0, 1.0 - avg_latency / max_latency)

        # --- Error score (0.0 to 1.0) ---
        # Lower error rate is better.
        error_score = 1.0 - min(candidate.error_rate, 1.0)

        # --- Weighted combination ---
        total_score = (
            cost_score * self._config.cost_weight
            + latency_score * self._config.latency_weight
            + error_score * self._config.error_weight
        )

        return total_score

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_model_tier(self, model_id: str) -> ModelTierEnum:
        """Determine the tier of a model based on configured pattern mappings."""
        for mapping in self._config.tier_mappings:
            if _glob_match(mapping.pattern, model_id):
                return mapping.tier
        return ModelTierEnum.STANDARD

    def _current_time_in_timezone(self) -> tuple[int, int]:
        """Get the current hour (0-23) and day of week (0=Sunday) in the configured timezone.

        Returns:
            Tuple of (hour, day_of_week).
        """
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(self._config.timezone))
        except ImportError:
            # Fallback to UTC if zoneinfo is not available.
            now = datetime.now(timezone.utc)

        # Python's weekday(): Monday=0, Sunday=6
        # We need Sunday=0, Saturday=6 (matching JavaScript convention).
        py_weekday = now.weekday()
        js_weekday = (py_weekday + 1) % 7

        return now.hour, js_weekday

    def _next_window_start(self, window: TimeWindow) -> datetime:
        """Compute the next occurrence of a time window's start hour."""
        now = datetime.now(timezone.utc)

        # Look ahead up to 7 days.
        for day_offset in range(8):
            candidate = now + timedelta(days=day_offset)
            hour, day_of_week = self._current_time_in_timezone()

            if day_of_week not in window.days_of_week:
                continue

            # If we are on the same day and the window start is already past, skip.
            if day_offset == 0 and hour >= window.start_hour:
                continue

            hours_until_start = day_offset * 24 + (window.start_hour - hour)
            return now + timedelta(hours=hours_until_start)

        # Fallback: try again in one hour.
        return now + timedelta(hours=1)


# ---------------------------------------------------------------------------
# Usage example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Define tier mappings using glob patterns (matching TypeScript approach).
    tier_mappings = [
        ModelTierMapping(pattern="gpt-4*", tier=ModelTierEnum.PREMIUM, cost_weight=10.0),
        ModelTierMapping(pattern="gpt-3.5*", tier=ModelTierEnum.STANDARD, cost_weight=3.0),
        ModelTierMapping(pattern="*-mini", tier=ModelTierEnum.ECONOMY, cost_weight=1.0),
        ModelTierMapping(pattern="claude-sonnet*", tier=ModelTierEnum.PREMIUM, cost_weight=8.0),
        ModelTierMapping(pattern="llama-3.1-70b", tier=ModelTierEnum.ECONOMY, cost_weight=2.0),
    ]

    # Define time windows.
    business_hours = TimeWindow(
        name="business_hours",
        start_hour=9,
        end_hour=17,
        days_of_week=[1, 2, 3, 4, 5],  # Monday-Friday
    )
    off_peak_hours = TimeWindow(
        name="off_peak",
        start_hour=17,
        end_hour=9,
        days_of_week=[0, 1, 2, 3, 4, 5, 6],  # All days
    )

    # Create the combined rotation policy with US Eastern timezone.
    config = TimeOfDayPolicyConfig(
        timezone="America/New_York",
        business_hours=business_hours,
        off_peak_hours=off_peak_hours,
        tier_mappings=tier_mappings,
        error_rate_threshold=0.5,
        max_consecutive_failures=5,
        latency_weight=0.2,
        cost_weight=0.6,
        error_weight=0.2,
    )
    policy = TimeOfDayRotationPolicy(config)

    # Simulate model snapshots.
    snapshots = [
        ModelSnapshot(
            model_id="gpt-4o",
            provider_id="openai",
            status=ModelStatus.ACTIVE,
            failure_count=0,
            error_rate=0.01,
            latency_avg=800.0,
            cost_accumulated=25.50,
        ),
        ModelSnapshot(
            model_id="gpt-4o-mini",
            provider_id="openai",
            status=ModelStatus.ACTIVE,
            failure_count=0,
            error_rate=0.02,
            latency_avg=400.0,
            cost_accumulated=3.20,
        ),
        ModelSnapshot(
            model_id="claude-sonnet",
            provider_id="anthropic",
            status=ModelStatus.ACTIVE,
            failure_count=1,
            error_rate=0.05,
            latency_avg=1200.0,
            cost_accumulated=18.00,
        ),
        ModelSnapshot(
            model_id="llama-3.1-70b",
            provider_id="vllm-internal",
            status=ModelStatus.ACTIVE,
            failure_count=0,
            error_rate=0.0,
            latency_avg=600.0,
            cost_accumulated=1.50,
        ),
    ]

    hour, day_of_week = policy._current_time_in_timezone()
    print(f"Current hour: {hour}, day of week: {day_of_week}")
    print(f"Is business hours: {business_hours.contains(hour, day_of_week)}")
    print()

    # Evaluate deactivation for each model.
    print("=== Deactivation Evaluation ===")
    for snap in snapshots:
        should = policy.should_deactivate(snap)
        reason = policy.get_reason(snap)
        print(f"  {snap.model_id}: deactivate={should}, reason={reason}")

    print()

    # Select the best model for a request.
    print("=== Selection ===")
    request = CompletionRequest(
        model="auto",
        messages=[{"role": "user", "content": "Hello!"}],
    )

    result = policy.select(snapshots, request)
    print(f"  Selected: {result.model_id} (provider={result.provider_id})")
    print(f"  Score: {result.score:.3f}")
    print(f"  Reason: {result.reason}")

    print()

    # Show individual scores.
    print("=== Individual Scores ===")
    for snap in snapshots:
        s = policy.score(snap, request)
        tier = policy._get_model_tier(snap.model_id)
        print(f"  {snap.model_id} (tier={tier.value}): score={s:.3f}")

    print()

    # Evaluate recovery for a standby model.
    print("=== Recovery Evaluation ===")
    standby_premium = ModelSnapshot(
        model_id="gpt-4o",
        provider_id="openai",
        status=ModelStatus.STANDBY,
        failure_count=0,
        error_rate=0.0,
        cooldown_remaining=0,
    )
    standby_economy = ModelSnapshot(
        model_id="gpt-4o-mini",
        provider_id="openai",
        status=ModelStatus.STANDBY,
        failure_count=0,
        error_rate=0.0,
        cooldown_remaining=0,
    )

    print(f"  gpt-4o (premium): recover={policy.should_recover(standby_premium)}")
    schedule = policy.get_recovery_schedule(standby_premium)
    if schedule:
        print(f"    Next recovery: {schedule.strftime('%Y-%m-%d %H:%M')}")
    else:
        print("    Next recovery: now")

    print(f"  gpt-4o-mini (economy): recover={policy.should_recover(standby_economy)}")
