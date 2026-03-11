#!/usr/bin/env bash
# scripts/check-licenses.sh — Verify MIT license headers in source files.
#
# Usage:
#   ./scripts/check-licenses.sh          # check only
#   ./scripts/check-licenses.sh --fix    # add missing headers

set -euo pipefail
cd "$(dirname "$0")/.."

FIX=false
if [ "${1:-}" = "--fix" ]; then
  FIX=true
fi

ERRORS=0

PY_HEADER="# MIT License — see LICENSE file for details."
TS_HEADER="// MIT License — see LICENSE file for details."

check_file() {
  local file="$1"
  local header="$2"

  if ! head -3 "$file" | grep -qF "MIT License"; then
    if [ "$FIX" = true ]; then
      # Prepend header
      local tmp
      tmp=$(mktemp)
      echo "$header" > "$tmp"
      echo "" >> "$tmp"
      cat "$file" >> "$tmp"
      mv "$tmp" "$file"
      echo "  FIXED: $file"
    else
      echo "  MISSING: $file"
      ERRORS=$((ERRORS + 1))
    fi
  fi
}

echo "Checking license headers..."
echo ""

# Python source files
echo "Python files (src/python/modelmesh/):"
while IFS= read -r -d '' file; do
  check_file "$file" "$PY_HEADER"
done < <(find src/python/modelmesh -name "*.py" -print0 2>/dev/null || true)

echo ""

# TypeScript source files
echo "TypeScript files (src/typescript/src/):"
while IFS= read -r -d '' file; do
  check_file "$file" "$TS_HEADER"
done < <(find src/typescript/src -name "*.ts" ! -name "*.test.ts" ! -name "*.d.ts" -print0 2>/dev/null || true)

echo ""

if [ "$ERRORS" -gt 0 ]; then
  echo "Found $ERRORS files without license headers."
  echo "Run './scripts/check-licenses.sh --fix' to add them automatically."
  exit 1
else
  echo "All source files have license headers."
fi
