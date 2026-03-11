---
layout: default
title: "Documentation Changelog"
---

# Documentation Changelog

All issues found and fixes applied during the 5 review cycles of the ModelMesh Lite documentation suite.

---

## Review Cycle 1: Cross-Reference Consistency and Link Validation

**Scope:** 84 markdown files across `docs/` (6 root-level, 6 in `interfaces/`, 51 in `connectors/`, 27 in `system/`).

**Result:** 31 link fixes across 28 files.

### Broken Links (1 fix)

| File | Issue | Fix |
| --- | --- | --- |
| `SystemConcept.md` | Referenced `ProviderSchemas.md` which does not exist (lines 101, 248) | Replaced with `[Provider Interface](interfaces/Provider.md)` and removed redundant footer reference |

### Root Docs Missing Subfolder References (4 fixes)

| File | Fix |
| --- | --- |
| `SystemConcept.md` | Updated footer to mention `system/Overview.md`, `interfaces/Provider.md`, `connectors/openai-llm.md` as entry points |
| `SystemServices.md` | Added link: "Individual service documentation with full code definitions is in [system/](system/Overview.md)." |
| `ConnectorInterfaces.md` | Added link: "Full interface definitions with code are in [interfaces/](interfaces/Provider.md)." |
| `ConnectorCatalogue.md` | Added link: "Individual connector documentation is in [connectors/](connectors/openai-llm.md)." |

### System Docs Pointing to Root Instead of Local Docs (7 fixes)

| File | Old Link | New Link |
| --- | --- | --- |
| `system/ConnectorRegistry.md` | `[ModelMesh](../SystemServices.md#modelmesh)` | `[ModelMesh](ModelMesh.md)` |
| `system/DeactivationEvaluator.md` | `[ModelState](../SystemServices.md#modelstate), [RotationPolicy](../SystemServices.md#rotationpolicy)` | `[ModelState](ModelState.md), [RotationPolicyService](RotationPolicyService.md)` |
| `system/ModelRegistry.md` | `[CapabilityPool](../SystemServices.md#capabilitypool)` | `[CapabilityPool](CapabilityPool.md)` |
| `system/OpenAIClient.md` | `[Router](../SystemServices.md#router)` | `[Router](Router.md)` |
| `system/ProxyServer.md` | `[Router](../SystemServices.md#router), [ModelMesh](../SystemServices.md#modelmesh)` | `[Router](Router.md), [ModelMesh](ModelMesh.md)` |
| `system/RecoveryEvaluator.md` | `[ModelState](../SystemServices.md#modelstate), [RotationPolicy](../SystemServices.md#rotationpolicy)` | `[ModelState](ModelState.md), [RotationPolicyService](RotationPolicyService.md)` |
| `system/SelectionStrategy.md` | `[RotationPolicy](../SystemServices.md#rotationpolicy), [CapabilityPool](../SystemServices.md#capabilitypool)` | `[RotationPolicyService](RotationPolicyService.md), [CapabilityPool](CapabilityPool.md)` |

### Unlinked Plain-Text Dependencies (13 fixes)

Added markdown links for plain-text "Depends on" entries in 13 system docs:

`CapabilityResolver.md`, `CapabilityPool.md`, `DeliveryFilter.md`, `Model.md`, `ModelState.md`, `ModelMesh.md`, `ProviderService.md`, `ProviderState.md`, `RetryPolicy.md`, `RotationPolicyService.md`, `RoutingPipeline.md`, `Router.md`, `StateFilter.md`

### Overview and RoutingPipeline Table Links (2 fixes)

| File | Fix |
| --- | --- |
| `system/Overview.md` | Added links for 10 services in the Service Groupings table |
| `system/RoutingPipeline.md` | Changed plain-text `SelectionStrategy` to `[SelectionStrategy](SelectionStrategy.md)` |

### Missing Interface References in Rotation Connectors (4 fixes)

Added `See [ConnectorInterfaces.md -- Rotation Policy](../ConnectorInterfaces.md#rotation-policy)...` to:

`connectors/modelmesh-priority-selection.md`, `connectors/modelmesh-session-stickiness.md`, `connectors/modelmesh-rate-limit-aware.md`, `connectors/modelmesh-load-balanced.md`

---

## Review Cycle 2: Interface Method Signature Consistency

**Scope:** Cross-checked method signatures between authoritative interface docs (`interfaces/*.md`), summary doc (`SystemServices.md`), and detailed system docs (`system/*.md`).

**Result:** 13 fixes across 2 files.

### SystemServices.md (5 fixes)

| Method | Before | After | Reason |
| --- | --- | --- | --- |
| `EventEmitter.emit()` | `emit(event_type, payload)` | `emit(event)` | Interface uses single `RoutingEvent` parameter |
| Event type format | Dot notation (`model.activated`) | Underscore format (`model_activated`) | Matches `Observability.md` authoritative definition |
| `RequestLogger.log()` | `log(request, response, decision)` | `log(entry)` | Interface uses single `RequestLogEntry` parameter |
| `StatisticsCollector.record()` | `record(model, provider, pool, metrics)` | `record(model_id, provider_id, pool_id, metrics)` | Matches `StatisticsCollector.md` parameter names |
| `DeactivationEvaluator.should_deactivate()` | `should_deactivate(model_state)` | `should_deactivate(snapshot)` | Matches interface `ModelSnapshot` parameter |

### system/RotationPolicyService.md (8 fixes)

| Issue | Fix |
| --- | --- |
| `DeactivationReason` enum had 4 values, missing 3 | Added `TOKEN_LIMIT`, `REQUEST_LIMIT`, `MANUAL`; renamed `MAINTENANCE` to `MAINTENANCE_WINDOW` |
| `RecoveryTrigger` enum missing `STARTUP_PROBE` | Added `STARTUP_PROBE` to both Python and TypeScript |
| Parameters used `model_state: ModelState` | Changed to `snapshot: ModelSnapshot` across 4 methods |
| `SelectionStrategy.select()` used `list[Model]` / `Model` | Changed to `list[ModelSnapshot]` / `SelectionResult` |
| Missing `ModelSnapshot` dataclass | Added `ModelSnapshot` definition to both Python and TypeScript |

---

## Review Cycle 3: Configuration Parameter Consistency

**Scope:** Compared configuration parameters between `SystemConfiguration.md` (authoritative), `ConnectorInterfaces.md`, and downstream docs.

**Result:** 7 fixes across 3 files.

### system/RetryPolicy.md (5 fixes)

| Parameter | Before | After | Authority |
| --- | --- | --- | --- |
| `retry.max_retries` | `max_retries` | `max_attempts` | `SystemConfiguration.md` |
| `retry.initial_delay` default | `1s` | `500ms` | `SystemConfiguration.md` |
| `retry.max_delay` default | `30s` | `10s` | `SystemConfiguration.md` |
| `retry.scope` value | `cross_provider` | `any` | `SystemConfiguration.md` |
| Missing params | — | Added `retryable_codes`, `non_retryable_codes`, `honor_retry_after` | `SystemConfiguration.md` |

### SystemServices.md (1 fix)

| Parameter | Before | After |
| --- | --- | --- |
| `storage.sync_policy` | `storage.sync_policy` | `storage.persistence.sync_policy` |

### system/StateManager.md (1 fix)

| Issue | Before | After |
| --- | --- | --- |
| Connector ID typo | `modelmesh.local-json.v1` | `modelmesh.local-file.v1` |

---

## Review Cycle 4: Naming Convention and Enum Consistency

**Scope:** Verified connector ID naming, connector type labels, enum value consistency, and Python/TypeScript naming style across all files.

**Result:** 8 files edited with fixes.

### EventType Enum Values (6 files, 48 individual value corrections)

**Problem:** Authoritative definition (`interfaces/Observability.md`) uses underscore format (`model_activated`). Five downstream files used dot format (`model.activated`).

| File | Fix |
| --- | --- |
| `system/EventEmitter.md` | All 8 enum values fixed in both Python and TypeScript |
| `connectors/modelmesh-console.md` | All 8 enum values fixed in both Python and TypeScript |
| `connectors/modelmesh-local-file-obs.md` | All 8 enum values fixed in both Python and TypeScript |
| `connectors/modelmesh-webhook.md` | All 8 enum values fixed in both Python and TypeScript |
| `SystemServices.md` | Event types table updated (all 8 rows) |
| `system/Overview.md` | Prose reference `model.deactivated` changed to `model_deactivated` |

### DeactivationReason Enum (1 file)

| File | Fix |
| --- | --- |
| `system/RotationPolicyService.md` | Added `TOKEN_LIMIT`, `REQUEST_LIMIT`, `MANUAL`; renamed `MAINTENANCE` to `MAINTENANCE_WINDOW` |

### RecoveryTrigger Enum (1 file)

| File | Fix |
| --- | --- |
| `system/RotationPolicyService.md` | Added `STARTUP_PROBE` |

### Deactivation Reason Docstrings (2 files)

| File | Fix |
| --- | --- |
| `system/ModelState.md` | Updated `deactivation_reason` docstring to list all 7 valid values |
| `system/CapabilityPool.md` | Updated `deactivate()` docstring to list all 7 valid values |

### Verified As Consistent (no fixes needed)

- All 51 connector IDs follow `connector_type.vendor.service.version` pattern
- All connector type labels match their ID prefix
- `LogLevel`, `SyncPolicy`, `SyncAction`, `DeprecationAction`, `ModelStatus` enums consistent everywhere
- Python/TypeScript naming conventions (`snake_case`/`camelCase` for methods, `PascalCase` for classes, `UPPER_SNAKE` for enums) consistent across all files

---

## Review Cycle 5: Completeness and Content Accuracy

**Scope:** Verified all 84 files exist with required sections; spot-checked content accuracy of model names, capability flags, and YAML format.

**Result:** 19 fixes across 16 files.

### Structural Completeness: PASS

All 84 expected files present. All required sections present. No TODO/FIXME/PLACEHOLDER markers found.

### ConnectorCatalogue.md Key Models Accuracy (11 fixes)

Updated "Key Models" column entries to match actual model enum values in connector docs:

| Provider | Before (speculative) | After (matches connector enums) |
| --- | --- | --- |
| OpenAI | GPT-5.2, GPT-5.2 Pro, GPT-5 mini/nano | GPT-4o, GPT-4.1, GPT-4.1 mini/nano, o3, o3-mini, o4-mini |
| Anthropic | Claude Opus 4.5, Sonnet 4.5, Haiku 4.5 | Claude Opus 4, Sonnet 4, 3.7 Sonnet, 3.5 Haiku, 3.5 Sonnet |
| Google Gemini | Gemini 3.1 Pro, Gemini 3 Flash | Gemini 2.5 Pro/Flash, 2.0 Flash/Flash Lite, 1.5 Pro/Flash |
| xAI | Grok 4, Grok 4.1 Fast | Grok 3, Grok 3 Mini/Fast, Grok 2, Grok 2 Vision |
| DeepSeek | DeepSeek V3.2, DeepSeek R1 | DeepSeek Chat, DeepSeek Reasoner |
| Mistral | Mistral Small 3.1 (vision) | Mistral Small |
| Cohere | Missing models | Added Command A, Embed v4, Embed v3 variants |
| Groq | Llama 4 Scout | Llama 3.3 70B, Llama 3.1 8B, Gemma 2 9B |
| Stability AI | SDXL | SD 3.5 Large/Medium/Turbo, Stable Image Core/Ultra |
| fal.ai | Kling 3.0 | Kling V2 |
| Replicate | Stable Video, Wan 2.1 | Flux Schnell, SDXL, Llama 3, Whisper |

### Provider Capability Matrix Accuracy (3 fixes)

| Provider | Column | Before | After |
| --- | --- | --- | --- |
| OpenAI | Search | yes | — |
| Google Gemini | Search | yes | — |
| HuggingFace | Tool Use, Batch | —, — | yes, yes |
| Cloudflare | Tool Use | — | yes |

### YAML Example Format Consistency (14 files)

Updated 14 connector docs from non-canonical `connectors: - id:` array format with `"${ENV_VAR}"` to canonical `providers:` map format with `${secrets:...}` syntax:

`groq-inference.md`, `together-inference.md`, `cloudflare-workers-ai.md`, `openrouter-gateway.md`, `aws-bedrock.md`, `google-cloud-ai.md`, `google-search.md`, `microsoft-bing-search.md`, `tavily-search.md`, `serper-search.md`, `deepl-translation.md`, `google-moderation.md`, `unstructured-doc-parse.md`, `llamaindex-doc-parse.md`

### Overview Service Groupings Table (1 fix)

Added `DeactivationEvaluator`, `RecoveryEvaluator`, and `SelectionStrategy` links to the "Rotation" row in `system/Overview.md`.

---

## Summary

| Cycle | Focus | Files Modified | Individual Fixes |
| --- | --- | --- | --- |
| 1 | Cross-references and links | 28 | 31 |
| 2 | Method signature consistency | 2 | 13 |
| 3 | Configuration parameter consistency | 3 | 7 |
| 4 | Naming convention and enum consistency | 8 | ~56 |
| 5 | Completeness and content accuracy | 16 | 19 |
| **Total** | | **~45 unique files** | **~126** |
