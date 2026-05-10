#!/usr/bin/env bash
# DEPLOY-001 (FAZ H): Lokal smoke runner.
#
# Geliştirici production deploy oncesi (veya post-deploy dogrulama icin)
# release.yml smoke gate'inin lokal versiyonunu calistirir.
#
# Kullanim:
#   BASE=https://kfinans.app ./scripts/smoke.sh         # production
#   ./scripts/smoke.sh                                  # lokal default http://localhost:8000 + http://localhost:3000
#
# Exit kodlari:
#   0 = tum smoke check'leri yesil
#   1 = bir veya daha fazlasi fail
set -euo pipefail

BASE="${BASE:-http://localhost:3000}"
API_BASE="${API_BASE:-http://localhost:8000}"
API="${API_BASE}/api/v1"

echo "=== KFinans smoke runner ==="
echo "Frontend: $BASE"
echo "API:      $API"
echo "(Health endpoint /health, prefix yok — main.py)"
echo

fail=0

# 1) Frontend up
echo "--- 1) Frontend up ---"
if curl -fsS -o /dev/null -w "frontend HTTP %{http_code}\n" "$BASE"; then
  echo "OK"
else
  echo "FAIL"
  fail=1
fi
echo

# 2) Backend health (prefix yok, /health direkt)
echo "--- 2) Backend /health ---"
if health=$(curl -fsS "${API_BASE}/health"); then
  echo "$health"
  echo "$health" | grep -q '"status":"ok"' && echo "OK" || { echo "FAIL — JSON beklenmedik"; fail=1; }
else
  echo "FAIL"
  fail=1
fi
echo

# 3) Auth chain (DB + endpoint + slowapi)
echo "--- 3) Auth chain (bogus creds -> 401) ---"
status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke-bogus@example.com","password":"wrong-pass-123"}')
echo "auth/login bogus -> HTTP $status"
if [ "$status" = "401" ] || [ "$status" = "423" ]; then
  echo "OK"
else
  echo "FAIL — 401/423 bekleniyor (DB veya endpoint kirik?)"
  fail=1
fi
echo

# 4) Security headers
echo "--- 4) Security headers ---"
headers=$(curl -sI "$BASE")
required=("strict-transport-security" "x-frame-options" "content-security-policy" "x-content-type-options")
for h in "${required[@]}"; do
  if echo "$headers" | grep -qi "^$h:"; then
    echo "  $h: OK"
  else
    echo "  $h: MISSING"
    fail=1
  fi
done
echo

# 5) X-Response-Time header (PERF-004)
echo "--- 5) X-Response-Time header (PERF-004) ---"
api_headers=$(curl -sI "${API_BASE}/health")
if echo "$api_headers" | grep -qi "^x-response-time:"; then
  echo "OK ($(echo "$api_headers" | grep -i "^x-response-time:" | tr -d '\r'))"
else
  echo "MISSING — RequestTimingMiddleware aktif degil"
  fail=1
fi
echo

if [ "$fail" -eq 0 ]; then
  echo "=== SMOKE PASS ==="
  exit 0
else
  echo "=== SMOKE FAIL ==="
  exit 1
fi
