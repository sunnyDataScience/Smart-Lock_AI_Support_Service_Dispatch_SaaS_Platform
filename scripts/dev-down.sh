#!/usr/bin/env bash
# dev-down.sh — Local development teardown
#
# 停止 dev-up.sh 啟動的所有服務。
#
# Usage:
#   ./scripts/dev-down.sh             # 停 ngrok + uvicorn (DB 保留)
#   ./scripts/dev-down.sh --stop-db   # 連同 DB 容器一起停止
#   ./scripts/dev-down.sh --remove-db # 連同 DB 容器停止並刪除 (清空資料！)

set -euo pipefail

DB_CONTAINER="lock_AI"
APP_PORT="8000"

STOP_DB=0
REMOVE_DB=0
for arg in "$@"; do
  case "$arg" in
    --stop-db)   STOP_DB=1 ;;
    --remove-db) STOP_DB=1; REMOVE_DB=1 ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | grep -E '^# ' | sed 's/^# //'
      exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '\033[36m[dev-down]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[dev-down]\033[0m %s\n' "$*"; }

# 1. Stop uvicorn (by port)
if pids=$(lsof -ti :$APP_PORT 2>/dev/null); then
  log "stopping uvicorn on :$APP_PORT (pids: $pids)"
  echo "$pids" | xargs -r kill 2>/dev/null || true
  sleep 1
  echo "$pids" | xargs -r kill -9 2>/dev/null || true
else
  log "no process bound to :$APP_PORT"
fi

# 2. Stop ngrok
if pids=$(pgrep -f "ngrok http $APP_PORT" 2>/dev/null); then
  log "stopping ngrok (pids: $pids)"
  echo "$pids" | xargs -r kill 2>/dev/null || true
else
  log "ngrok not running"
fi

# 3. Optional: stop DB
if [ "$STOP_DB" -eq 1 ]; then
  if docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
    log "stopping db container '$DB_CONTAINER'"
    docker stop "$DB_CONTAINER" >/dev/null
  else
    log "db container '$DB_CONTAINER' not running"
  fi
  if [ "$REMOVE_DB" -eq 1 ]; then
    if docker ps -a --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
      warn "removing db container '$DB_CONTAINER' (data will be lost)"
      docker rm "$DB_CONTAINER" >/dev/null
    fi
  fi
fi

log "done"
