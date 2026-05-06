#!/usr/bin/env bash
# scripts/dev/dev-down.sh — Local development teardown
#
# 停止 dev-up.sh / dev-up.sh --full / dev-up-gcp.sh 啟動的所有服務。
#
# Usage:
#   ./scripts/dev/dev-down.sh             # 情境 A 單服務：停 ngrok + agent (DB 保留)
#   ./scripts/dev/dev-down.sh --stop-db   # A：連 DB 容器一起停止
#   ./scripts/dev/dev-down.sh --remove-db # A：連 DB 容器停止並刪除 (清空資料！)
#   ./scripts/dev/dev-down.sh --multi     # 多服務：停 agent / api / web (+proxy if exists)
#   ./scripts/dev/dev-down.sh --gcp       # 別名：等同 --multi（情境 B 慣用）
#   ./scripts/dev/dev-down.sh --multi --use-local  # 收尾後切回 .env.local
#   ./scripts/dev/dev-down.sh --multi --stop-db    # 多服務 + 停 docker DB

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.dev-logs"

DB_CONTAINER="lock_AI"
AGENT_PORT="8000"
API_PORT="8001"
WEB_PORT="3000"

STOP_DB=0
REMOVE_DB=0
MULTI_MODE=0
USE_LOCAL_AFTER=0
for arg in "$@"; do
  case "$arg" in
    --stop-db)    STOP_DB=1 ;;
    --remove-db)  STOP_DB=1; REMOVE_DB=1 ;;
    --multi|--gcp)  MULTI_MODE=1 ;;   # --gcp 為向後相容別名
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
# 注意 next dev 會 spawn 子 process（next-server worker），主 PID 死了
# 子 process 仍可能綁住 port。靠兩個層次補刀：
#   1. lsof -ti :PORT（IPv4 listener）
#   2. fuser -k -n tcp PORT（更可靠，IPv4/IPv6 都抓得到）
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

  # 第二刀：lsof（抓 IPv4 listener）
  local lsof_pids=""
  lsof_pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$lsof_pids" ]; then
    log "  clearing $label by lsof on port $port (pids: $lsof_pids)"
    echo "$lsof_pids" | xargs -r kill 2>/dev/null || true
    sleep 1
    echo "$lsof_pids" | xargs -r kill -9 2>/dev/null || true
  fi

  # 第三刀：fuser sledgehammer（抓 IPv6 / 子 process）
  if command -v fuser >/dev/null 2>&1; then
    if fuser -n tcp "$port" >/dev/null 2>&1; then
      log "  clearing $label by fuser on port $port (next-server child / IPv6)"
      fuser -k -n tcp "$port" >/dev/null 2>&1 || true
      sleep 1
    fi
  fi

  # 最終確認
  if [ "$pid_killed" -eq 0 ] && [ -z "$lsof_pids" ]; then
    if ! command -v fuser >/dev/null 2>&1 || ! fuser -n tcp "$port" >/dev/null 2>&1; then
      log "  no $label process found"
    fi
  fi
}

# ── 情境 B：先停 agent / api / web / proxy ──────────────────────────
if [ "$MULTI_MODE" -eq 1 ]; then
  log "=== 多服務模式收尾（agent + api + web + proxy if any） ==="

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

  # 連 docker DB 一起停（情境 A --full 收尾用）
  if [ "$STOP_DB" -eq 1 ]; then
    if docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
      log "stopping db container '$DB_CONTAINER'"
      docker stop "$DB_CONTAINER" >/dev/null
    fi
    if [ "$REMOVE_DB" -eq 1 ]; then
      if docker ps -a --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
        warn "removing db container '$DB_CONTAINER' (data will be lost)"
        docker rm "$DB_CONTAINER" >/dev/null
      fi
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
