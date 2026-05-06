#!/usr/bin/env bash
# tests/smoke/api.sh — 18 endpoints happy-path smoke test
#
# Prereq:
#   1. uvicorn main:app --port 8001 已啟動
#   2. PostgreSQL 已套用 SQL/Schema_api_phase1.sql
#   3. 已存在 admin user (email/password 從 ADMIN_EMAIL/ADMIN_PASSWORD 環境變數)
#
# 用法：
#   ADMIN_EMAIL=admin@x.com ADMIN_PASSWORD=changeme123 ./tests/smoke/api.sh
#
set -euo pipefail

BASE="${API_BASE:-http://localhost:8001}"
TENANT="${TENANT_ID:-00000000-0000-0000-0000-000000000001}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-changeme123}"

pass=0
fail=0

check() {
    local label="$1"; shift
    local expected="$1"; shift
    local body
    body=$("$@" 2>&1) || true
    local status=$?
    if [ "$status" -eq 0 ]; then
        echo "✓ $label"
        pass=$((pass + 1))
    else
        echo "✗ $label  (expected: $expected)"
        echo "  $body"
        fail=$((fail + 1))
    fi
}

req() {
    local method="$1" path="$2" expect="$3"; shift 3
    local code
    code=$(curl -sS -o /tmp/api_smoke_body -w '%{http_code}' -X "$method" "$BASE$path" "$@") || return 1
    if [ "$code" != "$expect" ]; then
        cat /tmp/api_smoke_body
        echo " (got $code, want $expect)"
        return 1
    fi
}

echo "── 健康檢查 ──"
check "GET  /health"                         "200" req GET /health 200

echo "── Auth (5) ──"
check "POST /auth/login (admin)"              "200" req POST /api/v1/auth/login 200 \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}"
ACCESS=$(jq -r '.data.access_token' /tmp/api_smoke_body)
REFRESH=$(jq -r '.data.refresh_token' /tmp/api_smoke_body)

check "POST /auth/refresh"                    "200" req POST /api/v1/auth/refresh 200 \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\":\"$REFRESH\"}"
ACCESS=$(jq -r '.data.access_token' /tmp/api_smoke_body)
REFRESH=$(jq -r '.data.refresh_token' /tmp/api_smoke_body)

AUTH_HEAD=(-H "Authorization: Bearer $ACCESS" -H "X-Tenant-ID: $TENANT")
JSON_HEAD=(-H "Content-Type: application/json")

echo "── System Config (2) ──"
check "GET  /config"                          "200" req GET /api/v1/config 200 "${AUTH_HEAD[@]}"
check "PATCH /config"                         "200" req PATCH /api/v1/config 200 \
    "${AUTH_HEAD[@]}" "${JSON_HEAD[@]}" \
    -H "Idempotency-Key: smoke-config-$(date +%s)" \
    -d '{"rag":{"max_results":5}}'

echo "── Notifications (5) ──"
check "GET  /notifications"                   "200" req GET /api/v1/notifications 200 "${AUTH_HEAD[@]}"
check "POST /notifications/push"              "202" req POST /api/v1/notifications/push 202 \
    "${AUTH_HEAD[@]}" "${JSON_HEAD[@]}" \
    -H "Idempotency-Key: smoke-push-$(date +%s)" \
    -d "{\"target_type\":\"user\",\"target_id\":\"$(jq -r .data.user.id /tmp/api_smoke_body 2>/dev/null || echo $TENANT)\",\"type\":\"info\",\"title\":\"smoke\",\"body\":\"smoke test\"}"
check "POST /notifications/mark-all-read"     "200" req POST /api/v1/notifications/mark-all-read 200 \
    "${AUTH_HEAD[@]}" "${JSON_HEAD[@]}" \
    -H "Idempotency-Key: smoke-markall-$(date +%s)" \
    -d '{}'
check "POST /notifications/bulk"              "200" req POST /api/v1/notifications/bulk 200 \
    "${AUTH_HEAD[@]}" "${JSON_HEAD[@]}" \
    -H "Idempotency-Key: smoke-bulk-$(date +%s)" \
    -d '{"ids":["00000000-0000-0000-0000-000000000099"],"action":"mark_read"}'

echo "── KB Cases (5) ──"
check "POST /knowledge-base/cases"            "201" req POST /api/v1/knowledge-base/cases 201 \
    "${AUTH_HEAD[@]}" "${JSON_HEAD[@]}" \
    -H "Idempotency-Key: smoke-case-$(date +%s)" \
    -d '{"title":"smoke","problem_description":"門打不開","solution":"換電池","brand":"Chatlock"}'
CASE_ID=$(jq -r '.data.id' /tmp/api_smoke_body)
check "GET  /knowledge-base/cases"            "200" req GET /api/v1/knowledge-base/cases 200 "${AUTH_HEAD[@]}"
check "GET  /knowledge-base/cases/{id}"       "200" req GET "/api/v1/knowledge-base/cases/$CASE_ID" 200 "${AUTH_HEAD[@]}"
check "PUT  /knowledge-base/cases/{id}"       "200" req PUT "/api/v1/knowledge-base/cases/$CASE_ID" 200 \
    "${AUTH_HEAD[@]}" "${JSON_HEAD[@]}" \
    -H "Idempotency-Key: smoke-update-$(date +%s)" \
    -d '{"verified":true}'
check "DELETE /knowledge-base/cases/{id}"     "204" req DELETE "/api/v1/knowledge-base/cases/$CASE_ID" 204 \
    "${AUTH_HEAD[@]}" \
    -H "Idempotency-Key: smoke-delete-$(date +%s)"

echo "── Logout ──"
check "POST /auth/logout"                     "204" req POST /api/v1/auth/logout 204 "${AUTH_HEAD[@]}"

echo
echo "Total: $((pass + fail))   pass=$pass   fail=$fail"
[ "$fail" -eq 0 ]
