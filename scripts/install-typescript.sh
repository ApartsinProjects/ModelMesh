#!/usr/bin/env bash
# scripts/install-typescript.sh — Install ModelMesh TypeScript package for development.
#
# Usage:
#   ./scripts/install-typescript.sh

set -euo pipefail
cd "$(dirname "$0")/.."

echo "Installing ModelMesh TypeScript package..."

cd src/typescript

if ! command -v npm &>/dev/null; then
  echo "ERROR: npm is not installed or not in PATH." >&2
  exit 1
fi

npm install
echo ""
echo "Installed @nistrapa/modelmesh-core and dev dependencies."
echo "Run tests:  npm test"
echo "Build:      npm run build (if configured)"
