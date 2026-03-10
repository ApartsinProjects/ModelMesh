#!/usr/bin/env bash
# scripts/proxy-up.sh — Build and start the ModelMesh proxy via Docker Compose.
#
# Usage:
#   ./scripts/proxy-up.sh              # foreground (Ctrl+C to stop)
#   ./scripts/proxy-up.sh --detach     # background (use proxy-down.sh to stop)
#   ./scripts/proxy-up.sh --build-only # build without starting

set -euo pipefail
cd "$(dirname "$0")/.."

DETACH=""
BUILD_ONLY=""

for arg in "$@"; do
  case "$arg" in
    --detach|-d)  DETACH="-d" ;;
    --build-only) BUILD_ONLY="1" ;;
    --help|-h)
      echo "Usage: proxy-up.sh [--detach] [--build-only]"
      echo ""
      echo "  --detach, -d   Run in background"
      echo "  --build-only   Build the image without starting"
      exit 0
      ;;
  esac
done

# ── Preflight checks ───────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "ERROR: docker is not installed or not in PATH." >&2
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "WARNING: .env file not found. Creating from .env.example template..." >&2
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit it with your API keys." >&2
  else
    cat > .env << 'ENVEOF'
# ModelMesh proxy — add your API keys below
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
ENVEOF
    echo "Created empty .env — add your API keys before starting." >&2
  fi
fi

if [ ! -f "modelmesh.yaml" ]; then
  echo "WARNING: modelmesh.yaml not found. The proxy will use auto-detect mode." >&2
fi

# ── Build ───────────────────────────────────────────────────────────────
echo "Building ModelMesh proxy image..."
docker compose build

if [ -n "$BUILD_ONLY" ]; then
  echo "Build complete. Use 'proxy-up.sh' (without --build-only) to start."
  exit 0
fi

# ── Start ───────────────────────────────────────────────────────────────
echo "Starting ModelMesh proxy on http://localhost:8080 ..."
docker compose up --build $DETACH

if [ -n "$DETACH" ]; then
  echo ""
  echo "Proxy is running in background."
  echo "  Health:  curl http://localhost:8080/health"
  echo "  Models:  curl http://localhost:8080/v1/models"
  echo "  Logs:    docker compose logs -f"
  echo "  Stop:    ./scripts/proxy-down.sh"
fi
