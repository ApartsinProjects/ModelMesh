#!/usr/bin/env bash
# scripts/install-python.sh — Install ModelMesh Python package for development.
#
# Usage:
#   ./scripts/install-python.sh           # editable install (dev)
#   ./scripts/install-python.sh --prod    # standard install

set -euo pipefail
cd "$(dirname "$0")/.."

MODE="dev"
for arg in "$@"; do
  case "$arg" in
    --prod) MODE="prod" ;;
    --help|-h)
      echo "Usage: install-python.sh [--prod]"
      echo ""
      echo "  --prod  Standard install (non-editable)"
      echo "  (default)  Editable install with dev + yaml extras"
      exit 0
      ;;
  esac
done

echo "Installing ModelMesh Python package ($MODE mode)..."

if [ "$MODE" = "dev" ]; then
  pip install -e ".[yaml,dev]"
  echo ""
  echo "Installed in editable mode with yaml + dev extras."
  echo "Run tests:  cd src/python && python -m pytest ../../tests/ -v"
else
  pip install ".[yaml]"
  echo ""
  echo "Installed modelmesh-lite with YAML support."
fi

echo "Start proxy: python -m modelmesh.proxy"
