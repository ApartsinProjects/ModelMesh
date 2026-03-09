/**
 * Quickstart: Create an HttpHealthDiscovery, probe a provider, get health report.
 *
 * Demonstrates setting up HTTP health probing for a provider and retrieving
 * health reports using the HttpHealthDiscovery specialized class.
 */

import { HttpHealthDiscovery, HttpHealthDiscoveryConfig, ProbeResult, HealthReport } from "@modelmesh/cdk";

async function main(): Promise<void> {
    const discovery = new HttpHealthDiscovery({
        providers: ["openai"],
        healthPath: "/v1/models",
        expectedStatus: 200,
        healthIntervalSeconds: 30,
        failureThreshold: 3,
    });

    // Register the provider URL for probing
    discovery.registerProviderUrl("openai", "https://api.openai.com");

    // Probe the provider
    const result: ProbeResult = await discovery.probe("openai");
    console.log(`Probe success: ${result.success}`);
    console.log(`Latency: ${result.latency_ms?.toFixed(1)}ms`);

    // Get a full health report
    const reports: HealthReport[] = await discovery.getHealthReport("openai");
    for (const report of reports) {
        console.log(`Provider: ${report.provider_id}, Available: ${report.available}`);
        console.log(`Availability score: ${report.availability_score.toFixed(2)}`);
    }

    await discovery.close();
}

main().catch(console.error);
