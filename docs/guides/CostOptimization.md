# Cost Optimization Cookbook

Minimize AI spend with ModelMesh's multi-provider routing, budget enforcement, and cost-first strategies. This guide covers pricing comparisons, free tier stacking, budget configuration, usage tracking, and recommended provider stacks for different budgets. For budget configuration details, see [System Configuration](../SystemConfiguration.md#providers). For production deployment, see the [Production Guide](ProductionGuide.md).

## Provider Pricing Comparison

Approximate pricing per 1 million tokens (as of early 2025). Prices change frequently; check provider dashboards for current rates.

| Provider | Model | Input $/1M | Output $/1M | Free Tier |
|----------|-------|-----------|------------|-----------|
| Groq | Llama 3.3 70B | $0.59 | $0.79 | Yes (rate limited) |
| DeepSeek | DeepSeek-V3 | $0.27 | $1.10 | No |
| Google | Gemini 1.5 Flash | $0.075 | $0.30 | Yes (15 RPM) |
| Mistral | Mistral Small | $0.20 | $0.60 | No |
| OpenAI | GPT-4o mini | $0.15 | $0.60 | No |
| Anthropic | Claude 3.5 Haiku | $0.80 | $4.00 | No |
| OpenAI | GPT-4o | $2.50 | $10.00 | No |
| Anthropic | Claude 3.5 Sonnet | $3.00 | $15.00 | No |

## Free Tier Stacking

Combine multiple providers with free tiers to get substantial free capacity. When one free tier is exhausted, ModelMesh automatically rotates to the next provider.

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
```

### Python

```python
import modelmesh

# Uses free tiers automatically, rotating when rate limited
client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Explain quantum computing"}],
)
print(response.choices[0].message.content)
print(f"Cost: ${client.usage.total_cost:.6f}")
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';

const client = create('chat-completion');

const response = await client.chat.completions.create({
  model: 'chat-completion',
  messages: [{ role: 'user', content: 'Explain quantum computing' }],
});
console.log(response.choices[0].message?.content);
console.log(`Cost: $${client.usage.totalCost.toFixed(6)}`);
```

## Budget Strategies

### Cost-First Rotation

Always route to the cheapest available provider:

```yaml
pools:
  chat-completion:
    strategy: modelmesh.cost-first.v1
```

ModelMesh tracks accumulated cost per model and selects the one with the lowest spend. This naturally distributes load across cheap providers first.

### Daily and Monthly Limits

Set hard spending caps per provider:

```yaml
providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 5.00
      monthly_limit: 100.00

  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}
    budget:
      daily_limit: 5.00
      monthly_limit: 100.00
```

When a provider hits its daily limit, it is deactivated until the next day. Traffic routes to remaining providers.

### Per-Pool Budget Caps

Limit spending at the pool level to control costs per use case:

```yaml
pools:
  chat-completion:
    strategy: modelmesh.cost-first.v1
    deactivation:
      budget_limit: 20.00

  code-generation:
    strategy: modelmesh.priority-selection.v1
    deactivation:
      budget_limit: 50.00
```

### Tiered Cost Strategy

Use cheap models first, escalate to premium only when needed:

```yaml
providers:
  deepseek.api.v1:
    api_key: ${secrets:DEEPSEEK_API_KEY}
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
    fallback_strategy: modelmesh.cost-first.v1
```

DeepSeek handles all requests. If it fails or is rate limited, GPT-4o takes over automatically.

## Usage Tracking

### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

# Make some requests
for question in ["What is AI?", "Explain ML", "Define NLP"]:
    client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": question}],
    )

# Summary
print(f"Total cost:   ${client.usage.total_cost:.4f}")
print(f"Total tokens: {client.usage.total_tokens}")
print(f"Requests:     {client.usage.total_requests}")

# Breakdown by model
for model_id, usage in client.usage.by_model.items():
    print(f"  {model_id}: ${usage.total_cost:.4f} ({usage.total_tokens} tokens)")

# Budget status
status = client.usage.budget_status
if status:
    print(f"Budget used:      ${status.used:.2f}")
    print(f"Budget remaining: ${status.remaining:.2f}")
    print(f"Budget exceeded:  {status.exceeded}")
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';

const client = create('chat-completion');

// Make requests...

console.log(`Total cost:   $${client.usage.totalCost.toFixed(4)}`);
console.log(`Total tokens: ${client.usage.totalTokens}`);
console.log(`Requests:     ${client.usage.totalRequests}`);

for (const [modelId, usage] of Object.entries(client.usage.byModel)) {
  console.log(`  ${modelId}: $${usage.totalCost.toFixed(4)}`);
}
```

### Export Usage to CSV

Track costs over time using the observability logging connector:

```yaml
observability:
  logging:
    connector: modelmesh.local-file.v1
    level: metadata
    path: ./usage.jsonl
```

Each request logs a JSONL record with model, provider, tokens, cost, and latency. Process the file with any data tool:

```python
import json
import csv

with open("usage.jsonl") as f:
    records = [json.loads(line) for line in f if line.strip()]

with open("usage.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "model", "provider", "tokens", "cost"])
    for r in records:
        writer.writerow([
            r.get("timestamp"),
            r.get("model_id"),
            r.get("provider_id"),
            r.get("total_tokens", 0),
            r.get("cost", 0),
        ])
```

## Cost-Aware Middleware

Log cost per request and alert on expensive operations:

### Python

```python
from modelmesh import Middleware

class CostAlertMiddleware(Middleware):
    def __init__(self, alert_threshold=0.05):
        self.alert_threshold = alert_threshold
        self.session_cost = 0.0

    async def after_response(self, response, context):
        cost = getattr(response, "cost", 0.0) or 0.0
        self.session_cost += cost
        if cost > self.alert_threshold:
            print(f"ALERT: Expensive request ${cost:.4f} "
                  f"(model={context.model_id}, provider={context.provider_id})")
        return response

client = modelmesh.create("chat-completion", middleware=[CostAlertMiddleware()])
```

### TypeScript

```typescript
import { Middleware, create } from '@nistrapa/modelmesh-core';

class CostAlertMiddleware extends Middleware {
  private alertThreshold: number;
  private sessionCost = 0;

  constructor(alertThreshold = 0.05) {
    super();
    this.alertThreshold = alertThreshold;
  }

  async afterResponse(response, context) {
    const cost = response.cost ?? 0;
    this.sessionCost += cost;
    if (cost > this.alertThreshold) {
      console.warn(
        `ALERT: Expensive request $${cost.toFixed(4)} ` +
        `(model=${context.modelId}, provider=${context.providerId})`
      );
    }
    return response;
  }
}

const client = create('chat-completion', {
  middleware: [new CostAlertMiddleware(0.05)],
});
```

## Recommended Stacks

### Free Tier Only ($0/month)

Best for personal projects, prototyping, and low-volume applications.

```yaml
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
```

### Budget-Conscious ($10-50/month)

Best for startups and small teams. Use cheap providers as primary, premium as fallback.

```yaml
providers:
  groq.api.v1:
    api_key: ${secrets:GROQ_API_KEY}
  deepseek.api.v1:
    api_key: ${secrets:DEEPSEEK_API_KEY}
    budget:
      daily_limit: 1.00
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 1.00
      monthly_limit: 25.00

models:
  llama-3.3-70b:
    provider: groq.api.v1
    capabilities: [generation.text-generation.chat-completion]
  deepseek-v3:
    provider: deepseek.api.v1
    capabilities: [generation.text-generation.chat-completion]
  gpt-4o-mini:
    provider: openai.llm.v1
    capabilities: [generation.text-generation.chat-completion]

pools:
  chat-completion:
    strategy: modelmesh.priority-selection.v1
    model_priority: [llama-3.3-70b, deepseek-v3, gpt-4o-mini]
    fallback_strategy: modelmesh.cost-first.v1
```

### Enterprise ($200+/month)

Best for production workloads requiring high reliability and quality.

```yaml
providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 25.00
      monthly_limit: 500.00
  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}
    budget:
      daily_limit: 25.00
      monthly_limit: 500.00
  groq.api.v1:
    api_key: ${secrets:GROQ_API_KEY}
  deepseek.api.v1:
    api_key: ${secrets:DEEPSEEK_API_KEY}
    budget:
      monthly_limit: 50.00

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities: [generation.text-generation.chat-completion]
  claude-3-5-sonnet:
    provider: anthropic.claude.v1
    capabilities: [generation.text-generation.chat-completion]
  llama-3.3-70b:
    provider: groq.api.v1
    capabilities: [generation.text-generation.chat-completion]
  deepseek-v3:
    provider: deepseek.api.v1
    capabilities: [generation.text-generation.chat-completion]

pools:
  chat-completion:
    strategy: modelmesh.priority-selection.v1
    model_priority: [gpt-4o, claude-3-5-sonnet, llama-3.3-70b, deepseek-v3]
    fallback_strategy: modelmesh.cost-first.v1
    deactivation:
      retry_limit: 3
    recovery:
      cooldown: 60s
    retry:
      max_attempts: 2
      backoff: exponential_jitter
```

## Cost Optimization Tips

1. **Use `cost-first` strategy** for workloads where quality differences between models are acceptable
2. **Set daily limits** on premium providers to prevent surprise bills
3. **Stack free tiers** from Groq and Google Gemini for zero-cost baseline capacity
4. **Use `priority-selection`** to route to cheap models first and escalate only on failure
5. **Monitor `client.usage`** in your application to track spend in real time
6. **Export JSONL logs** to a dashboard for historical cost analysis
7. **Use `rate-limit-aware` strategy** to maximize free tier utilization before hitting paid limits
8. **Separate pools by use case** so you can budget chat, embeddings, and code generation independently

---

See also: [Production Guide](ProductionGuide.md) · [System Configuration](../SystemConfiguration.md) · [Architecture Patterns](ArchitecturePatterns.md) · [Quick Start](QuickStart.md)
