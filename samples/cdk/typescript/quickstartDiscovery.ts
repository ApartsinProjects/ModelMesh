/**
 * Quickstart: Implement a simple health discovery connector.
 *
 * Demonstrates setting up HTTP health probing for a provider and
 * retrieving health reports. This quickstart shows a minimal inline
 * implementation of the DiscoveryConnector interface.
 *
 * For a full YAML-registry-based implementation with rolling availability
 * scores, see samples/connectors/typescript/customDiscovery.ts.
 */

import {
    ProbeResult,
    HealthReport,
    DiscoveryConnector,
    SyncResult,
    SyncStatus,
} from "@modelmesh/core";

/**
 * Simple health probe discovery connector.
 *
 * Registers provider endpoints and simulates health probes.
 * A real implementation would make HTTP requests to the provider's
 * health endpoint (e.g., /v1/models, /health, /readiness).
 */
class SimpleHealthDiscovery implements DiscoveryConnector {
    private endpoints = new Map<string, string>();

    registerProviderUrl(providerId: string, baseUrl: string): void {
        this.endpoints.set(providerId, baseUrl);
    }

    async sync(_providers?: string[]): Promise<SyncResult> {
        return { newModels: [], deprecatedModels: [], updatedModels: [], errors: [] };
    }

    async getSyncStatus(): Promise<SyncStatus> {
        return { modelsSynced: 0, status: "idle" };
    }

    async probe(providerId: string): Promise<ProbeResult> {
        const baseUrl = this.endpoints.get(providerId);
        if (!baseUrl) {
            return { providerId, success: false, error: `Unknown provider: ${providerId}` };
        }
        // In a real implementation, make an HTTP GET to the health endpoint
        // and measure latency. For this quickstart, we return a simulated result.
        return {
            providerId,
            success: true,
            latencyMs: 42.5,
            statusCode: 200,
        };
    }

    async getHealthReport(providerId?: string): Promise<HealthReport[]> {
        const ids = providerId ? [providerId] : [...this.endpoints.keys()];
        return ids.map(id => ({
            providerId: id,
            available: true,
            latencyMs: 42.5,
            statusCode: 200,
            availabilityScore: 1.0,
            timestamp: new Date(),
        }));
    }
}

async function main(): Promise<void> {
    const discovery = new SimpleHealthDiscovery();

    // Register the provider URL for probing
    discovery.registerProviderUrl("openai", "https://api.openai.com");

    // Probe the provider
    const result: ProbeResult = await discovery.probe("openai");
    console.log(`Probe success: ${result.success}`);
    console.log(`Latency: ${result.latencyMs?.toFixed(1)}ms`);

    // Get a full health report
    const reports: HealthReport[] = await discovery.getHealthReport("openai");
    for (const report of reports) {
        console.log(`Provider: ${report.providerId}, Available: ${report.available}`);
        console.log(`Availability score: ${report.availabilityScore.toFixed(2)}`);
    }
}

main().catch(console.error);
