#!/usr/bin/env bash
# scripts/proxy-test.sh — Smoke-test a running ModelMesh proxy.
#
# Usage:
#   ./scripts/proxy-test.sh              # test against running proxy
#   ./scripts/proxy-test.sh --full       # build, start, test, stop
#   ./scripts/proxy-test.sh --url URL    # custom proxy URL

set -euo pipefail
cd "$(dirname "$0")/.."

PROXY_URL="http://localhost:8080"
FULL_CYCLE=""
PASSED=0
FAILED=0
TOTAL=0

for arg in "$@"; do
  case "$arg" in
    --full)     FULL_CYCLE="1" ;;
    --url)      shift; PROXY_URL="$1" ;;
    --help|-h)
      echo "Usage: proxy-test.sh [--full] [--url URL]"
      echo ""
      echo "  --full       Build, start, test, and stop the proxy"
      echo "  --url URL    Proxy base URL (default: http://localhost:8080)"
      exit 0
      ;;
  esac
done

# ── Helpers ─────────────────────────────────────────────────────────────
pass() { PASSED=$((PASSED + 1)); TOTAL=$((TOTAL + 1)); echo "  PASS: $1"; }
fail() { FAILED=$((FAILED + 1)); TOTAL=$((TOTAL + 1)); echo "  FAIL: $1 — $2"; }

# ── Full cycle: start proxy ────────────────────────────────────────────
if [ -n "$FULL_CYCLE" ]; then
  echo "Starting proxy for full-cycle test..."
  docker compose up --build -d
  echo "Waiting for proxy to be ready..."
  for i in $(seq 1 30); do
    if curl -sf "$PROXY_URL/health" > /dev/null 2>&1; then
      echo "Proxy is ready."
      break
    fi
    if [ "$i" -eq 30 ]; then
      echo "ERROR: Proxy did not become ready in 30 seconds." >&2
      docker compose logs
      docker compose down
      exit 1
    fi
    sleep 1
  done
fi

echo ""
echo "Running smoke tests against $PROXY_URL ..."
echo ""

# ── Test 1: Health endpoint ─────────────────────────────────────────────
echo "[1] GET /health"
RESP=$(curl -sf "$PROXY_URL/health" 2>&1) && {
  echo "$RESP" | grep -q '"running"' && pass "/health returns running status" || fail "/health" "missing 'running' field"
} || fail "/health" "request failed"

# ── Test 2: Models endpoint ─────────────────────────────────────────────
echo "[2] GET /v1/models"
RESP=$(curl -sf "$PROXY_URL/v1/models" 2>&1) && {
  echo "$RESP" | grep -q '"object":"list"' && pass "/v1/models returns list" || {
    echo "$RESP" | grep -q '"object": "list"' && pass "/v1/models returns list" || fail "/v1/models" "missing list object"
  }
  echo "$RESP" | grep -q '"data"' && pass "/v1/models has data array" || fail "/v1/models" "missing data array"
} || fail "/v1/models" "request failed"

# ── Test 3: Chat completion (non-streaming) ─────────────────────────────
echo "[3] POST /v1/chat/completions (non-streaming)"
RESP=$(curl -sf -X POST "$PROXY_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"text-generation","messages":[{"role":"user","content":"Say hello in one word."}],"max_tokens":10}' 2>&1) && {
  echo "$RESP" | grep -q '"choices"' && pass "chat completion returns choices" || fail "chat completion" "missing choices"
  echo "$RESP" | grep -q '"usage"' && pass "chat completion returns usage" || fail "chat completion" "missing usage"
  echo "$RESP" | grep -q '"model"' && pass "chat completion returns model" || fail "chat completion" "missing model"
} || fail "chat completion" "request failed"

# ── Test 4: Chat completion (streaming) ─────────────────────────────────
echo "[4] POST /v1/chat/completions (streaming)"
RESP=$(curl -sf -X POST "$PROXY_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"text-generation","messages":[{"role":"user","content":"Say hi"}],"stream":true,"max_tokens":10}' 2>&1) && {
  echo "$RESP" | grep -q 'data:' && pass "streaming returns SSE data lines" || fail "streaming" "no SSE data lines"
  echo "$RESP" | grep -q '\[DONE\]' && pass "streaming ends with [DONE]" || fail "streaming" "missing [DONE] marker"
} || fail "streaming" "request failed"

# ── Test 5: Invalid request ─────────────────────────────────────────────
echo "[5] POST /v1/chat/completions (invalid — no messages)"
HTTP_CODE=$(curl -so /dev/null -w "%{http_code}" -X POST "$PROXY_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"text-generation"}' 2>&1)
[ "$HTTP_CODE" = "400" ] && pass "missing messages returns 400" || fail "validation" "expected 400, got $HTTP_CODE"

# ── Test 6: 404 for unknown endpoint ───────────────────────────────────
echo "[6] GET /v1/unknown"
HTTP_CODE=$(curl -so /dev/null -w "%{http_code}" "$PROXY_URL/v1/unknown" 2>&1)
[ "$HTTP_CODE" = "404" ] && pass "unknown endpoint returns 404" || fail "404 check" "expected 404, got $HTTP_CODE"

# ── Test 7: OPTIONS preflight ──────────────────────────────────────────
echo "[7] OPTIONS /v1/chat/completions (CORS preflight)"
RESP=$(curl -sf -X OPTIONS -i "$PROXY_URL/v1/chat/completions" 2>&1) && {
  echo "$RESP" | grep -qi 'access-control-allow-origin' && pass "CORS headers present" || fail "CORS" "missing Allow-Origin"
} || fail "CORS preflight" "request failed"

# ── Summary ────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo "  Results: $PASSED passed, $FAILED failed ($TOTAL total)"
echo "═══════════════════════════════════════════"

# ── Full cycle: stop proxy ──────────────────────────────────────────────
if [ -n "$FULL_CYCLE" ]; then
  echo ""
  echo "Stopping proxy..."
  docker compose down
fi

[ "$FAILED" -eq 0 ] && exit 0 || exit 1
