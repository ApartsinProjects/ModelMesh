"""Quickstart: Create an HttpHealthDiscovery, probe a provider, get health report.

Demonstrates setting up HTTP health probing for a provider and retrieving
health reports using the HttpHealthDiscovery specialized class.
"""

import asyncio

from modelmesh.cdk import HttpHealthDiscovery, HttpHealthDiscoveryConfig


async def main() -> None:
    discovery = HttpHealthDiscovery(HttpHealthDiscoveryConfig(
        providers=["openai"],
        health_path="/v1/models",
        expected_status=200,
        health_interval_seconds=30,
        failure_threshold=3,
    ))

    # Register the provider URL for probing
    discovery.register_provider_url("openai", "https://api.openai.com")

    # Probe the provider
    result = await discovery.probe("openai")
    print(f"Probe success: {result.success}")
    print(f"Latency: {result.latency_ms:.1f}ms")

    # Get a full health report
    reports = await discovery.get_health_report("openai")
    for report in reports:
        print(f"Provider: {report.provider_id}, Available: {report.available}")
        print(f"Availability score: {report.availability_score:.2f}")

    # No close() needed -- HttpHealthDiscovery has no persistent connections


if __name__ == "__main__":
    asyncio.run(main())
