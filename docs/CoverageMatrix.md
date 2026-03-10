---
layout: default
title: "Test Coverage Matrix"
---

# Test Coverage Matrix

Correlates documented features with test coverage. The project includes 855 Python tests across 15 test files and 511 TypeScript tests across 13 test files, for a total of 1,366 tests.

---

## Summary

| Component | Tests | Test File | Status |
| --- | ---: | --- | --- |
| Interfaces (data types, ABCs) | 22 | `test_interfaces.py` | Covered |
| Core (Pool, Tree, Emitter, State) | 39 | `test_core.py` | Covered |
| Router | 9 | `test_router.py` | Covered |
| ModelMesh facade | 23 | `test_mesh.py` | Covered |
| MeshClient (OpenAI compat) | 12 | `test_client.py` | Covered |
| Config + Auto-detect | 19 | `test_config.py` | Covered |
| `modelmesh.create()` | 8 | `test_create.py` | Covered |
| CDK Base Classes | 50 | `test_cdk.py` | Covered |
| Observability Stack | 26 | `test_observability.py` | Covered |
| Pre-shipped Connectors | 32 | `test_connectors.py` | Covered |
| New Connectors (local providers, browser) | 93 | `test_new_connectors.py` | Covered |
| CDK Specialized + Mixins + Helpers | 97 | `test_specialized.py` | Covered |
| Local Provider Connectors | 28 | `test_providers.py` | Covered |
| Proxy Server + Docker Infrastructure | 80 | `test_docker.py` | Covered |
| **Total** | **855** | **15 files** | |

### TypeScript Test Suite

| Component | Tests | Test File | Status |
| --- | ---: | --- | --- |
| Interfaces (data types, factories, enums) | 12 | `interfaces.test.ts` | Covered |
| CapabilityTree | 9 | `capability-tree.test.ts` | Covered |
| EventEmitter | 10 | `event-emitter.test.ts` | Covered |
| StateManager | 16 | `state-manager.test.ts` | Covered |
| CapabilityPool | 15 | `pool.test.ts` | Covered |
| ModelMesh facade | 16 | `mesh.test.ts` | Covered |
| Router | 5 | `router.test.ts` | Covered |
| Pre-shipped Connectors + Cloud/Local Providers + RuntimeEnvironment + Registry + Runtime Guard + Docker Infrastructure | 230 | `connectors.test.ts` | Covered |
| MeshConfig + Auto-detect + LOCAL_PROVIDER_REGISTRY | 30 | `config.test.ts` | Covered |
| MeshClient (OpenAI compat) | 16 | `client.test.ts` | Covered |
| Secret Stores (env, dotenv, json, memory, encrypted, keyring) | 55 | `secret-stores.test.ts` | Covered |
| CORS Proxy | 12 | `proxy.test.ts` | Covered |
| **Total** | **511** | **13 files** | |

---

## Feature-to-Test Mapping

### 1. Interfaces (`docs/interfaces/`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| Severity enum (5 levels) | `Observability.md`, `Enums.md` | `TestSeverityEnum` (4 tests) | All values, ordering, string conversion |
| TraceEntry dataclass | `Observability.md` | `TestTraceEntry` (5 tests) | Creation, defaults, metadata, error field |
| CompletionRequest | `Provider.md` | `TestCompletionRequest` (3 tests) | Creation, defaults, all fields |
| CompletionResponse | `Provider.md` | `TestCompletionResponse` (2 tests) | Creation, defaults |
| ModelInfo | `Provider.md` | `TestModelInfo` (3 tests) | Creation, defaults, pricing |
| TokenUsage | `Provider.md` | `TestTokenUsage` (2 tests) | Defaults, total_tokens |
| ModelState | `RotationPolicy.md` | `TestModelState` (3 tests) | Creation, defaults, standby status |
| ObservabilityConnector ABC | `Observability.md` | `TestObservabilityConnectorABC` (2 tests) | Complete impl, missing methods |
| RoutingEvent | `Observability.md` | `TestRoutingEvent` (2 tests) | Creation, metadata default |
| ErrorClassification | `Provider.md` | `TestErrorClassification` (2 tests) | Defaults, retryable flag |

### 2. Core System (`docs/system/`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| CapabilityTree register/resolve | `CapabilityTree.md` | `TestCapabilityTree` (9 tests) | Register, resolve, parent resolution, leaves, paths, contains |
| EventEmitter pub/sub | `EventEmitter.md` | `TestEventEmitter` (7 tests) | Emit, multiple handlers, wildcard, off, clear |
| PoolModel dataclass | `CapabilityPool.md` | `TestPoolModel` (2 tests) | Defaults, to_model_state |
| CapabilityPool lifecycle | `CapabilityPool.md` | `TestCapabilityPool` (17 tests) | Add/remove/select/rotate/deactivate/reactivate, status, failure recording |
| Pool observability traces | `CapabilityPool.md` | `test_deactivation_emits_error_trace`, `test_failure_emits_warning_trace` | Trace emission on failure/deactivation |
| StateManager | `StateManager.md` | `TestStateManager` (10 tests) | Get/create, activate/deactivate, record success/failure, dirty tracking, reset |

### 3. Router (`docs/system/Router.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| Route to correct pool | `Router.md` | `test_route_to_correct_pool` | Pool resolution by virtual model name |
| Pool resolution | `Router.md` | `test_resolve_pool_direct` | Direct pool lookup |
| Unknown pool error | `Router.md` | `test_route_unknown_pool_raises` | KeyError on invalid pool |
| No active model error | `Router.md` | `test_no_active_model_raises` | NoActiveModelError |
| Retry with rotation | `Router.md` | `test_rotation_on_failure` | Automatic rotation on provider failure |
| Max retries exhausted | `Router.md` | `test_max_retries_exhausted` | Gives up after max_retries |
| Streaming route | `Router.md` | `test_streaming_route` | Async generator streaming |
| Observability traces | `Router.md` | `test_route_emits_traces`, `test_failure_emits_error_trace` | DEBUG/INFO/WARNING/ERROR traces |

### 4. ModelMesh Facade (`docs/system/ModelMesh.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| Initialize from config | `ModelMesh.md` | `test_initialize` | MeshConfig -> initialized state |
| Get client before init | `ModelMesh.md` | `test_get_client_before_init_raises` | RuntimeError guard |
| Get OpenAI-compatible client | `ModelMesh.md` | `test_get_client_returns_mesh_client` | Returns MeshClient |
| Pool/provider properties | `ModelMesh.md` | `test_pools_property`, `test_providers_property` | Dict accessors |
| Pool status | `ModelMesh.md` | `test_pool_status` | Health status reporting |
| Active providers | `ModelMesh.md` | `test_active_providers` | Provider enumeration |
| List models | `ModelMesh.md` | `test_list_models` | OpenAI /v1/models shape |
| Rotate | `ModelMesh.md` | `test_rotate`, `test_rotate_unknown_pool_raises` | Force rotation |
| Shutdown | `ModelMesh.md` | `test_shutdown` | Graceful shutdown |
| Null observability default | `ConnectorCatalogue.md` | `test_null_observability_default` | Defaults to NullObservabilityConnector |
| File observability config | `ConnectorCatalogue.md` | `test_file_observability_config` | File obs writes traces |
| Initialize emits trace | `ConnectorCatalogue.md` | `test_initialize_emits_trace` | "Initialized" trace in log file |
| Event emitter property | `EventEmitter.md` | `test_event_emitter_property` | Accessor |
| State manager property | `StateManager.md` | `test_state_manager_property` | Accessor |
| Capability tree property | `CapabilityTree.md` | `test_capability_tree_property` | Accessor |
| Capability auto-discovery from provider | `ConnectorCatalogue.md` | `test_capabilities_from_provider_when_config_omits` | Provider `list_models()` fallback |
| Config capabilities override provider | `ConnectorCatalogue.md` | `test_config_capabilities_override_provider` | Config wins over provider |
| Provider caps register in tree | `ConnectorCatalogue.md` | `test_provider_caps_register_in_tree` | Tree registration via auto-discovery |
| No provider instance → empty caps | `ConnectorCatalogue.md` | `test_no_provider_instance_yields_empty_caps` | Stub provider graceful handling |
| Explicit models in pool | `ConnectorCatalogue.md` | `test_explicit_models_in_pool` | Pool `models` list definition |
| Hybrid pool (capability + explicit) | `ConnectorCatalogue.md` | `test_hybrid_pool_capability_plus_explicit` | Both capability matching and explicit list |

### 5. MeshClient (`docs/system/OpenAIClient.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| chat.completions.create() | `OpenAIClient.md` | `test_chat_completion_create` | Sync chat completion |
| chat namespace | `OpenAIClient.md` | `test_has_chat_namespace` | Namespace structure |
| embeddings namespace | `OpenAIClient.md` | `test_has_embeddings_namespace` | Namespace structure |
| models.list() | `OpenAIClient.md` | `test_models_list`, `test_models_list_entry_shape` | OpenAI-compatible model listing |
| pool_status() | -- | `test_pool_status`, `test_pool_status_specific_pool`, `test_pool_status_unknown_pool_raises` | ModelMesh extension |
| active_providers() | -- | `test_active_providers` | ModelMesh extension |
| rotate() | -- | `test_rotate` | ModelMesh extension |
| mesh property | -- | `test_mesh_property` | Access underlying ModelMesh |

### 6. Config + Auto-detect (`docs/SystemConfiguration.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| MeshConfig from dict | `SystemConfiguration.md` | `test_from_dict` | Dict -> MeshConfig |
| MeshConfig properties | `SystemConfiguration.md` | `test_providers_property`, `test_models_property`, `test_pools_property`, `test_observability_property`, `test_storage_property`, `test_secrets_property` | Section accessors |
| Config merge | `SystemConfiguration.md` | `test_merge` | Deep merge |
| Config validation | `SystemConfiguration.md` | `test_validate_valid`, `test_validate_invalid_providers` | Structural validation |
| Provider auto-detection | `SystemConfiguration.md` | `TestAutoDetect` (9 tests) | Env var scanning, filtering, API key override |
| PROVIDER_REGISTRY | `ConnectorCatalogue.md` | `test_provider_registry_has_9_providers` | 9 pre-configured providers |

### 7. Convenience Layer (`docs/cdk/ConvenienceLayer.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| modelmesh.create() basic | `ConvenienceLayer.md` | `test_create_returns_mesh_client` | Returns MeshClient |
| create() with pool | `ConvenienceLayer.md` | `test_create_with_pool` | Pool-based creation |
| create() with config dict | `ConvenienceLayer.md` | `test_create_with_config_dict` | Layer 2 creation |
| create() with MeshConfig | `ConvenienceLayer.md` | `test_create_with_mesh_config_object` | Layer 2 creation |
| create() no args error | `ConvenienceLayer.md` | `test_create_no_args_raises` | ValueError guard |
| create() no providers error | `ConvenienceLayer.md` | `test_create_capabilities_no_providers_raises` | ValueError guard |
| create() invalid config type | `ConvenienceLayer.md` | `test_create_invalid_config_type_raises` | TypeError guard |
| create() with observability | `ConvenienceLayer.md` | `test_create_with_observability` | Observability config in auto-config |

### 8. CDK Base Classes (`docs/cdk/BaseClasses.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| BaseProvider config | `BaseClasses.md` | 21 tests in `TestBaseProvider` | Headers, endpoint, payload, models, pricing, quota, rate limits, error classification |
| BaseRotation policies | `BaseClasses.md` | 15 tests in `TestBaseRotation` | Deactivation (5 thresholds), recovery (cooldown), selection (priority) |
| BaseSecretStore | `BaseClasses.md` | 5 tests in `TestBaseSecretStore` | Resolve, caching, missing key handling |
| BaseStorage | `BaseClasses.md` | 9 tests in `TestBaseStorage` | Save/load, delete, exists, list, stat, locking |

### 9. Observability Stack (`docs/interfaces/Observability.md`, `docs/cdk/BaseClasses.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| NullObservabilityConnector | `ConnectorCatalogue.md` | `TestNullObservability` (5 tests) | All methods are no-ops |
| FileObservability JSON-Lines | `ConnectorCatalogue.md` | `TestFileObservability` (11 tests) | Write, append, rotation, severity filter, redaction |
| ConsoleObservability | `ConnectorCatalogue.md` | `TestConsoleObservability` (4 tests) | Color/no-color, severity filter, emit |
| BaseObservability severity | `BaseClasses.md` | `TestBaseObservabilitySeverityOrder` (3 tests) | Severity ordering, min_severity, redaction |
| Integration: mesh traces | -- | `test_full_lifecycle_traces` | End-to-end trace capture |
| Integration: pool deactivation | -- | `test_pool_deactivation_trace` | ERROR trace on model deactivation |

### 10. Pre-shipped Connectors (`docs/ConnectorCatalogue.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| CONNECTOR_REGISTRY (38 Python / 42 TS entries) | `ConnectorCatalogue.md` | `test_has_expected_connectors`, `test_all_have_connector_id` | Registry completeness |
| OpenAI Provider | `connectors/openai-llm.md` | `TestOpenAIProvider` (7 tests) | ID, URL, headers, models, endpoint |
| Anthropic Provider | `connectors/anthropic-llm.md` | `TestAnthropicProvider` (10 tests) | ID, headers, payload, response parsing |
| Env Secret Store | `connectors/modelmesh-env.md` | `TestEnvSecretStoreComprehensive` (7 tests) | ID, resolve, prefix, missing, interface |
| Dotenv Secret Store | `ConnectorCatalogue.md` | `TestDotenvSecretStoreComprehensive` (8 tests) | Parsing, comments, quotes, multiline, env override |
| JSON Secret Store | `ConnectorCatalogue.md` | `TestJsonSecretStoreComprehensive` (8 tests) | Flat, nested, dot-notation, json_path scoping |
| Memory Secret Store | `guides/SecretStores.md` | `TestMemorySecretStore` (12 tests) | CRUD, interface, caching, set invalidation |
| Encrypted File Store | `guides/SecretStores.md` | `TestEncryptedFileSecretStore` (12 tests) | Save/load, passphrase, hex key, round-trip, plaintext check |
| Keyring Secret Store | `ConnectorCatalogue.md` | `TestKeyringSecretStoreComprehensive` (6 tests) | ID, service name, availability, fallback |
| Azure Speech TTS | `ConnectorCatalogue.md` | `TestAzureSpeechProvider` (14 tests) | ID, region, URL, headers, SSML, models, XML escape |
| Ollama Provider | `ConnectorCatalogue.md` | `TestOllamaProvider` (8 tests) | ID, URL, empty API key, 4 default models, capabilities, endpoint, runtime |
| LM Studio Provider | `ConnectorCatalogue.md` | `TestLMStudioProvider` (8 tests) | ID, URL, empty API key, empty models, capabilities, endpoint, runtime |
| vLLM Provider | `ConnectorCatalogue.md` | `TestVLLMProvider` (8 tests) | ID, URL, empty API key, empty models, capabilities, endpoint, runtime |
| LocalAI Provider | `ConnectorCatalogue.md` | `TestLocalAIProvider` (8 tests) | ID, URL, empty API key, empty models, capabilities, endpoint, runtime |
| RuntimeEnvironment metadata | `ConnectorCatalogue.md` | `TestRuntimeEnvironment` (6 tests) | Enum values, classification of BaseProvider, MemoryStorage, MemorySecretStore |
| Stick-Until-Failure | `connectors/modelmesh-stick-until-failure.md` | (via `TestBaseRotation`) | Tested through base rotation tests |
| Local File Storage | `connectors/modelmesh-local-file.md` | (via `TestBaseStorage`) | Tested through base storage tests |

### 11. Browser Provider (`docs/guides/BrowserUsage.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| BrowserBaseProvider construction | `BrowserUsage.md` | `test_browser_provider_config` | Config defaults, proxyUrl |
| Fetch-based complete() | `BrowserUsage.md` | `test_browser_provider_complete` | Fetch API transport |
| Streaming via ReadableStream | `BrowserUsage.md` | `test_browser_provider_stream` | ReadableStream SSE parsing |
| CORS proxy URL prefixing | `BrowserUsage.md` | `test_browser_proxy_url_prefix` | proxyUrl prepended to API URL |
| createBrowser() convenience | `BrowserUsage.md` | `test_create_browser` | Browser-optimized create() |

### 12. Browser Storage & Secret Stores (`docs/ConnectorCatalogue.md`, `docs/guides/BrowserUsage.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| LocalStorageStorage connector ID | `ConnectorCatalogue.md` | `connectors.test.ts` | `modelmesh.localstorage.v1` |
| SessionStorageStorage connector ID | `ConnectorCatalogue.md` | `connectors.test.ts` | `modelmesh.sessionstorage.v1` |
| IndexedDBStorage connector ID | `ConnectorCatalogue.md` | `connectors.test.ts` | `modelmesh.indexeddb.v1` |
| BrowserSecretStore connector ID | `ConnectorCatalogue.md` | `connectors.test.ts` | `modelmesh.browser-secrets.v1` |
| Browser storage RuntimeEnvironment | `ConnectorCatalogue.md` | `connectors.test.ts` | BROWSER_ONLY classification |
| Browser exports (browser.ts) | `BrowserUsage.md` | `browser-provider.test.ts` | All browser connectors exported |

### 13. Audio Interfaces (`docs/ConnectorInterfaces.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| AudioRequest type | `ConnectorInterfaces.md` | `test_audio_request_creation` | Type construction, defaults |
| AudioResponse type | `ConnectorInterfaces.md` | `test_audio_response_creation` | Type construction, defaults |
| client.audio.speech.create() | `ConnectorCatalogue.md` | `test_audio_speech_create` | TTS routing through pool |
| client.audio.transcriptions.create() | `ConnectorCatalogue.md` | `test_audio_transcriptions_create` | STT routing through pool |

### 14. CDK Specialized Classes (`docs/cdk/BaseClasses.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| ThresholdRotationPolicy | `BaseClasses.md` | `TestThresholdRotation` (in `test_specialized.py`) | Threshold-based deactivation/recovery |
| ConsoleObservability | `BaseClasses.md` | `TestConsoleObservability` (in `test_specialized.py`) | ANSI output, severity filtering |
| KeyValueStorage | `BaseClasses.md` | `TestKeyValueStorage` (in `test_specialized.py`) | Memory and file backends |
| FileSecretStore | `BaseClasses.md` | `TestFileSecretStore` (in `test_specialized.py`) | .env, JSON, TOML file loading |
| HttpHealthDiscovery | `BaseClasses.md` | -- | Requires HTTP mock; coverage gap |
| CDK test helpers | `Helpers.md` | `TestConnectorTestHarness`, `TestMockHttpClient` (in `test_specialized.py`) | mockCompletionRequest, mockModelSnapshot, MockHttpClient, ConnectorTestHarness |

### 15. Proxy Server & Docker Deployment (`docs/guides/ProxyGuide.md`)

| Feature | Doc Reference | Test(s) | Notes |
| --- | --- | --- | --- |
| Dockerfile structure | `ProxyGuide.md` | `TestDockerfile` (10 tests) | Base image, COPY, pip install, pyyaml, EXPOSE, ENTRYPOINT |
| docker-compose.yaml | `ProxyGuide.md` | `TestDockerCompose` (7 tests) | Service, port mapping, env_file, config mount |
| modelmesh.yaml config | `ProxyGuide.md` | `TestModelMeshConfig` (10 tests) | Sections, secret refs, no hardcoded keys |
| .env.example template | `ProxyGuide.md` | `TestEnvExample` (5 tests) | Key presence, empty values |
| .gitignore protects secrets | -- | `TestGitignore` (2 tests) | .env and .env.* ignored |
| Automation scripts | `ProxyGuide.md` | `TestScripts` (15 tests) | Existence, content, shebang, strict mode |
| Browser test page | `ProxyGuide.md` | `TestBrowserTestPage` (10 tests) | HTML validity, no deps, fetch API, streaming, SSE |
| Proxy module structure | -- | `TestProxyModuleStructure` (7 tests) | Package, __init__, __main__, server, cli |
| Proxy CLI argument parsing | -- | `TestProxyCLI` (2 tests) | Default and custom args |
| Live proxy HTTP integration | `ProxyGuide.md` | `TestProxyLiveHTTP` (10 tests) | Health, models, chat, streaming, CORS, 400, 404, usage, status tracking |
| ServerStatus dataclass | -- | `TestServerStatus` (3 tests in `test_proxy.py`) | Defaults, custom values, asdict |
| ProxyState status reporting | -- | `TestProxyState` (3 tests in `test_proxy.py`) | Not running, running, counters |
| Bearer token auth | -- | `TestAuthTokenValidation` (4 tests in `test_proxy.py`) | No token, token configured, server stores token |
| /v1/models response shape | -- | `TestModelsEndpoint` (2 tests in `test_proxy.py`) | Pool IDs as models, OpenAI list format |
| Request parsing | -- | `TestRequestParsing` (4 tests in `test_proxy.py`) | Chat completion, streaming, tools, defaults |
| Response serialization | -- | `TestCompletionResponseSerialization` (5 tests in `test_proxy.py`) | Basic, streaming chunk, UUID gen, JSON serializable, tool calls |
| ProxyServer initialization | -- | `TestProxyServerInit` (5 tests in `test_proxy.py`) | MeshConfig, dict, invalid type, status, mesh property |

---

## Coverage Gaps

| Gap | Priority | Notes |
| --- | --- | --- |
| Streaming end-to-end with observability | Low | Streaming routes tested in `test_streaming_route`, but no trace verification for streaming paths |
| YAML config loading (`MeshConfig.from_yaml`) | Low | Dict loading tested; YAML loading requires file I/O |
| Discovery connector | Low | Interface defined, no pre-shipped connector to test |
| Webhook observability connector | Low | Documented in catalogue but not implemented |
| HttpHealthDiscovery | Low | Specialized class exists but no dedicated test (requires HTTP mock) |
| MetricsMixin | Low | Tested indirectly via provider tests |
| Browser provider end-to-end (real fetch) | Low | Unit tests mock fetch; no integration test with actual browser |
| Audio streaming (TTS binary stream) | Low | Audio types tested; binary stream end-to-end not yet covered |

---

## Document-to-Test Traceability

| Document | Features Documented | Tests Covering | Coverage |
| --- | --- | --- | --- |
| `SystemConcept.md` | Architecture overview | All tests collectively | Indirect |
| `ConnectorCatalogue.md` | 42 connectors, IDs, configs | `test_connectors.py` + `test_new_connectors.py` + `test_providers.py` + `connectors.test.ts` | Direct |
| `ConnectorInterfaces.md` | 6 interface ABCs | `test_interfaces.py` (22 tests) | Direct |
| `SystemConfiguration.md` | MeshConfig, auto-detect | `test_config.py` (19 tests) | Direct |
| `ModelCapabilities.md` | Capability tree hierarchy | `TestCapabilityTree` (9 tests) | Direct |
| `SystemServices.md` | Router, Pool, Emitter, State | `test_core.py` + `test_router.py` + `test_mesh.py` (65 tests) | Direct |
| `cdk/BaseClasses.md` | 6 base classes + hooks | `test_cdk.py` (50 tests) | Direct |
| `cdk/ConvenienceLayer.md` | `modelmesh.create()` API | `test_create.py` (8 tests) | Direct |
| `cdk/Enums.md` | All enum definitions | `test_interfaces.py` (Severity, ModelStatus, etc.) | Partial |
| `cdk/DeveloperGuide.md` | Tutorials 1-6 | Covered by CDK + connector tests | Indirect |
| `cdk/Mixins.md` | 5 mixin classes | *(no dedicated tests)* | Gap |
| `cdk/Helpers.md` | Test utilities | *(no dedicated tests)* | Gap |
| `cdk/Overview.md` | CDK architecture | All CDK tests | Indirect |
| `interfaces/Observability.md` | 4 sub-interfaces + types | `test_observability.py` (26 tests) | Direct |
| `interfaces/Provider.md` | Provider ABC + types | `test_interfaces.py` + `test_connectors.py` | Direct |
| `interfaces/RotationPolicy.md` | 3 rotation ABCs | `test_cdk.py::TestBaseRotation` (15 tests) | Direct |
| `interfaces/SecretStore.md` | SecretStore ABC | `test_cdk.py::TestBaseSecretStore` (5 tests) | Direct |
| `interfaces/Storage.md` | Storage ABC | `test_cdk.py::TestBaseStorage` (9 tests) | Direct |
| `interfaces/Discovery.md` | Discovery ABC | *(no dedicated tests)* | Gap |
| `guides/BrowserUsage.md` | BrowserBaseProvider, CORS proxy, createBrowser() | Browser provider tests | Direct |
| `ConnectorInterfaces.md` (Audio) | AudioRequest, AudioResponse, audio namespace | Audio interface tests | Direct |
| `guides/ProxyGuide.md` | Proxy server, Docker, CLI, REST API, browser access | `test_docker.py` (80 tests) + `test_proxy.py` (26 tests) + `connectors.test.ts` Docker section | Direct |
