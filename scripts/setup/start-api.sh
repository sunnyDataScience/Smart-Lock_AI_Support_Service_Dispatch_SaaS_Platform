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

# 1. Build image — 三種情況會 build：
#    a) 強制（REBUILD_API=1）
#    b) image 不存在
#    c) image 比 api/ 任何檔案舊（避免「程式碼改了卻沒 rebuild」的常見坑 → 前端會噴 UNKNOWN (404)）
REBUILD="${REBUILD_API:-0}"
NEED_BUILD=0

if [[ "$REBUILD" == "1" ]]; then
  NEED_BUILD=1
  log_info "REBUILD_API=1 — 強制重 build"
elif ! docker image inspect smart-lock-api:local >/dev/null 2>&1; then
  NEED_BUILD=1
  log_info "Image 不存在 — 首次 build"
else
  # 比 image 建立時間 vs api/ 最新檔案 mtime
  # Docker 的 .Created 是 UTC，必須用 TZ=UTC parse 否則會差 8 小時誤判（macOS `date -j` 預設 local）
  IMAGE_TS=$(docker image inspect smart-lock-api:local --format '{{.Created}}' 2>/dev/null)
  IMAGE_EPOCH=$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "${IMAGE_TS%%.*}" +%s 2>/dev/null \
              || date -u -d "$IMAGE_TS" +%s 2>/dev/null || echo 0)
  # api/ 內 .py / Dockerfile / requirements.txt 最新 mtime（macOS / Linux 兼容）
  API_LATEST_EPOCH=$(find api -type f \( -name "*.py" -o -name "Dockerfile" -o -name "requirements.txt" \) \
                     -not -path "*/.*" -print0 2>/dev/null \
                     | xargs -0 stat -f "%m" 2>/dev/null \
                     | sort -nr | head -1)
  if [[ -z "$API_LATEST_EPOCH" ]]; then
    API_LATEST_EPOCH=$(find api -type f \( -name "*.py" -o -name "Dockerfile" -o -name "requirements.txt" \) \
                       -printf '%T@\n' 2>/dev/null | cut -d. -f1 | sort -nr | head -1)
  fi
  if [[ -n "$API_LATEST_EPOCH" ]] && (( IMAGE_EPOCH > 0 )) && (( API_LATEST_EPOCH > IMAGE_EPOCH )); then
    NEED_BUILD=1
    log_warn "偵測到 api/ 程式碼比 image 新 — 自動重 build（避免 UNKNOWN (404) 坑）"
  fi
fi

if (( NEED_BUILD == 1 )); then
  log_step "Build smart-lock-api:local（首次約 1-3 分鐘，後續約 30s）"
  (cd api && docker build -t smart-lock-api:local . >/dev/null 2>&1) && log_ok "Build 完成" || {
    log_err "Build 失敗，重跑：cd api && docker build -t smart-lock-api:local ."
    exit 1
  }
else
  log_ok "Image smart-lock-api:local 已 up-to-date（REBUILD_API=1 可強制重 build）"
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
