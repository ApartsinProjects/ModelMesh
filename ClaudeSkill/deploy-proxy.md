# ModelMesh Deploy Proxy Skill

## Purpose
Set up and deploy the ModelMesh Docker proxy as an OpenAI-compatible REST API server.

## Prerequisites

- Docker and Docker Compose installed
- At least one AI provider API key

## Quick Deploy

### Step 1: Get the Project

```bash
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh
```

### Step 2: Configure API Keys

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
```

### Step 3: Configure Models and Pools

Edit `modelmesh.yaml` to define:
- Which providers to use
- Which models to expose
- Which pools to create (capability groupings)
- Rotation strategy

See the `configure.md` skill for detailed configuration options.

### Step 4: Build and Start

```bash
docker compose up --build
```

Or use the automation script:
```bash
./scripts/proxy-up.sh
```

For detached (background) mode:
```bash
./scripts/proxy-up.sh --detach
```

### Step 5: Verify

```bash
# Health check
curl http://localhost:8080/health

# List models and pools
curl http://localhost:8080/v1/models

# Test chat completion
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"text-generation","messages":[{"role":"user","content":"Hello!"}]}'
```

Or use the smoke test script:
```bash
./scripts/proxy-test.sh
```

## Authentication

To require a bearer token:

```bash
docker compose up --build
# Add to docker-compose.yaml command:
command: ["--config", "/app/modelmesh.yaml", "--host", "0.0.0.0", "--port", "8080", "--token", "my-secret-token"]
```

Clients must then include: `Authorization: Bearer my-secret-token`

## Proxy CLI Reference

```
python -m modelmesh.proxy [OPTIONS]

Options:
  --config PATH     YAML configuration file (default: auto-detect)
  --host HOST       Bind address (default: 0.0.0.0)
  --port PORT       Listen port (default: 8080)
  --token TOKEN     Optional bearer token for authentication
  --log-level LEVEL Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check (returns status, uptime, model count) |
| `GET` | `/v1/models` | List available models and pools |
| `POST` | `/v1/chat/completions` | Chat completion (streaming + non-streaming) |
| `POST` | `/v1/embeddings` | Text embeddings |
| `POST` | `/v1/audio/speech` | Text-to-speech |
| `POST` | `/v1/audio/transcriptions` | Speech-to-text |

## Docker Compose Configuration

```yaml
services:
  modelmesh-proxy:
    build: .
    ports:
      - "8080:8080"
    env_file: .env
    volumes:
      - ./modelmesh.yaml:/app/modelmesh.yaml:ro
    command: ["--config", "/app/modelmesh.yaml", "--host", "0.0.0.0", "--port", "8080"]
```

## Stopping

```bash
docker compose down
# Or:
./scripts/proxy-down.sh
# Clean up volumes and images:
./scripts/proxy-down.sh --clean
```

## Production Considerations

1. **Use `--token` for authentication** in production environments
2. **Set daily budget limits** per provider in `modelmesh.yaml`
3. **Use cloud secret stores** (AWS Secrets Manager, etc.) instead of env vars
4. **Monitor** via the `/health` endpoint for uptime checks
5. **Reverse proxy**: Place behind nginx/caddy for TLS and rate limiting
6. **Logging**: Use `--log-level DEBUG` during setup, `INFO` in production
