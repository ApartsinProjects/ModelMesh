# Production Deployment Guide

Take ModelMesh from development to production. This guide covers deployment modes, health checks, scaling, monitoring, secret management, budget enforcement, error handling, and Docker configuration. For the YAML configuration reference, see [System Configuration](../SystemConfiguration.md). For proxy-specific setup, see the [Proxy Guide](ProxyGuide.md).

## Deployment Modes

ModelMesh supports three deployment modes. Choose based on your architecture.

| Mode | Description | Best For |
|------|-------------|----------|
| **Embedded** | Import the library directly into your application | Microservices, serverless, CLIs |
| **Client-Server (Proxy)** | Run the proxy as a standalone service | Multi-app teams, polyglot stacks |
| **Docker** | Containerized proxy with health checks | Kubernetes, Docker Compose, cloud |

### Embedded (In-Process)

```python
import modelmesh

with modelmesh.create("chat-completion") as client:
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello!"}],
    )
```

No separate process needed. The library manages provider connections, routing, and state within your application.

### Client-Server (Proxy)

```bash
python -m modelmesh.proxy --config modelmesh.yaml --port 8080 --token $PROXY_TOKEN
```

Any OpenAI SDK client connects to the proxy. Multiple applications share the same routing, budget tracking, and provider pool.

### Docker

```bash
docker run -p 8080:8080 \
  --env-file .env \
  -v ./modelmesh.yaml:/app/modelmesh.yaml:ro \
  ghcr.io/apartsinprojects/modelmesh:latest \
  --config /app/modelmesh.yaml --host 0.0.0.0 --port 8080
```

## Health Checks

### Proxy Health Endpoint

The proxy exposes a `/health` endpoint for load balancers and orchestrators:

```bash
curl http://localhost:8080/health
```

Response:

```json
{
  "running": true,
  "host": "0.0.0.0",
  "port": 8080,
  "uptime_seconds": 3600.5,
  "active_connections": 3,
  "total_requests": 1284
}
```

### Provider Health Monitoring

Enable periodic provider health probes in your YAML configuration:

```yaml
discovery:
  health:
    enabled: true
    interval: 60s
    timeout: 10s
    failure_threshold: 3
```

When a provider fails `failure_threshold` consecutive probes, its models move to standby. They are automatically reactivated when probes succeed again.

### Docker Health Checks

Add a health check to your Docker Compose configuration:

```yaml
services:
  modelmesh-proxy:
    image: ghcr.io/apartsinprojects/modelmesh:latest
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

## Scaling

### Horizontal Scaling

Run multiple proxy instances behind a load balancer. Each instance maintains its own provider connections and routing state.

```yaml
# docker-compose.yaml
services:
  modelmesh-proxy:
    image: ghcr.io/apartsinprojects/modelmesh:latest
    deploy:
      replicas: 3
    ports:
      - "8080:8080"
    env_file: .env
    volumes:
      - ./modelmesh.yaml:/app/modelmesh.yaml:ro
```

For shared budget tracking across instances, use a centralized storage backend:

```yaml
storage:
  connector: redis.redis.v1
  url: redis://redis:6379
  sync_policy: immediate
```

### Connection Pooling

Configure connection limits per provider to avoid exhausting upstream connections:

```yaml
providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    connection_pool:
      max_connections: 50
      timeout: 30s
```

### Timeout Tuning

Set timeouts at the pool level to prevent slow providers from blocking requests:

```yaml
pools:
  chat-completion:
    strategy: modelmesh.stick-until-failure.v1
    retry:
      max_attempts: 2
      backoff: exponential_jitter
      initial_delay: 500ms
      max_delay: 10s
```

## Monitoring

### Observability Connectors

ModelMesh ships with built-in observability connectors. Configure them in your YAML to export routing decisions, request logs, and aggregate statistics.

#### Console Logging (Development)

```yaml
observability:
  routing:
    connector: modelmesh.console.v1
```

#### File Logging (Structured JSONL)

```yaml
observability:
  routing:
    connector: modelmesh.local-file.v1
    path: /var/log/modelmesh/routing.jsonl
  logging:
    connector: modelmesh.local-file.v1
    level: metadata
    path: /var/log/modelmesh/requests.jsonl
  statistics:
    connector: modelmesh.local-file.v1
    path: /var/log/modelmesh/stats.json
    flush_interval: 60s
```

#### Webhook (External Systems)

```yaml
observability:
  routing:
    connector: modelmesh.webhook.v1
    url: https://monitoring.example.com/hooks/modelmesh
```

#### Prometheus Metrics

```yaml
observability:
  statistics:
    connector: modelmesh.prometheus.v1
    port: 9090
    path: /metrics
```

### Logging Levels

| Level | Content |
|-------|---------|
| `metadata` | Timestamps, model, provider, token counts, latency, status |
| `summary` | Metadata plus truncated prompt and response |
| `full` | Metadata plus complete request and response payloads |

Use `metadata` in production to avoid logging sensitive prompt content. Use `full` only in development or controlled environments.

## Secret Management

### Development: Dotenv

```yaml
secrets:
  store: modelmesh.dotenv.v1
  path: ./.env
```

### Staging: Encrypted File

```yaml
secrets:
  store: modelmesh.encrypted-file.v1
  path: ./secrets.enc
  key: ${ENCRYPTION_KEY}
```

### Production: Cloud KMS

**AWS Secrets Manager:**

```yaml
secrets:
  store: aws.secrets-manager.v1
  region: us-east-1
```

**Google Secret Manager:**

```yaml
secrets:
  store: google.secret-manager.v1
  project: my-project-id
```

**Azure Key Vault:**

```yaml
secrets:
  store: microsoft.key-vault.v1
  vault_name: my-vault
```

See [Secret Stores Guide](SecretStores.md) for detailed setup instructions for each backend.

## Budget Enforcement

### Per-Provider Budgets

```yaml
providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 10.00
      monthly_limit: 200.00

  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}
    budget:
      daily_limit: 10.00
      monthly_limit: 200.00
```

### Per-Pool Budget Deactivation

```yaml
pools:
  chat-completion:
    strategy: modelmesh.cost-first.v1
    deactivation:
      budget_limit: 50.00
```

When a provider exceeds its budget, ModelMesh raises `BudgetExceededError` and routes to the next available provider. When all providers in a pool exceed their budgets, `AllProvidersExhaustedError` is raised.

### Runtime Budget Monitoring

```python
client = modelmesh.create("chat-completion")

# Check usage after requests
print(f"Total cost: ${client.usage.total_cost:.4f}")
print(f"Total tokens: {client.usage.total_tokens}")

status = client.usage.budget_status
if status and status.remaining < 1.00:
    print(f"Warning: only ${status.remaining:.2f} budget remaining")
```

## Error Handling

### Retry Strategies

Configure automatic retries with exponential backoff:

```yaml
pools:
  chat-completion:
    retry:
      max_attempts: 3
      backoff: exponential_jitter
      initial_delay: 500ms
      max_delay: 10s
      retryable_codes: [429, 500, 502, 503]
      non_retryable_codes: [400, 401, 403]
      scope: same_provider
      honor_retry_after: true
```

### Circuit Breaker Pattern

Use deactivation triggers to implement circuit breaker behavior:

```yaml
pools:
  chat-completion:
    deactivation:
      retry_limit: 5
      error_rate_threshold: 0.5
      error_codes: [429, 500, 503]
    recovery:
      cooldown: 120s
      probe_interval: 60s
```

When a model fails `retry_limit` consecutive requests or exceeds the `error_rate_threshold`, it moves to standby. After `cooldown`, ModelMesh probes the model and reactivates it if the probe succeeds.

### Graceful Degradation

Combine priority routing with fallback strategies:

```yaml
pools:
  chat-completion:
    strategy: modelmesh.priority-selection.v1
    model_priority: [gpt-4o, claude-3-5-sonnet, llama-3.3-70b]
    fallback_strategy: modelmesh.cost-first.v1
```

In application code, handle the case where all providers are exhausted:

```python
from modelmesh.exceptions import AllProvidersExhaustedError, BudgetExceededError

try:
    response = client.chat.completions.create(
        model="chat-completion",
        messages=messages,
    )
except BudgetExceededError:
    return {"error": "Budget limit reached. Please try again tomorrow."}
except AllProvidersExhaustedError:
    return {"error": "All AI providers are currently unavailable. Please retry."}
```

## Environment-Specific Configuration

Maintain separate YAML files per environment. Key differences:

| Concern | Development | Staging | Production |
|---------|------------|---------|------------|
| Secrets | `modelmesh.dotenv.v1` | `modelmesh.encrypted-file.v1` | `aws.secrets-manager.v1` |
| Providers | 1 free-tier (Groq) | 2 with low budgets | 3+ with daily/monthly limits |
| Strategy | `stick-until-failure` | `round-robin` | `priority-selection` with fallback |
| Observability | Console, `full` logging | File, `summary` logging | Webhook + Prometheus, `metadata` only |
| Storage | In-memory | Local file | Redis or S3 |
| Health probes | Disabled | Enabled, relaxed | Enabled, strict |

Example production config:

```yaml
# modelmesh.prod.yaml
secrets:
  store: aws.secrets-manager.v1
  region: us-east-1

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget: { daily_limit: 50.00, monthly_limit: 1000.00 }
  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}
    budget: { daily_limit: 50.00, monthly_limit: 1000.00 }
  groq.api.v1:
    api_key: ${secrets:GROQ_API_KEY}

pools:
  chat-completion:
    strategy: modelmesh.priority-selection.v1
    model_priority: [gpt-4o, claude-3-5-sonnet, llama-3.3-70b]
    fallback_strategy: modelmesh.cost-first.v1
    deactivation: { retry_limit: 3, error_codes: [429, 500, 503] }
    recovery: { cooldown: 60s, probe_interval: 300s }
    retry: { max_attempts: 3, backoff: exponential_jitter, honor_retry_after: true }

storage:
  connector: redis.redis.v1
  url: redis://redis:6379
  sync_policy: immediate

observability:
  routing: { connector: modelmesh.webhook.v1, url: https://monitoring.internal/hooks/modelmesh }
  logging: { connector: modelmesh.local-file.v1, level: metadata, path: /var/log/modelmesh/requests.jsonl }
  statistics: { connector: modelmesh.prometheus.v1, port: 9090 }

discovery:
  health: { enabled: true, interval: 60s, timeout: 10s, failure_threshold: 3 }
```

## Docker Compose Production Setup

```yaml
# docker-compose.prod.yaml
services:
  modelmesh-proxy:
    image: ghcr.io/apartsinprojects/modelmesh:latest
    ports:
      - "8080:8080"
    environment:
      - MODELMESH_CONFIG=/app/modelmesh.yaml
    env_file: .env.prod
    volumes:
      - ./modelmesh.prod.yaml:/app/modelmesh.yaml:ro
      - modelmesh-logs:/var/log/modelmesh
    command: ["--config", "/app/modelmesh.yaml", "--host", "0.0.0.0", "--port", "8080", "--token", "${PROXY_TOKEN}"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped

volumes:
  modelmesh-logs:
  redis-data:
```

Start with:

```bash
docker compose -f docker-compose.prod.yaml up -d
```

## Production Checklist

1. Use a cloud secret store (AWS/GCP/Azure) instead of `.env` files
2. Set daily and monthly budget limits on every provider
3. Enable health monitoring with `discovery.health`
4. Configure retry and deactivation policies on every pool
5. Set logging level to `metadata` (avoid logging prompts)
6. Use a persistent storage backend (Redis or S3) for shared state
7. Add Docker health checks with appropriate intervals
8. Set memory and CPU limits on containers
9. Use `restart: unless-stopped` for automatic recovery
10. Monitor the `/health` endpoint from your load balancer

---

See also: [Proxy Guide](ProxyGuide.md) · [Secret Stores](SecretStores.md) · [Error Handling](ErrorHandling.md) · [System Configuration](../SystemConfiguration.md) · [Cost Optimization](CostOptimization.md)
