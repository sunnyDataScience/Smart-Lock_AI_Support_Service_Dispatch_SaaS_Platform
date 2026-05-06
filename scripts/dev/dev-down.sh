#!/usr/bin/env bash
# scripts/dev/dev-down.sh — Local development teardown
#
# 停止 dev-up.sh 或 dev-up-gcp.sh 啟動的所有服務。
#
# Usage:
#   ./scripts/dev/dev-down.sh             # 情境 A：停 ngrok + uvicorn (DB 保留)
#   ./scripts/dev/dev-down.sh --stop-db   # A：連同 DB 容器一起停止
#   ./scripts/dev/dev-down.sh --remove-db # A：連同 DB 容器停止並刪除 (清空資料！)
#   ./scripts/dev/dev-down.sh --gcp       # 情境 B：停 agent / api / web / cloud-sql-proxy
#   ./scripts/dev/dev-down.sh --gcp --use-local  # 收尾後切回 .env.local（避免下次誤連 prod）

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.dev-logs"

DB_CONTAINER="lock_AI"
AGENT_PORT="8000"
API_PORT="8001"
WEB_PORT="3000"

STOP_DB=0
REMOVE_DB=0
GCP_MODE=0
USE_LOCAL_AFTER=0
for arg in "$@"; do
  case "$arg" in
    --stop-db)    STOP_DB=1 ;;
    --remove-db)  STOP_DB=1; REMOVE_DB=1 ;;
    --gcp)        GCP_MODE=1 ;;
    --use-local)  USE_LOCAL_AFTER=1 ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | grep -E '^# ' | sed 's/^# //'
      exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '\033[36m[dev-down]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[dev-down]\033[0m %s\n' "$*"; }

# 共用函式：依 PID file + port 雙保險停 process
stop_by_pid_and_port() {
  local pidfile="$1" port="$2" label="$3"
  local pid_killed=0

  # 先用 PID file
  if [ -f "$pidfile" ]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      log "stopping $label (pid $pid from $pidfile)"
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
      pid_killed=1
    fi
    rm -f "$pidfile"
  fi

  # 再用 port 補刀（防 PID file 過期但 port 還被綁）
  if pids=$(lsof -ti :"$port" 2>/dev/null); then
    log "  also clearing $label by port $port (pids: $pids)"
    echo "$pids" | xargs -r kill 2>/dev/null || true
    sleep 1
    echo "$pids" | xargs -r kill -9 2>/dev/null || true
  elif [ "$pid_killed" -eq 0 ]; then
    log "  no $label process found"
  fi
}

# ── 情境 B：先停 agent / api / web / proxy ──────────────────────────
if [ "$GCP_MODE" -eq 1 ]; then
  log "=== GCP 模式收尾 ==="

  stop_by_pid_and_port "$LOG_DIR/web.pid"   "$WEB_PORT"   "web (next.js)"
  stop_by_pid_and_port "$LOG_DIR/api.pid"   "$API_PORT"   "api (uvicorn)"
  stop_by_pid_and_port "$LOG_DIR/agent.pid" "$AGENT_PORT" "agent (uvicorn)"

  # cloud-sql-proxy 用專屬腳本停
  if [ -f "$LOG_DIR/cloud-sql-proxy.pid" ]; then
    log "stopping cloud-sql-proxy"
    "$PROJECT_ROOT/scripts/dev/proxy-down.sh" || true
  fi

  # 切回 .env.local（避免下次誤啟動連到 prod）
  if [ "$USE_LOCAL_AFTER" -eq 1 ]; then
    if [ -f "$PROJECT_ROOT/.env.local" ]; then
      log "切回 .env.local（避免下次誤連 prod）"
      "$PROJECT_ROOT/scripts/env/use-local.sh" >/dev/null
    else
      warn ".env.local 不存在，略過 use-local"
    fi
  fi

  log "done"
  exit 0
fi

# ── 情境 A（原有邏輯）：停 ngrok + uvicorn (port 8000) ──────────────
stop_by_pid_and_port "$LOG_DIR/agent.pid" "$AGENT_PORT" "uvicorn"

# Stop ngrok
if pids=$(pgrep -f "ngrok http $AGENT_PORT" 2>/dev/null); then
  log "stopping ngrok (pids: $pids)"
  echo "$pids" | xargs -r kill 2>/dev/null || true
else
  log "ngrok not running"
fi

# Optional: stop DB
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
