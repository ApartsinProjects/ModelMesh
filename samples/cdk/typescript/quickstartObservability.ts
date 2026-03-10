/**
 * Quickstart: Implement a console observability connector.
 *
 * Demonstrates the three core observability operations (emit, log, flush)
 * using an inline implementation of the ObservabilityConnector interface
 * with console output.
 *
 * For a full Slack + JSON file implementation, see
 * samples/connectors/typescript/customObservability.ts.
 */

import {
    ObservabilityConnector,
    RoutingEvent,
    RequestLogEntry,
    AggregateStats,
    TraceEntry,
    EventType,
} from "@nistrapa/modelmesh-core";

/**
 * Console-based observability connector for development.
 *
 * Prints routing events, request logs, statistics, and trace entries
 * to the console with simple formatting.
 */
class ConsoleObservabilityConnector implements ObservabilityConnector {
    emit(event: RoutingEvent): void {
        console.log(
            `[EVENT] ${event.eventType} ` +
            `model=${event.modelId ?? "n/a"} ` +
            `provider=${event.providerId ?? "n/a"}`
        );
    }

    log(entry: RequestLogEntry): void {
        console.log(
            `[LOG] model=${entry.modelId} ` +
            `provider=${entry.providerId} ` +
            `capability=${entry.capability} ` +
            `delivery=${entry.deliveryMode} ` +
            `latency=${entry.latencyMs}ms ` +
            `status=${entry.statusCode} ` +
            `tokens=${entry.tokensIn}/${entry.tokensOut}`
        );
    }

    flush(stats: Record<string, AggregateStats>): void {
        for (const [scope, s] of Object.entries(stats)) {
            console.log(
                `[STATS] ${scope}: ` +
                `requests=${s.requestsTotal} ` +
                `success=${s.requestsSuccess} ` +
                `failed=${s.requestsFailed} ` +
                `tokens=${s.tokensIn}/${s.tokensOut} ` +
                `cost=$${s.costTotal.toFixed(4)} ` +
                `latency_avg=${s.latencyAvg.toFixed(0)}ms ` +
                `latency_p95=${s.latencyP95.toFixed(0)}ms`
            );
        }
    }

    trace(entry: TraceEntry): void {
        console.log(`[TRACE] [${entry.severity}] ${entry.component}: ${entry.message}`);
    }
}

function main(): void {
    const obs = new ConsoleObservabilityConnector();

    // Emit a routing event
    obs.emit({
        eventType: EventType.MODEL_ACTIVATED,
        timestamp: new Date(),
        modelId: "gpt-4o",
        providerId: "openai",
        metadata: {},
    });

    // Log a request
    obs.log({
        timestamp: new Date(),
        modelId: "gpt-4o",
        providerId: "openai",
        capability: "generation.text-generation.chat-completion",
        deliveryMode: "sync",
        latencyMs: 142.5,
        statusCode: 200,
        tokensIn: 50,
        tokensOut: 120,
    });

    // Flush aggregate stats
    obs.flush({
        "gpt-4o": {
            requestsTotal: 100,
            requestsSuccess: 95,
            requestsFailed: 5,
            tokensIn: 5000,
            tokensOut: 10000,
            costTotal: 1.50,
            latencyAvg: 150.0,
            latencyP95: 300.0,
            downtimeTotal: 0.0,
            rotationEvents: 2,
        },
    });
}

main();
