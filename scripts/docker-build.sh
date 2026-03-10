#!/usr/bin/env bash
# scripts/docker-build.sh — Build the ModelMesh Docker image.
#
# Usage:
#   ./scripts/docker-build.sh               # build with default tag
#   ./scripts/docker-build.sh --tag NAME    # custom tag

set -euo pipefail
cd "$(dirname "$0")/.."

TAG="modelmesh-proxy:latest"

for arg in "$@"; do
  case "$arg" in
    --tag) shift; TAG="$1" ;;
    --help|-h)
      echo "Usage: docker-build.sh [--tag NAME]"
      echo ""
      echo "  --tag NAME   Docker image tag (default: modelmesh-proxy:latest)"
      exit 0
      ;;
  esac
done

if ! command -v docker &>/dev/null; then
  echo "ERROR: docker is not installed or not in PATH." >&2
  exit 1
fi

echo "Building Docker image: $TAG ..."
docker build -t "$TAG" .

echo ""
echo "Build complete: $TAG"
echo ""
echo "Run:"
echo "  docker run -p 8080:8080 --env-file .env -v ./modelmesh.yaml:/app/modelmesh.yaml:ro $TAG --config /app/modelmesh.yaml"
echo ""
echo "Or use Docker Compose:"
echo "  docker compose up --build"
