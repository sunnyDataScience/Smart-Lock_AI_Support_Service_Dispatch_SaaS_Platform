#!/usr/bin/env bash
# start-api.sh — build + run smart-lock-api container
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
cd "$REPO_ROOT"

log_title "Stage 2/4 — 後端 API"

# 確認 DB 在跑
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
  log_err "DB container ${DB_CONTAINER} 未啟動，請先跑 ./scripts/setup/start-db.sh"
  exit 1
fi

# 1. Build image（如果不存在 OR 強制 rebuild）
REBUILD="${REBUILD_API:-0}"
if [[ "$REBUILD" == "1" ]] || ! docker image inspect smart-lock-api:local >/dev/null 2>&1; then
  log_step "Build smart-lock-api:local（首次約 1-3 分鐘）"
  (cd api && docker build -t smart-lock-api:local . >/dev/null 2>&1) && log_ok "Build 完成" || {
    log_err "Build 失敗，重跑：cd api && docker build -t smart-lock-api:local ."
    exit 1
  }
else
  log_ok "Image smart-lock-api:local 已存在（REBUILD_API=1 可強制重 build）"
fi

# 2. 移除舊 container 並啟動
if docker ps -a --format '{{.Names}}' | grep -q "^${API_CONTAINER}$"; then
  log_step "移除既有 ${API_CONTAINER} container"
  docker rm -f "$API_CONTAINER" >/dev/null
fi

log_step "啟動 ${API_CONTAINER} container"
docker run -d \
  --name "$API_CONTAINER" \
  --link "${DB_CONTAINER}:db" \
  -p ${API_HOST_PORT}:8080 \
  -e POSTGRES_URI="postgresql://lock:0000@db:5432/lock_AI_data" \
  -e API_JWT_SECRET_KEY="dev-secret-key" \
  smart-lock-api:local >/dev/null

# 3. Health check
log_step "等待 API 健康檢查"
if wait_http "http://localhost:${API_HOST_PORT}/health" 30 "API"; then
  echo ""
  log_ok "API 就緒：http://localhost:${API_HOST_PORT}"
  log_info "Logs：docker logs -f ${API_CONTAINER}"
  log_info "OpenAPI docs：http://localhost:${API_HOST_PORT}/docs"
else
  log_err "API 啟動失敗，看 logs：docker logs ${API_CONTAINER}"
  exit 1
fi
