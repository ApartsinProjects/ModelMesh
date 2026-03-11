#!/usr/bin/env bash
# scripts/test-all.sh — Run the full ModelMesh test suite (Python + TypeScript).
#
# Usage:
#   ./scripts/test-all.sh           # run all tests
#   ./scripts/test-all.sh --python  # Python only
#   ./scripts/test-all.sh --ts      # TypeScript only

set -euo pipefail
cd "$(dirname "$0")/.."

RUN_PY="1"
RUN_TS="1"
EXIT_CODE=0

for arg in "$@"; do
  case "$arg" in
    --python)  RUN_TS="" ;;
    --ts)      RUN_PY="" ;;
    --help|-h)
      echo "Usage: test-all.sh [--python] [--ts]"
      echo ""
      echo "  --python  Run Python tests only"
      echo "  --ts      Run TypeScript tests only"
      exit 0
      ;;
  esac
done

# ── Python tests ─────────────────────────────────────────────────────────
if [ -n "$RUN_PY" ]; then
  echo "═══════════════════════════════════════════"
  echo "  Python tests"
  echo "═══════════════════════════════════════════"
  cd src/python
  if python -m pytest ../../tests/ -v --tb=short; then
    echo "Python: ALL PASSED"
  else
    echo "Python: SOME FAILED"
    EXIT_CODE=1
  fi
  cd ../..
  echo ""
fi

# ── TypeScript tests ─────────────────────────────────────────────────────
if [ -n "$RUN_TS" ]; then
  echo "═══════════════════════════════════════════"
  echo "  TypeScript tests"
  echo "═══════════════════════════════════════════"
  cd src/typescript
  npm install --prefer-offline --no-audit 2>/dev/null || npm install
  if npm test; then
    echo "TypeScript: ALL PASSED"
  else
    echo "TypeScript: SOME FAILED"
    EXIT_CODE=1
  fi
  cd ../..
  echo ""
fi

# ── Summary ──────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════"
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "  All tests passed."
else
  echo "  Some tests failed."
fi
echo "═══════════════════════════════════════════"

exit $EXIT_CODE
