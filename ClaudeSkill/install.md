# ModelMesh Install Skill

## Purpose
Install ModelMesh into the user's project. Supports Python (pip), TypeScript (npm), and Docker.

## Decision Steps

1. **Detect project type** by checking for existing files:
   - `pyproject.toml` or `setup.py` or `requirements.txt` → Python project
   - `package.json` → TypeScript/Node.js project
   - `Dockerfile` or `docker-compose.yaml` → Docker project
   - Multiple detected → ask user which integration they want

2. **Ask which providers the user has API keys for.** At minimum one is needed:
   - OpenAI (`OPENAI_API_KEY`)
   - Anthropic (`ANTHROPIC_API_KEY`)
   - Groq (`GROQ_API_KEY`) — has free tier
   - Google (`GOOGLE_API_KEY`) — has free tier
   - Others: DeepSeek, Mistral, Together, OpenRouter, xAI, Cohere

## Python Installation

```bash
# Standard install (zero dependencies)
pip install modelmesh-lite

# With YAML config support
pip install modelmesh-lite[yaml]

# Development install (from source)
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh && pip install -e ".[yaml,dev]"
```

Add to `requirements.txt`:
```
modelmesh-lite>=0.1.0
```

Or `pyproject.toml`:
```toml
dependencies = ["modelmesh-lite>=0.1.0"]
```

## TypeScript Installation

```bash
npm install @nistrapa/modelmesh-core
```

Or with yarn/pnpm:
```bash
yarn add @nistrapa/modelmesh-core
pnpm add @nistrapa/modelmesh-core
```

## Docker Installation

**Pre-built image (fastest):**
```bash
docker pull ghcr.io/apartsinprojects/modelmesh:latest

# Run with inline env vars
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="sk-..." \
  ghcr.io/apartsinprojects/modelmesh:latest \
  --host 0.0.0.0 --port 8080

# Or with env file and config
docker run -p 8080:8080 \
  --env-file .env \
  -v ./modelmesh.yaml:/app/modelmesh.yaml:ro \
  ghcr.io/apartsinprojects/modelmesh:latest \
  --config /app/modelmesh.yaml --host 0.0.0.0 --port 8080
```

**From source (Docker Compose):**
```bash
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh
cp .env.example .env   # add your API keys
docker compose up --build
```

**From source (Docker directly):**
```bash
docker build -t modelmesh-proxy .
docker run -p 8080:8080 --env-file .env -v ./modelmesh.yaml:/app/modelmesh.yaml:ro modelmesh-proxy --config /app/modelmesh.yaml
```

## Verification

After installing, verify:

**Python:**
```python
import modelmesh
print(modelmesh.__name__)  # "modelmesh"
```

**TypeScript:**
```typescript
import { create } from '@nistrapa/modelmesh-core';
console.log(typeof create);  // "function"
```

**Docker:**
```bash
curl http://localhost:8080/health
# {"status": "ok", ...}
```

## Environment Setup

After installing the package, help the user set environment variables:

```bash
# At minimum one provider key
export OPENAI_API_KEY="sk-..."
# Or for free-tier providers:
export GROQ_API_KEY="gsk_..."
export GOOGLE_API_KEY="AI..."
```

For Docker, create a `.env` file (never commit to git):
```env
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
```
