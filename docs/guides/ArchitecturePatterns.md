# Multi-Provider Architecture Patterns

Real-world ModelMesh deployment topologies. Each pattern includes a YAML configuration, Python code example, and guidance on when to use it. For configuration details, see [System Configuration](../SystemConfiguration.md). For cost-focused patterns, see [Cost Optimization](CostOptimization.md).

## Pattern 1: Free-Tier Aggregator

Chain 3-4 free-tier providers and rotate automatically when one is exhausted. Ideal for zero-cost prototyping or personal projects.

**When to use:** Hobby projects, prototyping, low-volume internal tools, education.

### Configuration

```yaml
secrets:
  store: modelmesh.env.v1

providers:
  groq.api.v1:
    api_key: ${secrets:GROQ_API_KEY}
  google.gemini.v1:
    api_key: ${secrets:GOOGLE_API_KEY}

models:
  llama-3.3-70b:
    provider: groq.api.v1
    capabilities: [generation.text-generation.chat-completion]
  gemini-1.5-flash:
    provider: google.gemini.v1
    capabilities: [generation.text-generation.chat-completion]

pools:
  chat-completion:
    strategy: modelmesh.rate-limit-aware.v1
    rate_limit:
      threshold: 0.8
    deactivation:
      error_codes: [429]
    recovery:
      cooldown: 60s
      on_quota_reset: true
```

### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

# Automatically uses free tiers, rotates on rate limit
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Explain photosynthesis"}],
)
print(response.choices[0].message.content)
print(f"Provider used: {client.active_providers()}")
print(f"Cost: ${client.usage.total_cost:.6f}")
```

## Pattern 2: Cost Tiering

Route to the cheapest model first. When it fails or is rate limited, escalate to a premium model. Balances cost and reliability.

**When to use:** Startups, budget-conscious teams, workloads where cheaper models are good enough for most requests.

### Configuration

```yaml
secrets:
  store: modelmesh.env.v1

providers:
  deepseek.api.v1:
    api_key: ${secrets:DEEPSEEK_API_KEY}
    budget:
      daily_limit: 2.00
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 10.00

models:
  deepseek-v3:
    provider: deepseek.api.v1
    capabilities: [generation.text-generation.chat-completion]
  gpt-4o:
    provider: openai.llm.v1
    capabilities: [generation.text-generation.chat-completion]

pools:
  chat-completion:
    strategy: modelmesh.priority-selection.v1
    model_priority: [deepseek-v3, gpt-4o]
    retry:
      max_attempts: 2
      backoff: exponential_jitter
      initial_delay: 500ms
```

### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

# DeepSeek handles the request. If it fails, GPT-4o takes over.
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Write a Python quicksort"}],
)
print(response.choices[0].message.content)

# Check which model actually served the request
explanation = client.explain(model="chat-completion")
print(f"Served by: {explanation['selected_model']}")
```

## Pattern 3: Capability Routing

Create separate pools for different capabilities. Chat, embeddings, TTS, and search each route to specialized providers.

**When to use:** Applications with multiple AI capabilities (chatbot + search + voice), where each capability has different provider strengths.

### Configuration

```yaml
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}
  cohere.api.v1:
    api_key: ${secrets:COHERE_API_KEY}

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.audio.text-to-speech
  claude-3-5-sonnet:
    provider: anthropic.claude.v1
    capabilities:
      - generation.text-generation.chat-completion
  embed-english-v3:
    provider: cohere.api.v1
    capabilities:
      - representation.embeddings.text-embeddings
  text-embedding-3-small:
    provider: openai.llm.v1
    capabilities:
      - representation.embeddings.text-embeddings

pools:
  chat-completion:
    strategy: modelmesh.stick-until-failure.v1

  text-embeddings:
    strategy: modelmesh.cost-first.v1

  text-to-speech:
    strategy: modelmesh.stick-until-failure.v1
```

### Python

```python
import modelmesh

# Separate clients for each capability
chat_client = modelmesh.create("chat-completion")
embed_client = modelmesh.create("text-embeddings")
tts_client = modelmesh.create("text-to-speech")

# Chat goes to GPT-4o or Claude
chat_response = chat_client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
)

# Embeddings go to Cohere or OpenAI (cheapest first)
embed_response = embed_client.embeddings.create(
    model="text-embeddings",
    input="Hello world",
)

# TTS goes to OpenAI
tts_response = tts_client.audio.speech.create(
    model="text-to-speech",
    input="Hello world",
)
```

## Pattern 4: Geographic Routing

Route requests to providers based on geographic region. EU users hit EU-compliant providers; US users hit US providers. Useful for data residency compliance.

**When to use:** GDPR compliance, data sovereignty requirements, latency optimization for global users.

### Configuration

```yaml
secrets:
  store: modelmesh.env.v1

providers:
  mistral.api.v1:
    api_key: ${secrets:MISTRAL_API_KEY}
    # Mistral is EU-based (Paris)
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    # OpenAI is US-based

models:
  mistral-large:
    provider: mistral.api.v1
    capabilities: [generation.text-generation.chat-completion]
  gpt-4o:
    provider: openai.llm.v1
    capabilities: [generation.text-generation.chat-completion]

pools:
  chat-eu:
    capability: generation.text-generation.chat-completion
    providers: [mistral.api.v1]
    strategy: modelmesh.stick-until-failure.v1

  chat-us:
    capability: generation.text-generation.chat-completion
    providers: [openai.llm.v1]
    strategy: modelmesh.stick-until-failure.v1

  chat-global:
    capability: generation.text-generation.chat-completion
    strategy: modelmesh.latency-first.v1
```

### Python

```python
import modelmesh

def get_chat_client(user_region: str):
    """Select pool based on user's region."""
    if user_region in ("EU", "EEA", "UK"):
        return modelmesh.create("chat-eu")
    elif user_region == "US":
        return modelmesh.create("chat-us")
    else:
        return modelmesh.create("chat-global")

# Route based on user region
client = get_chat_client(user_region="EU")
response = client.chat.completions.create(
    model="chat-eu",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
# -> Routed to Mistral (EU-based)
```

## Pattern 5: A/B Testing

Split traffic between two models to compare quality, latency, or cost. Use round-robin for even splits or load-balanced for weighted distribution.

**When to use:** Evaluating new models before full rollout, comparing provider quality, benchmarking latency.

### Configuration

```yaml
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities: [generation.text-generation.chat-completion]
  claude-3-5-sonnet:
    provider: anthropic.claude.v1
    capabilities: [generation.text-generation.chat-completion]

pools:
  chat-ab-test:
    capability: generation.text-generation.chat-completion
    strategy: modelmesh.round-robin.v1
```

### Python

```python
import modelmesh
from modelmesh import Middleware

class ABTestMiddleware(Middleware):
    """Log which model served each request for A/B analysis."""
    def __init__(self):
        self.results = []

    async def after_response(self, response, context):
        self.results.append({
            "model": context.model_id,
            "provider": context.provider_id,
            "tokens": response.usage.total_tokens if response.usage else 0,
            "latency_ms": context.metadata.get("latency_ms", 0),
        })
        return response

ab_tracker = ABTestMiddleware()
client = modelmesh.create("chat-ab-test", middleware=[ab_tracker])

# Run test queries
prompts = [
    "Explain recursion",
    "Write a sorting algorithm",
    "Describe machine learning",
    "What is a neural network",
]

for prompt in prompts:
    response = client.chat.completions.create(
        model="chat-ab-test",
        messages=[{"role": "user", "content": prompt}],
    )

# Analyze results
for i, result in enumerate(ab_tracker.results):
    print(f"Query {i+1}: {result['model']} ({result['provider']}), "
          f"{result['tokens']} tokens")
```

## Pattern 6: Canary Deployment

Route a small percentage of traffic to a new model while keeping most traffic on the stable model. Validate the new model in production before full rollout.

**When to use:** Deploying a new model version, testing a new provider, gradual migration between models.

### Configuration

```yaml
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities: [generation.text-generation.chat-completion]
  gpt-4o-2025-preview:
    provider: openai.llm.v1
    capabilities: [generation.text-generation.chat-completion]

pools:
  chat-completion:
    strategy: modelmesh.load-balanced.v1
    balance_mode: absolute
```

### Python

```python
import modelmesh
import random
from modelmesh import Middleware

class CanaryMiddleware(Middleware):
    """Route 5% of traffic to canary, 95% to stable."""
    def __init__(self, canary_pct: float = 0.05):
        self.canary_pct = canary_pct
        self.canary_count = 0
        self.stable_count = 0

    async def before_request(self, request, context):
        is_canary = random.random() < self.canary_pct
        context.metadata["is_canary"] = is_canary
        if is_canary:
            self.canary_count += 1
        else:
            self.stable_count += 1
        return request

    async def after_response(self, response, context):
        tag = "CANARY" if context.metadata.get("is_canary") else "STABLE"
        print(f"[{tag}] {context.model_id}: {response.usage.total_tokens} tokens")
        return response

canary = CanaryMiddleware(canary_pct=0.05)
client = modelmesh.create("chat-completion", middleware=[canary])

for i in range(100):
    client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": f"Test query {i}"}],
    )
print(f"Canary: {canary.canary_count}, Stable: {canary.stable_count}")
```

## Pattern 7: Fallback Chain

Primary provider handles all traffic. On failure, fall back to a secondary cloud provider. If all cloud providers are down, fall back to a local model (Ollama).

**When to use:** Mission-critical applications requiring maximum uptime, air-gapped fallback, disaster recovery.

### Configuration

```yaml
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}
  ollama.local.v1:
    base_url: http://localhost:11434

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities: [generation.text-generation.chat-completion]
  claude-3-5-sonnet:
    provider: anthropic.claude.v1
    capabilities: [generation.text-generation.chat-completion]
  llama-3.2-local:
    provider: ollama.local.v1
    capabilities: [generation.text-generation.chat-completion]

pools:
  chat-completion:
    strategy: modelmesh.priority-selection.v1
    model_priority: [gpt-4o, claude-3-5-sonnet, llama-3.2-local]
    deactivation:
      retry_limit: 2
      error_codes: [429, 500, 502, 503]
    recovery:
      cooldown: 30s
      probe_interval: 60s
    retry:
      max_attempts: 1
      backoff: fixed
      initial_delay: 500ms
```

### Python

```python
import modelmesh
from modelmesh.exceptions import AllProvidersExhaustedError

client = modelmesh.create("chat-completion")

try:
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print(response.choices[0].message.content)

    # Show which provider served the request
    explanation = client.explain(model="chat-completion")
    print(f"Served by: {explanation['selected_model']}")
except AllProvidersExhaustedError:
    print("All providers (cloud and local) are unavailable")

# Inspect the fallback chain
print(client.describe())
# Pool "chat-completion" (strategy: priority-selection)
#   -> gpt-4o [openai.llm.v1] (active)
#      claude-3-5-sonnet [anthropic.claude.v1] (active)
#      llama-3.2-local [ollama.local.v1] (active)
```

## Pattern Summary

| Pattern | Strategy | Providers | Key Benefit |
|---------|----------|-----------|-------------|
| Free-Tier Aggregator | `rate-limit-aware` | 2-4 free-tier | Zero cost |
| Cost Tiering | `priority-selection` | Cheap + Premium | Cost/quality balance |
| Capability Routing | Mixed per pool | Specialized | Best provider per task |
| Geographic Routing | Per-region pools | Region-specific | Data compliance |
| A/B Testing | `round-robin` | 2 candidates | Model comparison |
| Canary Deployment | `load-balanced` + middleware | Stable + New | Safe rollout |
| Fallback Chain | `priority-selection` | Cloud + Local | Maximum uptime |

## Combining Patterns

Patterns are composable. A production deployment might combine several:

```yaml
pools:
  # Pattern 2 + 7: Cost tiering with local fallback
  chat-completion:
    strategy: modelmesh.priority-selection.v1
    model_priority: [deepseek-v3, gpt-4o, llama-3.2-local]

  # Pattern 3: Separate embeddings pool
  text-embeddings:
    strategy: modelmesh.cost-first.v1

  # Pattern 1: Free tier for non-critical tasks
  chat-internal:
    strategy: modelmesh.rate-limit-aware.v1
    providers: [groq.api.v1, google.gemini.v1]
```

---

See also: [Cost Optimization](CostOptimization.md) · [Production Guide](ProductionGuide.md) · [System Configuration](../SystemConfiguration.md) · [Connector Catalogue](../ConnectorCatalogue.md)
