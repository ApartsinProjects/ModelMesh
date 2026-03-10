"""
11 - Production Routing Scenarios
==================================

Demonstrates realistic production routing behaviors using mock providers
(no real API keys required). Each scenario builds a complete ModelMesh
configuration and exercises the routing pipeline.

This sample covers:
  1. Failover cascade -- providers A and B fail, C succeeds
  2. Quota exhaustion -- provider raises 429, mesh moves to backup
  3. Latency simulation -- slow vs fast provider routing
  4. Observability output -- ConsoleConnector showing traces and events
  5. Pool introspection -- describe() and pool_status() after failures

Run::

    PYTHONPATH=src/python python samples/system/python/11_production_scenarios.py
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import AsyncIterator

from modelmesh import ModelMesh, MeshConfig
from modelmesh.core.event_emitter import EventType
from modelmesh.core.pool import PoolModel
from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    ErrorClassification,
    ModelInfo,
    ModelPricing,
    ProviderConnector,
    QuotaStatus,
    RateLimitStatus,
    TokenUsage,
)


# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------

class FakeProviderBase(ProviderConnector):
    """Base class for mock providers with minimal boilerplate."""

    def __init__(self, name: str = "FakeProvider"):
        self.name = name

    def get_capabilities(self):
        return ["generation.text-generation.chat-completion"]

    def supports(self, capability):
        return capability in self.get_capabilities()

    def list_models(self):
        return [ModelInfo(id="mock-model", name="Mock Model")]

    def get_model_info(self, model_id):
        return ModelInfo(id=model_id, name=model_id)

    def check_quota(self):
        return QuotaStatus()

    def get_rate_limits(self):
        return RateLimitStatus()

    def get_pricing(self, model_id):
        return ModelPricing()

    def report_usage(self, model_id, usage):
        pass

    def classify_error(self, error):
        return ErrorClassification(retryable=False)


class FailingProvider(FakeProviderBase):
    """Provider that always raises an error."""

    def __init__(self, name: str, error_msg: str = "Service unavailable"):
        super().__init__(name)
        self._error_msg = error_msg

    async def complete(self, request):
        raise RuntimeError(f"[{self.name}] {self._error_msg}")

    async def stream(self, request):
        raise RuntimeError(f"[{self.name}] {self._error_msg}")
        yield  # pragma: no cover


class SucceedingProvider(FakeProviderBase):
    """Provider that always returns a successful response."""

    def __init__(self, name: str, reply: str = "Hello from mock!"):
        super().__init__(name)
        self._reply = reply

    async def complete(self, request):
        return CompletionResponse(
            id=f"resp-{self.name}",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=self._reply),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(
                prompt_tokens=10, completion_tokens=8, total_tokens=18
            ),
        )

    async def stream(self, request):
        yield CompletionResponse(
            id=f"chunk-{self.name}",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content=self._reply),
                    finish_reason="stop",
                )
            ],
        )


class QuotaExhaustedProvider(FakeProviderBase):
    """Provider that simulates HTTP 429 quota exhaustion."""

    def __init__(self, name: str):
        super().__init__(name)

    async def complete(self, request):
        raise RuntimeError(f"[{self.name}] 429 Too Many Requests: quota exhausted")

    async def stream(self, request):
        raise RuntimeError(f"[{self.name}] 429 Too Many Requests")
        yield  # pragma: no cover

    def check_quota(self):
        return QuotaStatus(used=1000, limit=1000, remaining=0)


class SlowProvider(FakeProviderBase):
    """Provider that simulates latency with a sleep."""

    def __init__(self, name: str, delay_seconds: float = 0.5,
                 reply: str = "Slow response"):
        super().__init__(name)
        self._delay = delay_seconds
        self._reply = reply

    async def complete(self, request):
        await asyncio.sleep(self._delay)
        return CompletionResponse(
            id=f"resp-{self.name}",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=self._reply),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(
                prompt_tokens=10, completion_tokens=5, total_tokens=15
            ),
        )

    async def stream(self, request):
        await asyncio.sleep(self._delay)
        yield CompletionResponse(
            id=f"chunk-{self.name}",
            model=request.model,
            choices=[
                CompletionChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content=self._reply),
                    finish_reason="stop",
                )
            ],
        )


# ---------------------------------------------------------------------------
# Helper: build a MeshConfig with inline provider instances
# ---------------------------------------------------------------------------

def build_config(providers: dict, models: dict, pool_id: str = "chat",
                  failure_threshold: int = 1,
                  observability_connector: str = "modelmesh.null.v1"):
    """Build a MeshConfig from inline provider instances."""
    providers_cfg = {}
    for pid, instance in providers.items():
        providers_cfg[pid] = {
            "connector": pid,
            "enabled": True,
            "instance": instance,
        }

    return MeshConfig(raw={
        "providers": providers_cfg,
        "models": models,
        "pools": {
            pool_id: {
                "capability": "generation.text-generation.chat-completion",
                "strategy": "stick-until-failure",
                "failure_threshold": failure_threshold,
            },
        },
        "observability": {"connector": observability_connector},
    })


# ===================================================================
# Scenario 1: Failover Cascade
# ===================================================================

async def scenario_failover_cascade():
    """Three providers: A fails, B fails, C succeeds."""
    print("=" * 70)
    print("SCENARIO 1: Failover Cascade")
    print("=" * 70)
    print("  Provider A: always fails")
    print("  Provider B: always fails")
    print("  Provider C: always succeeds")
    print()

    prov_a = FailingProvider("ProviderA", "Connection timeout")
    prov_b = FailingProvider("ProviderB", "Internal server error")
    prov_c = SucceedingProvider("ProviderC", "Hello from the backup provider!")

    config = build_config(
        providers={"prov-a": prov_a, "prov-b": prov_b, "prov-c": prov_c},
        models={
            "a.gpt-4o": {
                "provider": "prov-a",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
            "b.claude-sonnet": {
                "provider": "prov-b",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
            "c.gemini-pro": {
                "provider": "prov-c",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
        },
    )

    mesh = ModelMesh()
    mesh.initialize(config)

    # Subscribe to routing events
    mesh.event_emitter.on(EventType.REQUEST_FAILURE, lambda e: print(
        f"  [event] REQUEST_FAILURE: model={e.data.get('model_id')} "
        f"error={e.data.get('error', '')[:60]}"
    ))
    mesh.event_emitter.on(EventType.MODEL_ROTATED, lambda e: print(
        f"  [event] MODEL_ROTATED: new_model={e.data.get('new_model_id')}"
    ))
    mesh.event_emitter.on(EventType.REQUEST_SUCCESS, lambda e: print(
        f"  [event] REQUEST_SUCCESS: model={e.data.get('model_id')}"
    ))

    print("Routing request...")
    req = CompletionRequest(
        model="chat",
        messages=[{"role": "user", "content": "What is failover?"}],
    )
    response = await mesh.route(req)
    print(f"\nResponse: {response.choices[0].message.content}")
    print(f"Model used: {response.model}")

    mesh.shutdown()
    print()


# ===================================================================
# Scenario 2: Quota Exhaustion
# ===================================================================

async def scenario_quota_exhaustion():
    """Primary provider's quota is exhausted, mesh routes to backup."""
    print("=" * 70)
    print("SCENARIO 2: Quota Exhaustion Handling")
    print("=" * 70)
    print("  Provider A: quota exhausted (429)")
    print("  Provider B: available with remaining quota")
    print()

    prov_a = QuotaExhaustedProvider("PrimaryProvider")
    prov_b = SucceedingProvider("BackupProvider", "Response from backup after quota exhaustion!")

    config = build_config(
        providers={"prov-a": prov_a, "prov-b": prov_b},
        models={
            "a.gpt-4o": {
                "provider": "prov-a",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
            "b.claude": {
                "provider": "prov-b",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
        },
    )

    mesh = ModelMesh()
    mesh.initialize(config)

    # Show quota status before request
    print("Quota status before request:")
    print(f"  Provider A remaining: {prov_a.check_quota().remaining}")
    print(f"  Provider B remaining: {prov_b.check_quota().remaining}")
    print()

    mesh.event_emitter.on(EventType.REQUEST_FAILURE, lambda e: print(
        f"  [event] REQUEST_FAILURE: model={e.data.get('model_id')}"
    ))
    mesh.event_emitter.on(EventType.REQUEST_SUCCESS, lambda e: print(
        f"  [event] REQUEST_SUCCESS: model={e.data.get('model_id')}"
    ))

    print("Routing request...")
    req = CompletionRequest(
        model="chat",
        messages=[{"role": "user", "content": "Explain quotas"}],
    )
    response = await mesh.route(req)
    print(f"\nResponse: {response.choices[0].message.content}")

    # Show pool status after routing
    print("\nPool status after routing:")
    status = mesh.pool_status()
    for pool_id, info in status.items():
        print(f"  Pool '{pool_id}': active={info['active']}, "
              f"standby={info['standby']}, total={info['total']}, "
              f"current={info['current_model']}")

    mesh.shutdown()
    print()


# ===================================================================
# Scenario 3: Latency Simulation
# ===================================================================

async def scenario_latency_comparison():
    """Provider A is slow, Provider B is fast."""
    print("=" * 70)
    print("SCENARIO 3: Latency Simulation")
    print("=" * 70)
    print("  Provider A: 200ms latency")
    print("  Provider B: near-instant")
    print()

    prov_a = SlowProvider("SlowProvider", delay_seconds=0.2, reply="Slow reply")
    prov_b = SucceedingProvider("FastProvider", "Fast reply!")

    config = build_config(
        providers={"prov-a": prov_a, "prov-b": prov_b},
        models={
            "a.slow-model": {
                "provider": "prov-a",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
            "b.fast-model": {
                "provider": "prov-b",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
        },
    )

    mesh = ModelMesh()
    mesh.initialize(config)

    # Route using stick-until-failure -- goes to the first model (A)
    req = CompletionRequest(
        model="chat",
        messages=[{"role": "user", "content": "Test latency"}],
    )

    print("Request 1 (routed to first model - slow):")
    t0 = time.time()
    response = await mesh.route(req)
    elapsed_1 = (time.time() - t0) * 1000
    print(f"  Response: {response.choices[0].message.content}")
    print(f"  Latency: {elapsed_1:.0f}ms")

    # Force rotation to provider B
    print("\nForcing rotation to fast model...")
    mesh.rotate("chat")

    print("Request 2 (routed to fast model):")
    t0 = time.time()
    response = await mesh.route(req)
    elapsed_2 = (time.time() - t0) * 1000
    print(f"  Response: {response.choices[0].message.content}")
    print(f"  Latency: {elapsed_2:.0f}ms")

    print(f"\nLatency comparison: slow={elapsed_1:.0f}ms vs fast={elapsed_2:.0f}ms")

    mesh.shutdown()
    print()


# ===================================================================
# Scenario 4: Observability with ConsoleConnector
# ===================================================================

async def scenario_observability():
    """Show real observability output during routing."""
    print("=" * 70)
    print("SCENARIO 4: Observability Output")
    print("=" * 70)
    print("  Using ConsoleConnector to show traces during routing")
    print()

    from modelmesh.connectors.observability.console_connector import (
        ConsoleObservabilityConnector,
        ConsoleConnectorConfig,
    )

    obs = ConsoleObservabilityConnector(ConsoleConnectorConfig(
        use_color=True,
        show_timestamp=True,
        prefix="[ModelMesh]",
        min_severity="debug",
    ))

    prov_a = FailingProvider("UnstableProvider", "Connection reset")
    prov_b = SucceedingProvider("StableProvider", "Observability demo response!")

    config = build_config(
        providers={"prov-a": prov_a, "prov-b": prov_b},
        models={
            "a.unstable-model": {
                "provider": "prov-a",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
            "b.stable-model": {
                "provider": "prov-b",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
        },
    )

    mesh = ModelMesh()
    # Inject the console observability connector before initialization
    mesh._observability = obs
    mesh.initialize(config)

    req = CompletionRequest(
        model="chat",
        messages=[{"role": "user", "content": "Show observability"}],
    )

    print("\n--- Routing with console traces enabled ---\n")
    response = await mesh.route(req)
    print(f"\n--- End traces ---")
    print(f"\nResponse: {response.choices[0].message.content}")

    mesh.shutdown()
    print()


# ===================================================================
# Scenario 5: Pool Introspection
# ===================================================================

async def scenario_pool_introspection():
    """Demonstrate describe() and pool_status() after failures."""
    print("=" * 70)
    print("SCENARIO 5: Pool Introspection")
    print("=" * 70)
    print()

    prov_a = FailingProvider("ProviderA", "Overloaded")
    prov_b = FailingProvider("ProviderB", "Maintenance")
    prov_c = SucceedingProvider("ProviderC", "Stable service")

    # failure_threshold=1 so each failure immediately deactivates,
    # demonstrating clear pool state changes as models cascade.

    config = build_config(
        providers={"prov-a": prov_a, "prov-b": prov_b, "prov-c": prov_c},
        models={
            "a.model-alpha": {
                "provider": "prov-a",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
            "b.model-beta": {
                "provider": "prov-b",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
            "c.model-gamma": {
                "provider": "prov-c",
                "capabilities": [
                    "generation.text-generation.chat-completion",
                ],
            },
        },
    )

    mesh = ModelMesh()
    mesh.initialize(config)
    client = mesh.get_client()

    # Show initial state
    print("--- Before routing ---")
    # Replace Unicode arrows with ASCII for portability on all terminals
    print(client.describe().replace("\u2192", "->"))
    print()
    print("Pool status:", mesh.pool_status())
    print()

    # Route a request -- A fails (deactivated), B fails (deactivated), C succeeds
    print("Routing request (A fails, B fails, C succeeds)...")
    req = CompletionRequest(
        model="chat",
        messages=[{"role": "user", "content": "introspection test"}],
    )
    response = await mesh.route(req)
    print(f"Response: {response.choices[0].message.content}\n")

    # Show state after routing (A and B are now STANDBY)
    print("--- After routing ---")
    print(client.describe().replace("\u2192", "->"))
    print()
    status = mesh.pool_status()
    print("Pool status:", status)
    print(f"\n  Active models: {status['chat']['active']}")
    print(f"  Standby models: {status['chat']['standby']}")
    print(f"  Current model: {status['chat']['current_model']}")

    # List active providers
    print(f"\n  Active providers: {mesh.active_providers()}")

    # Reactivate model-alpha (simulating a quota reset or recovery)
    print("\nReactivating 'a.model-alpha' (simulating quota reset)...")
    pool = mesh._pools["chat"]
    pool.reactivate("a.model-alpha")
    print(client.describe().replace("\u2192", "->"))
    print()
    status = mesh.pool_status()
    print(f"  Active models after reactivation: {status['chat']['active']}")
    print(f"  Standby models after reactivation: {status['chat']['standby']}")

    mesh.shutdown()
    print()


# ===================================================================
# Main
# ===================================================================

async def main():
    await scenario_failover_cascade()
    await scenario_quota_exhaustion()
    await scenario_latency_comparison()
    await scenario_observability()
    await scenario_pool_introspection()
    print("All production scenarios completed.")


if __name__ == "__main__":
    asyncio.run(main())
