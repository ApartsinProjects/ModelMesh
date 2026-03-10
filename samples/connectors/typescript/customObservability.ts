/**
 * Custom Observability Connector — Slack Webhook + Structured JSON Logging
 *
 * Demonstrates how to implement a custom observability connector for ModelMesh Lite
 * that sends formatted routing events to a Slack channel via webhook and writes
 * structured JSON log entries to rotating log files on disk.
 *
 * Implements all three required observability sub-interfaces:
 *   - Events     : emit routing events to Slack with rich formatting
 *   - Logging    : record request/response data as structured JSON with rotation
 *   - Statistics : aggregate metrics and flush them periodically
 *
 * See: docs/interfaces/Observability.md
 */
// For a simpler CDK-based approach, see samples/cdk/typescript/

import * as fs from "node:fs";
import * as path from "node:path";

// ---------------------------------------------------------------------------
// Types imported from @nistrapa/modelmesh-core (reproduced here for self-containment)
// ---------------------------------------------------------------------------

/** Types of routing events emitted by the library. */
enum EventType {
    MODEL_ACTIVATED = "model_activated",
    MODEL_DEACTIVATED = "model_deactivated",
    MODEL_ROTATED = "model_rotated",
    PROVIDER_HEALTH_CHANGED = "provider_health_changed",
    PROVIDER_DEACTIVATED = "provider_deactivated",
    PROVIDER_RECOVERED = "provider_recovered",
    POOL_MEMBERSHIP_CHANGED = "pool_membership_changed",
    DISCOVERY_MODELS_UPDATED = "discovery_models_updated",
}

/** Detail level for request/response logging. */
enum LogLevel {
    METADATA = "metadata",
    SUMMARY = "summary",
    FULL = "full",
}

/** A routing state-change event. */
interface RoutingEvent {
    event_type: EventType;
    timestamp: Date;
    model_id?: string;
    provider_id?: string;
    pool_id?: string;
    metadata: Record<string, unknown>;
}

/** A single request/response log record. */
interface RequestLogEntry {
    timestamp: Date;
    model_id: string;
    provider_id: string;
    capability: string;
    delivery_mode: string;
    latency_ms: number;
    status_code: number;
    tokens_in: number;
    tokens_out: number;
    cost?: number;
    error?: string;
}

/** Aggregate metrics for a single model, provider, or pool over a time window. */
interface AggregateStats {
    requests_total: number;
    requests_success: number;
    requests_failed: number;
    tokens_in: number;
    tokens_out: number;
    cost_total: number;
    latency_avg: number;
    latency_p95: number;
    downtime_total: number;
    rotation_events: number;
}

// ---------------------------------------------------------------------------
// Observability sub-interfaces (from docs/interfaces/Observability.md)
// ---------------------------------------------------------------------------

interface Events {
    emit(event: RoutingEvent): void;
}

interface Logging {
    log(entry: RequestLogEntry): void;
}

interface Statistics {
    flush(stats: Record<string, AggregateStats>): void;
}

interface ObservabilityConnector extends Events, Logging, Statistics {}

// ---------------------------------------------------------------------------
// Configuration types
// ---------------------------------------------------------------------------

/** Configuration for the Slack + JSON observability connector. */
interface SlackJsonObservabilityConfig {
    /** Slack incoming webhook URL. */
    slackWebhookUrl: string;
    /** Slack channel override (optional; uses webhook default if omitted). */
    slackChannel?: string;
    /** Event types to send to Slack. If omitted, all events are sent. */
    slackEventFilter?: EventType[];
    /** Directory where JSON log files are written. */
    logDirectory: string;
    /** Maximum log file size in bytes before rotation (default: 10MB). */
    maxLogFileSizeBytes?: number;
    /** Maximum number of rotated log files to keep (default: 10). */
    maxLogFiles?: number;
    /** Whether to also send statistics summaries to Slack (default: false). */
    sendStatsToSlack?: boolean;
    /** Minimum latency_ms to trigger a Slack alert for slow requests (default: none). */
    slowRequestThresholdMs?: number;
}

// ---------------------------------------------------------------------------
// Slack message formatting helpers
// ---------------------------------------------------------------------------

/** A Slack Block Kit block for rich message formatting. */
interface SlackBlock {
    type: string;
    text?: { type: string; text: string; emoji?: boolean };
    fields?: Array<{ type: string; text: string }>;
    elements?: Array<{ type: string; text: string }>;
}

/** A Slack webhook message payload. */
interface SlackMessage {
    channel?: string;
    username?: string;
    icon_emoji?: string;
    blocks: SlackBlock[];
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

class SlackJsonObservabilityConnector implements ObservabilityConnector {
    private readonly config: SlackJsonObservabilityConfig;
    private readonly logDir: string;
    private readonly maxFileSize: number;
    private readonly maxFiles: number;

    /** In-memory buffer for statistics that have been flushed to us. */
    private statsHistory: Array<{
        timestamp: Date;
        stats: Record<string, AggregateStats>;
    }> = [];

    /** Current log file path. */
    private currentLogFile: string;
    /** Current log file size in bytes (tracked to avoid repeated stat calls). */
    private currentLogFileSize: number = 0;

    constructor(config: SlackJsonObservabilityConfig) {
        this.config = config;
        this.logDir = path.resolve(config.logDirectory);
        this.maxFileSize = config.maxLogFileSizeBytes ?? 10 * 1024 * 1024; // 10MB
        this.maxFiles = config.maxLogFiles ?? 10;

        // Ensure the log directory exists.
        if (!fs.existsSync(this.logDir)) {
            fs.mkdirSync(this.logDir, { recursive: true });
        }

        // Initialize the current log file.
        this.currentLogFile = this.generateLogFileName();
        this.currentLogFileSize = this.getFileSize(this.currentLogFile);
    }

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    /**
     * Emit a routing event to Slack.
     *
     * Formats the event as a rich Slack message using Block Kit, with
     * color-coded headers based on event severity. Only events matching
     * the configured filter are sent.
     */
    emit(event: RoutingEvent): void {
        // Check event filter.
        if (
            this.config.slackEventFilter &&
            !this.config.slackEventFilter.includes(event.event_type)
        ) {
            return;
        }

        // Also write the event to the JSON log for completeness.
        this.appendToLogFile({
            type: "event",
            event_type: event.event_type,
            timestamp: event.timestamp.toISOString(),
            model_id: event.model_id,
            provider_id: event.provider_id,
            pool_id: event.pool_id,
            metadata: event.metadata,
        });

        // Build and send Slack message.
        const message = this.formatEventForSlack(event);
        this.sendToSlack(message);
    }

    // -----------------------------------------------------------------------
    // Logging
    // -----------------------------------------------------------------------

    /**
     * Record a request/response log entry as structured JSON.
     *
     * Each entry is written as a single JSON line (NDJSON format) to the
     * current log file. When the file exceeds the configured maximum size,
     * it is rotated.
     *
     * If the request latency exceeds the slow request threshold, an
     * additional Slack alert is sent.
     */
    log(entry: RequestLogEntry): void {
        const logRecord: Record<string, unknown> = {
            type: "request",
            timestamp: entry.timestamp.toISOString(),
            model_id: entry.model_id,
            provider_id: entry.provider_id,
            capability: entry.capability,
            delivery_mode: entry.delivery_mode,
            latency_ms: entry.latency_ms,
            status_code: entry.status_code,
            tokens_in: entry.tokens_in,
            tokens_out: entry.tokens_out,
        };

        // Include cost if present.
        if (entry.cost !== undefined) {
            logRecord.cost_usd = entry.cost;
        }

        // Include error if present.
        if (entry.error) {
            logRecord.error = entry.error;
        }

        this.appendToLogFile(logRecord);

        // Alert on slow requests if threshold is configured.
        if (
            this.config.slowRequestThresholdMs &&
            entry.latency_ms > this.config.slowRequestThresholdMs
        ) {
            this.sendSlowRequestAlert(entry);
        }
    }

    // -----------------------------------------------------------------------
    // Statistics
    // -----------------------------------------------------------------------

    /**
     * Flush buffered aggregate statistics.
     *
     * Writes the full stats snapshot to the JSON log and optionally sends
     * a summary to Slack. Also maintains an in-memory history for trend
     * analysis.
     */
    flush(stats: Record<string, AggregateStats>): void {
        const timestamp = new Date();

        // Write to JSON log.
        this.appendToLogFile({
            type: "statistics",
            timestamp: timestamp.toISOString(),
            scopes: stats,
        });

        // Store in memory for trend analysis.
        this.statsHistory.push({ timestamp, stats });

        // Keep only the last 100 snapshots in memory.
        if (this.statsHistory.length > 100) {
            this.statsHistory = this.statsHistory.slice(-100);
        }

        // Optionally send to Slack.
        if (this.config.sendStatsToSlack) {
            const message = this.formatStatsForSlack(stats, timestamp);
            this.sendToSlack(message);
        }
    }

    // -----------------------------------------------------------------------
    // Private: Slack formatting
    // -----------------------------------------------------------------------

    /** Format a routing event into a rich Slack Block Kit message. */
    private formatEventForSlack(event: RoutingEvent): SlackMessage {
        const emoji = this.getEventEmoji(event.event_type);
        const severity = this.getEventSeverity(event.event_type);
        const title = this.formatEventTitle(event.event_type);

        const blocks: SlackBlock[] = [
            {
                type: "header",
                text: {
                    type: "plain_text",
                    text: `${emoji} ${title}`,
                    emoji: true,
                },
            },
            {
                type: "section",
                fields: [
                    {
                        type: "mrkdwn",
                        text: `*Event:*\n${event.event_type}`,
                    },
                    {
                        type: "mrkdwn",
                        text: `*Time:*\n${event.timestamp.toISOString()}`,
                    },
                ],
            },
        ];

        // Add model/provider/pool info if present.
        const infoFields: Array<{ type: string; text: string }> = [];
        if (event.model_id) {
            infoFields.push({
                type: "mrkdwn",
                text: `*Model:*\n\`${event.model_id}\``,
            });
        }
        if (event.provider_id) {
            infoFields.push({
                type: "mrkdwn",
                text: `*Provider:*\n\`${event.provider_id}\``,
            });
        }
        if (event.pool_id) {
            infoFields.push({
                type: "mrkdwn",
                text: `*Pool:*\n\`${event.pool_id}\``,
            });
        }
        if (infoFields.length > 0) {
            blocks.push({ type: "section", fields: infoFields });
        }

        // Add metadata if non-empty.
        if (Object.keys(event.metadata).length > 0) {
            const metaStr = Object.entries(event.metadata)
                .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
                .join("\n");
            blocks.push({
                type: "section",
                text: {
                    type: "mrkdwn",
                    text: `*Metadata:*\n\`\`\`${metaStr}\`\`\``,
                },
            });
        }

        // Add a divider at the end.
        blocks.push({ type: "divider" } as SlackBlock);

        return {
            channel: this.config.slackChannel,
            username: "ModelMesh Lite",
            icon_emoji: ":robot_face:",
            blocks,
        };
    }

    /** Format aggregate stats into a Slack summary message. */
    private formatStatsForSlack(
        stats: Record<string, AggregateStats>,
        timestamp: Date,
    ): SlackMessage {
        const blocks: SlackBlock[] = [
            {
                type: "header",
                text: {
                    type: "plain_text",
                    text: "ModelMesh Stats Summary",
                    emoji: true,
                },
            },
            {
                type: "section",
                text: {
                    type: "mrkdwn",
                    text: `*Window ending:* ${timestamp.toISOString()}`,
                },
            },
        ];

        // Add a section for each scope.
        for (const [scopeId, scopeStats] of Object.entries(stats)) {
            const successRate =
                scopeStats.requests_total > 0
                    ? ((scopeStats.requests_success / scopeStats.requests_total) * 100).toFixed(1)
                    : "N/A";

            blocks.push({
                type: "section",
                fields: [
                    { type: "mrkdwn", text: `*Scope:*\n\`${scopeId}\`` },
                    { type: "mrkdwn", text: `*Requests:*\n${scopeStats.requests_total}` },
                    { type: "mrkdwn", text: `*Success Rate:*\n${successRate}%` },
                    { type: "mrkdwn", text: `*Avg Latency:*\n${scopeStats.latency_avg.toFixed(0)}ms` },
                    { type: "mrkdwn", text: `*P95 Latency:*\n${scopeStats.latency_p95.toFixed(0)}ms` },
                    { type: "mrkdwn", text: `*Cost:*\n$${scopeStats.cost_total.toFixed(4)}` },
                ],
            });
        }

        blocks.push({ type: "divider" } as SlackBlock);

        return {
            channel: this.config.slackChannel,
            username: "ModelMesh Lite",
            icon_emoji: ":bar_chart:",
            blocks,
        };
    }

    /** Send a Slack alert for a slow request. */
    private sendSlowRequestAlert(entry: RequestLogEntry): void {
        const message: SlackMessage = {
            channel: this.config.slackChannel,
            username: "ModelMesh Lite",
            icon_emoji: ":warning:",
            blocks: [
                {
                    type: "section",
                    text: {
                        type: "mrkdwn",
                        text: `*Slow Request Alert*\nModel \`${entry.model_id}\` via \`${entry.provider_id}\` took *${entry.latency_ms.toFixed(0)}ms* (threshold: ${this.config.slowRequestThresholdMs}ms)`,
                    },
                },
                {
                    type: "section",
                    fields: [
                        { type: "mrkdwn", text: `*Capability:*\n${entry.capability}` },
                        { type: "mrkdwn", text: `*Status:*\n${entry.status_code}` },
                        { type: "mrkdwn", text: `*Tokens:*\n${entry.tokens_in} in / ${entry.tokens_out} out` },
                    ],
                },
            ],
        };
        this.sendToSlack(message);
    }

    /** Get an emoji for an event type. */
    private getEventEmoji(eventType: EventType): string {
        const emojiMap: Record<EventType, string> = {
            [EventType.MODEL_ACTIVATED]: ":white_check_mark:",
            [EventType.MODEL_DEACTIVATED]: ":red_circle:",
            [EventType.MODEL_ROTATED]: ":arrows_counterclockwise:",
            [EventType.PROVIDER_HEALTH_CHANGED]: ":thermometer:",
            [EventType.PROVIDER_DEACTIVATED]: ":no_entry:",
            [EventType.PROVIDER_RECOVERED]: ":green_heart:",
            [EventType.POOL_MEMBERSHIP_CHANGED]: ":busts_in_silhouette:",
            [EventType.DISCOVERY_MODELS_UPDATED]: ":mag:",
        };
        return emojiMap[eventType] ?? ":bell:";
    }

    /** Get a severity level for an event type. */
    private getEventSeverity(eventType: EventType): string {
        switch (eventType) {
            case EventType.MODEL_DEACTIVATED:
            case EventType.PROVIDER_DEACTIVATED:
                return "warning";
            case EventType.PROVIDER_HEALTH_CHANGED:
                return "info";
            case EventType.MODEL_ACTIVATED:
            case EventType.PROVIDER_RECOVERED:
                return "success";
            default:
                return "info";
        }
    }

    /** Format an event type into a human-readable title. */
    private formatEventTitle(eventType: EventType): string {
        return eventType
            .replace(/_/g, " ")
            .replace(/\b\w/g, (c) => c.toUpperCase());
    }

    // -----------------------------------------------------------------------
    // Private: Slack HTTP
    // -----------------------------------------------------------------------

    /**
     * Send a message to Slack via the webhook URL.
     *
     * Uses fire-and-forget: errors are logged to console but do not
     * propagate to the caller. Observability should not break the
     * request pipeline.
     */
    private sendToSlack(message: SlackMessage): void {
        fetch(this.config.slackWebhookUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(message),
        }).catch((err: Error) => {
            // Log the error locally but do not throw. Observability failures
            // must not affect the request pipeline.
            console.error(`[ModelMesh Observability] Slack webhook error: ${err.message}`);
        });
    }

    // -----------------------------------------------------------------------
    // Private: JSON file logging with rotation
    // -----------------------------------------------------------------------

    /**
     * Append a structured log record to the current log file.
     *
     * Writes each record as a single JSON line (NDJSON format). Checks
     * whether the current file has exceeded the maximum size and rotates
     * if necessary.
     */
    private appendToLogFile(record: Record<string, unknown>): void {
        const line = JSON.stringify(record) + "\n";
        const lineBytes = Buffer.byteLength(line, "utf8");

        // Rotate if adding this line would exceed the max file size.
        if (this.currentLogFileSize + lineBytes > this.maxFileSize) {
            this.rotateLogFiles();
        }

        fs.appendFileSync(this.currentLogFile, line, "utf8");
        this.currentLogFileSize += lineBytes;
    }

    /**
     * Rotate log files.
     *
     * Renames the current log file with a timestamp suffix, creates a new
     * current file, and deletes the oldest files if the count exceeds
     * the configured maximum.
     */
    private rotateLogFiles(): void {
        // Rename the current file with a timestamp.
        const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
        const rotatedName = path.join(
            this.logDir,
            `modelmesh-${timestamp}.log`,
        );

        try {
            if (fs.existsSync(this.currentLogFile)) {
                fs.renameSync(this.currentLogFile, rotatedName);
            }
        } catch (err: unknown) {
            console.error(
                `[ModelMesh Observability] Log rotation rename error: ${err instanceof Error ? err.message : err}`,
            );
        }

        // Create a new current log file.
        this.currentLogFile = this.generateLogFileName();
        this.currentLogFileSize = 0;

        // Clean up old files beyond the retention limit.
        this.cleanOldLogFiles();
    }

    /** Remove the oldest log files if the count exceeds maxFiles. */
    private cleanOldLogFiles(): void {
        try {
            const files = fs
                .readdirSync(this.logDir)
                .filter((f) => f.startsWith("modelmesh-") && f.endsWith(".log"))
                .map((f) => ({
                    name: f,
                    path: path.join(this.logDir, f),
                    mtime: fs.statSync(path.join(this.logDir, f)).mtimeMs,
                }))
                .sort((a, b) => b.mtime - a.mtime); // newest first

            // Delete files beyond the retention limit.
            for (let i = this.maxFiles; i < files.length; i++) {
                fs.unlinkSync(files[i].path);
            }
        } catch (err: unknown) {
            console.error(
                `[ModelMesh Observability] Log cleanup error: ${err instanceof Error ? err.message : err}`,
            );
        }
    }

    /** Generate the current log file name. */
    private generateLogFileName(): string {
        return path.join(this.logDir, "modelmesh-current.log");
    }

    /** Get the size of a file in bytes, returning 0 if it does not exist. */
    private getFileSize(filePath: string): number {
        try {
            return fs.statSync(filePath).size;
        } catch {
            return 0;
        }
    }
}

// ---------------------------------------------------------------------------
// YAML configuration example
// ---------------------------------------------------------------------------

/*
# modelmesh.yaml — observability section for Slack + JSON connector
#
# observability:
#   - connector: custom
#     connector_class: SlackJsonObservabilityConnector
#     config:
#       slack_webhook_url: "${secrets:slack-webhook-url}"
#       slack_channel: "#modelmesh-alerts"
#       slack_event_filter:
#         - model_deactivated
#         - model_rotated
#         - provider_deactivated
#         - provider_recovered
#       log_directory: "./logs/modelmesh"
#       max_log_file_size_bytes: 10485760   # 10 MB
#       max_log_files: 10
#       send_stats_to_slack: false
#       slow_request_threshold_ms: 5000
#     events:
#       filter: [rotation, deactivation, recovery, health]
#       include_metadata: true
#     logging:
#       level: summary
#       redact_secrets: true
#     statistics:
#       flush_interval: 60s
#       retention: 7d
#       scopes: [model, provider, pool]
*/

export { SlackJsonObservabilityConnector };
export type {
    SlackJsonObservabilityConfig,
    ObservabilityConnector,
    Events,
    Logging,
    Statistics,
    RoutingEvent,
    RequestLogEntry,
    AggregateStats,
    EventType,
    LogLevel,
};
