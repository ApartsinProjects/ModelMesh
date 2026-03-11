/**
 * Custom Rotation Policy Connector — Time-of-Day Routing
 *
 * Demonstrates how to implement a custom rotation policy for ModelMesh Lite
 * that routes requests to cheaper models during off-peak hours and premium
 * models during business hours. This is useful for organizations that want to
 * minimize costs overnight while maintaining quality during working hours.
 *
 * Implements all three required rotation sub-interfaces:
 *   - DeactivationPolicy  : deactivate premium models outside business hours
 *   - RecoveryPolicy      : recover premium models when business hours resume
 *   - SelectionStrategy   : score candidates based on time-of-day cost weighting
 *
 * See: docs/interfaces/RotationPolicy.md
 */
// For a simpler CDK-based approach, see samples/cdk/typescript/

// ---------------------------------------------------------------------------
// Types imported from @nistrapa/modelmesh-core (reproduced here for self-containment)
// ---------------------------------------------------------------------------

/** Lifecycle status of a model within a pool. */
enum ModelStatus {
    ACTIVE = "active",
    STANDBY = "standby",
}

/** Reason a model was moved from active to standby. */
enum DeactivationReason {
    ERROR_THRESHOLD = "error_threshold",
    QUOTA_EXHAUSTED = "quota_exhausted",
    BUDGET_EXCEEDED = "budget_exceeded",
    TOKEN_LIMIT = "token_limit",
    REQUEST_LIMIT = "request_limit",
    MAINTENANCE_WINDOW = "maintenance_window",
    MANUAL = "manual",
}

/** Trigger that caused a standby model to return to active. */
enum RecoveryTrigger {
    COOLDOWN_EXPIRED = "cooldown_expired",
    QUOTA_RESET = "quota_reset",
    PROBE_SUCCESS = "probe_success",
    MANUAL = "manual",
    STARTUP_PROBE = "startup_probe",
}

/** Point-in-time snapshot of a model's operational state. */
interface ModelSnapshot {
    modelId: string;
    providerId: string;
    status: ModelStatus;
    failureCount: number;
    errorRate: number;
    cooldownRemaining?: number;
    quotaUsed: number;
    tokensUsed: number;
    costAccumulated: number;
    latencyAvg?: number;
    lastRequest?: Date;
    lastFailure?: Date;
}

/** Result of the selection strategy choosing a model for a request. */
interface SelectionResult {
    modelId: string;
    providerId: string;
    score: number;
    reason: string;
}

/** Normalized request sent to a provider for completion (from Provider interface). */
interface CompletionRequest {
    model: string;
    messages: Record<string, unknown>[];
    temperature?: number;
    maxTokens?: number;
    tools?: Record<string, unknown>[];
    stream: boolean;
}

// ---------------------------------------------------------------------------
// Rotation sub-interfaces (from docs/interfaces/RotationPolicy.md)
// ---------------------------------------------------------------------------

interface DeactivationPolicy {
    shouldDeactivate(snapshot: ModelSnapshot): boolean;
    getReason(snapshot: ModelSnapshot): DeactivationReason | null;
}

interface RecoveryPolicy {
    shouldRecover(snapshot: ModelSnapshot): boolean;
    getRecoverySchedule(snapshot: ModelSnapshot): Date | null;
}

interface SelectionStrategy {
    select(candidates: ModelSnapshot[], request: CompletionRequest): SelectionResult;
    score(candidate: ModelSnapshot, request: CompletionRequest): number;
}

// ---------------------------------------------------------------------------
// Configuration types
// ---------------------------------------------------------------------------

/** A named time window with start/end hours (24h format, UTC). */
interface TimeWindow {
    /** Descriptive name, e.g. "business_hours" or "off_peak" */
    name: string;
    /** Start hour in UTC (0-23), inclusive */
    startHour: number;
    /** End hour in UTC (0-23), exclusive */
    endHour: number;
    /** Days of week this window applies to (0=Sunday, 6=Saturday) */
    daysOfWeek: number[];
}

/**
 * Classification of a model into a cost tier.
 *
 * Premium models are preferred during business hours; economy models
 * are preferred off-peak. Standard models are always available.
 */
enum ModelTier {
    PREMIUM = "premium",
    STANDARD = "standard",
    ECONOMY = "economy",
}

/** Maps a model ID pattern to a tier. */
interface ModelTierMapping {
    /** Glob-like pattern matching model IDs (e.g. "gpt-4*") */
    pattern: string;
    /** The tier this model belongs to */
    tier: ModelTier;
    /** Base cost weight (higher = more expensive) */
    costWeight: number;
}

/** Full configuration for the time-of-day rotation policy. */
interface TimeOfDayPolicyConfig {
    /** IANA timezone for business-hour calculations, e.g. "America/New_York" */
    timezone: string;
    /** Business hours window definition */
    businessHours: TimeWindow;
    /** Off-peak hours window definition */
    offPeakHours: TimeWindow;
    /** Model-to-tier mappings */
    tierMappings: ModelTierMapping[];
    /** Error rate threshold triggering deactivation regardless of time */
    errorRateThreshold: number;
    /** Maximum consecutive failures before deactivation regardless of time */
    maxConsecutiveFailures: number;
    /** Weight given to latency in scoring (0.0 - 1.0) */
    latencyWeight: number;
    /** Weight given to cost in scoring (0.0 - 1.0) */
    costWeight: number;
    /** Weight given to error rate in scoring (0.0 - 1.0) */
    errorWeight: number;
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

class TimeOfDayRotationPolicy
    implements DeactivationPolicy, RecoveryPolicy, SelectionStrategy
{
    private readonly config: TimeOfDayPolicyConfig;

    constructor(config: TimeOfDayPolicyConfig) {
        this.config = config;

        // Validate that scoring weights sum to 1.0 (within floating-point tolerance).
        const totalWeight =
            config.latencyWeight + config.costWeight + config.errorWeight;
        if (Math.abs(totalWeight - 1.0) > 0.001) {
            throw new Error(
                `Scoring weights must sum to 1.0, got ${totalWeight.toFixed(3)}`,
            );
        }
    }

    // -----------------------------------------------------------------------
    // DeactivationPolicy
    // -----------------------------------------------------------------------

    /**
     * Determine whether a model should be deactivated.
     *
     * A model is deactivated when:
     *   1. Its error rate exceeds the threshold (always, regardless of time).
     *   2. It has too many consecutive failures (always).
     *   3. It is a PREMIUM model and we are currently in off-peak hours.
     *   4. It is an ECONOMY model and we are currently in business hours
     *      AND there are no error/quota concerns driving its use.
     */
    shouldDeactivate(snapshot: ModelSnapshot): boolean {
        // Always deactivate on health issues.
        if (snapshot.errorRate >= this.config.errorRateThreshold) {
            return true;
        }
        if (snapshot.failureCount >= this.config.maxConsecutiveFailures) {
            return true;
        }

        // Time-based deactivation.
        const tier = this.getModelTier(snapshot.modelId);
        const now = this.currentTimeInTimezone();

        if (tier === ModelTier.PREMIUM && this.isInWindow(now, this.config.offPeakHours)) {
            // Premium models should be deactivated during off-peak to save cost.
            return true;
        }

        // Economy models stay active during business hours as fallbacks;
        // they are only deactivated if there is no reason to keep them.
        // This policy keeps economy models available as a safety net.

        return false;
    }

    /**
     * Return the reason for deactivation, or null if the model should stay active.
     *
     * Provides a specific reason that will appear in observability events.
     */
    getReason(snapshot: ModelSnapshot): DeactivationReason | null {
        if (snapshot.errorRate >= this.config.errorRateThreshold) {
            return DeactivationReason.ERROR_THRESHOLD;
        }
        if (snapshot.failureCount >= this.config.maxConsecutiveFailures) {
            return DeactivationReason.ERROR_THRESHOLD;
        }

        const tier = this.getModelTier(snapshot.modelId);
        const now = this.currentTimeInTimezone();

        if (tier === ModelTier.PREMIUM && this.isInWindow(now, this.config.offPeakHours)) {
            // Use MAINTENANCE_WINDOW to signal a scheduled/time-based deactivation.
            return DeactivationReason.MAINTENANCE_WINDOW;
        }

        return null;
    }

    // -----------------------------------------------------------------------
    // RecoveryPolicy
    // -----------------------------------------------------------------------

    /**
     * Determine whether a standby model should be recovered.
     *
     * A model should recover when:
     *   1. It was deactivated due to errors and the cooldown has expired.
     *   2. It is a PREMIUM model and business hours have started.
     *   3. It is an ECONOMY model and off-peak hours have started.
     */
    shouldRecover(snapshot: ModelSnapshot): boolean {
        // If still cooling down from error-based deactivation, do not recover.
        if (
            snapshot.cooldownRemaining !== undefined &&
            snapshot.cooldownRemaining > 0
        ) {
            return false;
        }

        // If the model still has a high error rate, do not recover yet.
        if (snapshot.errorRate >= this.config.errorRateThreshold) {
            return false;
        }

        const tier = this.getModelTier(snapshot.modelId);
        const now = this.currentTimeInTimezone();

        // Premium models recover at the start of business hours.
        if (tier === ModelTier.PREMIUM && this.isInWindow(now, this.config.businessHours)) {
            return true;
        }

        // Economy models recover at the start of off-peak hours.
        if (tier === ModelTier.ECONOMY && this.isInWindow(now, this.config.offPeakHours)) {
            return true;
        }

        // Standard models recover whenever their cooldown expires.
        if (tier === ModelTier.STANDARD) {
            return true;
        }

        // Models deactivated for errors can recover once cooldown expires.
        if (snapshot.failureCount > 0 && (snapshot.cooldownRemaining ?? 0) <= 0) {
            return true;
        }

        return false;
    }

    /**
     * Return the next time recovery should be checked for this model.
     *
     * Aligns recovery checks with the start of the relevant time window
     * so models come online right when they are needed.
     */
    getRecoverySchedule(snapshot: ModelSnapshot): Date | null {
        const tier = this.getModelTier(snapshot.modelId);
        const now = this.currentTimeInTimezone();

        // If the model has a remaining cooldown, schedule recovery after it.
        if (
            snapshot.cooldownRemaining !== undefined &&
            snapshot.cooldownRemaining > 0
        ) {
            return new Date(Date.now() + snapshot.cooldownRemaining * 1000);
        }

        // Premium models: schedule for the next business hours start.
        if (tier === ModelTier.PREMIUM && !this.isInWindow(now, this.config.businessHours)) {
            return this.nextWindowStart(this.config.businessHours);
        }

        // Economy models: schedule for the next off-peak start.
        if (tier === ModelTier.ECONOMY && !this.isInWindow(now, this.config.offPeakHours)) {
            return this.nextWindowStart(this.config.offPeakHours);
        }

        // Standard models and already-in-window models: check in 60 seconds.
        return new Date(Date.now() + 60_000);
    }

    // -----------------------------------------------------------------------
    // SelectionStrategy
    // -----------------------------------------------------------------------

    /**
     * Select the best model from the active candidate list.
     *
     * Scores each candidate considering time-of-day cost preferences,
     * current latency, and error rate, then returns the highest-scoring model.
     */
    select(
        candidates: ModelSnapshot[],
        request: CompletionRequest,
    ): SelectionResult {
        if (candidates.length === 0) {
            throw new Error("No active candidates available for selection");
        }

        let bestCandidate = candidates[0];
        let bestScore = -Infinity;

        for (const candidate of candidates) {
            const candidateScore = this.score(candidate, request);
            if (candidateScore > bestScore) {
                bestScore = candidateScore;
                bestCandidate = candidate;
            }
        }

        const tier = this.getModelTier(bestCandidate.modelId);
        const now = this.currentTimeInTimezone();
        const windowName = this.isInWindow(now, this.config.businessHours)
            ? "business_hours"
            : "off_peak";

        return {
            modelId: bestCandidate.modelId,
            providerId: bestCandidate.providerId,
            score: bestScore,
            reason: `Selected ${tier} model for ${windowName} (score: ${bestScore.toFixed(3)})`,
        };
    }

    /**
     * Score a single candidate for the given request.
     *
     * The score is a weighted combination of three factors:
     *   - Cost score: how well the model's cost tier matches the current time window
     *   - Latency score: inverse of average latency (lower latency = higher score)
     *   - Error score: inverse of error rate (lower error rate = higher score)
     *
     * During business hours, premium models get a cost boost.
     * During off-peak hours, economy models get a cost boost.
     * Standard models receive a neutral cost score at all times.
     */
    score(candidate: ModelSnapshot, request: CompletionRequest): number {
        const tier = this.getModelTier(candidate.modelId);
        const tierMapping = this.getTierMapping(candidate.modelId);
        const now = this.currentTimeInTimezone();
        const isBusinessHours = this.isInWindow(now, this.config.businessHours);

        // --- Cost score (0.0 to 1.0) ---
        // During business hours: premium=1.0, standard=0.6, economy=0.3
        // During off-peak:       economy=1.0, standard=0.6, premium=0.2
        let costScore: number;
        if (isBusinessHours) {
            switch (tier) {
                case ModelTier.PREMIUM:
                    costScore = 1.0;
                    break;
                case ModelTier.STANDARD:
                    costScore = 0.6;
                    break;
                case ModelTier.ECONOMY:
                    costScore = 0.3;
                    break;
            }
        } else {
            switch (tier) {
                case ModelTier.ECONOMY:
                    costScore = 1.0;
                    break;
                case ModelTier.STANDARD:
                    costScore = 0.6;
                    break;
                case ModelTier.PREMIUM:
                    costScore = 0.2;
                    break;
            }
        }

        // --- Latency score (0.0 to 1.0) ---
        // Map latency from [0ms, 10000ms] to [1.0, 0.0].
        const maxLatency = 10_000; // 10 seconds as the worst-case benchmark
        const avgLatency = candidate.latencyAvg ?? 500; // default 500ms
        const latencyScore = Math.max(0, 1.0 - avgLatency / maxLatency);

        // --- Error score (0.0 to 1.0) ---
        // Lower error rate is better.
        const errorScore = 1.0 - Math.min(candidate.errorRate, 1.0);

        // --- Weighted combination ---
        const totalScore =
            costScore * this.config.costWeight +
            latencyScore * this.config.latencyWeight +
            errorScore * this.config.errorWeight;

        return totalScore;
    }

    // -----------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------

    /**
     * Determine the tier of a model based on configured pattern mappings.
     *
     * Patterns support simple glob matching: "*" matches any sequence of
     * characters. If no pattern matches, the model defaults to STANDARD.
     */
    private getModelTier(modelId: string): ModelTier {
        const mapping = this.getTierMapping(modelId);
        return mapping?.tier ?? ModelTier.STANDARD;
    }

    /** Find the tier mapping entry for a model ID. */
    private getTierMapping(modelId: string): ModelTierMapping | undefined {
        return this.config.tierMappings.find((m) =>
            this.globMatch(m.pattern, modelId),
        );
    }

    /**
     * Simple glob matching: "*" matches any sequence of characters.
     *
     * Examples:
     *   globMatch("gpt-4*", "gpt-4o")           => true
     *   globMatch("gpt-4*", "gpt-4-turbo")      => true
     *   globMatch("gpt-4*", "gpt-3.5-turbo")    => false
     *   globMatch("*-mini", "gpt-4o-mini")       => true
     */
    private globMatch(pattern: string, text: string): boolean {
        const regexStr = "^" + pattern.replace(/\*/g, ".*") + "$";
        return new RegExp(regexStr).test(text);
    }

    /**
     * Get the current time components in the configured timezone.
     *
     * Returns a simple object with hour (0-23) and dayOfWeek (0=Sunday).
     */
    private currentTimeInTimezone(): { hour: number; dayOfWeek: number } {
        const now = new Date();

        // Use Intl.DateTimeFormat to get time in the target timezone.
        const formatter = new Intl.DateTimeFormat("en-US", {
            timeZone: this.config.timezone,
            hour: "numeric",
            hour12: false,
            weekday: "short",
        });

        const parts = formatter.formatToParts(now);
        const hourPart = parts.find((p) => p.type === "hour");
        const hour = parseInt(hourPart?.value ?? "0", 10);

        // Get day of week in the target timezone.
        const dayFormatter = new Intl.DateTimeFormat("en-US", {
            timeZone: this.config.timezone,
            weekday: "narrow",
        });
        const dayStr = dayFormatter.format(now);
        const dayMap: Record<string, number> = {
            S: 0,
            M: 1,
            T: 2,
            W: 3,
            F: 5,
        };
        // "T" is ambiguous (Tuesday or Thursday). Use the full name instead.
        const fullDayFormatter = new Intl.DateTimeFormat("en-US", {
            timeZone: this.config.timezone,
            weekday: "long",
        });
        const fullDay = fullDayFormatter.format(now);
        const fullDayMap: Record<string, number> = {
            Sunday: 0,
            Monday: 1,
            Tuesday: 2,
            Wednesday: 3,
            Thursday: 4,
            Friday: 5,
            Saturday: 6,
        };
        const dayOfWeek = fullDayMap[fullDay] ?? 0;

        return { hour, dayOfWeek };
    }

    /**
     * Check whether the current time falls within a time window.
     *
     * Handles windows that cross midnight (e.g., 22:00 - 06:00) by
     * checking both ranges.
     */
    private isInWindow(
        time: { hour: number; dayOfWeek: number },
        window: TimeWindow,
    ): boolean {
        // Check day of week first.
        if (!window.daysOfWeek.includes(time.dayOfWeek)) {
            return false;
        }

        // Handle same-day windows (e.g., 09:00 - 17:00).
        if (window.startHour < window.endHour) {
            return time.hour >= window.startHour && time.hour < window.endHour;
        }

        // Handle cross-midnight windows (e.g., 22:00 - 06:00).
        if (window.startHour > window.endHour) {
            return time.hour >= window.startHour || time.hour < window.endHour;
        }

        // startHour === endHour means the window covers the full day.
        return true;
    }

    /**
     * Compute the next occurrence of a time window's start hour.
     *
     * Iterates forward day-by-day from now until it finds a matching
     * day of week, then returns a Date set to that day's start hour.
     */
    private nextWindowStart(window: TimeWindow): Date {
        const now = new Date();

        // Start from the current day and look ahead up to 7 days.
        for (let dayOffset = 0; dayOffset <= 7; dayOffset++) {
            const candidate = new Date(now.getTime() + dayOffset * 86_400_000);

            // Get day of week in the configured timezone.
            const fullDayFormatter = new Intl.DateTimeFormat("en-US", {
                timeZone: this.config.timezone,
                weekday: "long",
            });
            const fullDay = fullDayFormatter.format(candidate);
            const fullDayMap: Record<string, number> = {
                Sunday: 0, Monday: 1, Tuesday: 2, Wednesday: 3,
                Thursday: 4, Friday: 5, Saturday: 6,
            };
            const candidateDow = fullDayMap[fullDay] ?? 0;

            if (!window.daysOfWeek.includes(candidateDow)) {
                continue;
            }

            // Build a Date at the window start hour in the configured timezone.
            // We approximate by setting the UTC date and adjusting for offset.
            const hourFormatter = new Intl.DateTimeFormat("en-US", {
                timeZone: this.config.timezone,
                hour: "numeric",
                hour12: false,
            });
            const currentHourParts = hourFormatter.formatToParts(candidate);
            const currentHour = parseInt(
                currentHourParts.find((p) => p.type === "hour")?.value ?? "0",
                10,
            );

            // If we are on the same day and the window start is already past, skip.
            if (dayOffset === 0 && currentHour >= window.startHour) {
                continue;
            }

            // Return an approximate time. In production, use a proper tz library.
            const hoursUntilStart =
                dayOffset * 24 + (window.startHour - currentHour);
            return new Date(now.getTime() + hoursUntilStart * 3_600_000);
        }

        // Fallback: try again in one hour.
        return new Date(now.getTime() + 3_600_000);
    }
}

// ---------------------------------------------------------------------------
// YAML configuration example
// ---------------------------------------------------------------------------

/*
# modelmesh.yaml — rotation policy section for time-of-day routing
#
# pools:
#   chat-pool:
#     rotation:
#       policy: custom
#       policy_class: TimeOfDayRotationPolicy
#       config:
#         timezone: "America/New_York"
#         business_hours:
#           name: business_hours
#           start_hour: 9
#           end_hour: 17
#           days_of_week: [1, 2, 3, 4, 5]   # Monday-Friday
#         off_peak_hours:
#           name: off_peak
#           start_hour: 17
#           end_hour: 9
#           days_of_week: [0, 1, 2, 3, 4, 5, 6]  # All days
#         tier_mappings:
#           - pattern: "gpt-4*"
#             tier: premium
#             cost_weight: 10.0
#           - pattern: "gpt-3.5*"
#             tier: standard
#             cost_weight: 3.0
#           - pattern: "meta-llama/*70B*"
#             tier: premium
#             cost_weight: 8.0
#           - pattern: "meta-llama/*7B*"
#             tier: economy
#             cost_weight: 1.0
#           - pattern: "mistralai/Mistral-7B*"
#             tier: economy
#             cost_weight: 1.0
#         error_rate_threshold: 0.5
#         max_consecutive_failures: 5
#         latency_weight: 0.2
#         cost_weight: 0.6
#         error_weight: 0.2
*/

export { TimeOfDayRotationPolicy, ModelTier };
export type {
    TimeOfDayPolicyConfig,
    TimeWindow,
    ModelTierMapping,
    DeactivationPolicy,
    RecoveryPolicy,
    SelectionStrategy,
    ModelSnapshot,
    SelectionResult,
};
