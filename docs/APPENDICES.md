# ModelMesh Lite — Appendices

> Reference material for [ModelMesh Lite](README.md).

---

## Appendix A — Model Capability Hierarchy

```
capability
│
├── generation
│   ├── text-generation
│   │   ├── chat-completion
│   │   ├── text-completion
│   │   └── code-generation
│   ├── structured-generation
│   │   ├── json-generation
│   │   ├── schema-constrained-output
│   │   └── function-call-generation
│   ├── image-generation
│   │   ├── text-to-image
│   │   ├── image-to-image
│   │   └── inpainting
│   ├── audio-generation
│   │   ├── text-to-speech
│   │   └── music-generation
│   └── video-generation
│       ├── text-to-video
│       └── image-to-video
│
├── understanding
│   ├── text-understanding
│   │   ├── summarization
│   │   ├── classification
│   │   ├── sentiment-analysis
│   │   └── entity-extraction
│   ├── vision-understanding
│   │   ├── image-captioning
│   │   ├── object-detection
│   │   └── ocr
│   ├── audio-understanding
│   │   ├── speech-to-text
│   │   ├── speaker-identification
│   │   └── audio-classification
│   └── document-understanding
│       ├── document-parsing
│       ├── table-extraction
│       └── form-extraction
│
├── transformation
│   ├── translation
│   ├── rewriting
│   ├── style-transfer
│   ├── image-editing
│   │   ├── background-removal
│   │   ├── upscaling
│   │   └── format-conversion
│   └── audio-processing
│       ├── noise-reduction
│       ├── voice-cloning
│       └── audio-separation
│
├── representation
│   ├── embeddings
│   │   ├── text-embeddings
│   │   ├── image-embeddings
│   │   └── multimodal-embeddings
│   ├── tokenization
│   └── feature-extraction
│
├── retrieval
│   ├── search
│   │   ├── semantic-search
│   │   ├── web-search
│   │   ├── image-search
│   │   └── code-search
│   ├── knowledge-graph
│   │   ├── graph-query
│   │   ├── entity-linking
│   │   └── relation-extraction
│   ├── rag
│   │   ├── retrieval-augmented-generation
│   │   └── grounded-generation
│   └── reranking
│
├── interaction
│   ├── tool-calling
│   ├── agent-execution
│   │   ├── single-step-agent
│   │   └── multi-step-agent
│   └── multi-turn-conversation
│
└── evaluation
    ├── content-moderation
    ├── toxicity-detection
    ├── factuality-checking
    └── quality-scoring
```

---

## Appendix B — Predefined Capability Pools

| Pool                    | Hierarchy Node                                   | Input → Output |
| ----------------------- | ------------------------------------------------ | -------------- |
| `text-generation`       | generation.text-generation                       | prompt → text  |
| `structured-generation` | generation.structured-generation                 | prompt → JSON  |
| `image-generation`      | generation.image-generation                      | prompt → image |
| `embeddings`            | representation.embeddings                        | text → vector  |
| `speech-to-text`        | understanding.audio-understanding.speech-to-text | audio → text   |
| `text-to-speech`        | generation.audio-generation.text-to-speech       | text → audio   |
| `vision-understanding`  | understanding.vision-understanding               | image → text   |

---

## Appendix C — Model Attribute Reference

### Batch Processing Attributes

| Attribute                 | Description                              |
| ------------------------- | ---------------------------------------- |
| `batch.supported`         | model accepts batch submissions          |
| `batch.max_items`         | maximum requests per batch               |
| `batch.max_payload`       | maximum total batch size                 |
| `batch.completion_window` | expected turnaround (e.g., 24h)          |
| `batch.callback`          | supports webhook notification            |
| `batch.polling`           | supports status polling                  |
| `batch.partial_results`   | can return completed items early         |
| `batch.cost_discount`     | batch pricing vs synchronous (e.g., 50%) |

### Feature Attributes

`structured_output`, `tool_calling`, `system_prompt`, `json_mode`, `grounding`, `fine_tunable`, `logprobs`

### Constraint Attributes

`context_window`, `max_output_tokens`, `max_images`, `max_file_size`, `supported_languages`

### Capability + Delivery Matrix

| Capability         | Sync | Stream | Batch |
| ------------------ | ---- | ------ | ----- |
| chat-completion    | yes  | yes    | yes   |
| text-to-image      | yes  | —      | yes   |
| text-embeddings    | yes  | —      | yes   |
| speech-to-text     | yes  | —      | yes   |
| text-to-speech     | yes  | yes    | yes   |
| document-parsing   | yes  | —      | yes   |
| web-search         | yes  | —      | —     |
| content-moderation | yes  | —      | yes   |

### Model Schema Example

```yaml
Model: GPT-4o (OpenAI)
  capability:
    - generation.text-generation.chat-completion
    - generation.structured-generation.json-generation
    - understanding.vision-understanding.image-captioning
    - interaction.tool-calling
  delivery:
    synchronous: yes
    streaming: yes
    batch: { supported: yes, max_items: 50000, completion_window: 24h, cost_discount: 0.5 }
  features:
    structured_output: yes, tool_calling: yes, system_prompt: yes, json_mode: yes, fine_tunable: yes
  constraints:
    context_window: 128000, max_output_tokens: 16384, max_images: 20
```

---

## Appendix D — Provider Infrastructure Capabilities

| Category             | Examples                                             |
| -------------------- | ---------------------------------------------------- |
| **Discovery**        | enumerate models, query model details                |
| **Quota & Usage**    | query current quota, usage history, remaining budget |
| **Pricing**          | query model pricing, batch discounts                 |
| **Batch Operations** | submit, cancel, query status, retrieve results       |
| **File Management**  | upload, list, delete files                           |
| **Fine-Tuning**      | create job, monitor training, deploy                 |
| **Authentication**   | API key, OAuth, service account                      |

**Routing integration:** `enumerate_models` → auto-discover at startup; `query_current_quota` → proactive rotation; `query_pricing` → cost-first strategy; `batch.supported` → batch-only routing; `files.upload` → document workflows.

---

## Appendix E — Provider Schema Examples

### OpenAI

```yaml
authentication: { method: api_key, key_rotation: yes }
quota: { query_current: yes, query_remaining: yes, reset_schedule: monthly }
pricing: { per_token: yes, batch_discount: 0.5 }
discovery: { enumerate_models: yes, model_details: yes }
batch: { supported: yes, max_items: 50000 }
files: { upload: yes, list: yes, delete: yes, max_size: 512MB }
fine_tuning: { supported: yes, monitor: yes, deploy: yes }
```

### HuggingFace Inference API

```yaml
authentication: { method: api_key }
quota: { query_current: partial, reset_schedule: rolling }
pricing: { free_tier: yes }
discovery: { enumerate_models: yes, capability_query: yes }
batch: { supported: no }
files: { upload: yes (Hub) }
fine_tuning: { supported: yes (AutoTrain) }
```

---

## Appendix F — Per-Pool Rotation Policy Attributes

### Deactivation (Active → Standby)

**Error-based triggers:**

| Attribute              | Description                                  | Example           |
| ---------------------- | -------------------------------------------- | ----------------- |
| `retry_limit`          | consecutive failures before deactivation     | `3`               |
| `error_rate_threshold` | error rate over sliding window               | `0.5`             |
| `error_codes`          | HTTP codes that count as deactivation-worthy | `[429, 500, 503]` |

**Request-count-based triggers:**

| Attribute              | Description                                            | Example  |
| ---------------------- | ------------------------------------------------------ | -------- |
| `request_limit`        | max requests before deactivation (e.g., free-tier cap) | `1000`   |
| `token_limit`          | max tokens before deactivation                         | `500000` |
| `budget.daily_limit`   | daily spend cap                                        | `5.00`   |
| `budget.monthly_limit` | monthly spend cap                                      | `50.00`  |

**Time-based triggers:**

| Attribute            | Description                          | Example           |
| -------------------- | ------------------------------------ | ----------------- |
| `quota_window`       | deactivate when quota period expires | `monthly`         |
| `maintenance_window` | scheduled deactivation periods       | `cron: 0 2 * * 0` |

### Recovery (Standby → Active)

| Attribute                | Description                                | Example                |
| ------------------------ | ------------------------------------------ | ---------------------- |
| `cooldown`               | time from deactivation before reactivation | `60s`                  |
| `probe_on_start`         | test standby models at library startup     | `true`                 |
| `probe_interval`         | periodically test standby models           | `300s`                 |
| `recover_on_quota_reset` | reactivate on provider quota reset         | `true`                 |
| `quota_reset_schedule`   | calendar schedule for quota resets         | `monthly`, `daily_utc` |

### Selection (Among Active Models)

**Rate-limit-aware** switches models preemptively when usage approaches a configurable threshold (`rate_limit.threshold`), with no deactivation, just a proactive switch. **Load-balanced** distributes requests by rate-limit headroom: `absolute` mode distributes evenly across models; `relative` mode distributes proportionally to each model's known limit. Both use provider-reported rate data when available, falling back to local counting.

| Attribute              | Description                                          | Example                   |
| ---------------------- | ---------------------------------------------------- | ------------------------- |
| `strategy`             | selection strategy                                   | `cost-first`              |
| `model_priority`       | ordered model preference list                        | `[gpt-4o, claude-sonnet]` |
| `provider_priority`    | ordered provider preference list                     | `[openai, anthropic]`     |
| `fallback_strategy`    | strategy after priority list exhausted               | `cost-first`              |
| `allowed_providers`    | restrict pool to these providers                     | `[openai, anthropic]`     |
| `excluded_providers`   | block these providers from pool                      | `[huggingface]`           |
| `rate_limit.min_delta` | minimum time between requests to the same model      | `200ms`                   |
| `rate_limit.max_rpm`   | max requests per minute before switching models      | `60`                      |
| `rate_limit.threshold` | switch at this fraction of limit (0.0–1.0)           | `0.8`                     |
| `balance_mode`         | load-balance distribution: `absolute` or `relative`  | `relative`                |

### Retry (Before Rotation)

| Attribute                | Description                                        | Example                    |
| ------------------------ | -------------------------------------------------- | -------------------------- |
| `retry.max_attempts`     | retries on same model before rotating              | `2`                        |
| `retry.backoff`          | backoff strategy                                   | `exponential_jitter`       |
| `retry.initial_delay`    | first retry delay                                  | `500ms`                    |
| `retry.max_delay`        | maximum backoff delay                              | `10s`                      |
| `retry.retryable_codes`  | HTTP codes eligible for retry                      | `[429, 500, 502, 503]`    |
| `retry.non_retryable`    | HTTP codes that skip retry and rotate immediately  | `[400, 401, 403, 404]`    |
| `retry.scope`            | retry scope: `same_model`, `same_provider`, `any`  | `same_model`               |
| `retry.honor_retry_after`| use provider's Retry-After header when present     | `true`                     |

### Provider-Level Actions

| Attribute               | Description                                          | Example                            |
| ----------------------- | ---------------------------------------------------- | ---------------------------------- |
| `provider_deactivation` | deactivate all models of a provider across all pools | `on_auth_failure`, `on_api_outage` |
| `provider_recovery`     | reactivate all models when provider recovers         | `on_probe_success`, `on_manual`    |

---

## Appendix G — Pre-shipped Connectors

Full connector catalogue with descriptions, free-tier limits, and provider links: **[ConnectorCatalogue.md](ConnectorCatalogue.md)**.

Connector types: provider connectors (AI model providers, web API services), storage, secret stores, observability, discovery, and rotation policies.

---

## Appendix H — Configuration and API Examples

### YAML Configuration

```yaml
secrets:
  store: aws-secrets-manager
  region: us-east-1

providers:
  openai:
    enabled: true
    api_key: ${secrets:openai-api-key}
    budget: { daily_limit: 5.00 }
  huggingface:
    enabled: true
    api_key: ${secrets:hf-api-key}

pools:
  text-generation:
    strategy: cost-first
    retry_limit: 3
    cooldown: 60s
  image-generation:
    strategy: stick-until-failure
    provider_priority: [huggingface, openrouter, openai]
  code-review:
    hierarchy_node: generation.text-generation.code-generation
    strategy: priority-selection
    provider_priority: [openai]
    fallback_strategy: cost-first

state:
  connector: local-file
  path: ./mesh-state.json
  sync_policy: sync-on-boundary
```

### Programmatic API

```python
mesh = ModelMesh.from_yaml("config.yaml")
mesh.pools["text-generation"].strategy = "latency-first"  # runtime override
mesh.add_provider("anthropic", api_key="...")              # dynamic addition
```

### Configuration Persistence

```python
mesh.save_config(connector="local-file", path="config.yaml")
mesh = ModelMesh.from_storage(connector="s3", bucket="my-configs", key="mesh.yaml")
```

### Custom Connectors

```python
# Provider
class MyProvider(ProviderConnector):
    def complete(self, request): ...
    def check_quota(self): ...
mesh.add_provider("my-provider", connector=MyProvider(...))

# Secret store
class VaultStore(SecretStore):
    def get(self, name): ...
mesh = ModelMesh.from_yaml("config.yaml", secret_store=VaultStore(...))

# Storage
class PgStorage(StorageConnector):
    def load(self): ...
    def save(self, data): ...
mesh.configure_state(connector=PgStorage(...), sync_policy="sync-on-boundary")
```

### Secrets CLI

```bash
modelmesh secrets set openai-api-key "sk-..." --store aws-secrets-manager
modelmesh secrets import .env --store aws-secrets-manager
modelmesh secrets list --store aws-secrets-manager
```

### State Serialization

```python
snapshot = mesh.export_state()           # export
save_to_database(snapshot)
mesh.import_state(load_from_database())  # restore
```

### Routing Pipeline Example

```
Request: "parse 500 invoice PDFs, return structured JSON"

1. Capability resolution     → document-understanding.document-parsing
2. Pool selection            → models at document-parsing leaf
3. Delivery mode filter      → batch-capable models on batch-capable providers only
4. Provider state filter     → exclude standby providers
5. Strategy application      → cost-first → Claude Sonnet (Anthropic)
6. Intelligent retry         → on transient failure, retry with backoff → rotate to GPT-4o (OpenAI)
```

---

## Appendix I — Observability Reference

### Routing Decision Record

Fields: requested capability, resolved pool, selected model/provider, delivery mode, replaced provider, rotation reason, fallback chain, routing latency.

### Logging Levels

- **metadata** — timestamps, model, provider, token counts, latency, status
- **summary** — metadata + truncated prompt/response
- **full** — metadata + complete payloads

### Aggregate Metrics

| Metric                                                  | Scope           |
| ------------------------------------------------------- | --------------- |
| `requests_total`, `requests_success`, `requests_failed` | model, provider |
| `tokens_in`, `tokens_out`, `cost_total`                 | model, provider |
| `latency_avg`, `latency_p95`                            | model, provider |
| `downtime_total`, `standby_events`, `quota_resets`      | provider        |
| `rotation_events`                                       | pool            |

### Statistics API

```python
stats = mesh.stats()
stats.provider("openai").requests_total   # 1,284
stats.provider("openai").cost_total       # $4.27
stats.model("gpt-4o").latency_p95         # 1.8s
stats.pool("text-generation").rotation_events  # 7
```

### Configuration

```yaml
observability:
  routing_decisions: { connector: webhook, url: https://my-app.com/hooks/mesh }
  request_logging: { level: metadata, connector: local-file, path: ./requests.jsonl }
  statistics: { connector: local-file, path: ./stats.json, flush_interval: 60s }
```

---

## Appendix J — AI API Provider Reference

Full provider catalogue with key models, capabilities, free-tier limits, and documentation links: **[ConnectorCatalogue.md](ConnectorCatalogue.md#ai-model-providers)**.
