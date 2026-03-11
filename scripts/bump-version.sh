#!/usr/bin/env bash
# scripts/bump-version.sh — Bump version in both Python and TypeScript packages.
#
# Usage:
#   ./scripts/bump-version.sh 0.3.0

set -euo pipefail
cd "$(dirname "$0")/.."

if [ $# -ne 1 ]; then
  echo "Usage: bump-version.sh <version>"
  echo "  Example: bump-version.sh 0.3.0"
  exit 1
fi

VERSION="$1"

# Validate semver format (basic check)
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+'; then
  echo "Error: version must be semver (e.g., 0.3.0)"
  exit 1
fi

echo "Bumping version to $VERSION..."

# Python: pyproject.toml
sed -i "s/^version = \".*\"/version = \"$VERSION\"/" src/python/pyproject.toml
echo "  Updated src/python/pyproject.toml"

# TypeScript: package.json
cd src/typescript
npm version "$VERSION" --no-git-tag-version
cd ../..
echo "  Updated src/typescript/package.json"

# Verify consistency
PY_VER=$(grep '^version' src/python/pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
TS_VER=$(node -p "require('./src/typescript/package.json').version")

if [ "$PY_VER" = "$TS_VER" ]; then
  echo ""
  echo "Version $VERSION set in both packages."
else
  echo ""
  echo "WARNING: versions diverged! Python=$PY_VER, TypeScript=$TS_VER"
  exit 1
fi
