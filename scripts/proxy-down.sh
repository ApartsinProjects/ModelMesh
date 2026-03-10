#!/usr/bin/env bash
# scripts/proxy-down.sh — Stop the ModelMesh proxy Docker container.
#
# Usage:
#   ./scripts/proxy-down.sh          # stop containers
#   ./scripts/proxy-down.sh --clean  # stop and remove volumes/images

set -euo pipefail
cd "$(dirname "$0")/.."

CLEAN=""
for arg in "$@"; do
  case "$arg" in
    --clean) CLEAN="1" ;;
    --help|-h)
      echo "Usage: proxy-down.sh [--clean]"
      echo ""
      echo "  --clean   Also remove volumes and built images"
      exit 0
      ;;
  esac
done

echo "Stopping ModelMesh proxy..."

if [ -n "$CLEAN" ]; then
  docker compose down --rmi local --volumes --remove-orphans
  echo "Stopped and cleaned up images + volumes."
else
  docker compose down
  echo "Stopped."
fi
